# ============================================================
# src/managers/points_manager.py — Points & Challenge System
# ============================================================
# Handles all point economy: earning, spending, multipliers,
# daily claims, challenge tracking, and the leaderboard cache.
# ============================================================

import json
import os
import random
import time

from config import Config
from src.db import Database
from src.utils.challenges import (
    NORMAL_CHALLENGES,
    EVENT_CHALLENGES,
    MODE_POINTS,
)


class PointsManager:
    """Manages user points, daily streaks, multipliers, and challenges."""

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.data = {}
        self._leaderboard_cache = None
        self.load_points()

    # ── Persistence ─────────────────────────────────────────

    def load_points(self):
        """Load the points JSON file from disk or from the configured database."""
        if self.db.enabled:
            self.data = self.db.load_json("points_data", {})
            if not isinstance(self.data, dict):
                self.data = {}
            return

        if os.path.exists(Config.POINTS_FILE):
            with open(Config.POINTS_FILE, "r") as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}
        else:
            self.data = {}

    def save_points(self):
        """Write the current points data to disk or to the configured database."""
        if self.db.enabled:
            self.db.save_json("points_data", self.data)
            self.invalidate_leaderboard_cache()
            return

        with open(Config.POINTS_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # ── Multipliers ─────────────────────────────────────────

    def get_multiplier(self, user_id: int) -> float:
        """Return the combined permanent × temporary multiplier for a user."""
        user_data = self.get_points(user_id)
        perm    = user_data.get("permanent_multiplier", 1.0)
        temp    = user_data.get("temporary_multiplier", 1.0)
        expires = user_data.get("temporary_multiplier_expires", 0)

        # Expire temporary multiplier if needed
        if temp != 1.0 and int(time.time()) >= expires:
            user_data["temporary_multiplier"] = 1.0
            user_data["temporary_multiplier_expires"] = 0
            self.save_points()
            temp = 1.0

        return perm * temp

    def set_permanent_multiplier(self, user_id: int, multiplier: float):
        user_data = self.get_points(user_id)
        user_data["permanent_multiplier"] = float(multiplier)
        self.save_points()

    def set_temporary_multiplier(self, user_id: int, multiplier: float, duration: int):
        user_data = self.get_points(user_id)
        user_data["temporary_multiplier"] = float(multiplier)
        user_data["temporary_multiplier_expires"] = int(time.time()) + int(duration)
        self.save_points()

    # ── Core Points ─────────────────────────────────────────

    def add_points(self, user_id: int, mode) -> int:
        """
        Award (or deduct) points.
        `mode` can be an int, a numeric string, or a MODE_POINTS key.
        """
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = {"points": 0, "wins": 0}

        # Resolve how many raw points to award
        if isinstance(mode, int):
            pts = mode
        else:
            try:
                pts = int(mode)
            except ValueError:
                pts = MODE_POINTS.get(mode, 10)

        # Apply multiplier only to positive awards
        if pts > 0:
            pts = int(round(pts * self.get_multiplier(user_id)))

        self.data[user_id_str]["points"] += pts
        self.save_points()
        self.invalidate_leaderboard_cache()
        return pts

    def add_win(self, user_id: int):
        """Increment win count for a user."""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = {"points": 0, "wins": 0}
        self.data[user_id_str]["wins"] += 1
        self.save_points()
        self.invalidate_leaderboard_cache()

    def set_points(self, user_id: int, points: int):
        """Set a user's point total directly."""
        user_data = self.get_points(user_id)
        user_data["points"] = int(points)
        self.save_points()
        self.invalidate_leaderboard_cache()

    def set_wins(self, user_id: int, wins: int):
        """Set a user's win total directly."""
        user_data = self.get_points(user_id)
        user_data["wins"] = int(wins)
        self.save_points()
        self.invalidate_leaderboard_cache()

    def get_points(self, user_id: int) -> dict:
        """
        Return the full data dict for a user, creating missing keys
        with sensible defaults so callers never need to worry.
        """
        user_id_str = str(user_id)
        user_data = self.data.get(user_id_str)
        modified = False

        if user_data is None:
            user_data = {"points": 0, "wins": 0}
            self.data[user_id_str] = user_data
            modified = True

        # Ensure all expected keys exist
        defaults = {
            "daily_claims":                {"last_claim": 0, "streak": 0, "multiplier": 1.0},
            "permanent_multiplier":        1.0,
            "temporary_multiplier":        1.0,
            "temporary_multiplier_expires": 0,
            "challenges":                  {"normal": None, "event": None, "completed": [], "last_reset": 0},
        }
        for key, default in defaults.items():
            if key not in user_data:
                user_data[key] = default
                modified = True

        if modified:
            self.save_points()
        return user_data

    # ── Daily Claim ─────────────────────────────────────────

    def claim_daily(self, user_id: int):
        """
        Claim daily reward with streak multiplier.
        Returns (success, points_earned, streak, time_until_next, completion_info).
        """
        current_time = int(time.time())
        user_data  = self.get_points(user_id)
        daily_data = user_data["daily_claims"]

        # Cooldown check — 24 hours
        time_since_last = current_time - daily_data["last_claim"]
        if time_since_last < 86400:
            return False, 0, daily_data["streak"], 86400 - time_since_last, None

        # Streak logic: 48-hour grace window
        if time_since_last < 172800:
            daily_data["streak"] += 1
        else:
            daily_data["streak"] = 1

        effective_streak = min(daily_data["streak"], 30)
        multiplier = min(1.0 + (effective_streak // 5) * 0.1, 2.0)

        base_points   = 10
        streak_points = int(base_points * multiplier)
        total_mult    = self.get_multiplier(user_id)
        points_earned = int(round(streak_points * total_mult))

        daily_data["last_claim"]  = current_time
        daily_data["multiplier"]  = multiplier
        user_data["points"]      += points_earned

        # Check daily-streak challenge
        completion = None
        if daily_data["streak"] >= 7:
            _, completion = self.update_challenge_progress(
                user_id, "event", "daily_streak", daily_data["streak"]
            )

        self.save_points()
        self.invalidate_leaderboard_cache()
        return True, points_earned, daily_data["streak"], 0, completion

    # ── Challenges ──────────────────────────────────────────

    def get_user_challenges(self, user_id: int) -> dict:
        """Return the challenges sub-dict for a user, with safe defaults."""
        user_data = self.get_points(user_id)
        challenges = user_data.setdefault(
            "challenges",
            {"normal": None, "event": None, "completed": [], "last_reset": 0},
        )
        for key, default in [("normal", None), ("event", None), ("completed", []), ("last_reset", 0)]:
            challenges.setdefault(key, default)

        # Ensure any existing active challenge has a reroll counter.
        for active in ("normal", "event"):
            current = challenges.get(f"current_{active}")
            if current is not None and "rerolls" not in current:
                current["rerolls"] = 0
                self.save_points()

        return challenges

    def get_challenge_reroll_cost(self, user_id: int, challenge_type: str):
        """Return the current reroll cost for an active challenge."""
        challenges = self.get_user_challenges(user_id)
        current = challenges.get(f"current_{challenge_type}")
        if not current:
            return None
        return 0 if current.get("rerolls", 0) == 0 else 10

    def reroll_challenge(self, user_id: int, challenge_type: str):
        """Reroll the user's active challenge, applying point cost if needed."""
        challenges = self.get_user_challenges(user_id)
        current = challenges.get(f"current_{challenge_type}")
        if not current:
            return False, "You do not have an active challenge to reroll."

        cost = self.get_challenge_reroll_cost(user_id, challenge_type)
        if cost is None:
            return False, "Unable to determine reroll cost."

        points = self.get_points(user_id)["points"]
        if cost > 0 and points < cost:
            return False, f"You need {cost} points to reroll this challenge, but you only have {points}."

        pool = NORMAL_CHALLENGES if challenge_type == "normal" else EVENT_CHALLENGES
        available = [c for c in pool if c["id"] != current["id"]] or pool
        challenge = random.choice(available)

        if cost > 0:
            self.add_points(user_id, -cost)

        challenges[f"current_{challenge_type}"] = {
            "id":          challenge["id"],
            "name":        challenge["name"],
            "description": challenge["description"],
            "reward":      challenge["reward"],
            "target":      challenge["target"],
            "type":        challenge["type"],
            "progress":    0,
            "assigned_at": int(time.time()),
            "rerolls":     current.get("rerolls", 0) + 1,
        }
        self.save_points()
        return True, challenges[f"current_{challenge_type}"], cost

    def assign_random_challenge(self, user_id: int, challenge_type: str):
        """
        Assign a random challenge.
        Returns (success: bool, result: str | dict).
        """
        self.get_points(user_id)
        challenges = self.get_user_challenges(user_id)
        current_time = int(time.time())

        # Rate limit: max 3 completions per hour
        completed_recently = [
            c for c in challenges.get("completed", [])
            if current_time - c["timestamp"] < 3600
        ]
        if len(completed_recently) >= 3:
            return False, "You've completed the maximum challenges for this hour. Try again later!"

        pool = NORMAL_CHALLENGES if challenge_type == "normal" else EVENT_CHALLENGES

        # Don't allow re-rolling an active challenge
        current = challenges.get(f"current_{challenge_type}")
        if current is not None:
            return False, "You already have an active challenge. Complete it before asking for a new one."

        # Avoid immediate repeats
        last_completed = challenges.get("completed", [])
        last_id = last_completed[-1]["id"] if last_completed else None
        available = [c for c in pool if c["id"] != last_id] or pool

        challenge = random.choice(available)
        challenges[f"current_{challenge_type}"] = {
            "id":          challenge["id"],
            "name":        challenge["name"],
            "description": challenge["description"],
            "reward":      challenge["reward"],
            "target":      challenge["target"],
            "type":        challenge["type"],
            "progress":    0,
            "assigned_at": current_time,
            "rerolls":     0,
        }
        self.save_points()
        return True, challenges[f"current_{challenge_type}"]

    def update_challenge_progress(self, user_id: int, challenge_type: str,
                                  progress_type: str, amount: int = 1):
        """Increment progress on the user's active challenge (if matching)."""
        challenges = self.get_user_challenges(user_id)
        current = challenges.get(f"current_{challenge_type}")
        if not current or current["type"] != progress_type:
            return False, None

        current["progress"] = min(current["progress"] + amount, current["target"])

        completion_info = None
        if current["progress"] >= current["target"]:
            completed = self.complete_challenge(user_id, challenge_type)
            if completed:
                _, reward, name = completed
                completion_info = {
                    "id":     current["id"],
                    "name":   name,
                    "reward": reward,
                    "type":   challenge_type,
                }
        self.save_points()
        return True, completion_info

    def complete_challenge(self, user_id: int, challenge_type: str):
        """Mark a challenge as complete: award points and clear the slot."""
        challenges = self.get_user_challenges(user_id)
        current = challenges.get(f"current_{challenge_type}")
        if not current:
            return False

        self.add_points(user_id, current["reward"])
        challenges["completed"].append({
            "id":        current["id"],
            "name":      current["name"],
            "reward":    current["reward"],
            "timestamp": int(time.time()),
        })
        challenges[f"current_{challenge_type}"] = None
        self.save_points()
        return True, current["reward"], current["name"]

    def track_invite(self, user_id: int):
        self.update_challenge_progress(user_id, "normal", "invites")

    # ── Leaderboard ─────────────────────────────────────────

    def leaderboard(self, top: int = 10):
        """Return the cached leaderboard (sorted by points, descending)."""
        if not self._leaderboard_cache:
            self._leaderboard_cache = sorted(
                self.data.items(),
                key=lambda x: x[1]["points"],
                reverse=True,
            )
        return self._leaderboard_cache[:top]

    def leaderboard_by_wins(self, top: int = 10):
        """Return the top users sorted by wins, descending."""
        return sorted(
            self.data.items(),
            key=lambda x: x[1]["wins"],
            reverse=True,
        )[:top]

    def check_leaderboard_challenges(self):
        """Award leaderboard-rank challenge progress for top-10 users."""
        top_10 = [int(uid) for uid, _ in self.leaderboard()[:10]]
        for uid in top_10:
            self.update_challenge_progress(uid, "event", "leaderboard_rank")

    def invalidate_leaderboard_cache(self):
        """Clear the cached leaderboard so next call re-sorts."""
        self._leaderboard_cache = None
        self.check_leaderboard_challenges()
