import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_NAME = os.getenv("DATABASE_NAME")
SINGUP_CHANNEL = os.getenv("SINGUP_CHANNEL")
