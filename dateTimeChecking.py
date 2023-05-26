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


def formatDate(date: str) -> str:
    """Formats the date to be in the format YYYY-MM-DD."""
    return datetime.date.fromisoformat(date).strftime("%Y-%m-%d")


def formatTime(time: str) -> str:
    """Formats the time to be in the format HH:MM:SS."""
    return datetime.time.fromisoformat(time).strftime("%H:%M:%S")
