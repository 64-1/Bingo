from telegram.ext import Application, CallbackQueryHandler
from app.bot.commands import start as cmd_start
from app.bot.commands import team as cmd_team
from app.bot.flows import create_team as flow_create
from app.bot.flows import join_team as flow_join
from app.bot.flows import submit as flow_submit

# Button-only actions that are NOT conversations:
async def menu_board(update, context): return await cmd_team.board(update, context)
async def menu_submit(update, context): return await flow_submit.start(update, context)
async def menu_leaderboard(update, context): return await cmd_team.leaderboard(update, context)
async def menu_team(update, context): return await cmd_team.team_info(update, context)

def setup_bot_handlers(app: Application):
    # Conversations first (so their entry points catch)
    app.add_handler(flow_create.conversation())
    app.add_handler(flow_join.conversation())
    app.add_handler(flow_submit.conversation())

    # Inline button actions
    app.add_handler(CallbackQueryHandler(menu_board, pattern=r"^menu:board$"))
    app.add_handler(CallbackQueryHandler(menu_submit, pattern=r"^menu:submit$"))
    app.add_handler(CallbackQueryHandler(menu_leaderboard, pattern=r"^menu:leaderboard$"))
    app.add_handler(CallbackQueryHandler(menu_team, pattern=r"^menu:team$"))

    # Commands
    for h in cmd_start.handlers(): app.add_handler(h)
    for h in cmd_team.handlers():  app.add_handler(h)

    # Error logging (optional)
    async def on_error(update_obj, context):
        print(f"[telegram-error] err={context.error} update={getattr(update_obj,'to_dict',lambda: str(update_obj))()}")
    app.add_error_handler(on_error)
