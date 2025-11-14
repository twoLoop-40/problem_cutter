"""
Job Service (작업 관리)

명세: Specs/System/AppArchitecture.idr - JobService
"""

import uuid
from typing import Optional, List
from pathlib import Path
from app.models import Job, JobStatus
from app.repositories import JobRepository


class JobService:
    """
    작업 관리 서비스 (명세: JobService)

    비즈니스 로직:
    - Job 생성/조회/삭제
    - 상태 전환 (ValidJobTransition 보장)
    - 진행 상황 추적
    """

    def __init__(self, repository: JobRepository):
        self.repo = repository

    def create_job(
        self,
        pdf_path: str,
        mathpix_api_key: Optional[str] = None,
        mathpix_app_id: Optional[str] = None
    ) -> Job:
        """
        새 작업 생성 (명세: createJob)

        Returns:
            생성된 Job
        """
        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            pdf_path=pdf_path,
            status=JobStatus.PENDING.value,
            progress_percentage=0,
            progress_message="대기 중",
            mathpix_api_key=mathpix_api_key,
            mathpix_app_id=mathpix_app_id
        )

        return self.repo.save(job)

    def get_job(self, job_id: str) -> Optional[Job]:
        """작업 조회 (명세: getJob)"""
        return self.repo.find_by_id(job_id)

    def get_all_jobs(self) -> List[Job]:
        """모든 작업 조회"""
        return self.repo.find_all()

    def delete_job(self, job_id: str) -> bool:
        """작업 삭제"""
        return self.repo.delete(job_id)

    def update_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        """
        작업 상태 업데이트 (명세: updateStatus)

        상태 전환 규칙 (명세: ValidJobTransition):
        - Pending → Processing
        - Processing → Completed
        - Processing → Failed
        """
        return self.repo.update_status(job_id, status)

    def update_progress(
        self,
        job_id: str,
        percentage: int,
        message: str,
        estimated_remaining: Optional[int] = None
    ) -> Optional[Job]:
        """
        진행 상황 업데이트 (명세: updateProgress)

        Args:
            job_id: 작업 ID
            percentage: 진행률 (0-100)
            message: 현재 단계 메시지
            estimated_remaining: 예상 남은 시간 (초)
        """
        return self.repo.update_progress(job_id, percentage, message, estimated_remaining)

    def save_result(
        self,
        job_id: str,
        total_problems: int,
        success_count: int,
        output_zip_path: str,
        processing_time_seconds: int
    ) -> Optional[Job]:
        """
        결과 저장 (명세: saveResult)

        Args:
            job_id: 작업 ID
            total_problems: 총 문제 수
            success_count: 성공한 문제 수
            output_zip_path: 출력 ZIP 파일 경로
            processing_time_seconds: 실행 시간 (초)
        """
        result = {
            "total_problems": total_problems,
            "success_count": success_count,
            "output_zip_path": output_zip_path,
            "processing_time_seconds": processing_time_seconds
        }

        return self.repo.save_result(job_id, result)

    def record_error(self, job_id: str, error: str) -> Optional[Job]:
        """에러 기록 (명세: recordError)"""
        return self.repo.record_error(job_id, error)

    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """상태별 작업 조회"""
        return self.repo.find_by_status(status)
