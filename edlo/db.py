from collections.abc import Generator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
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

settings = get_settings()

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session