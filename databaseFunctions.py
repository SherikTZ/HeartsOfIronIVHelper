import sqlite3
import datetime as dt


def insertNewSignUpAttempt(
    connection: sqlite3.Connection, cursor: sqlite3.Cursor, userID: str
) -> None:
    """Inserts a new signup attempt into the database. Used to prevent calling the signup command multiple times. Also, used to prevent signing up too many times in a given period of time."""
    isActive = 1  # By default sets record to be active. Sign up attempts are deactived when the signup is finished, the bot is restarted, the game starts or signup expires.

    cursor.execute(
        "INSERT INTO signup_attempts (player_id, datetime, is_active) VALUES(?, ?, ?)",
        (userID, dt.datetime.now(), isActive),
    )
    connection.commit()


def insertNewUnsignAttempt(
    connection: sqlite3.Connection, cursor: sqlite3.Cursor, userID: str
) -> None:
    """Inserts a new unsign attempt into the database. Used to prevent calling the unsign command multiple times. Also, used to prevent unsigning too many times in a given period of time."""
    isActive = 1  # By default sets record to be active. Unsign attempts are deactived when the unsign is finished, the bot is restarted, the game starts or unsign expires.

    cursor.execute(
        "INSERT INTO unsign_attempts (player_id, datetime, is_active) VALUES(?, ?, ?)",
        (userID, dt.datetime.now(), isActive),
    )
    connection.commit()


def insertPlayerIfNotExists(
    cursor: sqlite3.Cursor, userID: str, discordTag: str
) -> None:
    """Checks if a player exists in the database. If not, inserts a new player."""
    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM players WHERE player_id=? LIMIT 1)",
        (userID,),
    )

    userExists = cursor.fetchone()[0]
    if not userExists:
        cursor.execute(
            "INSERT INTO players (player_id, discord_tag) VALUES (?, ?)",
            (
                userID,
                discordTag,
            ),
        )


def insertGameRecord(
    connection: sqlite3.Connection,
    cursor: sqlite3.Cursor,
    gameID: str,
    userID: str,
    countryID: str,
    controller: str,
    option: str,
) -> None:
    "Inserts a new game record into the database. Used to sign up for a game."

    cursor.execute(
        "INSERT INTO game_records (game_id, player_id, country_id, faction_id, ending_id, controller, option, singup_time) VALUES (?,?,?,?,?, ?, ?, ?)",
        (
            int(gameID),
            int(userID),
            int(countryID),
            int(getFactionID(cursor, countryID)),
            3,
            int(controller),
            option,
            dt.datetime.now(),
        ),
    )
    connection.commit()


def setPlayerSignUpAttemptsInactive(
    connection: sqlite3.Connection, cursor: sqlite3.Cursor, playerID: str
) -> None:
    """Sets all signup attempts for a given player to inactive. Used to prevent signing up for multiple games at once. Executed when the view for signing up is stopped."""

    cursor.execute(
        "UPDATE signup_attempts SET is_active = 0 WHERE player_id = ?",
        (playerID,),
    )
    connection.commit()


def checkIfUserAlreadyHasSignUp(cursor: sqlite3.Cursor, userID: str) -> bool:
    """Checks if a user already has an active signup attempt. Used to prevent calling the signup command multiple times.""" ""

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM signup_attempts WHERE player_id = ? and is_active = 1 LIMIT 1)",
        (userID,),
    )
    return bool(int(cursor.fetchone()[0]))


def checkIfUserAlreadyHasUnsign(cursor: sqlite3.Cursor, userID: str) -> bool:
    """Checks if a user already has an active unsign attempt. Used to prevent calling the unsign command multiple times."""

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM unsign_attempts WHERE player_id = ? and is_active = 1 LIMIT 1)",
        (userID,),
    )
    return bool(int(cursor.fetchone()[0]))


