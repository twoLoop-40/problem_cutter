"""
Database 설정 (SQLite)

명세: Specs/System/AppArchitecture.idr - JobRepository (SQLite 기반)
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models import Base

# SQLite 데이터베이스 파일 경로
DATABASE_URL = "sqlite:///./jobs.db"

# Engine 생성
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 전용 설정
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    데이터베이스 초기화

    테이블 생성 (없을 경우)
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """
    데이터베이스 세션 가져오기 (FastAPI Depends용)

    Usage:
        @app.get("/jobs")
        def get_jobs(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
