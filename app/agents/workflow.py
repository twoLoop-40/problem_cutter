"""
LangGraph Workflow Definition

Idris2 명세: Specs/System/Agent/Workflow.idr

LangGraph StateGraph 기반 워크플로우 정의
"""

from typing import Dict, Any
from .state import ExtractionState
from core.ocr.interface import OcrStrategy, DEFAULT_OCR_STRATEGY


# =============================================================================
# Node Functions (LangGraph Nodes)
# =============================================================================

def convert_pdf_node(state: ExtractionState) -> ExtractionState:
    """
    PDF → 이미지 변환 Node

    Idris2: ConvertPdfNode
    """
    print(f"[Node: convert_pdf] PDF 변환 시작: {state['pdf_path']}")

    # TODO: 실제 PDF 변환 구현
    # from core.pdf_converter import pdf_to_images
    # images = pdf_to_images(state["pdf_path"], dpi=300)

    return {
        **state,
        "current_state": "DetectingLayout",
        "images": [],  # TODO: 실제 이미지 경로 목록
        "progress": 10,
        "message": "PDF → 이미지 변환 완료",
    }


def detect_layout_node(state: ExtractionState) -> ExtractionState:
    """
    레이아웃 감지 Node

    Idris2: DetectLayoutNode
    """
    print(f"[Node: detect_layout] 레이아웃 감지 시작")

    # TODO: 실제 레이아웃 감지 구현
    # from core.layout_detector import LayoutDetector
    # detector = LayoutDetector()
    # layouts = [detector.detect_layout(img) for img in state["images"]]

    return {
        **state,
        "current_state": "SeparatingColumns",
        "layouts": [],  # TODO: 실제 레이아웃 JSON 경로
        "progress": 20,
        "message": "레이아웃 감지 완료",
    }


def separate_columns_node(state: ExtractionState) -> ExtractionState:
    """
    컬럼 분리 Node

    Idris2: SeparateColumnsNode
    """
    print(f"[Node: separate_columns] 컬럼 분리 시작")

    return {
        **state,
        "current_state": "RunningOcrStage1",
        "progress": 30,
        "message": "컬럼 분리 완료",
    }


def run_ocr_stage1_node(state: ExtractionState) -> ExtractionState:
    """
    Stage1 OCR 실행 Node (Fast OCR)

    Idris2: RunOcrStage1Node
    """
    print(f"[Node: run_ocr_stage1] Stage1 OCR 시작")

    # TODO: 실제 OCR 실행 구현
    # from core.ocr import OcrEngineRegistry
    # engine = OcrEngineRegistry.get(state["ocr_strategy"].stage1_engine)
    # ocr_output = engine.execute(OcrInput(...))

    return {
        **state,
        "current_state": "ExtractingProblemsStage1",
        "ocr_stage1_result": None,  # TODO: 실제 OCR 결과
        "progress": 40,
        "message": "Stage1 OCR 실행 완료",
    }


def extract_problems_stage1_node(state: ExtractionState) -> ExtractionState:
    """
    문제 추출 Node (Stage1)

    Idris2: ExtractProblemsStage1Node
    """
    print(f"[Node: extract_problems_stage1] 문제 추출 시작")

    return {
        **state,
        "current_state": "ValidatingStage1",
        "detected_problems": [],  # TODO: 실제 감지된 문제 번호
        "progress": 50,
        "message": "문제 추출 완료 (Stage1)",
    }


def validate_stage1_node(state: ExtractionState) -> ExtractionState:
    """
    Stage1 검증 Node

    Idris2: ValidateStage1Node
    """
    print(f"[Node: validate_stage1] Stage1 검증 시작")

    # TODO: 실제 검증 구현
    detected = state.get("detected_problems", [])
    expected = state.get("expected_problems", list(range(1, 21)))

    missing = [n for n in expected if n not in detected]

    return {
        **state,
        "current_state": "DecidingNextAction",
        "missing_problems": missing,
        "progress": 60,
        "message": "Stage1 검증 완료",
    }


def decide_node(state: ExtractionState) -> ExtractionState:
    """
    판단 Node (LLM 또는 규칙 기반)

    Idris2: DecideNode
    """
    print(f"[Node: decide] Agent 판단 시작")

    missing = state.get("missing_problems", [])

    if len(missing) == 0:
        decision = "proceed"  # 파일 생성으로 진행
    elif len(missing) <= 3:
        decision = "stage2"   # Stage2 OCR 실행
    else:
        decision = "proceed"  # 부분 성공으로 처리

    return {
        **state,
        "current_state": "DecidingNextAction",
        "decision": decision,
        "progress": 65,
        "message": "Agent 판단 완료",
    }


def run_ocr_stage2_node(state: ExtractionState) -> ExtractionState:
    """
    Stage2 OCR 실행 Node (Accurate OCR)

    Idris2: RunOcrStage2Node
    """
    print(f"[Node: run_ocr_stage2] Stage2 OCR 시작")

    # TODO: Stage2 OCR 구현

    return {
        **state,
        "current_state": "ExtractingProblemsStage2",
        "ocr_stage2_result": None,  # TODO: 실제 OCR 결과
        "progress": 70,
        "message": "Stage2 OCR 실행 완료",
    }


def extract_problems_stage2_node(state: ExtractionState) -> ExtractionState:
    """
    문제 추출 Node (Stage2)

    Idris2: ExtractProblemsStage2Node
    """
    print(f"[Node: extract_problems_stage2] 문제 추출 시작 (Stage2)")

    return {
        **state,
        "current_state": "ValidatingFinal",
        "progress": 80,
        "message": "문제 추출 완료 (Stage2)",
    }


