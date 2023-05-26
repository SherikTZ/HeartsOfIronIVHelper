import discord


async def dmAreClosed(user: discord.User) -> bool:
    """Returns True if the bot can't DM the user, False otherwise.
    If DMs are closed user cannot sign up for the game."""

    try:
        dmChannel = await user.create_dm()
        return False
    except discord.Forbidden:
        return True
