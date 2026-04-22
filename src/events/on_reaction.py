# ============================================================
# src/events/on_reaction.py — Reaction Handler (thin shim)
# ============================================================
# All routing logic lives in AstorEngine.process_reaction.
# This file only registers the Discord event and delegates.
# ============================================================


def setup(bot, engine):
    """Register on_raw_reaction_add; delegate to AstorEngine."""

    @bot.event
    async def on_raw_reaction_add(payload):
        await engine.process_reaction(payload)
