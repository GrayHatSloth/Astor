# ============================================================
# src/managers/mode_manager.py - Weekly Game Modes
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
    # Clues are intentionally abstract and cryptic - no easy hints.
    # Clue 1 is sent immediately (hardest); clue 2 after 8 h; clue 3 after 16 h.
    # Answer is revealed at 24 h if still unsolved.
    MYSTERIES = [
        {
            "answer": "echo",
            "clues": [
                "I am born in the space between a sound and the surface that rejected it - a voice that has lost its owner.",
                "Mountains multiply me; open fields erase me. I always arrive after the source, carrying the same message, diminished.",
                "A Greek nymph was condemned to become me - stripped of everything except the last words she heard, forced to repeat them forever.",
            ],
        },
        {
            "answer": "tide",
            "clues": [
                "I am the slow breath of the ocean - an inhale and exhale that no storm creates and no calm can stop.",
                "I am governed by something 384,000 kilometres away. I have been rising and falling since before the first human walked the earth.",
                "Shakespeare wrote of me: 'There is a ____ in the affairs of men, which, taken at the flood, leads on to fortune.' Sailors predict me to the minute.",
            ],
        },
        {
            "answer": "oath",
            "clues": [
                "I weigh nothing and occupy no space - yet entire kingdoms have crumbled the moment I was broken.",
                "Courts demand me. Religions sanctify me. A villain breaks me carelessly; a hero dies rather than betray me.",
                "I am an invisible contract sealed by words alone - the precise line between a casual promise and a bond that outlives the person who made it.",
            ],
        },
        {
            "answer": "fossil",
            "clues": [
                "I am a life that turned to stone - preserved not by care, but by catastrophe, pressure, and the indifference of deep time.",
                "I contain no heartbeat, yet I carry proof of heartbeats that stopped millions of years ago.",
                "Miners find me by accident. Scientists reconstruct entire worlds from my existence. I am the autobiography of the Earth, written in rock.",
            ],
        },
        {
            "answer": "fever",
            "clues": [
                "I am your body turning against itself - and simultaneously your body fighting for itself. Both statements are true at once.",
                "For centuries I was thought to be the disease itself. Modern medicine discovered I am the war, not the enemy.",
                "Gold Rush prospectors named their obsession after me. Doctors have measured me with glass tubes and mercury for four hundred years.",
            ],
        },
        {
            "answer": "compass",
            "clues": [
                "I have no engine, no eyes, no voice - yet I have guided more explorers into the unknown than any star in the sky.",
                "I speak only one language: direction. I have exactly four possible answers, and in the entire history of navigation I have never given a wrong one.",
                "I do not point to the geographic top of the world. I am drawn instead to a restless magnetic anomaly - a wandering wound in the Earth's own field.",
            ],
        },
        {
            "answer": "debt",
            "clues": [
                "I grow while you sleep. I travel without legs. Entire civilisations have collapsed beneath my silent, accumulating weight.",
                "I am a relationship between two parties - but only one of them is glad I exist.",
                "I was invented the moment humanity invented money - and in five thousand years of recorded history, no empire has ever permanently abolished me.",
            ],
        },
        {
            "answer": "shadow",
            "clues": [
                "I am always beside you in the light - yet it is the light itself that prevents me from ever truly touching you.",
                "I have no substance, no mass, no temperature. Ancient civilisations feared me; children still do. I am the precise shape of an absence.",
                "Carl Jung made me a metaphor for the hidden self - the part of a person they refuse to acknowledge. In reality I am simply what you block.",
            ],
        },
        {
            "answer": "silence",
            "clues": [
                "I am the only thing that becomes louder the instant you become aware of me.",
                "I can be a gift, a weapon, a punishment, or a prayer - without producing a single vibration.",
                "In 1952, John Cage composed four minutes and thirty-three seconds of me and called it music. The audience heard something they had never consciously heard before: themselves.",
            ],
        },
        {
            "answer": "border",
            "clues": [
                "I am drawn on paper, painted onto maps, and enforced with weapons - yet I do not exist anywhere in the natural world.",
                "Animals cross me daily without the slightest knowledge of my existence. I only have meaning for the one species that invented me.",
                "I divide the same river, the same mountain range, the same sky - on the basis of decisions made by people who have been dead for centuries.",
            ],
        },
        {
            "answer": "anchor",
            "clues": [
                "My entire purpose is to stop movement - yet I am completely useless until I am first dropped into the unknown below.",
                "I weigh tonnes, yet I hold something thousands of times heavier in place. I succeed by getting stuck - deliberately.",
                "As a tattoo I meant homecoming. As a religious symbol I meant stability of the soul. As a naval tool I had one meaning only: do not drift.",
            ],
        },
        {
            "answer": "ink",
            "clues": [
                "I was born in darkness - squeezed from cuttlefish, pressed from berries, distilled from char - yet I carry every word ever written by human hands.",
                "I am the layer between a thought and its permanence. Without me, every manuscript, every treaty, every love letter would be blank paper.",
                "When Gutenberg put me into a press, knowledge could finally leave the room where it was created - and no king, no priest, no wall could stop it.",
            ],
        },
        {
            "answer": "salt",
            "clues": [
                "I am the only rock that humans eat - and I am present in every tear, every drop of blood, and every ocean on this planet.",
                "I preserve the dead, flavour the living, and make the sea undrinkable. Remove me entirely from a human body and it will fail within days.",
                "Roman soldiers were given an allowance of me as part of their wages. The Latin word for that allowance became the English word for what you earn at work.",
            ],
        },
        {
            "answer": "alphabet",
            "clues": [
                "I was invented only once in all of human history - and then copied. Every writing system used by a living language today descends from a single ancient source.",
                "I am not language. I am not words. I am the technology that makes it possible to store language outside a human mind.",
                "My English name comes from the first two letters of the Greek adaptation of the Phoenician system - the one that Greek traders learned and eventually passed to Rome.",
            ],
        },
        {
            "answer": "prism",
            "clues": [
                "I do not create what you see when you look through me - I reveal that it was already there, hidden inside something you assumed was pure and simple.",
                "White light enters me as one thing and leaves as seven. I divide without destroying anything.",
                "Newton used me to prove that sunlight was not a single simple substance. Pink Floyd put me on an album cover as a symbol of hidden complexity.",
            ],
        },
        {
            "answer": "plague",
            "clues": [
                "I have ended more human lives than every war in recorded history combined - moving silently, without malice, without strategy, without an army.",
                "I travelled along trade routes, carried by animals, breathed through crowded cities. No wall, no army, no border has ever stopped me.",
                "In the 14th century I killed between a third and a half of Europe's population and reshaped civilisation as profoundly as any military conquest - I am the catastrophe that wears no face.",
            ],
        },
        {
            "answer": "clock",
            "clues": [
                "I did not exist for the first ninety-nine percent of human history - yet humans have always been governed by what I measure.",
                "I divide a continuous, unbroken flow into identical fragments and assign each a number. This single invention may have reshaped human behaviour more than any other.",
                "Before me, every city in the world kept its own local time. Railways made that impossible - and in forcing all of them to agree on mine, I created the modern world.",
            ],
        },
        {
            "answer": "cipher",
            "clues": [
                "I am a language built inside another language - a shell around a message, engineered so that only one person in the world can remove it.",
                "Armies have used me since ancient Rome. A famous version of me was solved by mathematicians working in secret, and that breakthrough changed the course of a major conflict.",
                "My name means zero in Arabic - the same root that gave mathematics the concept of nothing. I am both the method of concealment and the concealed message itself.",
            ],
        },
        {
            "answer": "labyrinth",
            "clues": [
                "I was not built to keep something out - I was built to keep something in. I am the cage designed to confuse rather than confine.",
                "Every path inside me leads somewhere, but only one leads out. I am the deliberate architecture of disorientation.",
                "Daedalus built me beneath a Cretan palace to imprison a creature half man and half bull. Only a hero who unspooled a thread behind him found the way back.",
            ],
        },
        {
            "answer": "paradox",
            "clues": [
                "I am a statement that destroys itself - or a situation that is perfectly logical and completely impossible at the exact same time.",
                "A man declares: 'This statement is false.' If he is right, he is wrong. If he is wrong, he is right. I am born and sustained in that loop.",
                "Philosophers have battled me for millennia without resolution. Physicists found me alive in quantum mechanics. I am the crack in the wall of reason through which the universe leaks.",
            ],
        },
        {
            "answer": "entropy",
            "clues": [
                "I am the universe's only non-negotiable direction of travel - the irreversible drift from order toward chaos that nothing can permanently reverse.",
                "I am why your coffee cools, why buildings crumble if untended, why no memory stays perfectly sharp. I am the second law of thermodynamics made visible in everyday life.",
                "The only way to fight me locally - to organise, to clean, to build - is to generate more of me somewhere else. Every act of order costs the universe something.",
            ],
        },
        {
            "answer": "covenant",
            "clues": [
                "I am an agreement older than any legal contract - sealed not with signatures but with sacrifice, ritual, and the invocation of something greater than both parties.",
                "After a flood, one was made with a rainbow as its seal. Another was sealed with circumcision. I am the agreement that cannot simply be cancelled by one party.",
                "I am the difference between a deal and a sacred bond. Breaking me does not merely harm the other party - it offends the witness.",
            ],
        },
        {
            "answer": "abyss",
            "clues": [
                "I am depth without a bottom - the place where measurement gives up and imagination begins to fill what remains.",
                "I exist at the floor of every deep ocean trench, at the edge of every black hole, and at the centre of every despair too large for ordinary words.",
                "Nietzsche warned: stare into me long enough and I stare back into you. I am not mere emptiness - I am the version of emptiness that looks.",
            ],
        },
        {
            "answer": "legacy",
            "clues": [
                "I am what you leave behind after you are gone - not your body, not your buildings, but the shape your existence pressed into the world.",
                "Empires spend centuries trying to control me. Artists spend lifetimes hoping for me. Most people never learn what theirs is until after they are no longer there to know.",
                "I am the answer to the question asked only after a person cannot hear it: 'What did they matter?'",
            ],
        },
        {
            "answer": "instinct",
            "clues": [
                "I am the knowledge you were born with - older than any language, older than any conscious thought, written not in books but in the architecture of the body itself.",
                "You act on me before you understand me. By the time your conscious mind has processed the situation, you have already obeyed.",
                "A newborn knows to suckle without instruction. A bird knows the route south without a map. A human flinches before registering danger. I am the code beneath the code.",
            ],
        },
        {
            "answer": "myth",
            "clues": [
                "I am a story that was never meant to be taken literally - yet I have shaped the beliefs and behaviour of more people than any history book ever printed.",
                "Civilisations use me to answer what science cannot yet address and what science can never address: why the world exists, why people suffer, what we owe the dead.",
                "I compress the accumulated fear, wonder, and moral imagination of an entire culture into the shape of a story about heroes, monsters, and the origins of everything.",
            ],
        },
        {
            "answer": "smoke",
            "clues": [
                "I am what fire leaves behind once it has consumed everything solid - I rise because I am lighter than the air that refuses to hold me.",
                "Peoples separated by mountain ranges used me to communicate across impossible distances long before any telegraph existed. The Catholic Church still uses me to announce a new pope.",
                "I am the visible evidence of a process that is already complete - the ghost of combustion, still drifting upward long after the fire beneath has gone cold.",
            ],
        },
        {
            "answer": "law",
            "clues": [
                "I was not discovered in nature - I was invented. Yet once invented, every society that created me claimed I was natural, inevitable, or divinely ordained.",
                "I can strip you of your freedom, your property, and your life - without laying a single hand on you.",
                "Every human society in all of recorded history has had some version of me. No human society in all of recorded history has ever kept me perfectly.",
            ],
        },
        {
            "answer": "dream",
            "clues": [
                "I am generated by the brain to process its own electrical noise - a story assembled from fragments of memory while the body lies chemically paralysed.",
                "Freud believed I was the royal road to the unconscious mind. Modern neuroscientists believe I am memory consolidation in action. Both explanations might be simultaneously correct.",
                "You will spend roughly six years of your entire life inside me - experiencing it as vividly as waking reality - and forget ninety-five percent of it within ten minutes of leaving.",
            ],
        },
        {
            "answer": "map",
            "clues": [
                "I am an agreed-upon distortion: I flatten a sphere, warp distances, and draw boundaries that exist nowhere in nature - yet I am the most useful picture of reality ever produced.",
                "Empires drew me to claim what they could not yet hold. Explorers died filling in my blank spaces. Every territorial war in history began with someone disagreeing over me.",
                "Every GPS system, every navigation app, every satellite image is the descendant of the ancient problem I was invented to solve: how to represent a curved world on a flat surface.",
            ],
        },
        {
            "answer": "prison",
            "clues": [
                "I am a building whose entire purpose is to stop time - to hold a person fixed at one moment while the rest of the world continues moving without them.",
                "I exist in every society that has written laws - yet no two societies have ever agreed on whether my purpose is punishment, deterrence, or rehabilitation.",
                "The philosopher Foucault argued I was the hidden blueprint for all modern institutions: that schools, hospitals, and factories were all built on the same logic of confinement and continuous surveillance.",
            ],
        },
        {
            "answer": "threshold",
            "clues": [
                "I am the instant between two states - the point at which before and after exist simultaneously, and for a fraction of time, neither is yet true.",
                "In architecture I am a physical object: a strip of wood at the base of a doorway. In physics I am the precise value at which a system changes its behaviour entirely.",
                "Every initiation ceremony, every rite of passage, every coming-of-age ritual across every culture is built around me - the crossing of the line between one identity and another.",
            ],
        },
        {
            "answer": "gravity",
            "clues": [
                "I am not truly a force in the classical sense - Einstein proved I am the curvature of spacetime itself, a geometry created by the presence of mass.",
                "I am the weakest of the four fundamental forces of nature, yet I am the one that has shaped every galaxy, every star, and every planet in the observable universe.",
                "An apple may or may not have struck his head - but Newton was the first to realise that what pulls objects toward the ground is precisely the same thing that holds the Moon in its orbit.",
            ],
        },
    ]

    # ── Debate topics ────────────────────────────────────────
    DEBATE_TOPICS = [
        "Is school useful?",
        "Cats vs dogs - which is the better pet?",
        "Is AI dangerous for society?",
        "What is the world's best cuisine?",
        "TV shows vs movies - which is better?",
        "Is social media doing more harm than good?",
        "Is it better to be early or fashionably late?",
        "Morning person vs night owl - which is better?",
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
        # random.sample never repeats elements, guaranteeing no same-week duplicates.
        # With 32 mysteries in the pool, 7 are always safely available.
        selected = random.sample(self.MYSTERIES, min(7, len(self.MYSTERIES)))

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
                "**7 riddles over 7 days** - can you crack them all?"
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
                    # Normal day start - record timestamp and post clue 1
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
                            f"🕵️ **Day {day_index + 1}/7 - New Riddle!**\n"
                            f"Post your one-word answer in this channel.\n"
                            f"**Clue 1/{total_clues}:** {mystery['clues'][0]}\n"
                            f"*(Next clue in {interval_hrs}h - the answer will be revealed after {interval_hrs * total_clues}h if unsolved)*"
                        )

                    self._mystery_task = self.bot.loop.create_task(
                        self._mystery_clue_loop(mystery_ch, mystery)
                    )
                    day_sleep = Config.MYSTERY_DAY_DURATION_SECONDS
                else:
                    # Resumed day - skip clue 1 (already sent), resume from correct clue
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

        # Per-user wrong-guess cooldown - silently delete rate-limited guesses
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

        # Wrong guess - record time to rate-limit future attempts
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
            msg += f"👑 {name} - {max_clicks} clicks\n"

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
