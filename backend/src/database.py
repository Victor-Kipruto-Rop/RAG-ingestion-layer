from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

connect_args = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}
engine_options = {'pool_pre_ping': True, 'connect_args': connect_args}
if not settings.database_url.startswith('sqlite'):
    engine_options.update({
        'pool_size': max(1, settings.db_pool_size),
        'max_overflow': max(0, settings.db_max_overflow),
        'pool_timeout': max(1, settings.db_pool_timeout_seconds),
        'pool_recycle': max(60, settings.db_pool_recycle_seconds),
    })
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
