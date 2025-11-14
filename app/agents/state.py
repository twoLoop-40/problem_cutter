"""
LangGraph State Definition

Idris2 명세:
- Specs/System/Agent/State.idr (LangGraphState) - 단순 순차 처리
- Specs/System/LangGraphWorkflow.idr (PdfExtractionState) - 병렬 처리

LangGraph의 TypedDict 상태 정의
"""

from typing import TypedDict, Optional, List
from core.ocr.interface import OcrStrategy, OcrExecutionResult


class ColumnState(TypedDict):
    """
    컬럼별 상태 (Idris2: ColumnState)

    각 컬럼은 독립적으로 처리됨 (병렬 가능)
    """
    column_index: int
    """컬럼 인덱스 (0: 왼쪽, 1: 오른쪽)"""

    image_path: Optional[str]
    """컬럼 이미지 경로"""

    found_problems: List[int]
    """이 컬럼에서 발견된 문제 번호들"""

    extracted_count: int
    """추출된 문제 수"""

    mathpix_verified: bool
    """Mathpix로 재검증 여부"""

    success: bool
    """이 컬럼 처리 성공 여부"""


class PageState(TypedDict):
    """
    페이지별 상태 (Idris2: PageState)

    각 페이지는 독립적으로 처리됨 (병렬 가능)
    """
    page_num: int
    """페이지 번호 (1부터 시작)"""

    image_path: Optional[str]
    """원본 페이지 이미지 경로"""

    column_count: int
    """컬럼 수 (1, 2, 3)"""

    column_states: List[ColumnState]
    """컬럼별 상태들 (병렬 처리)"""

    validated: bool
    """검증 완료 여부"""

    completed: bool
    """페이지 처리 완료 여부"""


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

    # 중간 결과 (Legacy - 순차 처리용)
    images: Optional[List[str]]
    """PDF 이미지들 (변환 후) - 이미지 경로 목록"""

    layouts: Optional[List[str]]
    """레이아웃 정보 - 레이아웃 JSON 경로 목록"""

    # 병렬 처리용 상태 (Idris2: PdfExtractionState)
    page_states: Optional[List[PageState]]
    """페이지별 상태들 (병렬 처리)"""

    total_pages: int
    """전체 페이지 수"""

    dpi: int
    """DPI 설정"""

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
