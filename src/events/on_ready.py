# ============================================================
# src/events/on_ready.py — Bot Ready Handler
# ============================================================
# Fires when the bot connects to Discord.
# Syncs slash commands and starts background loops.
# ============================================================

import os

import discord

from config import Config

# These will be injected at setup time
from src.commands.weekly  import weekly_commands
from src.commands.economy import points_commands, shop_commands
from src.commands.admin   import admin_commands
from src.commands.utility import utility_commands


def setup(bot, managers):
    """
    Register the on_ready event.
    `managers` is a dict with keys:
      points_manager, shop_manager, mode_manager,
      twist_manager, effect_manager, enforcement
    """
    pm = managers["points_manager"]
    sm = managers["shop_manager"]
    mm = managers["mode_manager"]
    tm = managers["twist_manager"]
    em = managers["effect_manager"]

    @bot.event
    async def on_ready():
        print(f"Bot online: {bot.user}")
        print(f"[READY] PID: {os.getpid()}")
        print("[READY] uploaded successfully")

        conn = getattr(bot, "_connection", None)
        print(f"[READY] Session: {getattr(conn, 'session_id', 'unknown') if conn else 'unknown'}")

        if bot.guilds:
            bot.guild = bot.guilds[0]
            print(f"[READY] Connected to guild: {bot.guild.name}")

            # Register slash commands (once per lifetime)
            if not getattr(bot, "commands_registered", False):
                await weekly_commands.setup(bot, mm, tm)
                await points_commands.setup(bot, pm)
                await shop_commands.setup(bot, sm)
                await admin_commands.setup(bot, sm)
                await utility_commands.setup(bot)
                bot.commands_registered = True

            # Sync commands with Discord
            try:
                guild_obj = discord.Object(id=Config.GUILD_ID)
                synced = await bot.tree.sync(guild=guild_obj)
                print(f"[READY] Synced {len(synced)} guild commands")
            except Exception as e:
                print(f"[READY] Command sync failed: {e}")

            # Start background loops (once per lifetime)
            if not bot.loops_started:
                bot.loop.create_task(em.chaos_button_loop())
                bot.loop.create_task(em.effect_expiry_loop())

                # Import inline to avoid circular dependency
                from src.handlers.weekly_reset import weekly_reset_loop
                bot.loop.create_task(weekly_reset_loop(bot, mm, tm))

                bot.loops_started = True
                print("[READY] Background loops started.")
            else:
                print("[READY] Loops already running, skipping.")
        else:
            bot.guild = None
            print("[READY] No guild found!")
