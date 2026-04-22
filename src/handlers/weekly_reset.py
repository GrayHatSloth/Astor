# ============================================================
# src/handlers/weekly_reset.py — Automatic Weekly Reset Loop
# ============================================================
# Runs in the background. Every Sunday at 00:00 UTC it ends
# the current twist / frenzy and starts a new random week.
# ============================================================

import asyncio
import datetime
import logging

logger = logging.getLogger(__name__)


async def weekly_reset_loop(bot, mode_manager, twist_manager):
    """
    Sleep until next Sunday 00:00 UTC, then cycle the weekly event.
    Called once at startup and runs forever.
    """
    await bot.wait_until_ready()

    while not bot.is_closed():
        # Calculate seconds until next Sunday 00:00 UTC
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        days_ahead = 6 - utc_now.weekday()          # 6 = Sunday
        if days_ahead < 0:
            days_ahead += 7

        next_sunday = datetime.datetime(
            utc_now.year, utc_now.month, utc_now.day,
            tzinfo=datetime.timezone.utc,
        ) + datetime.timedelta(days=days_ahead)
        next_sunday = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)

        if next_sunday <= utc_now:
            next_sunday += datetime.timedelta(days=7)

        wait = (next_sunday - utc_now).total_seconds()
        await asyncio.sleep(wait)

        # ── End the current week ────────────────────────────
        if bot.guild:
            gen = bot.get_channel(bot.config.GENERAL_CHANNEL_ID)
            if gen:
                await twist_manager.end_twist(gen)

                # End Button Frenzy specifically (awards winner points)
                if (
                    mode_manager.active_mode
                    and mode_manager.active_mode.get("type") == "button_frenzy"
                ):
                    await mode_manager.end_button_frenzy(gen)

        # ── Start a new week (only if nothing is active) ────
        if not mode_manager.active_mode:
            await mode_manager.start_weekly_mode()
            gen = bot.get_channel(bot.config.GENERAL_CHANNEL_ID)
            if gen:
                await twist_manager.start_twist(gen)
        else:
            logger.warning("Weekly reset skipped — a mode is still active.")
