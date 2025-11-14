"""
Job 모델 (SQLAlchemy ORM)

명세: Specs/System/AppArchitecture.idr
- JobStatus: Pending | Processing | Completed | Failed
- ValidJobTransition: Pending → Processing → (Completed | Failed)
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class JobStatus(str, Enum):
    """작업 상태 (명세: JobStatus)"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    """
    Job Entity (명세: Job)

    작업의 전체 생명주기를 추적
    """
    __tablename__ = "jobs"

    # Primary key
    id = Column(String, primary_key=True, index=True)  # UUID

    # Job 기본 정보
    pdf_path = Column(String, nullable=False)
    status = Column(String, default=JobStatus.PENDING, nullable=False)

    # 진행 상황 (명세: JobProgress)
    progress_percentage = Column(Integer, default=0)
    progress_message = Column(String, default="대기 중")
    estimated_remaining = Column(Integer, nullable=True)  # 초

    # 결과 (명세: JobResult)
    result = Column(JSON, nullable=True)  # { totalProblems, successCount, outputZipPath, processingTimeSeconds }

    # 에러
    error = Column(Text, nullable=True)

    # Mathpix 설정 (선택)
    mathpix_api_key = Column(String, nullable=True)
    mathpix_app_id = Column(String, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, progress={self.progress_percentage}%)>"

    def to_dict(self):
        """Dict 변환 (API 응답용)"""
        return {
            "job_id": self.id,
            "pdf_path": self.pdf_path,
            "status": self.status,
            "progress": {
                "percentage": self.progress_percentage,
                "message": self.progress_message,
                "estimated_remaining": self.estimated_remaining
            },
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
