# ============================================================
# bot.py — Astor Entry Point
# ============================================================
# Creates the bot, instantiates every manager, wires up all
# event handlers, and runs.
# ============================================================

import os
import sys
import threading
from pathlib import Path

# Ensure `src` package is importable from different deployment root layouts.
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
if project_root.name == "src":
    sys.path.insert(0, str(project_root.parent))

import discord
from discord.ext import commands
from flask import Flask

from config import Config
from src.utils.pid import create_pid_file, remove_pid_file

app = Flask("astor")

@app.route("/", methods=["GET"])
def home():
    return "Astor is running", 200


def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ── Managers ────────────────────────────────────────────────
from src.managers.enforcement import Enforcement
from src.managers.points_manager import PointsManager
from src.managers.shop_manager import ShopManager
from src.managers.effect_manager import EffectManager
from src.managers.mode_manager import ModeManager
from src.managers.twist_manager import WeeklyTwistManager
from src.handlers import prefix_handler

# ── Event setup functions ───────────────────────────────────
from src.events.on_ready import setup as setup_on_ready
from src.events.on_message import setup as setup_on_message
from src.events.on_message_delete import setup as setup_on_message_delete
from src.events.on_reaction import setup as setup_on_reaction
from src.events.on_voice import setup as setup_on_voice


def main():
    # ── Intents ─────────────────────────────────────────────
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    intents.members = True

    # ── Bot instance ────────────────────────────────────────
    bot = commands.Bot(command_prefix=Config.COMMAND_PREFIXES, intents=intents)
    bot.config = Config
    print("[INFO] Starting Astor bot...")

    # ── Instantiate managers ────────────────────────────────
    enforcement = Enforcement(bot)
    twist_manager = WeeklyTwistManager(bot)
    mode_manager = ModeManager(bot, twist_manager)
    effect_manager = EffectManager(bot, enforcement)
    points_manager = PointsManager(bot)
    shop_manager = ShopManager(bot)

    # Attach to bot for cross-module access
    bot.points_manager = points_manager
    bot.shop_manager = shop_manager
    bot.mode_manager = mode_manager
    bot.weekly_twist_manager = twist_manager
    bot.effect_manager = effect_manager
    bot.enforcement = enforcement

    # ── Extra runtime state ─────────────────────────────────
    bot.button_message_id = None
    bot.loops_started = False
    bot.commands_registered = False
    bot.deleted_messages = []  # rolling cache for a.snipe

    # ── Managers dict (passed to event setup functions) ─────
    managers = {
        "points_manager": points_manager,
        "shop_manager": shop_manager,
        "mode_manager": mode_manager,
        "twist_manager": twist_manager,
        "effect_manager": effect_manager,
        "enforcement": enforcement,
        "prefix_handler": prefix_handler,
    }

    # ── Register event handlers ─────────────────────────────
    setup_on_ready(bot, managers)
    setup_on_message(bot, managers)
    setup_on_message_delete(bot)
    setup_on_reaction(bot, managers)
    setup_on_voice(bot, points_manager)

    # ── Run ─────────────────────────────────────────────────
    create_pid_file()
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    try:
        bot.run(Config.TOKEN)
    except KeyboardInterrupt:
        print("[DEBUG] KeyboardInterrupt received, shutting down.")
    finally:
        remove_pid_file()


if __name__ == "__main__":
    main()