def checkIfPlayerSignedForOption(
    cursor: sqlite3.Cursor, playerID: str, option: int, gameID: str
) -> bool:
    "Checks if player signed for a given option. Used to prevent signing for the same option multiple times."

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM game_records WHERE player_id = ? AND option = ? and game_id = ? and is_active = 1 LIMIT 1)",
        (playerID, option, gameID),
    )
    return bool(int(cursor.fetchone()[0]))


def checkIfCountryHasController(
    cursor: sqlite3.Cursor, gameID: str, countryID: str, controller: str
) -> bool:
    "Checks if a country has a controller. Used to prevent signing for a country that already has the same type of controller."

    cursor.execute(
        "SELECT EXISTS(SELECT 1 FROM game_records WHERE game_id = ? AND country_id = ? AND controller = ? AND is_active = 1 LIMIT 1)",
        (gameID, countryID, controller),
    )
    return bool(int(cursor.fetchone()[0]))


def fetchAvailableCountries(cursor: sqlite3.Cursor, gameID: str, userID: str) -> list:
    """Returns a sorted list of available countries for a given game and user. Used to display available countries to the user.
    Selects all countries, and then removes majors, minors, and countries the user signed for from the list.
    """

    cursor.execute(
        "SELECT country_id, name, emoji FROM countries JOIN countries_factions_historical USING(country_id)",
    )

    allCountries = cursor.fetchall()

    cursor.execute(
        "SELECT country_id, name, emoji FROM countries JOIN countries_factions_historical USING(country_id) WHERE country_id IN ( SELECT country_id FROM game_records JOIN countries USING(country_id) WHERE game_id = ? AND is_major = 1 and is_active = 1 GROUP BY country_id HAVING COUNT(*) = 2)",
        (gameID,),
    )

    signedMajors = cursor.fetchall()

    cursor.execute(
        "SELECT country_id, name, emoji FROM countries JOIN countries_factions_historical USING(country_id) WHERE country_id IN ( SELECT country_id FROM game_records JOIN countries USING(country_id) WHERE game_id = ? AND is_major = 0 and is_active = 1 GROUP BY country_id HAVING COUNT(*) = 1)",
        (gameID,),
    )

    singedMinors = cursor.fetchall()

    cursor.execute(
        "SELECT country_id, name, emoji FROM countries JOIN countries_factions_historical USING(country_id) WHERE country_id IN ( SELECT country_id FROM game_records JOIN countries USING(country_id) WHERE game_id = ? AND player_id = ? and is_active = 1)",
        (gameID, userID),
    )

    signedNationsByPlayer = cursor.fetchall()

    allCountriesSet = set(allCountries)
    signedCountriesSet = set(signedMajors + singedMinors + signedNationsByPlayer)

    availableCountriesSet = allCountriesSet - signedCountriesSet
    availableCountries = list(availableCountriesSet)
    availableCountries = sorted(
        availableCountries, key=lambda x: x[0]
    )  # Sorts by country_id

    return availableCountries


def getFactionID(cursor: sqlite3.Cursor, countryID: str) -> int:
    "Returns faction_id for a given country. Used for historical games."

    cursor.execute(
        "SELECT faction_id FROM countries_factions_historical WHERE country_id = ?",
        (countryID,),
    )
    return cursor.fetchone()[0]


def getPrimaryControllerID(cursor: sqlite3.Cursor, gameID: str, countryID: str) -> str:
    """Returns player_id of the primary controller for a given country."""

    cursor.execute(
        "SELECT player_id FROM game_records JOIN players USING(player_id) WHERE game_id = ? AND country_id = ? AND controller = 1",
        (gameID, countryID),
    )
    return cursor.fetchone()[0]


def isCountryMajor(cursor: sqlite3.Cursor, countryID: str) -> bool:
    "Checks if a country is a major or not."

    cursor.execute(
        "SELECT is_major FROM countries WHERE country_id = ?;",
        (countryID,),
    )
    return bool(int(cursor.fetchone()[0]))
