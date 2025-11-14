"""
LangGraph Agent Service (FastAPI 통합)

기존 agent_extraction_service를 LangGraph로 교체

Version 2.0: 병렬 처리 아키텍처
- Idris2 명세: Specs/System/LangGraphWorkflow.idr
- PageLevel 병렬: 페이지별 독립 처리
- ColumnLevel 병렬: 컬럼별 독립 처리
"""

from pathlib import Path
from typing import Optional

from app.models import JobStatus
from app.services.job_service import JobService
from app.agents.parallel_workflow import (
    create_parallel_extraction_workflow,
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

        print("[LangGraphService] 초기화 완료 (병렬 처리 모드)")

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
            from app.models import JobStatus

            # 작업 상태를 processing으로 변경
            self.job_service.update_status(job_id, JobStatus.PROCESSING)

            # 병렬 처리 워크플로우 생성 (캐시됨)
            if self.workflow is None:
                self.workflow = create_parallel_extraction_workflow()

            # 초기 상태 생성
            initial_state = create_initial_state(
                job_id=job_id,
                pdf_path=pdf_path,
                dpi=300,  # TODO: 설정 가능하게
            )

            print(f"[LangGraphService] 병렬 워크플로우 시작: {job_id}")

            # 워크플로우 실행 (동기 - LangGraph 내부에서 asyncio 사용)
            final_state = self.workflow.invoke(initial_state)

            print(f"[LangGraphService] 병렬 워크플로우 완료: {job_id}")

            # 결과 처리
            if final_state["current_state"] == "Complete":
                # 성공: 상태 업데이트 및 결과 저장
                from app.models import JobStatus

                self.job_service.update_status(job_id, JobStatus.COMPLETED)

                detected = final_state["detected_problems"]
                missing = final_state.get("missing_problems", [])

                self.job_service.save_result(
                    job_id=job_id,
                    total_problems=len(detected) + len(missing),
                    success_count=len(detected),
                    output_zip_path=final_state.get("zip_path", ""),
                    processing_time_seconds=60,  # TODO: 실제 시간 계산
                )

                print(f"[LangGraphService] Job {job_id} 완료: {len(detected)}개 문제 감지")
            else:
                # 실패
                from app.models import JobStatus
                error_msg = final_state.get("error", "Unknown error")

                self.job_service.update_status(job_id, JobStatus.FAILED)
                self.job_service.record_error(job_id, error_msg)

                print(f"[LangGraphService] Job {job_id} 실패: {error_msg}")

        except Exception as e:
            import traceback
            from app.models import JobStatus

            error_msg = f"{str(e)}\n{traceback.format_exc()}"

            self.job_service.update_status(job_id, JobStatus.FAILED)
            self.job_service.record_error(job_id, error_msg)

            print(f"[LangGraphService] Job {job_id} 예외 발생: {str(e)}")

    def _update_progress(self, job_id: str, progress: int, message: str):
        """진행률 업데이트 (LangGraph 내부에서 처리되므로 스텁)"""
        pass
