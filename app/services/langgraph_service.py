"""
LangGraph Agent Service (FastAPI 통합)

기존 agent_extraction_service를 LangGraph로 교체
"""

from pathlib import Path
from typing import Optional

from app.models import JobStatus
from app.services.job_service import JobService
from app.agents.workflow_impl import (
    create_extraction_workflow,
    create_initial_state,
    initialize_ocr_registry,
)


class LangGraphService:
    """
    LangGraph 기반 추출 서비스

    기존 AgentExtractionService를 대체
    """

    def __init__(self, job_service: JobService):
        self.job_service = job_service
        self.workflow = None

        # OCR 레지스트리 초기화
        initialize_ocr_registry()

    def execute_extraction(
        self,
        job_id: str,
        pdf_path: str,
        expected_problem_count: Optional[int] = None,
        mathpix_api_key: Optional[str] = None,
        mathpix_app_id: Optional[str] = None,
    ):
        """
        LangGraph 워크플로우 실행

        Args:
            job_id: Job ID
            pdf_path: PDF 경로
            expected_problem_count: 기대하는 문제 수 (미사용)
            mathpix_api_key: Mathpix API 키 (미사용)
            mathpix_app_id: Mathpix App ID (미사용)
        """
        try:
            # 워크플로우 생성 (캐시됨)
            if self.workflow is None:
                self.workflow = create_extraction_workflow()

            # 초기 상태 생성
            initial_state = create_initial_state(
                job_id=job_id,
                pdf_path=pdf_path,
            )

            # 워크플로우 실행 (동기)
            final_state = self.workflow.invoke(initial_state)

            # 결과 처리
            if final_state["current_state"] == "Complete":
                # 성공
                self.job_service.complete_job(
                    job_id=job_id,
                    detected_problems=final_state["detected_problems"],
                    missing_problems=final_state.get("missing_problems", []),
                    output_dir=final_state.get("output_dir"),
                    output_zip_path=final_state.get("zip_path"),
                    processing_time_seconds=60,  # TODO: 실제 시간 계산
                )
            else:
                # 실패
                error_msg = final_state.get("error", "Unknown error")
                self.job_service.fail_job(job_id, error_msg)

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.job_service.fail_job(job_id, error_msg)

    def _update_progress(self, job_id: str, progress: int, message: str):
        """진행률 업데이트 (LangGraph 내부에서 처리되므로 스텁)"""
        pass
