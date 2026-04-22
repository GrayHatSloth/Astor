# ============================================================
# src/events/on_message.py — Message Handler (thin shim)
# ============================================================
# All routing logic lives in AstorEngine.process_message.
# This file only registers the Discord event and delegates.
# ============================================================


def setup(bot, engine):
    """Register the on_message event; delegate to AstorEngine."""

    @bot.event
    async def on_message(message):
        await engine.process_message(message)
