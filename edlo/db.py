from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from edlo.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", 
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase): 
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    kwargs: dict = {"pool_pre_ping": True} 
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False} 
    else:
        kwargs |= {"pool_size": 5, "max_overflow": 5, "pool_recycle": 1800}
    return create_engine(settings.database_url, **kwargs)

@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker:
    return sessionmaker(get_engine(), expire_on_commit=False)