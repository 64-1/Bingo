from telegram import Update

# Unified reply that works for commands and callback buttons
async def reply(update: Update, text: str, **kwargs):
    if getattr(update, "message", None):
        return await update.message.reply_text(text, **kwargs)
    if getattr(update, "callback_query", None):
        return await update.callback_query.message.reply_text(text, **kwargs)
