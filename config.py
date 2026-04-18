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

    # ── Data File Paths ─────────────────────────────────────
    # All JSON persistence files live in the data/ folder
    POINTS_FILE = os.path.join("data", "points.json")
    SHOP_FILE = os.path.join("data", "shop.json")
    SHOP_DATA_FILE = os.path.join("data", "shop_data.json")
    WHITELIST_FILE = os.path.join("data", "whitelist_cmds.json")

    # ── Special User IDs ────────────────────────────────────
    WHITELIST_IDS = {992399209686892604}
    THATDAY_ONLY_ID = 1406738792726925494
