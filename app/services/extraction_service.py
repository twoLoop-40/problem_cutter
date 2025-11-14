"""
Extraction Service (추출 실행)

명세: Specs/System/AppArchitecture.idr - ExtractionService

기존 workflows/with_mathpix.py를 재사용하여 추출 실행
"""

import time
import traceback
from pathlib import Path
from typing import Optional, Callable
from app.models import JobStatus
from app.services.job_service import JobService


class ExtractionService:
    """
    추출 실행 서비스 (명세: ExtractionService)

    기존 Domain 로직 (workflows/)을 호출하여 실제 추출 수행
    """

    def __init__(self, job_service: JobService):
        self.job_service = job_service

    def execute_extraction(
        self,
        job_id: str,
        pdf_path: str,
        mathpix_api_key: Optional[str] = None,
        mathpix_app_id: Optional[str] = None
    ):
        """
        추출 실행 (명세: executeExtraction)

        워크플로우:
        1. 상태를 Processing으로 변경
        2. workflows/with_mathpix.py 로직 실행
        3. 진행 상황 콜백 호출
        4. 완료 또는 실패 처리
        """
        start_time = time.time()

        try:
            # 1. 상태를 Processing으로 변경
            self.job_service.update_status(job_id, JobStatus.PROCESSING)
            self.on_progress(job_id, 0, "PDF 변환 시작")

            # 2. 기존 워크플로우 로직 실행
            # TODO: workflows/with_mathpix.py를 import하여 실행
            # 현재는 간단한 시뮬레이션

            self._run_workflow(
                job_id=job_id,
                pdf_path=pdf_path,
                mathpix_api_key=mathpix_api_key,
                mathpix_app_id=mathpix_app_id
            )

            # 3. 완료 처리
            elapsed = int(time.time() - start_time)
            output_path = f"output/{Path(pdf_path).stem}_result.zip"

            self.on_complete(
                job_id=job_id,
                total_problems=20,  # TODO: 실제 값
                success_count=19,  # TODO: 실제 값
                output_zip_path=output_path,
                processing_time_seconds=elapsed
            )

        except Exception as e:
            # 4. 실패 처리
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.on_failure(job_id, error_msg)

    def _run_workflow(
        self,
        job_id: str,
        pdf_path: str,
        mathpix_api_key: Optional[str],
        mathpix_app_id: Optional[str]
    ):
        """
        실제 워크플로우 실행

        TODO: workflows/with_mathpix.py 로직을 여기에 통합
        """
        # 1. PDF → 이미지 변환
        self.on_progress(job_id, 10, "PDF → 이미지 변환 중")
        time.sleep(1)  # 시뮬레이션

        # 2. 레이아웃 감지
        self.on_progress(job_id, 20, "레이아웃 감지 중")
        time.sleep(1)

        # 3. 컬럼 분리
        self.on_progress(job_id, 30, "컬럼 분리 중")
        time.sleep(1)

        # 4. Tesseract OCR
        self.on_progress(job_id, 50, "Tesseract OCR 실행 중")
        time.sleep(2)

        # 5. 문제 추출
        self.on_progress(job_id, 70, "문제 추출 중")
        time.sleep(1)

        # 6. 검증
        self.on_progress(job_id, 80, "검증 중")
        time.sleep(1)

        # 7. Mathpix 재추출 (필요시)
        if mathpix_api_key and mathpix_app_id:
            self.on_progress(job_id, 85, "Mathpix 재추출 중")
            time.sleep(2)

        # 8. 파일 생성
        self.on_progress(job_id, 95, "파일 생성 중")
        time.sleep(1)

        # 9. ZIP 패키징
        self.on_progress(job_id, 100, "완료")

    def on_progress(
        self,
        job_id: str,
        percentage: int,
        message: str,
        estimated_remaining: Optional[int] = None
    ):
        """진행 상황 콜백 (명세: onProgress)"""
        self.job_service.update_progress(
            job_id=job_id,
            percentage=percentage,
            message=message,
            estimated_remaining=estimated_remaining
        )
        print(f"[{job_id}] {percentage}% - {message}")

    def on_complete(
        self,
        job_id: str,
        total_problems: int,
        success_count: int,
        output_zip_path: str,
        processing_time_seconds: int
    ):
        """완료 콜백 (명세: onComplete)"""
        self.job_service.save_result(
            job_id=job_id,
            total_problems=total_problems,
            success_count=success_count,
            output_zip_path=output_zip_path,
            processing_time_seconds=processing_time_seconds
        )
        self.job_service.update_status(job_id, JobStatus.COMPLETED)
        print(f"[{job_id}] ✅ 완료: {success_count}/{total_problems} 문제 추출")

    def on_failure(self, job_id: str, error: str):
        """실패 콜백 (명세: onFailure)"""
        self.job_service.record_error(job_id, error)
        print(f"[{job_id}] ❌ 실패: {error}")
