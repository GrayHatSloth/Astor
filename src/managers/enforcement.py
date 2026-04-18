# ============================================================
# src/managers/enforcement.py — Message Rule Enforcement
# ============================================================
# Checks every message against the currently active twist or
# button-frenzy effect.  Violations are deleted and the user
# is DM'd with a cooldown to prevent spam.
# ============================================================

import time


class Enforcement:
    """Deletes messages that break the current twist / frenzy rule."""

    DM_COOLDOWN_SECONDS = 30  # Min seconds between DMs to the same user

    def __init__(self, bot):
        self.bot = bot

        # Weekly twist state
        self.active_twist = None
        self.no_letter    = None
        self.banned_word  = None
        self.required_word = None
        self.last_messages = {}       # user_id → last message content  (for no_repeat)

        # Button Frenzy effect (overrides twist when set)
        self.current_effect = None

        # DM cooldown tracker:  user_id → last_dm_timestamp
        self.user_dm_cooldown = {}

    # ── Public API ──────────────────────────────────────────

    def set_effect(self, effect: dict):
        """Apply a button-frenzy effect (takes priority over twist)."""
        self.current_effect = effect
        self.user_dm_cooldown = {}

    def set_twist(self, twist: dict | None):
        """Set (or clear) the weekly twist enforcement rule."""
        self.active_twist  = twist
        self.no_letter     = None
        self.banned_word   = None
        self.required_word = None
        self.last_messages = {}
        self.user_dm_cooldown = {}

        if not twist:
            return
        if twist.get("type") == "no_letter":
            self.no_letter = twist["letter"]
        elif twist.get("type") == "no_word":
            self.banned_word = twist["word"]
        elif twist.get("type") == "must_include":
            self.required_word = twist["word"]

    def has_active_rules(self) -> bool:
        """Quick check so on_message can skip enforcement entirely."""
        return self.current_effect is not None or self.active_twist is not None

    # ── Message Check ───────────────────────────────────────

    async def check_message(self, message):
        """Delete the message if it violates the active rule, and DM the user."""
        if message.author.bot:
            return
        # Ignore command invocations
        if any(message.content.startswith(p) for p in [".", ",", "!"]):
            return

        effect = self.current_effect or self.active_twist
        if not effect:
            return

        content    = message.content.lower()
        guild_id   = message.guild.id
        channel_id = self.bot.config.GENERAL_CHANNEL_ID
        msg_id     = getattr(self.bot, "button_message_id", 0)
        twist_link = f"https://discord.com/channels/{guild_id}/{channel_id}/{msg_id}"

        # ── must_include ──
        if effect.get("type") == "must_include":
            if effect["word"].lower() not in content:
                await message.delete()
                if self._can_dm(message.author.id):
                    await message.author.send(
                        f"⚠️ Messages must include '{effect['word']}'!\n{twist_link}"
                    )

        # ── max_words ──
        elif effect.get("type") == "max_words":
            limit = effect.get("limit", 999)
            if len(content.split()) > limit:
                await message.delete()
                if self._can_dm(message.author.id):
                    await message.author.send(
                        f"⚠️ Max {limit} words per message!\n{twist_link}"
                    )

        # ── no_letter ──
        elif effect.get("type") == "no_letter":
            letter = effect["letter"].lower()
            if letter in content:
                await message.delete()
                if self._can_dm(message.author.id):
                    await message.author.send(
                        f"⚠️ Messages cannot contain '{letter}'!\n{twist_link}"
                    )

        # ── no_link ──
        elif effect.get("type") == "no_link":
            if "http" in content or "www" in content:
                await message.delete()
                if self._can_dm(message.author.id):
                    await message.author.send(
                        f"⚠️ Messages cannot contain links!\n{twist_link}"
                    )

        # ── no_repeat ──
        elif effect.get("type") == "no_repeat":
            uid = message.author.id
            if self.last_messages.get(uid) == content:
                await message.delete()
                if self._can_dm(uid):
                    await message.author.send(
                        f"⚠️ No repeating messages!\n{twist_link}"
                    )
                return
            self.last_messages[uid] = content

    # ── DM Cooldown ─────────────────────────────────────────

    def _can_dm(self, user_id: int) -> bool:
        """Return True if we haven't DM'd this user in the last N seconds."""
        now = time.time()
        last = self.user_dm_cooldown.get(user_id, 0)
        if now - last < self.DM_COOLDOWN_SECONDS:
            return False
        self.user_dm_cooldown[user_id] = now
        return True
