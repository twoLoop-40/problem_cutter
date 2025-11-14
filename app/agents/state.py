"""
LangGraph State Definition

Idris2 명세: Specs/System/Agent/State.idr (LangGraphState)

LangGraph의 TypedDict 상태 정의
"""

from typing import TypedDict, Optional, List
from core.ocr.interface import OcrStrategy, OcrExecutionResult


class ExtractionState(TypedDict):
    """
    LangGraph 상태 (Idris2: LangGraphState)

    모든 Node 함수가 이 상태를 받아서 업데이트된 상태를 반환
    """
    # Job 정보
    job_id: str
    """Job ID (FastAPI Job과 연동)"""

    pdf_path: str
    """PDF 경로"""

    ocr_strategy: OcrStrategy
    """OCR 설정 (엔진 선택)"""

    # 현재 상태
    current_state: str
    """현재 Agent 상태 (Initial, ConvertingPdf, DetectingLayout, ...)"""

    # 중간 결과
    images: Optional[List[str]]
    """PDF 이미지들 (변환 후) - 이미지 경로 목록"""

    layouts: Optional[List[str]]
    """레이아웃 정보 - 레이아웃 JSON 경로 목록"""

    # OCR 결과
    ocr_stage1_result: Optional[OcrExecutionResult]
    """Stage1 OCR 결과 (엔진 독립적)"""

    ocr_stage2_result: Optional[OcrExecutionResult]
    """Stage2 OCR 결과 (엔진 독립적)"""

    # 문제 검출 결과
    detected_problems: List[int]
    """최종 검출된 문제 번호들"""

    expected_problems: Optional[List[int]]
    """기대하는 문제 번호들"""

    missing_problems: List[int]
    """누락된 문제 번호들"""

    # Agent 판단
    decision: Optional[str]
    """Agent 결정 (proceed, stage2, retry, abort)"""

    # 출력
    output_dir: Optional[str]
    """출력 디렉토리"""

    zip_path: Optional[str]
    """ZIP 경로"""

    # 진행률
    progress: int
    """진행률 (0-100)"""

    message: str
    """현재 메시지"""

    error: Optional[str]
    """에러 메시지"""
