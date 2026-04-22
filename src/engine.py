# ============================================================
# src/engine.py — AstorEngine (Central Routing Hub)
# ============================================================
# All game logic flows through this class.  Discord event
# handlers (on_message, on_reaction) are thin shims that
# just call engine.process_message / engine.process_reaction.
#
# Having one central authority means:
#   - behaviour is predictable and easy to trace
#   - adding a new system = one line here, not a new event file
#   - logic can be tested in isolation without Discord running
# ============================================================

import logging
import random

from src.utils.helpers import EMOJI_PATTERN

logger = logging.getLogger(__name__)


class AstorEngine:
    """Central message and reaction routing hub."""

    def __init__(self, bot, managers: dict):
        self.bot            = bot
        self.enforcement    = managers["enforcement"]
        self.mode_manager   = managers["mode_manager"]
        self.twist_manager  = managers["twist_manager"]
        self.points_manager = managers["points_manager"]
        self.effect_manager = managers["effect_manager"]
        self.prefix_handler = managers["prefix_handler"]

    # ── Message Routing ──────────────────────────────────────

    async def process_message(self, message):
        """Route an incoming message through every game system in order."""
        if message.author.bot:
            return

        # 1. Prefix commands  (a.snipe, a.thatday, a.blacklist …)
        handled = await self.prefix_handler.handle_prefix_command(self.bot, message)
        if handled:
            return

        # 2. Blacklist filter
        if await self.prefix_handler.check_blacklist(message):
            return

        # 3. Enforcement rules (active twist / frenzy effects)
        if self.enforcement.has_active_rules():
            await self.enforcement.check_message(message)

        # 4. Weekly mode  (mystery guesses, etc.)
        await self.mode_manager.handle_message(message)

        # 5. Weekly twist message tracking
        await self.twist_manager.handle_message(message)

        # 6. Challenge progress counters
        await self._track_challenge_progress(message)

        # 7. discord.py built-in command dispatch (slash commands go here)
        await self.bot.process_commands(message)

    # ── Reaction Routing ─────────────────────────────────────

    async def process_reaction(self, payload):
        """Route an incoming reaction through every game system in order."""
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        # Chaos button press (Button Frenzy mode)
        if payload.message_id in self.effect_manager.chaos_buttons:
            await self.effect_manager.handle_chaos_button(payload)
            return

        # Weekly twist activation (✅ button)
        if payload.emoji.name == "✅" and payload.message_id == self.bot.button_message_id:
            await self._handle_twist_activation(payload, channel, guild)

        # Reaction-based challenge tracking
        self.points_manager.update_challenge_progress(payload.user_id, "normal", "reactions")

    # ── Twist Activation ─────────────────────────────────────

    async def _handle_twist_activation(self, payload, channel, guild):
        """Handle a ✅ reaction on the weekly twist button."""
        tm = self.twist_manager

        if tm.pending_twist and not tm.active_twist:
            twist_type = random.choice(["most_messages", "first_to_x", "most_words", "most_replies"])

            if twist_type == "first_to_x":
                tm.first_to_x_target = random.randint(5000, 10000)

            tm.active_twist = {"type": twist_type, "winner_declared": False}
            tm.data = {}
            tm.pending_twist = False

            labels = {
                "most_messages": "📊 Send the most messages this week to win!",
                "first_to_x":   f"🏁 First to reach {tm.first_to_x_target} messages wins!",
                "most_words":   "📝 Send the most words this week to win!",
                "most_replies": "💬 Get the most replies to your messages to win!",
            }
            await channel.send(
                f"@everyone\n🎉 **Weekly Twist Started!** {labels[twist_type]}"
            )

        # Remove the user's reaction so the button stays clean
        message = await channel.fetch_message(payload.message_id)
        member = await guild.fetch_member(payload.user_id)
        if member:
            try:
                await message.remove_reaction(payload.emoji, member)
            except Exception:
                pass

    # ── Challenge Progress ───────────────────────────────────

    async def _track_challenge_progress(self, message):
        """Update challenge counters based on message content."""
        uid = message.author.id
        ch  = message.channel

        async def track(challenge_type, progress_type, amount=1):
            updated, comp = self.points_manager.update_challenge_progress(
                uid, challenge_type, progress_type, amount
            )
            if comp and ch:
                from src.views.challenge_view import ChallengeCompleteView, build_challenge_completion_embed
                try:
                    member = await message.guild.fetch_member(uid)
                except Exception:
                    member = None
                if member:
                    embed = build_challenge_completion_embed(member, comp["name"], comp["reward"])
                    await ch.send(embed=embed, view=ChallengeCompleteView(uid))

        # Messages sent
        await track("normal", "messages")

        # Unique mentions
        if message.mentions:
            await track("normal", "mentions", len(set(m.id for m in message.mentions)))

        # Unique emoji used
        emojis = set(EMOJI_PATTERN.findall(message.content))
        if emojis:
            await track("normal", "emojis", len(emojis))

        # Stickers
        if message.stickers:
            await track("normal", "stickers", len(message.stickers))

        # Thread posts
        if (
            hasattr(message.channel, "type")
            and message.channel.type.name == "public_thread"
        ):
            await track("normal", "threads", 1)
