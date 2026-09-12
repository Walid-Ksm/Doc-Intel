from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL not set. Check .env file")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
