# ============================================================
# src/managers/effect_manager.py — Chaos Button & Frenzy Effects
# ============================================================
# During "Button Frenzy" mode, chaos buttons spawn in general
# chat every 3-5 hours. Pressing one activates a random
# enforcement effect and awards frenzy points.
# ============================================================

import asyncio
import json
import logging
import pathlib
import random
import time

from config import Config

_STATE_FILE = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "effect_state.json"

logger = logging.getLogger(__name__)


class EffectManager:
    """Spawns chaos buttons and applies effects during Button Frenzy."""

    def __init__(self, bot, enforcement):
        self.bot = bot
        self.enforcement = enforcement

        # Currently active effect (if any)
        self.active_effect = None
        self.effect_end_time = None

        # Maps message_id → {"active": bool}
        self.chaos_buttons = {}

        # Pool of effects a chaos button can trigger
        self.effect_pool = [
            {"type": "must_include", "word": "lol", "duration": 1200},
            {"type": "max_words",    "limit": 3,    "duration": 1200},
            {"type": "no_letter",                    "duration": 1200},   # letter randomised on apply
            {"type": "no_link",                      "duration": 1800},
        ]

    # ── Background Loop: Spawn Buttons ──────────────────────

    async def chaos_button_loop(self):
        """Continuously spawn chaos buttons while Button Frenzy is active."""
        await self.bot.wait_until_ready()

        while True:
            # Only spawn during Button Frenzy mode
            mode_mgr = getattr(self.bot, "mode_manager", None)
            active   = getattr(mode_mgr, "active_mode", None) if mode_mgr else None

            if not active or active.get("type") != "button_frenzy":
                await asyncio.sleep(10)
                continue

            # Wait between spawns (configurable via Config)
            await asyncio.sleep(random.randint(Config.CHAOS_BUTTON_MIN_INTERVAL, Config.CHAOS_BUTTON_MAX_INTERVAL))

            channel = self.bot.get_channel(self.bot.config.GENERAL_CHANNEL_ID)
            if not channel:
                continue

            msg = await channel.send("🔘 A mysterious button appeared... Press it.")
            await msg.add_reaction("🔘")
            self.chaos_buttons[msg.id] = {"active": True}
            logger.info("Spawned chaos button: %s", msg.id)

    # ── Handle a Button Press ───────────────────────────────

    async def handle_chaos_button(self, payload):
        """Called by on_raw_reaction_add when a chaos button is pressed."""
        msg_id = payload.message_id
        if msg_id not in self.chaos_buttons or not self.chaos_buttons[msg_id]["active"]:
            return

        # Disable immediately so only the first press counts
        self.chaos_buttons[msg_id]["active"] = False

        channel = self.bot.get_channel(payload.channel_id)

        # Pick and configure a random effect
        effect = random.choice(self.effect_pool)
        if effect["type"] == "no_letter":
            effect = effect.copy()
            effect["letter"] = random.choice("abcdefghijklmnopqrstuvwxyz")

        self.active_effect  = effect
        self.effect_end_time = time.time() + effect["duration"]
        self.enforcement.set_effect(effect)
        self._persist_effect()

        await channel.send(self._format_effect_message(effect))

        # Award frenzy points to the clicker
        user_id = payload.user_id
        mode = self.bot.mode_manager.active_mode
        if mode and mode["type"] == "button_frenzy":
            mode["clicks"][user_id] = mode["clicks"].get(user_id, 0) + 1
            self.bot.points_manager.add_points(user_id, "button_frenzy_click")
            self.bot.points_manager.update_challenge_progress(user_id, "event", "button_clicks")

        logger.info("Activated effect: %s", effect)

    # ── Background Loop: Expire Effects ─────────────────────

    async def effect_expiry_loop(self):
        """Clear the active effect once its duration has elapsed."""
        await self.bot.wait_until_ready()

        while True:
            await asyncio.sleep(30)
            if self.active_effect and self.effect_end_time and time.time() >= self.effect_end_time:
                self.active_effect = None
                self.effect_end_time = None
                self.enforcement.set_effect(None)
                self._persist_effect()
                logger.info("Active effect expired.")

    # ── State Persistence ────────────────────────────────────

    def _persist_effect(self):
        """Write the current effect state to disk so it survives restarts."""
        state = (
            {"effect": self.active_effect, "end_time": self.effect_end_time}
            if self.active_effect
            else {}
        )
        try:
            _STATE_FILE.write_text(json.dumps(state))
        except OSError as exc:
            logger.warning("Could not save effect state: %s", exc)

    def restore_effect_state(self):
        """Load and re-apply a previously active effect on startup."""
        if not _STATE_FILE.exists():
            return
        try:
            state = json.loads(_STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load effect state: %s", exc)
            return

        if not state:
            return

        end_time = state.get("end_time", 0)
        if time.time() >= end_time:
            # Effect already expired while the bot was offline — clear file
            _STATE_FILE.write_text("{}")
            logger.info("Saved effect had already expired; cleared.")
            return

        effect = state["effect"]
        self.active_effect   = effect
        self.effect_end_time = end_time
        self.enforcement.set_effect(effect)
        remaining = int(end_time - time.time())
        logger.info("Restored active effect: %s (%ds remaining)", effect["type"], remaining)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _format_effect_message(effect: dict) -> str:
        """Build the announcement text for a newly activated effect."""
        t = effect["type"]
        mins = effect["duration"] // 60

        if t == "must_include":
            return f"⚡ Effect: All messages must include **'{effect['word']}'** for {mins} minutes!"
        if t == "max_words":
            return f"⚡ Effect: Max **{effect['limit']} words** per message for {mins} minutes!"
        if t == "no_letter":
            return f"⚡ Effect: The letter **'{effect['letter']}'** is banned for {mins} minutes!"
        if t == "no_link":
            return f"⚡ Effect: **No links** allowed for {mins} minutes!"
        return f"⚡ Unknown effect activated for {mins} minutes!"
