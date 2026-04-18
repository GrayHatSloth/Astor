# ============================================================
# src/managers/twist_manager.py — Weekly Twist Competitions
# ============================================================
# A "twist" is a mini-competition that runs alongside the
# weekly mode.  Users click a button to start; then it
# tracks messages / words / replies to crown a winner.
# ============================================================

import random

import discord


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
            print("[TWIST] Already pending or active.")
            return False

        self.pending_twist = True
        msg = await channel.send("✅ Click this button to start the weekly twist!")
        await msg.add_reaction("✅")
        self.bot.button_message_id = msg.id
        return True

    async def end_twist(self, channel):
        """End the twist and announce the winner (if applicable)."""
        if not self.active_twist:
            return

        twist_type = self.active_twist["type"]

        # first_to_x already declared its winner in real-time
        if twist_type == "first_to_x" and self.active_twist["winner_declared"]:
            self.active_twist = None
            return

        # For other types, the user with the highest count wins
        if not self.data:
            await channel.send("⏰ Weekly Twist ended! Nobody participated.")
            self.active_twist = None
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
            f"🏆 Weekly Twist ended! {name} wins with **{self.data[winner_id]}** ({label})!"
        )
        self.active_twist = None

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
