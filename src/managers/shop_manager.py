# ============================================================
# src/managers/shop_manager.py — Shop & Item Economy
# ============================================================
# Manages the shop catalogue, stock, purchases, item effects
# (roles, boosters, nicknames, channel access), and history.
# ============================================================

import json
import os
import time

import discord

from config import Config
from src.db import Database


class ShopManager:
    """Handles shop items, purchases, nickname requests, and stock."""

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.items = {}
        self.data = {}
        self._enabled_items_cache = None
        self.load_shop()
        self.load_data()

    # ── Persistence ─────────────────────────────────────────

    def load_shop(self):
        """Load the item catalogue from disk or the configured database."""
        if self.db.enabled:
            self.items = self.db.load_json("shop_items", {})
            if not isinstance(self.items, dict):
                self.items = {}
            if not self.items:
                self.create_default_items()
            return

        if os.path.exists(Config.SHOP_FILE):
            with open(Config.SHOP_FILE, "r") as f:
                try:
                    self.items = json.load(f)
                except json.JSONDecodeError:
                    self.items = {}
        else:
            self.items = {}
            self.create_default_items()

    def save_shop(self):
        if self.db.enabled:
            self.db.save_json("shop_items", self.items)
            self.invalidate_cache()
            return

        with open(Config.SHOP_FILE, "w") as f:
            json.dump(self.items, f, indent=4)
        self.invalidate_cache()

    def load_data(self):
        """Load purchase history and nickname requests."""
        if self.db.enabled:
            self.data = self.db.load_json("shop_data", {})
            if not isinstance(self.data, dict):
                self.data = {}
        elif os.path.exists(Config.SHOP_DATA_FILE):
            with open(Config.SHOP_DATA_FILE, "r") as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}
        else:
            self.data = {}

        self.data.setdefault("nickname_requests", {})
        self.data.setdefault("purchase_history", {})
        self.save_data()

    def save_data(self):
        if self.db.enabled:
            self.db.save_json("shop_data", self.data)
            return

        with open(Config.SHOP_DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # ── Default Items ───────────────────────────────────────

    def create_default_items(self):
        """Seed the shop with starter items."""
        self.items = {
            "vip_package": {
                "name": "⭐ VIP Package",
                "description": "Get VIP role + access to exclusive VIP chat channel",
                "price": 750, "type": "vip_package",
                "role_id": None, "channel_id": None,
                "stock": -1, "enabled": True,
            },
            "custom_nickname": {
                "name": "📝 Custom Nickname",
                "description": "Change your nickname (admin approval required)",
                "price": 200, "type": "nickname",
                "stock": -1, "enabled": True,
            },
            "points_multiplier": {
                "name": "⚡ 2x Points Multiplier",
                "description": "Earn double points permanently",
                "price": 1000, "type": "permanent_multiplier",
                "multiplier": 2, "stock": -1, "enabled": True,
            },
            "temporary_booster": {
                "name": "🚀 24h Points Booster",
                "description": "Earn 3x points for 24 hours",
                "price": 400, "type": "temporary_booster",
                "multiplier": 3, "duration": 86400,
                "stock": -1, "enabled": True,
            },
            "priority_speaker": {
                "name": "🎤 Priority Speaker",
                "description": "Get priority role for voice channels",
                "price": 400, "type": "role",
                "role_id": None, "stock": -1, "enabled": True,
            },
            "custom_badge": {
                "name": "🎗️ Custom Badge",
                "description": "Get a cosmetic role badge (max 3 per user)",
                "price": 80, "type": "role",
                "role_id": None, "stock": -1, "enabled": True,
                "max_per_user": 3,
            },
        }
        self.save_shop()

    # ── Queries ─────────────────────────────────────────────

    def get_item(self, item_id: str):
        return self.items.get(item_id)

    def get_enabled_items(self):
        """Cached list of (item_id, item) tuples for enabled items."""
        if self._enabled_items_cache is None:
            self._enabled_items_cache = [
                (iid, item) for iid, item in self.items.items()
                if item.get("enabled", False)
            ]
        return self._enabled_items_cache

    def invalidate_cache(self):
        self._enabled_items_cache = None

    def total_pages(self, items_per_page: int) -> int:
        enabled = self.get_enabled_items()
        if not enabled:
            return 1
        return (len(enabled) + items_per_page - 1) // items_per_page

    def get_paged_items(self, page: int, items_per_page: int):
        enabled = self.get_enabled_items()
        start = page * items_per_page
        return enabled[start : start + items_per_page]

    # ── Purchase History ────────────────────────────────────

    def get_purchase_count(self, user_id, item_id) -> int:
        return self.data.get("purchase_history", {}).get(str(user_id), {}).get(item_id, 0)

    def record_purchase(self, user_id, item_id):
        self.data.setdefault("purchase_history", {})
        uid = str(user_id)
        self.data["purchase_history"].setdefault(uid, {})
        self.data["purchase_history"][uid].setdefault(item_id, 0)
        self.data["purchase_history"][uid][item_id] += 1
        self.save_data()

    # ── Affordability Check ─────────────────────────────────

    def can_afford(self, user_id, item_id):
        """Return (can_buy: bool, reason: str)."""
        item = self.get_item(item_id)
        if not item or not item.get("enabled"):
            return False, "Item not available"

        user_points = self.bot.points_manager.get_points(user_id)["points"]
        if user_points < item["price"]:
            return False, f"You need {item['price']} points, you have {user_points}"

        if item["stock"] == 0:
            return False, "Out of stock"

        max_per = item.get("max_per_user")
        if max_per is not None:
            count = self.get_purchase_count(user_id, item_id)
            if count >= max_per:
                return False, f"You can only purchase this item {max_per} time(s). You've bought it {count} time(s)."

        return True, "OK"

    # ── Purchase Flow ───────────────────────────────────────

    async def purchase_item(self, user_id, item_id, requested_nickname=None):
        """
        Attempt to buy an item.
        Returns (success, message, [completion_events]).
        """
        can_buy, reason = self.can_afford(user_id, item_id)
        if not can_buy:
            return False, reason, []

        item = self.get_item(item_id)

        # Apply the gameplay effect first
        success = await self.apply_item_effect(user_id, item)
        if not success:
            return False, "Could not apply item effect.", []

        # Deduct cost
        self.bot.points_manager.add_points(user_id, -item["price"])

        completions = []

        if item["type"] == "nickname":
            self.add_nickname_request(user_id, requested_nickname)

        self.record_purchase(user_id, item_id)

        # Track shop-purchase challenge
        _, comp = self.bot.points_manager.update_challenge_progress(user_id, "event", "shop_purchase")
        if comp:
            completions.append(comp)

        # Track role-request challenge
        if item["type"] == "role":
            _, comp = self.bot.points_manager.update_challenge_progress(user_id, "event", "role_request")
            if comp:
                completions.append(comp)

        # Reduce stock if finite
        if item["stock"] > 0:
            item["stock"] -= 1
            self.save_shop()

        return True, "Purchase successful!", completions

    # ── Effect Application ──────────────────────────────────

    async def apply_item_effect(self, user_id, item) -> bool:
        """Apply the actual Discord-side effect of a purchased item."""
        item_type = item["type"]
        guild  = self.bot.get_guild(Config.GUILD_ID)
        member = None
        if guild:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)

        try:
            if item_type == "role":
                role = guild.get_role(item["role_id"]) if guild and item.get("role_id") else None
                if role and member:
                    await member.add_roles(role)
                    return True
                return False

            elif item_type == "vip_package":
                ok = True
                if item.get("role_id") and guild and member:
                    role = guild.get_role(item["role_id"])
                    if role:
                        await member.add_roles(role)
                    else:
                        ok = False
                if item.get("channel_id") and guild and member:
                    ch = guild.get_channel(item["channel_id"])
                    if ch:
                        await ch.set_permissions(member, read_messages=True)
                    else:
                        ok = False
                return ok

            elif item_type == "nickname":
                return True  # Needs admin approval — no immediate effect

            elif item_type == "permanent_multiplier":
                self.bot.points_manager.set_permanent_multiplier(user_id, item.get("multiplier", 2))
                return True

            elif item_type == "temporary_booster":
                self.bot.points_manager.set_temporary_multiplier(
                    user_id, item.get("multiplier", 2), item.get("duration", 3600)
                )
                return True

            elif item_type == "channel_access":
                ch = guild.get_channel(item["channel_id"]) if guild and item.get("channel_id") else None
                if ch and member:
                    await ch.set_permissions(member, read_messages=True)
                    return True
                return False

            return True  # Unknown types succeed silently

        except Exception as e:
            print(f"[SHOP] Error applying item effect: {e}")
            return False

    # ── Nickname Requests ───────────────────────────────────

    def add_nickname_request(self, user_id, requested_nickname=None):
        self.data.setdefault("nickname_requests", {})
        self.data["nickname_requests"][str(user_id)] = {
            "status": "pending",
            "requested_nickname": requested_nickname,
            "requested_at": int(time.time()),
        }
        self.save_data()
