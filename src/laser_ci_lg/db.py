from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(path: str = "data/laser-ci.sqlite"):
    return create_engine(f"sqlite:///{path}", future=True, echo=False)


SessionLocal = sessionmaker(
    bind=get_engine(), autoflush=False, autocommit=False, future=True
)
