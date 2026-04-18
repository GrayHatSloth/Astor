# ============================================================
# src/managers/mode_manager.py — Weekly Game Modes
# ============================================================
# Each week a random mode is chosen (or forced by an admin).
# This manager starts modes, locks/unlocks channels, runs the
# mystery-clue loop, and ends Button Frenzy with a winner.
# ============================================================

import random
import asyncio
import time

import discord

from config import Config


class ModeManager:
    """Orchestrates weekly game modes and their channel states."""

    # All six available modes
    MODE_TYPES = [
        "invite_comp", "debate", "movie_night",
        "profile_comp", "button_frenzy", "mystery",
    ]

    def __init__(self, bot, twist_manager):
        self.bot = bot
        self.twist_manager = twist_manager
        self.active_mode = None

        # Anti-spam for mystery guesses
        self.last_guess_time = {}

    # ── Start a Weekly Mode ─────────────────────────────────

    async def start_weekly_mode(self, forced_mode: str = None) -> bool:
        """
        Activate a new weekly mode (random or forced).
        Returns False if a mode is already running.
        """
        if self.active_mode is not None:
            print("[MODE] start_weekly_mode called while one is already active.")
            return False

        # Lock every mode channel, then unlock the relevant one
        await self._update_channel_states(None)

        mode_type = forced_mode or random.choice(self.MODE_TYPES)
        announce  = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)

        # ── Invite Competition ──────────────────────────────
        if mode_type == "invite_comp":
            self.active_mode = {"type": "invite_comp"}
            await self._update_channel_states(Config.INVITE_CHANNEL_ID)
            await announce.send("📨 Weekly Mode: Invite Competition! Invite the most users to win.")
            ch = self.bot.get_channel(Config.INVITE_CHANNEL_ID)
            if ch:
                await ch.send("📨 Invite Competition has started! Track your invites!")

        # ── Debate ──────────────────────────────────────────
        elif mode_type == "debate":
            topic = random.choice([
                "Is school useful?", "Cats vs dogs", "Is AI dangerous?",
                "What is the best cuisine?", "TV shows vs movies",
                "Is social media harmful?", "Is it better to be early or late?",
                "Is it better to be a morning person or a night owl?",
            ])
            self.active_mode = {"type": "debate", "topic": topic}
            await self._update_channel_states(Config.DEBATE_CHANNEL_ID)
            ch = self.bot.get_channel(Config.DEBATE_CHANNEL_ID)
            if ch:
                await ch.send(f"🗣 Weekly Debate!\nTopic: **{topic}**")

        # ── Movie / Game Night ──────────────────────────────
        elif mode_type == "movie_night":
            self.active_mode = {"type": "movie_night"}
            await self._update_channel_states(Config.MOVIE_CHANNEL_ID)
            ch = self.bot.get_channel(Config.MOVIE_CHANNEL_ID)
            if ch:
                await ch.send("🎬 Weekly Mode: Movie/Game Night! Stay tuned.")

        # ── Profile Competition ─────────────────────────────
        elif mode_type == "profile_comp":
            category = random.choice(["pfp", "bio", "banner"])
            self.active_mode = {"type": "profile_comp", "category": category}
            await self._update_channel_states(Config.PROFILE_COMP_CHANNEL_ID)
            ch = self.bot.get_channel(Config.PROFILE_COMP_CHANNEL_ID)
            if ch:
                await ch.send(f"🏆 Weekly Mode: Profile Competition!\nBest **{category.upper()}** wins!")

        # ── Button Frenzy ───────────────────────────────────
        elif mode_type == "button_frenzy":
            self.active_mode = {"type": "button_frenzy", "clicks": {}}
            await self._update_channel_states(None)
            await announce.send(
                "🔥 Weekly Mode: Button Frenzy!\n"
                "Press the chaos buttons as much as possible throughout the week!\n"
                "Chaos buttons will spawn every 3-5 hours."
            )

        # ── Mystery Solving ─────────────────────────────────
        elif mode_type == "mystery":
            mystery = random.choice([
                {"answer": "shadow", "clues": ["I follow you", "I disappear in darkness", "I appear with light"]},
                {"answer": "time",   "clues": ["I never stop", "You can't see me", "I heal everything"]},
                {"answer": "echo",   "clues": ["I repeat you", "I live in caves", "I copy your voice"]},
                {"answer": "wind",   "clues": ["I can be gentle or strong", "You can feel me but not see me", "I move the trees"]},
                {"answer": "mirror", "clues": ["I reflect you", "I can show your true self", "I copy your image"]},
                {"answer": "book",   "clues": ["I hold knowledge", "I have many pages", "I tell stories"]},
                {"answer": "dream",  "clues": ["I can be sweet or scary", "I happen when you sleep", "I feel real but I'm not"]},
            ])
            self.active_mode = {
                "type": "mystery",
                "answer": mystery["answer"],
                "clues": mystery["clues"],
                "solved": False,
                "current_clue": 0,
                "last_clue_time": time.time(),
            }
            self.last_guess_time = {}
            await self._update_channel_states(None)
            await announce.send(f"🕵️ Weekly Mode: Mystery Solving!\nClue 1: **{mystery['clues'][0]}**")
            self.bot.loop.create_task(self._reveal_mystery_clues(announce))

        return True

    # ── Channel Lock / Unlock ───────────────────────────────

    async def _update_channel_states(self, active_channel_id: int | None):
        """
        Prefix inactive mode-channels with 'not-active-' and
        remove the prefix from the currently active channel.
        """
        mode_channels = [
            Config.DEBATE_CHANNEL_ID,
            Config.INVITE_CHANNEL_ID,
            Config.MOVIE_CHANNEL_ID,
            Config.PROFILE_COMP_CHANNEL_ID,
        ]
        for cid in mode_channels:
            try:
                ch = self.bot.get_channel(cid)
                if not ch:
                    continue
                base = ch.name.replace("not-active-", "", 1) if ch.name.startswith("not-active-") else ch.name

                if cid == active_channel_id:
                    if ch.name.startswith("not-active-"):
                        await ch.edit(name=base)
                else:
                    if not ch.name.startswith("not-active-"):
                        await ch.edit(name=f"not-active-{base}")
            except Exception as e:
                print(f"[MODE] Failed to update channel {cid}: {e}")

    # ── End Button Frenzy ───────────────────────────────────

    async def end_button_frenzy(self, channel):
        """Announce the Button Frenzy winner and award points."""
        if not self.active_mode or self.active_mode["type"] != "button_frenzy":
            return

        clicks = self.active_mode["clicks"]
        if not clicks:
            await channel.send("❌ Button Frenzy ended! Nobody clicked anything.")
            self.active_mode = None
            return

        max_clicks = max(clicks.values())
        winners = [uid for uid, c in clicks.items() if c == max_clicks]

        msg = "🏆 **Button Frenzy ended!**\n"
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

    # ── Mystery: Clue Revelation Loop ───────────────────────

    async def _reveal_mystery_clues(self, channel):
        """Reveal clues on a timer, then auto-answer if unsolved."""
        await asyncio.sleep(900)  # 15 min until clue 2

        if not self._mystery_active():
            return
        clues = self.active_mode["clues"]
        idx = self.active_mode["current_clue"] + 1

        if idx < len(clues):
            self.active_mode["current_clue"] = idx
            await channel.send(f"🔍 Clue {idx + 1}: **{clues[idx]}**")

            await asyncio.sleep(900)  # 15 min until final clue
            if not self._mystery_active():
                return

            final = self.active_mode["current_clue"] + 1
            if final < len(clues):
                self.active_mode["current_clue"] = final
                await channel.send(f"🔍 Final Clue: **{clues[final]}**")
                await channel.send("⚠️ You have 10 minutes to solve the mystery!")

                await asyncio.sleep(600)
                if self._mystery_active():
                    answer = self.active_mode["answer"]
                    await channel.send(f"❌ Time's up! The answer was **{answer}**.")
                    self.active_mode = None

    def _mystery_active(self) -> bool:
        return (
            self.active_mode is not None
            and self.active_mode.get("type") == "mystery"
            and not self.active_mode.get("solved")
        )

    # ── Mystery: Guess Handler ──────────────────────────────

    async def handle_message(self, message):
        """Check if a message solves the mystery."""
        if not self.active_mode or self.active_mode.get("type") != "mystery":
            return
        if self.active_mode.get("solved"):
            return

        uid     = message.author.id
        answer  = self.active_mode["answer"].lower()
        content = message.content.lower().strip()

        if content == answer:
            self.active_mode["solved"] = True
            self.bot.points_manager.add_points(uid, "mystery")
            self.bot.points_manager.add_win(uid)
            await message.channel.send(
                f"🎉 {message.author.mention} solved the mystery! The answer was **{answer}**!"
            )
            self.active_mode = None
            return

        # Anti-spam: ignore rapid duplicate guesses
        now  = time.time()
        last = self.last_guess_time.get(uid)
        if last and now - last["timestamp"] < 10 and content == last["content"]:
            try:
                await message.delete()
            except Exception:
                pass
            return
        self.last_guess_time[uid] = {"timestamp": now, "content": content}
