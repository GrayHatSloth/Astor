# ============================================================
# src/managers/twist_manager.py — Weekly Twist Competitions
# ============================================================
# A "twist" is a mini-competition that runs alongside the
# weekly mode.  Users click a button to start; then it
# tracks messages / words / replies to crown a winner.
# ============================================================

import json
import logging
import pathlib
import random

import discord

logger = logging.getLogger(__name__)

_TWIST_STATE_FILE = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "twist_state.json"


class WeeklyTwistManager:
    """Tracks weekly twist state, message stats, and declares winners."""

    def __init__(self, bot):
        self.bot = bot
        self.active_twist  = None   # {"type": ..., "winner_declared": bool}
        self.pending_twist = False  # True after button is sent, before it's clicked
        self.data = {}              # user_id → count (messages / words / replies)
        self.first_to_x_target = 0

    # ── Start / End ─────────────────────────────────────────

    async def start_twist(self, channel) -> bool:
        """Send the '✅ click to start' message. Returns False if already running."""
        if self.pending_twist or self.active_twist:
            logger.warning("start_twist called but already pending or active.")
            return False

        self.pending_twist = True
        msg = await channel.send(
            "@everyone\n"
            "✅ **A weekly twist is available!** Click the button below to start it."
        )
        await msg.add_reaction("✅")
        self.bot.button_message_id = msg.id
        self._persist_twist()
        return True

    async def end_twist(self, channel):
        """End the twist and announce the winner (if applicable)."""
        if not self.active_twist:
            return

        twist_type = self.active_twist["type"]

        # first_to_x already declared its winner in real-time
        if twist_type == "first_to_x" and self.active_twist["winner_declared"]:
            self.active_twist = None
            self._persist_twist()
            return

        # For other types, the user with the highest count wins
        if not self.data:
            await channel.send("⏰ Weekly Twist ended! Nobody participated.")
            self.active_twist = None
            self._persist_twist()
            return

        winner_id = max(self.data, key=self.data.get)
        self.bot.points_manager.add_points(winner_id, "weekly_twist")
        self.bot.points_manager.add_win(winner_id)

        try:
            user = await self.bot.fetch_user(winner_id)
            name = user.mention
        except Exception:
            name = f"Unknown ({winner_id})"

        label = {
            "most_messages": "most messages",
            "most_words":    "most words",
            "most_replies":  "most replies received",
        }.get(twist_type, twist_type)

        await channel.send(
            f"@everyone\n🏆 **Weekly Twist ended!** {name} wins with **{self.data[winner_id]}** ({label})!"
        )
        self.active_twist = None
        self._persist_twist()

    # ── Message Tracking ────────────────────────────────────

    async def handle_message(self, message):
        """Update twist counters based on message activity."""
        if not self.active_twist:
            return

        uid = message.author.id
        twist_type = self.active_twist["type"]

        if uid not in self.data:
            self.data[uid] = 0

        # most_messages & first_to_x both count raw messages
        if twist_type in ("most_messages", "first_to_x"):
            self.data[uid] += 1

            if twist_type == "first_to_x":
                if (
                    self.data[uid] >= self.first_to_x_target
                    and not self.active_twist["winner_declared"]
                ):
                    self.active_twist["winner_declared"] = True
                    self.bot.points_manager.add_points(uid, "weekly_twist")
                    self.bot.points_manager.add_win(uid)
                    self._persist_twist()
                    await message.channel.send(
                        f"🏆 {message.author.mention} reached {self.first_to_x_target} "
                        f"messages and wins the Weekly Twist!"
                    )

        # most_words counts total words
        elif twist_type == "most_words":
            self.data[uid] += len(message.content.split())

        # most_replies counts replies *received* (not sent)
        elif twist_type == "most_replies":
            if message.reference:
                try:
                    replied = await message.channel.fetch_message(message.reference.message_id)
                    orig = replied.author.id
                    if orig not in self.data:
                        self.data[orig] = 0
                    self.data[orig] += 1
                except Exception:
                    pass

    # ── Activate (called by AstorEngine on ✅ reaction) ────────────

    async def activate_twist(self, channel) -> bool:
        """
        Randomly choose a twist type, set state to active, and announce.
        Called by AstorEngine when the ✅ button is clicked.
        Returns True if the twist was started, False if not pending.
        """
        if not (self.pending_twist and not self.active_twist):
            return False

        twist_type = random.choice(["most_messages", "first_to_x", "most_words", "most_replies"])
        target = 0
        if twist_type == "first_to_x":
            target = random.randint(5000, 10000)
            self.first_to_x_target = target

        self.active_twist = {"type": twist_type, "winner_declared": False}
        self.data = {}
        self.pending_twist = False
        self._persist_twist()

        labels = {
            "most_messages": "📊 Send the most messages this week to win!",
            "first_to_x":   f"🏁 First to reach {target} messages wins!",
            "most_words":   "📝 Send the most words this week to win!",
            "most_replies": "💬 Get the most replies to your messages to win!",
        }
        await channel.send(
            f"@everyone\n🎉 **Weekly Twist Started!** {labels[twist_type]}"
        )
        return True

    # ── State Persistence ────────────────────────────────────

    def _persist_twist(self):
        """Write current twist state to disk so it survives restarts."""
        state = {
            "active_twist":      self.active_twist,
            "pending_twist":     self.pending_twist,
            "data":              {str(k): v for k, v in self.data.items()},
            "first_to_x_target": self.first_to_x_target,
            "button_message_id": getattr(self.bot, "button_message_id", None),
        }
        try:
            _TWIST_STATE_FILE.write_text(json.dumps(state))
        except OSError as exc:
            logger.warning("Could not save twist state: %s", exc)

    def restore_twist_state(self):
        """Load and re-apply twist state on startup. Called from on_ready."""
        if not _TWIST_STATE_FILE.exists():
            return
        try:
            saved = json.loads(_TWIST_STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load twist state: %s", exc)
            return

        self.active_twist      = saved.get("active_twist")
        self.pending_twist     = saved.get("pending_twist", False)
        self.data              = {int(k): v for k, v in saved.get("data", {}).items()}
        self.first_to_x_target = saved.get("first_to_x_target", 0)

        msg_id = saved.get("button_message_id")
        if msg_id:
            self.bot.button_message_id = msg_id

        if self.active_twist:
            logger.info("Restored active twist: %s", self.active_twist.get("type"))
        elif self.pending_twist:
            logger.info("Restored pending twist (button_message_id=%s)", msg_id)
