from sqlalchemy import text
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import engine
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import UserModel

with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

# Drop all existing tables then recreate them (dev-only reset).
# WARNING: This destroys all existing data.
# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# Seed the dummy user needed for current hardcoded dev endpoints
with SessionLocal() as session:
    dummy_user = UserModel(id="user-123", email="dev@example.com", role="admin")
    session.merge(
        dummy_user
    )  # merge is safer than add, it handles duplicates gracefully
    session.commit()

print("Tables created and seeded successfully.")
