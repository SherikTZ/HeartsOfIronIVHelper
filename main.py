import discord
from discord.ext import commands

from config import TOKEN, DATABASE_NAME, SINGUP_CHANNEL
from dateTimeFunctions import validateDate, validateTime
from signUpViews import SignupHandler

import sqlite3


bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()


@bot.command()
async def addGame(ctx, *args):
    """Adds a game to the database.
    Usage: !addGame <gameType> <gameDate> <gameTime>.
    Example: !addGame historical 2021-01-01 12:00."""

    if len(args) < 3:
        await ctx.message.reply("Invalid number of arguments.")
        return -1

    gameType = args[0]
    gameDate = args[1]
    gameTime = args[2]

    if not validateDate(gameDate):
        await ctx.message.reply("Invalid date.")
        return -1

    if not validateTime(gameTime):
        await ctx.message.reply("Invalid time.")
        return -1

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM types WHERE name=? LIMIT 1)", (gameType,)
    )
    if cursor.fetchone()[0] == 0:
        await ctx.message.reply("Invalid game type.")
        return -1
    else:
        cursor.execute("Select type_id from types where name = ?", (gameType,))
        type_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO games (type_id, starting_time) VALUES (?, ?)",
            (type_id, str(gameDate) + " " + str(gameTime)),
        )
        connection.commit()
        # await ctx.send("Game added.")
        await ctx.message.reply("Game added.")
        return 0


@bot.command()
async def listGames(ctx):
    """Lists all the games in the database. Usage: !listGames."""

    cursor.execute(
        "SELECT game_id, t.name, starting_time FROM games JOIN types t USING(type_id)"
    )
    games = cursor.fetchall()

    if len(games) == 0:
        await ctx.message.reply("No games found.")
        return -1

    message = ""

    for record in games:
        message += (
            f"Game ID: {record[0]}, Type: {record[1]}, Starting Time: {record[2]}\n"
        )

    await ctx.message.reply(message)


@bot.command()
async def deleteGame(ctx, *args):
    """Deletes a game from the database. Usage: !deleteGame <gameID>. Example: !deleteGame 1."""
    if len(args) < 1:
        await ctx.message.reply("Invalid number of arguments.")
        return -1

    gameID = args[0]

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM games WHERE game_id=? LIMIT 1)", (gameID,)
    )

    if cursor.fetchone()[0] == 0:
        await ctx.message.reply("Invalid game ID.")
        return -1
    else:
        cursor.execute("DELETE FROM games WHERE game_id = ?", (gameID,))
        connection.commit()

    await ctx.message.reply("Game deleted.")


@bot.command()
async def editGame(ctx, *args):
    """Edits a game in the database.
    Usage: !editGame <gameID> <field>.
    Example: !editGame 1 2021-01-01 12:00."""
    if len(args) < 2:
        await ctx.message.reply("Invalid number of arguments.")
        return -1

    gameID = args[0]
    field = args[1]

    if validateDate(field):
        cursor.execute("SELECT starting_time FROM games WHERE game_id = ?", (gameID,))
        time = cursor.fetchone()[0]
        field = field + " " + time[11:]
        cursor.execute(
            "UPDATE games SET starting_time = ? WHERE game_id = ?", (field, gameID)
        )
        connection.commit()
        await ctx.message.reply("Game edited.")
        return 0
    elif validateTime(field):
        cursor.execute("SELECT starting_time FROM games WHERE game_id = ?", (gameID,))
        date = cursor.fetchone()[0]
        field = date[:10] + " " + field
        cursor.execute(
            "UPDATE games SET starting_time = ? WHERE game_id = ?", (field, gameID)
        )
        connection.commit()
        await ctx.message.reply("Game edited.")
        return 0
    else:
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM types WHERE name=? LIMIT 1)", (field,)
        )
        if cursor.fetchone()[0] == 0:
            await ctx.message.reply("Invalid game type.")
            return -1
        else:
            cursor.execute("Select type_id from types where name = ?", (field,))
            type_id = cursor.fetchone()[0]

            cursor.execute(
                "UPDATE games SET type_id = ? WHERE game_id = ?", (type_id, gameID)
            )
            connection.commit()
            await ctx.message.reply("Game edited.")
            return 0


@bot.command()
async def createSingUpMessage(ctg, *args):
    gameID = args[0]
    cursor.execute("SELECT faction_id, name FROM factions")
    factions = cursor.fetchall()
    message = ""

    for faction in factions:
        message += faction[1].upper() + "\n"
        message += "---------------------\n"
        cursor.execute(
            "Select country_id, name from countries JOIN countries_factions_historical USING(country_id) WHERE faction_id = ?",
            (faction[0],),
        )
        countries = cursor.fetchall()
        for country in countries:
            primaryOption = "None"
            secondaryOption = "None"

            cursor.execute(
                "SELECT player_id from game_records where game_id = ? and country_id = ? and option = 1",
                (gameID, country[0]),
            )

            row = cursor.fetchone()
            if row is not None:
                primaryOptionID = row[0]

                cursor.execute(
                    "SELECT discord_tag from players where player_id = ?",
                    (primaryOptionID,),
                )
                primaryOption = cursor.fetchone()[0]

            cursor.execute(
                "SELECT player_id from game_records where game_id = ? and country_id = ? and option = 2",
                (gameID, country[0]),
            )

            row = cursor.fetchone()
            if row is not None:
                secondaryOptionID = row[0]

                cursor.execute(
                    "SELECT discord_tag from players where player_id = ?",
                    (secondaryOptionID,),
                )

                secondaryOption = cursor.fetchone()[0]

            message += (
                country[1]
                + "|Primary Option: "
                + f"**{primaryOption}**"
                + "|Secondary Option: "
                + f"**{secondaryOption}**"
                + "\n"
            )
        message += "\n"

    channel = bot.get_channel(int(SINGUP_CHANNEL))
    view = SignupHandler(gameID, connection, cursor, bot)
    await channel.send(message, view=view)


@bot.command()
async def resetDB(ctx):
    """Resets the database."""
    cursor.execute("DELETE FROM game_records")
    cursor.execute("DELETE FROM signup_attempts")
    cursor.execute("DELETE FROM unsign_attempts")
    connection.commit()
    await ctx.message.reply("Database reset.")


@bot.event
async def on_disconnect():
    """Closes the database connection when the bot disconnects."""
    connection.close()


bot.run(TOKEN)