def validate_final_node(state: ExtractionState) -> ExtractionState:
    """
    최종 검증 Node

    Idris2: ValidateFinalNode
    """
    print(f"[Node: validate_final] 최종 검증 시작")

    return {
        **state,
        "current_state": "GeneratingFiles",
        "progress": 85,
        "message": "최종 검증 완료",
    }


def generate_files_node(state: ExtractionState) -> ExtractionState:
    """
    파일 생성 Node

    Idris2: GenerateFilesNode
    """
    print(f"[Node: generate_files] 파일 생성 시작")

    # TODO: 파일 생성 구현

    return {
        **state,
        "current_state": "CreatingZip",
        "output_dir": None,  # TODO: 실제 출력 디렉토리
        "progress": 90,
        "message": "파일 생성 완료",
    }


def create_zip_node(state: ExtractionState) -> ExtractionState:
    """
    ZIP 패키징 Node

    Idris2: CreateZipNode
    """
    print(f"[Node: create_zip] ZIP 패키징 시작")

    # TODO: ZIP 생성 구현

    return {
        **state,
        "current_state": "Complete",
        "zip_path": None,  # TODO: 실제 ZIP 경로
        "progress": 100,
        "message": "완료",
    }


# =============================================================================
# Conditional Edge Functions
# =============================================================================

def decide_next_step(state: ExtractionState) -> str:
    """
    다음 단계 결정 (Conditional Edge)

    Idris2: decideNextStep

    Returns:
        str: 다음 노드 이름 ("generate", "stage2", "abort")
    """
    decision = state.get("decision")

    if decision == "proceed":
        return "generate"
    elif decision == "stage2":
        return "stage2"
    else:
        return "abort"


# =============================================================================
# Workflow Creation
# =============================================================================

def create_extraction_workflow():
    """
    LangGraph 워크플로우 생성

    Idris2: defaultWorkflow

    Returns:
        CompiledGraph: 컴파일된 LangGraph 워크플로우
    """
    print("[Workflow] LangGraph 워크플로우 생성 시작")

    # TODO: 실제 LangGraph 구현
    # from langgraph.graph import StateGraph, END
    #
    # workflow = StateGraph(ExtractionState)
    #
    # # Add nodes
    # workflow.add_node("convert_pdf", convert_pdf_node)
    # workflow.add_node("detect_layout", detect_layout_node)
    # workflow.add_node("separate_columns", separate_columns_node)
    # workflow.add_node("run_ocr_stage1", run_ocr_stage1_node)
    # workflow.add_node("extract_problems_stage1", extract_problems_stage1_node)
    # workflow.add_node("validate_stage1", validate_stage1_node)
    # workflow.add_node("decide", decide_node)
    # workflow.add_node("run_ocr_stage2", run_ocr_stage2_node)
    # workflow.add_node("extract_problems_stage2", extract_problems_stage2_node)
    # workflow.add_node("validate_final", validate_final_node)
    # workflow.add_node("generate_files", generate_files_node)
    # workflow.add_node("create_zip", create_zip_node)
    #
    # # Add edges
    # workflow.set_entry_point("convert_pdf")
    # workflow.add_edge("convert_pdf", "detect_layout")
    # workflow.add_edge("detect_layout", "separate_columns")
    # workflow.add_edge("separate_columns", "run_ocr_stage1")
    # workflow.add_edge("run_ocr_stage1", "extract_problems_stage1")
    # workflow.add_edge("extract_problems_stage1", "validate_stage1")
    # workflow.add_edge("validate_stage1", "decide")
    #
    # # Conditional edges
    # workflow.add_conditional_edges(
    #     "decide",
    #     decide_next_step,
    #     {
    #         "generate": "generate_files",
    #         "stage2": "run_ocr_stage2",
    #         "abort": END,
    #     }
    # )
    #
    # workflow.add_edge("run_ocr_stage2", "extract_problems_stage2")
    # workflow.add_edge("extract_problems_stage2", "validate_final")
    # workflow.add_edge("validate_final", "generate_files")
    # workflow.add_edge("generate_files", "create_zip")
    # workflow.add_edge("create_zip", END)
    #
    # # Compile
    # app = workflow.compile()

    print("[Workflow] LangGraph 워크플로우 생성 완료 (스텁)")

    # 스텁 반환 (LangGraph 미설치 시)
    return None


def create_initial_state(
    job_id: str,
    pdf_path: str,
    ocr_strategy: OcrStrategy = DEFAULT_OCR_STRATEGY,
) -> ExtractionState:
    """
    초기 LangGraph 상태 생성

    Idris2: initialLangGraphState

    Args:
        job_id: Job ID
        pdf_path: PDF 경로
        ocr_strategy: OCR 전략

    Returns:
        ExtractionState: 초기 상태
    """
    return ExtractionState(
        job_id=job_id,
        pdf_path=pdf_path,
        ocr_strategy=ocr_strategy,
        current_state="Initial",
        images=None,
        layouts=None,
        ocr_stage1_result=None,
        ocr_stage2_result=None,
        detected_problems=[],
        expected_problems=None,
        missing_problems=[],
        decision=None,
        output_dir=None,
        zip_path=None,
        progress=0,
        message="대기 중",
        error=None,
    )
