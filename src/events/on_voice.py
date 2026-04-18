# ============================================================
# src/events/on_voice.py — Voice State Tracking
# ============================================================
# Tracks when users join / leave voice channels so the
# voice_minutes challenge can be progressed.
# ============================================================

from config import Config


def setup(bot, points_manager):
    """Register on_voice_state_update."""

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.bot:
            return

        ch = bot.get_channel(Config.GENERAL_CHANNEL_ID)

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            points_manager.update_challenge_progress(member.id, "normal", "voice_minutes", 1)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            points_manager.update_challenge_progress(member.id, "normal", "voice_minutes", 1)
