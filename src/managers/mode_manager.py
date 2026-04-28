# ============================================================
# src/managers/mode_manager.py — Weekly Game Modes
# ============================================================
# Each week a random mode is chosen (or forced by an admin).
# This manager starts modes, locks/unlocks channels, runs the
# mystery-clue loop, and ends Button Frenzy with a winner.
# ============================================================

import asyncio
import json
import logging
import pathlib
import random
import time

import discord

from config import Config

logger = logging.getLogger(__name__)

_MODE_STATE_FILE = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "mode_state.json"


class ModeManager:
    """Orchestrates weekly game modes and their channel states."""

    # ── All available modes ──────────────────────────────────
    MODE_TYPES = [
        "invite_comp", "debate", "movie_night",
        "profile_comp", "button_frenzy", "mystery",
    ]

    # ── Mystery pool ─────────────────────────────────────────
    # Each entry has an "answer" (exact single word) and 3 clues.
    # Clues are intentionally abstract — no obvious hints.
    # Clue 1 is sent immediately; clue 2 after 8 h; clue 3 after 16 h.
    # Answer is revealed at 24 h if still unsolved.
    MYSTERIES = [
        {
            "answer": "horizon",
            "clues": [
                "The closer you come to me, the further I retreat.",
                "I exist in every direction at once, yet I occupy no single point.",
                "Sailors have chased me for centuries. No one has ever arrived.",
            ],
        },
        {
            "answer": "question",
            "clues": [
                "Answer me completely and I produce more of myself.",
                "I am born the moment you realise you do not know something.",
                "I am the seed of all knowledge, yet I contain none.",
            ],
        },
        {
            "answer": "gravity",
            "clues": [
                "I have no colour, no taste, no smell — yet nothing in the universe ignores me.",
                "I bend light itself and collapse dying stars.",
                "Without me, you would float off this earth and the moon would vanish into space.",
            ],
        },
        {
            "answer": "memory",
            "clues": [
                "I can resurrect the dead and return you to places that no longer exist.",
                "I am not always accurate — yet you trust me more than any witness.",
                "The harder you try to hold me, the more I change.",
            ],
        },
        {
            "answer": "secret",
            "clues": [
                "Share me once and I shrink. Share me twice and I vanish entirely.",
                "I can bind people together or destroy them — without a single action.",
                "Everyone carries me. No one admits it.",
            ],
        },
        {
            "answer": "language",
            "clues": [
                "I can make a stranger feel at home and a brother feel like an enemy.",
                "I have no shape, yet I build empires and start wars.",
                "I was born before writing, yet I carry all human knowledge.",
            ],
        },
        {
            "answer": "darkness",
            "clues": [
                "I am not a thing — yet I fill every space that light abandons.",
                "Remove me and nothing in the room changes, only how you see it.",
                "I existed before the first fire was ever lit.",
            ],
        },
        {
            "answer": "future",
            "clues": [
                "Everyone travels toward me at the same speed, yet no one has ever arrived.",
                "I am made of nothing, yet every action in history is taken in my name.",
                "The moment you believe you have reached me, I become something else.",
            ],
        },
        {
            "answer": "trust",
            "clues": [
                "I take years to build and a single moment to destroy.",
                "You cannot see me — but you feel my absence instantly.",
                "Without me, no team, no friendship, no civilisation can stand.",
            ],
        },
        {
            "answer": "idea",
            "clues": [
                "I weigh nothing, yet I have started revolutions and ended dynasties.",
                "I travel from mind to mind without a body or a vehicle.",
                "Once I exist, I am impossible to fully destroy — even if the one who had me dies.",
            ],
        },
        {
            "answer": "reflection",
            "clues": [
                "I appear wherever water is perfectly still, yet I do not live in the water.",
                "I copy you with perfect accuracy but reverse everything you are.",
                "Shatter my surface and I multiply — but I never truly disappear.",
            ],
        },
    ]

    # ── Debate topics ────────────────────────────────────────
    DEBATE_TOPICS = [
        "Is school useful?",
        "Cats vs dogs — which is the better pet?",
        "Is AI dangerous for society?",
        "What is the world's best cuisine?",
        "TV shows vs movies — which is better?",
        "Is social media doing more harm than good?",
        "Is it better to be early or fashionably late?",
        "Morning person vs night owl — which is better?",
        "Should homework be abolished?",
        "Is fame worth the loss of privacy?",
    ]

    def __init__(self, bot, twist_manager):
        self.bot = bot
        self.twist_manager = twist_manager
        self.active_mode = None

        # Task for the current day's clue reveal loop
        self._mystery_task = None
        # Task for the overall 7-day week loop
        self._mystery_week_task = None

        # Per-user timestamp of last wrong guess (rate-limit spam)
        self._wrong_guess_time = {}

    # ── Start a Weekly Mode ─────────────────────────────────

    async def start_weekly_mode(self, forced_mode: str = None) -> bool:
        """
        Activate a new weekly mode (random or forced).
        Returns False if a mode is already running.
        """
        if self.active_mode is not None:
            logger.warning("start_weekly_mode called while a mode is already active.")
            return False

        # Lock every mode channel before deciding which one to open
        await self._update_channel_states(None)

        mode_type = forced_mode or random.choice(self.MODE_TYPES)
        announce  = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
        logger.info("Starting weekly mode: %s", mode_type)

        # ── Invite Competition ──────────────────────────────
        if mode_type == "invite_comp":
            self.active_mode = {"type": "invite_comp"}
            self._persist_mode()
            await self._update_channel_states(Config.INVITE_CHANNEL_ID)
            if announce:
                await announce.send(
                    "@everyone\n"
                    "📨 **Weekly Mode: Invite Competition!** "
                    "Invite the most new members this week to win."
                )
            ch = self.bot.get_channel(Config.INVITE_CHANNEL_ID)
            if ch:
                await ch.send("@everyone\n📨 Invite Competition has started! Track your invites here.")

        # ── Debate ──────────────────────────────────────────
        elif mode_type == "debate":
            topic = random.choice(self.DEBATE_TOPICS)
            self.active_mode = {"type": "debate", "topic": topic}
            self._persist_mode()
            await self._update_channel_states(Config.DEBATE_CHANNEL_ID)
            ch = self.bot.get_channel(Config.DEBATE_CHANNEL_ID)
            if ch:
                await ch.send(f"@everyone\n🗣 **Weekly Debate!**\nThis week's topic: **{topic}**")

        # ── Movie / Game Night ──────────────────────────────
        elif mode_type == "movie_night":
            self.active_mode = {"type": "movie_night"}
            self._persist_mode()
            await self._update_channel_states(Config.MOVIE_CHANNEL_ID)
            ch = self.bot.get_channel(Config.MOVIE_CHANNEL_ID)
            if ch:
                await ch.send("@everyone\n🎬 **Weekly Mode: Movie/Game Night!** Stay tuned for details.")

        # ── Profile Competition ─────────────────────────────
        elif mode_type == "profile_comp":
            category = random.choice(["pfp", "bio", "banner"])
            self.active_mode = {"type": "profile_comp", "category": category}
            self._persist_mode()
            await self._update_channel_states(Config.PROFILE_COMP_CHANNEL_ID)
            ch = self.bot.get_channel(Config.PROFILE_COMP_CHANNEL_ID)
            if ch:
                await ch.send(f"@everyone\n🏆 **Weekly Mode: Profile Competition!**\nBest **{category.upper()}** wins this week!")

        # ── Button Frenzy ───────────────────────────────────
        elif mode_type == "button_frenzy":
            self.active_mode = {"type": "button_frenzy", "clicks": {}}
            self._persist_mode()
            await self._update_channel_states(None)
            if announce:
                await announce.send(
                    "@everyone\n"
                    "🔥 **Weekly Mode: Button Frenzy!**\n"
                    "Press the chaos buttons as much as possible throughout the week!\n"
                    f"Chaos buttons will spawn every "
                    f"{Config.CHAOS_BUTTON_MIN_INTERVAL // 3600}–"
                    f"{Config.CHAOS_BUTTON_MAX_INTERVAL // 3600} hours."
                )

        # ── Mystery Solving ─────────────────────────────────
        elif mode_type == "mystery":
            await self._start_mystery(announce)

        return True

    # ── Mystery: start ───────────────────────────────────────

    async def _start_mystery(self, announce):
        """
        Select 7 distinct mysteries for the week, send the @everyone
        announcement, and kick off the 7-day week loop.
        """
        pool = self.MYSTERIES.copy()
        random.shuffle(pool)
        # If we ever have fewer than 7 mysteries, wrap around
        selected = (pool * 2)[:7]

        # `solved` starts as True so _mystery_active() returns False
        # until the week loop sets the first daily mystery.
        self.active_mode = {
            "type":            "mystery",
            "mysteries":       selected,
            "current_day":     -1,
            "current_mystery": None,
            "solved":          True,
            "started":         time.time(),
            "day_started":     time.time(),
        }
        self._wrong_guess_time = {}
        self._persist_mode()

        await self._update_channel_states(Config.MYSTERY_CHANNEL_ID)

        mystery_ch = self.bot.get_channel(Config.MYSTERY_CHANNEL_ID)

        if announce:
            await announce.send(
                "@everyone\n"
                "🕵️ **This week's event: Mystery Solving!**\n"
                "Every day a brand-new riddle will appear in the mystery channel.\n"
                "**7 riddles over 7 days** — can you crack them all?"
            )

        self._mystery_week_task = self.bot.loop.create_task(
            self._mystery_week_loop(announce, mystery_ch)
        )

    # ── Mystery: 7-day week loop ─────────────────────────────

    async def _mystery_week_loop(self, announce, mystery_ch, *, resume_day: int = 0, first_day_remaining: float | None = None):
        """
        Run one mystery per day for 7 days.
        Each day: post clue 1, start the clue loop, wait 24 h, then advance.
        resume_day / first_day_remaining are used when resuming after a restart.
        """
        try:
            mysteries = self.active_mode["mysteries"]

            for day_index, mystery in enumerate(mysteries):
                # Skip days already completed before this restart
                if day_index < resume_day:
                    continue

                if not self.active_mode or self.active_mode.get("type") != "mystery":
                    return

                is_resumed_day = (day_index == resume_day and first_day_remaining is not None)

                if not is_resumed_day:
                    # Normal day start — record timestamp and post clue 1
                    self.active_mode["current_day"]     = day_index
                    self.active_mode["current_mystery"] = mystery
                    self.active_mode["solved"]          = False
                    self.active_mode["day_started"]     = time.time()
                    self._wrong_guess_time              = {}
                    self._persist_mode()

                    interval_hrs = Config.MYSTERY_CLUE_INTERVAL_SECONDS // 3600
                    total_clues  = len(mystery["clues"])

                    if mystery_ch:
                        await mystery_ch.send(
                            f"@everyone\n"
                            f"🕵️ **Day {day_index + 1}/7 — New Riddle!**\n"
                            f"Post your one-word answer in this channel.\n"
                            f"**Clue 1/{total_clues}:** {mystery['clues'][0]}\n"
                            f"*(Next clue in {interval_hrs}h — the answer will be revealed after {interval_hrs * total_clues}h if unsolved)*"
                        )

                    self._mystery_task = self.bot.loop.create_task(
                        self._mystery_clue_loop(mystery_ch, mystery)
                    )
                    day_sleep = Config.MYSTERY_DAY_DURATION_SECONDS
                else:
                    # Resumed day — skip clue 1 (already sent), resume from correct clue
                    self._mystery_task = self.bot.loop.create_task(
                        self._mystery_clue_loop_resume(mystery_ch, mystery, first_day_remaining)
                    )
                    day_sleep = first_day_remaining

                # Wait the allotted time, then advance regardless of solve status
                await asyncio.sleep(day_sleep)

                # Cancel the clue loop if it hasn't ended naturally
                if self._mystery_task and not self._mystery_task.done():
                    self._mystery_task.cancel()
                    try:
                        await self._mystery_task
                    except asyncio.CancelledError:
                        pass
                self._mystery_task = None

            # All 7 days complete
            if mystery_ch:
                await mystery_ch.send(
                    "🏆 **Mystery Week is over!**\n"
                    "All 7 riddles have been played. Great effort from everyone who guessed!"
                )
            if announce:
                await announce.send(
                    "@everyone ⏰ **Mystery Week has ended!** See you next week."
                )

            await self._update_channel_states(None)
            self.active_mode        = None
            self._persist_mode()
            self._mystery_week_task = None
            logger.info("Mystery week completed naturally.")

        except asyncio.CancelledError:
            logger.debug("Mystery week loop cancelled.")

    # ── Mystery: daily clue loop ─────────────────────────────

    async def _mystery_clue_loop(self, channel, mystery):
        """
        Reveal the remaining clues for one daily mystery, then expire if
        nobody solves it.  Takes the mystery dict as a parameter so it
        stays correct even as active_mode is updated by the week loop.

        Timing (all configurable via Config):
          Clue 1 sent at 0 h (by _mystery_week_loop)
          Clue 2 sent at 8 h
          Clue 3 sent at 16 h  +  "8 h remaining" warning
          Auto-reveal at 24 h
        """
        try:
            clues  = mystery["clues"]
            answer = mystery["answer"]
            total  = len(clues)

            for i in range(1, total):
                await asyncio.sleep(Config.MYSTERY_CLUE_INTERVAL_SECONDS)

                if not self._mystery_active():
                    return

                is_last = (i == total - 1)
                label   = f"Final Clue ({i + 1}/{total})" if is_last else f"Clue {i + 1}/{total}"
                if channel:
                    await channel.send(f"🔍 **{label}:** {clues[i]}")

                if is_last and channel:
                    final_hrs = Config.MYSTERY_FINAL_GUESS_SECONDS // 3600
                    await channel.send(
                        f"⚠️ That was the last clue! You have **{final_hrs} hours** to answer."
                    )

            # Final guess window
            await asyncio.sleep(Config.MYSTERY_FINAL_GUESS_SECONDS)

            if self._mystery_active() and channel:
                await channel.send(
                    f"❌ Nobody solved today's mystery.\n"
                    f"The answer was **{answer}**."
                )
            if self._mystery_active():
                self.active_mode["solved"] = True
                self._persist_mode()
            self._mystery_task = None
            logger.info("Mystery day timed out. Answer was: %s", answer)

        except asyncio.CancelledError:
            logger.debug("Mystery clue loop cancelled.")

    # ── Mystery: clue loop resume (after restart) ───────────────

    async def _mystery_clue_loop_resume(self, channel, mystery, remaining_in_day: float):
        """
        Resume revealing clues mid-day after a restart.
        Skips clues already sent and waits only the time still owed.
        """
        try:
            clues    = mystery["clues"]
            answer   = mystery["answer"]
            total    = len(clues)
            interval = Config.MYSTERY_CLUE_INTERVAL_SECONDS

            elapsed_in_day = Config.MYSTERY_DAY_DURATION_SECONDS - remaining_in_day

            # Index of the next clue to send (clue 0 was already posted at day start)
            next_idx = int(elapsed_in_day / interval) + 1

            if next_idx >= total:
                # All clues already sent; we're in the final guess window
                await asyncio.sleep(remaining_in_day)
                if self._mystery_active() and channel:
                    await channel.send(
                        f"❌ Nobody solved today's mystery.\n"
                        f"The answer was **{answer}**."
                    )
                if self._mystery_active():
                    self.active_mode["solved"] = True
                    self._persist_mode()
                self._mystery_task = None
                logger.info("Resumed mystery day timed out. Answer was: %s", answer)
                return

            # Wait until the next clue's scheduled slot
            wait = next_idx * interval - elapsed_in_day
            if wait > 0:
                await asyncio.sleep(wait)

            # Send remaining clues from next_idx onward
            for i in range(next_idx, total):
                if i > next_idx:
                    await asyncio.sleep(interval)

                if not self._mystery_active():
                    return

                is_last = (i == total - 1)
                label   = f"Final Clue ({i + 1}/{total})" if is_last else f"Clue {i + 1}/{total}"
                if channel:
                    await channel.send(f"🔍 **{label}:** {clues[i]}")

                if is_last and channel:
                    final_hrs = Config.MYSTERY_FINAL_GUESS_SECONDS // 3600
                    await channel.send(
                        f"⚠️ That was the last clue! You have **{final_hrs} hours** to answer."
                    )

            # Final guess window
            await asyncio.sleep(Config.MYSTERY_FINAL_GUESS_SECONDS)

            if self._mystery_active() and channel:
                await channel.send(
                    f"❌ Nobody solved today's mystery.\n"
                    f"The answer was **{answer}**."
                )
            if self._mystery_active():
                self.active_mode["solved"] = True
                self._persist_mode()
            self._mystery_task = None
            logger.info("Resumed mystery day timed out. Answer was: %s", answer)

        except asyncio.CancelledError:
            logger.debug("Resumed mystery clue loop cancelled.")

    def _mystery_active(self) -> bool:
        return (
            self.active_mode is not None
            and self.active_mode.get("type") == "mystery"
            and not self.active_mode.get("solved")
        )

    # ── Mystery: guess handler ───────────────────────────────

    async def handle_message(self, message):
        """Check if a message posted in the mystery channel is the correct answer."""
        if not self._mystery_active():
            return

        # Only accept guesses posted in the dedicated mystery channel
        if message.channel.id != Config.MYSTERY_CHANNEL_ID:
            return

        uid     = message.author.id
        content = message.content.lower().strip()
        current = self.active_mode.get("current_mystery") or {}
        answer  = current.get("answer", "").lower()

        if not answer:
            return

        # Per-user wrong-guess cooldown — silently delete rate-limited guesses
        now  = time.time()
        last = self._wrong_guess_time.get(uid, 0)
        if now - last < Config.MYSTERY_GUESS_COOLDOWN_SECONDS:
            try:
                await message.delete()
            except Exception:
                pass
            return

        if content == answer:
            # Mark solved so the clue loop exits cleanly on cancel
            self.active_mode["solved"] = True
            self._persist_mode()

            if self._mystery_task and not self._mystery_task.done():
                self._mystery_task.cancel()
            self._mystery_task = None

            self.bot.points_manager.add_points(uid, "mystery")
            self.bot.points_manager.add_win(uid)

            day   = self.active_mode.get("current_day", 0) + 1
            total = len(self.active_mode.get("mysteries", []))
            await message.channel.send(
                f"🎉 {message.author.mention} solved **Day {day}/{total}**! "
                f"The answer was **{answer}**!"
            )
            logger.info("Mystery day %s solved by user %s. Answer: %s", day, uid, answer)
            return

        # Wrong guess — record time to rate-limit future attempts
        self._wrong_guess_time[uid] = now

    # ── State Persistence ────────────────────────────────────

    def _persist_mode(self):
        """Write current active_mode to disk so it survives restarts."""
        mode = self.active_mode
        if mode and mode.get("type") == "button_frenzy":
            # JSON requires string keys; user IDs are ints
            mode = dict(mode)
            mode["clicks"] = {str(k): v for k, v in mode["clicks"].items()}
        try:
            _MODE_STATE_FILE.write_text(json.dumps({"active_mode": mode}))
        except OSError as exc:
            logger.warning("Could not save mode state: %s", exc)

    async def restore_mode_state(self):
        """Load and re-apply mode state on startup. Called from on_ready."""
        if not _MODE_STATE_FILE.exists():
            return
        try:
            saved = json.loads(_MODE_STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load mode state: %s", exc)
            return

        mode = saved.get("active_mode")
        if not mode:
            return

        if mode.get("type") == "button_frenzy":
            mode["clicks"] = {int(k): v for k, v in mode.get("clicks", {}).items()}

        self.active_mode = mode

        if mode.get("type") != "mystery":
            logger.info("Restored weekly mode: %s", mode.get("type"))
            return

        # ── Mystery mode: figure out where we are in the week ──
        mysteries   = mode.get("mysteries", [])
        current_day = mode.get("current_day", 0)
        day_started = mode.get("day_started", time.time())

        elapsed_in_week = time.time() - day_started
        days_elapsed    = int(elapsed_in_week / Config.MYSTERY_DAY_DURATION_SECONDS)
        new_day         = current_day + days_elapsed

        if new_day >= len(mysteries):
            logger.info("Mystery week ended while offline; clearing mode.")
            self.active_mode = None
            self._persist_mode()
            await self._update_channel_states(None)
            return

        # Advance to the correct day
        self.active_mode["current_day"]     = new_day
        self.active_mode["current_mystery"] = mysteries[new_day]
        self.active_mode["solved"]          = False
        self.active_mode["day_started"]     = day_started + days_elapsed * Config.MYSTERY_DAY_DURATION_SECONDS
        self._persist_mode()

        time_into_day    = elapsed_in_week - days_elapsed * Config.MYSTERY_DAY_DURATION_SECONDS
        remaining_in_day = Config.MYSTERY_DAY_DURATION_SECONDS - time_into_day

        mystery_ch = self.bot.get_channel(Config.MYSTERY_CHANNEL_ID)
        announce   = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)

        self._mystery_week_task = self.bot.loop.create_task(
            self._mystery_week_loop(
                announce, mystery_ch,
                resume_day=new_day,
                first_day_remaining=remaining_in_day,
            )
        )
        logger.info(
            "Resumed mystery mode at day %d/%d (~%ds remaining today)",
            new_day + 1, len(mysteries), int(remaining_in_day),
        )

    # ── Cancel all mystery tasks ─────────────────────────────

    def cancel_mystery_tasks(self):
        """Cancel all mystery background tasks (used when forcibly ending mystery mode)."""
        if self._mystery_task and not self._mystery_task.done():
            self._mystery_task.cancel()
        self._mystery_task = None
        if self._mystery_week_task and not self._mystery_week_task.done():
            self._mystery_week_task.cancel()
        self._mystery_week_task = None

    # ── Channel Lock / Unlock ────────────────────────────────

    async def _update_channel_states(self, active_channel_id: int | None):
        """
        Prefix inactive mode-channels with 'not-active-' and
        set @everyone permissions to hide/show the appropriate channel.
        """
        mode_channels = [
            Config.DEBATE_CHANNEL_ID,
            Config.INVITE_CHANNEL_ID,
            Config.MOVIE_CHANNEL_ID,
            Config.PROFILE_COMP_CHANNEL_ID,
            Config.MYSTERY_CHANNEL_ID,
        ]
        for cid in mode_channels:
            try:
                ch = self.bot.get_channel(cid)
                if not ch:
                    continue
                base = ch.name.replace("not-active-", "", 1) if ch.name.startswith("not-active-") else ch.name
                everyone = ch.guild.default_role

                if cid == active_channel_id:
                    if ch.name.startswith("not-active-"):
                        await ch.edit(name=base)
                    await ch.set_permissions(
                        everyone,
                        view_channel=True,
                        send_messages=True,
                    )
                else:
                    if not ch.name.startswith("not-active-"):
                        await ch.edit(name=f"not-active-{base}")
                    await ch.set_permissions(
                        everyone,
                        view_channel=False,
                        send_messages=False,
                    )
            except Exception as e:
                logger.warning("Failed to update channel %s: %s", cid, e)

    # ── End Button Frenzy ────────────────────────────────────

    async def end_button_frenzy(self, channel):
        """Announce the Button Frenzy winner and award points."""
        if not self.active_mode or self.active_mode["type"] != "button_frenzy":
            return

        clicks = self.active_mode["clicks"]
        if not clicks:
            await channel.send("❌ Button Frenzy ended! Nobody clicked anything.")
            self.active_mode = None
            self._persist_mode()
            return

        max_clicks = max(clicks.values())
        winners    = [uid for uid, c in clicks.items() if c == max_clicks]

        msg = "@everyone\n🏆 **Button Frenzy ended!**\n"
        for winner_id in winners:
            self.bot.points_manager.add_points(winner_id, "button_frenzy")
            self.bot.points_manager.add_win(winner_id)
            try:
                user = await self.bot.fetch_user(winner_id)
                name = user.mention
            except (discord.NotFound, discord.HTTPException):
                name = f"Unknown ({winner_id})"
            msg += f"👑 {name} — {max_clicks} clicks\n"

        await channel.send(msg)
        self.active_mode = None
        self._persist_mode()
        logger.info("Button Frenzy ended. Winners: %s", winners)

    async def end_weekly_mode(self, channel):
        """End the current weekly mode early and reset channel state."""
        if not self.active_mode:
            return

        mode_type = self.active_mode.get("type")
        if mode_type == "button_frenzy":
            await self.end_button_frenzy(channel)
            return

        if mode_type == "mystery":
            self.cancel_mystery_tasks()
            if channel:
                await channel.send(
                    "@everyone\n⏹️ **Mystery Week ended early!**\n"
                    "The current mystery event has been cancelled."
                )
        else:
            if channel:
                await channel.send(
                    f"@everyone\n⏹️ **Weekly Mode ended early!**\n"
                    f"The current mode ({mode_type.replace('_', ' ').title()}) has been cancelled."
                )

        await self._update_channel_states(None)
        self.active_mode = None
        self._persist_mode()
        logger.info("Weekly mode ended early: %s", mode_type)
