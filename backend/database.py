from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.config import settings

engine = create_engine(
    settings.database_url.replace("sqlite+apsw://", "sqlite://"),
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine):
    from backend.models import Base
    Base.metadata.create_all(bind=engine)