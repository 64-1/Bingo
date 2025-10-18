from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Create Team", callback_data="menu:create")],
        [InlineKeyboardButton("🔑 Join Team", callback_data="menu:join")],
        [
            InlineKeyboardButton("🎯 Board", callback_data="menu:board"),
            InlineKeyboardButton("📸 Submit", callback_data="menu:submit"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
            InlineKeyboardButton("👥 My Team", callback_data="menu:team"),
        ],
    ])

def pretty_help_text():
    return (
        "📖 *How to use BingoQuest*\n\n"
        "/create_team\nCreate a new team (or use the button)\n\n"
        "/join\nJoin a team with code (or use the button)\n\n"
        "/team\nSee team members, score, join code\n\n"
        "/board\nList all challenges and points\n\n"
        "/submit\nLeader uploads photo/video proof\n\n"
        "/leaderboard\nSee top teams\n\n"
        "/status\nSee your team’s approved/pending\n\n"
        "/menu\nShow the quick buttons again"
    )
