# ============================================================
# src/events/on_reaction.py — Reaction Handler
# ============================================================
# Handles two types of reactions:
#   1. Chaos button presses (Button Frenzy mode)
#   2. Weekly twist activation (✅ button)
# Also tracks reaction-based challenge progress.
# ============================================================

import random


def setup(bot, managers):
    """
    Register on_raw_reaction_add.
    `managers` dict: effect_manager, twist_manager, points_manager
    """
    em = managers["effect_manager"]
    tm = managers["twist_manager"]
    pm = managers["points_manager"]

    @bot.event
    async def on_raw_reaction_add(payload):
        # Ignore the bot's own reactions
        if payload.user_id == bot.user.id:
            return

        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        # ── Chaos Buttons ───────────────────────────────────
        if payload.message_id in em.chaos_buttons:
            await em.handle_chaos_button(payload)
            return

        # ── Weekly Twist Activation ─────────────────────────
        if payload.emoji.name == "✅" and payload.message_id == bot.button_message_id:
            message = await channel.fetch_message(payload.message_id)

            if tm.pending_twist and not tm.active_twist:
                # Pick a random twist type
                twist_type = random.choice(["most_messages", "first_to_x", "most_words", "most_replies"])

                if twist_type == "first_to_x":
                    tm.first_to_x_target = random.randint(5000, 10000)

                tm.active_twist = {"type": twist_type, "winner_declared": False}
                tm.data = {}
                tm.pending_twist = False

                labels = {
                    "most_messages": "📊 Send the most messages this week to win!",
                    "first_to_x":   f"🏁 First to reach {tm.first_to_x_target} messages wins!",
                    "most_words":   "📝 Send the most words this week to win!",
                    "most_replies": "💬 Get the most replies to your messages to win!",
                }
                await channel.send(
                    f"@everyone\n🎉 **Weekly Twist Started!** {labels[twist_type]}"
                )

            # Remove the user's reaction so the button stays clean
            member = await guild.fetch_member(payload.user_id)
            if member:
                try:
                    await message.remove_reaction(payload.emoji, member)
                except Exception:
                    pass

        # ── Challenge tracking for reactions ────────────────
        pm.update_challenge_progress(payload.user_id, "normal", "reactions")
