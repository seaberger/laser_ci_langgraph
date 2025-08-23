import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(path: str = "data/laser-ci.sqlite"):
    os.makedirs("data", exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True, echo=False)


engine = get_engine()
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

def bootstrap_db():
    from .models import Base
    Base.metadata.create_all(engine)
