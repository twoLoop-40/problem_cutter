"""
Job Repository (SQLite 기반)

명세: Specs/System/AppArchitecture.idr - JobRepository
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Job, JobStatus


class JobRepository:
    """
    Job 저장소 (명세: JobRepository)

    SQLite를 통한 Job 영속성 관리
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def save(self, job: Job) -> Job:
        """작업 저장 (명세: save)"""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def find_by_id(self, job_id: str) -> Optional[Job]:
        """작업 조회 (명세: findById)"""
        return self.db.query(Job).filter(Job.id == job_id).first()

    def find_all(self) -> List[Job]:
        """모든 작업 조회 (명세: findAll)"""
        return self.db.query(Job).order_by(Job.created_at.desc()).all()

    def delete(self, job_id: str) -> bool:
        """작업 삭제 (명세: delete)"""
        job = self.find_by_id(job_id)
        if job:
            self.db.delete(job)
            self.db.commit()
            return True
        return False

    def find_by_status(self, status: JobStatus) -> List[Job]:
        """상태별 조회 (명세: findByStatus)"""
        return self.db.query(Job).filter(Job.status == status.value).all()

    def update_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        """
        작업 상태 업데이트

        명세: ValidJobTransition
        - Pending → Processing
        - Processing → Completed
        - Processing → Failed
        """
        job = self.find_by_id(job_id)
        if job:
            job.status = status.value
            self.db.commit()
            self.db.refresh(job)
        return job

    def update_progress(self, job_id: str, percentage: int, message: str, estimated_remaining: Optional[int] = None) -> Optional[Job]:
        """진행 상황 업데이트 (명세: JobProgress)"""
        job = self.find_by_id(job_id)
        if job:
            job.progress_percentage = percentage
            job.progress_message = message
            job.estimated_remaining = estimated_remaining
            self.db.commit()
            self.db.refresh(job)
        return job

    def save_result(self, job_id: str, result: dict) -> Optional[Job]:
        """결과 저장 (명세: JobResult)"""
        job = self.find_by_id(job_id)
        if job:
            job.result = result
            self.db.commit()
            self.db.refresh(job)
        return job

    def record_error(self, job_id: str, error: str) -> Optional[Job]:
        """에러 기록"""
        job = self.find_by_id(job_id)
        if job:
            job.error = error
            job.status = JobStatus.FAILED.value
            self.db.commit()
            self.db.refresh(job)
        return job
