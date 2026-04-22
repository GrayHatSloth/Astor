# ============================================================
# config.py — Central Configuration
# ============================================================
# All bot settings live here. Environment variables hold secrets,
# plain constants hold Discord IDs and bot behavior settings.
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root if it exists.
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)


class Config:
    """Single source of truth for every tuneable value in the bot."""

    # ── Data directory and persistence ──────────────────────
    # If the deployment environment provides a persistent volume, set DATA_PATH
    # to that mount and data will be stored there instead of the repo folder.
    DATA_ROOT = Path(os.getenv("DATA_PATH", project_root / "data")).resolve()
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    POINTS_FILE = str(DATA_ROOT / "points.json")
    SHOP_FILE = str(DATA_ROOT / "shop.json")
    SHOP_DATA_FILE = str(DATA_ROOT / "shop_data.json")
    WHITELIST_FILE = str(DATA_ROOT / "whitelist_cmds.json")

    # ── External persistence ─────────────────────────────────
    DATABASE_URL = os.getenv("DATABASE_URL")

    # ── Secret ──────────────────────────────────────────────
    TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if TOKEN is None:
        raise ValueError(
            "DISCORD_BOT_TOKEN (or DISCORD_TOKEN) is not set. "
            "Set it in a root .env file locally or configure it in your Render environment."    
        )

    # ── Guild & Channels ──────────────────────────────────────
    GUILD_ID = int(os.getenv("GUILD_ID", "1392833250984071209"))

    GENERAL_CHANNEL_ID = 1477724171852054660
    ANNOUNCEMENT_CHANNEL_ID = 1477724097361346590
    DEBATE_CHANNEL_ID = 1477764058043383911
    INVITE_CHANNEL_ID = 1477764132110602321
    MOVIE_CHANNEL_ID = 1477764272758067220
    PROFILE_COMP_CHANNEL_ID = 1483879171154509955

    # ── Prefix Commands ─────────────────────────────────────
    COMMAND_PREFIXES = ("a.",)

    # ── Special User IDs ────────────────────────────────────
    WHITELIST_IDS = {992399209686892604}
    THATDAY_ONLY_ID = 1406738792726925494

    # ── Mystery mode ─────────────────────────────────────────
    MYSTERY_CHANNEL_ID             = 1496545158202659077  # dedicated guess channel
    MYSTERY_CLUE_INTERVAL_SECONDS  = 28800  # 8 h between each clue reveal
    MYSTERY_FINAL_GUESS_SECONDS    = 28800  # 8 h window after the final clue (24 h total per mystery)
    MYSTERY_GUESS_COOLDOWN_SECONDS = 5      # min seconds between wrong guesses per user
    MYSTERY_DAY_DURATION_SECONDS   = 86400  # 24 h — one mystery per day, 7 days per week

    # ── Button Frenzy ────────────────────────────────────────
    CHAOS_BUTTON_MIN_INTERVAL      = 10800  # 3 h minimum between chaos button spawns
    CHAOS_BUTTON_MAX_INTERVAL      = 18000  # 5 h maximum between chaos button spawns

    # ── Timeout token ────────────────────────────────────────
    TIMEOUT_TOKEN_DURATION_MINUTES = 5      # how long a timeout-token mute lasts
    TIMEOUT_TOKEN_COOLDOWN_SECONDS = 3600   # 1 h between uses of a token
