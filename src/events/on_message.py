# ============================================================
# src/events/on_message.py — Message Handler
# ============================================================
# Routes every incoming message through:
#   1. Prefix commands (a.snipe, a.thatday, a.blacklist)
#   2. Blacklist check
#   3. Enforcement rules (twists / frenzy effects)
#   4. Weekly mode message handling (mystery guesses)
#   5. Weekly twist tracking
#   6. Challenge progress tracking
# ============================================================

import re

from src.utils.helpers import EMOJI_PATTERN


def setup(bot, managers):
    """
    Register the on_message event.
    `managers` dict has: enforcement, mode_manager, twist_manager,
                         points_manager, prefix_handler (module)
    """
    enforcement    = managers["enforcement"]
    mode_manager   = managers["mode_manager"]
    twist_manager  = managers["twist_manager"]
    points_manager = managers["points_manager"]
    prefix_handler = managers["prefix_handler"]

    @bot.event
    async def on_message(message):
        # Ignore all bot messages
        if message.author.bot:
            return

        # 1. Prefix commands
        handled = await prefix_handler.handle_prefix_command(bot, message)
        if handled:
            return

        # 2. Blacklist
        if await prefix_handler.check_blacklist(message):
            return

        # 3. Enforcement (twist / frenzy rules)
        if enforcement.has_active_rules():
            await enforcement.check_message(message)

        # 4. Mystery mode guess handler
        await mode_manager.handle_message(message)

        # 5. Weekly twist message tracking
        await twist_manager.handle_message(message)

        # 6. Challenge progress
        await _track_challenge_progress(message, points_manager)

        # 7. Let discord.py process built-in commands
        await bot.process_commands(message)


async def _track_challenge_progress(message, pm):
    """Update challenge counters based on message content."""
    uid = message.author.id
    ch  = message.channel

    # Helper to update + notify
    async def track(challenge_type, progress_type, amount=1):
        updated, comp = pm.update_challenge_progress(uid, challenge_type, progress_type, amount)
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

    # Threads
    if (
        hasattr(message.channel, "type")
        and message.channel.type.name == "public_thread"
    ):
        await track("normal", "threads", 1)
