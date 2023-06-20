import datetime


def validateDate(date: str) -> bool:
    """Checks if the date is in the format YYYY-MM-DD. Used to validate database input."""
    try:
        datetime.date.fromisoformat(date)
        return True
    except ValueError:
        return False


def validateTime(time: str) -> bool:
    """Checks if the time is in the format HH:MM:SS. Used to validate database input."""
    try:
        datetime.time.fromisoformat(time)
        return True
    except ValueError:
        return False


def calculateTimeUntilGame(gameDateTime: str) -> datetime.timedelta:
    """Calculates the time until a game starts."""
    return datetime.datetime.fromisoformat(gameDateTime) - datetime.datetime.now()


def getDatetimeAfterTimeDelta(timeDelta: datetime.timedelta) -> datetime.datetime:
    """Returns the current datetime plus a given timedelta."""
    return datetime.datetime.now() + timeDelta
