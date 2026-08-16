"""
Standalone Database Session & Engine Configuration
===================================================
Independent SQLite connection for PromptDatabase.
"""

from pathlib import Path
from contextlib import contextmanager
from sqlmodel import SQLModel, Session, create_engine

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "youtube_pipeline.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


def init_db():
    """Initializes and creates tables if not existing."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    """Provides a transactional database session."""
    with Session(engine) as session:
        yield session
