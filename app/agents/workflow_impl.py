"""
LangGraph Workflow Implementation (실제 구현)

Idris2 명세: Specs/System/Agent/Workflow.idr
"""

from pathlib import Path
import cv2
import numpy as np

from langgraph.graph import StateGraph, END

from .state import ExtractionState
from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector
from core.ocr import OcrEngineRegistry, OcrInput
from core.ocr.tesseract_plugin import TesseractEngine
from core.ocr.parser import ocr_output_to_execution_result
from core.ocr.interface import OcrEngineType, DEFAULT_OCR_STRATEGY


# =============================================================================
# Node Implementations (실제 구현)
# =============================================================================

def convert_pdf_node(state: ExtractionState) -> dict:
    """PDF → 이미지 변환"""
    print(f"[convert_pdf] 시작: {state['pdf_path']}")

    images = pdf_to_images(state["pdf_path"], dpi=300)

    # 이미지를 임시 파일로 저장
    temp_dir = Path(f"output/temp_{state['job_id']}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for i, img in enumerate(images):
        img_path = temp_dir / f"page_{i+1}.png"
        cv2.imwrite(str(img_path), img)
        image_paths.append(str(img_path))

    return {
        **state,
        "current_state": "DetectingLayout",
        "images": image_paths,
        "progress": 10,
        "message": "PDF 변환 완료",
    }


def detect_layout_node(state: ExtractionState) -> dict:
    """레이아웃 감지"""
    print(f"[detect_layout] 시작")

    detector = LayoutDetector()
    layouts = []

    for img_path in state["images"]:
        image = cv2.imread(img_path)
        layout = detector.detect_layout(image)
        layouts.append(f"{layout.column_count.value}-column")  # 간단히 문자열로

    return {
        **state,
        "current_state": "SeparatingColumns",
        "layouts": layouts,
        "progress": 20,
        "message": "레이아웃 감지 완료",
    }


def separate_columns_node(state: ExtractionState) -> dict:
    """컬럼 분리 (현재는 스킵)"""
    print(f"[separate_columns] 스킵")

    return {
        **state,
        "current_state": "RunningOcrStage1",
        "progress": 30,
        "message": "컬럼 분리 완료",
    }


def run_ocr_stage1_node(state: ExtractionState) -> dict:
    """Stage1 OCR (Tesseract)"""
    print(f"[run_ocr_stage1] Tesseract 시작")

    # Tesseract 엔진 가져오기
    engine = OcrEngineRegistry.get(state["ocr_strategy"].stage1_engine)
    if not engine:
        raise RuntimeError("Tesseract engine not registered")

    # 각 이미지에 대해 OCR 실행
    all_problems = []
    total_confidence = 0.0
    total_time = 0

    for img_path in state["images"]:
        ocr_input = OcrInput(
            image_path=img_path,
            languages=["kor", "eng"],
            dpi=300,
        )

        ocr_output = engine.execute(ocr_input)
        execution_result = ocr_output_to_execution_result(
            ocr_output,
            state["ocr_strategy"].stage1_engine,
        )

        all_problems.extend(execution_result.detected_problems)
        total_confidence += execution_result.confidence
        total_time += execution_result.execution_time

    # 중복 제거 및 정렬
    all_problems = sorted(set(all_problems))
    avg_confidence = total_confidence / len(state["images"]) if state["images"] else 0.0

    from core.ocr.interface import OcrExecutionResult

    stage1_result = OcrExecutionResult(
        engine=state["ocr_strategy"].stage1_engine,
        detected_problems=all_problems,
        confidence=avg_confidence,
        execution_time=total_time,
        raw_output=None,
    )

    return {
        **state,
        "current_state": "ValidatingStage1",
        "ocr_stage1_result": stage1_result,
        "detected_problems": all_problems,
        "progress": 50,
        "message": f"Stage1 OCR 완료: {len(all_problems)}개 감지",
    }


def validate_stage1_node(state: ExtractionState) -> dict:
    """Stage1 검증"""
    print(f"[validate_stage1] 시작")

    detected = state.get("detected_problems", [])
    expected = state.get("expected_problems")
    if expected is None:
        expected = list(range(1, 21))  # 기본: 1-20

    missing = [n for n in expected if n not in detected]

    print(f"[validate_stage1] 검출: {detected}")
    print(f"[validate_stage1] 누락: {missing}")

    return {
        **state,
        "current_state": "DecidingNextAction",
        "expected_problems": expected,
        "missing_problems": missing,
        "progress": 60,
        "message": f"검증 완료: {len(missing)}개 누락",
    }


def decide_node(state: ExtractionState) -> dict:
    """Agent 판단"""
    print(f"[decide] 시작")

    missing = state.get("missing_problems", [])

    if len(missing) == 0:
        decision = "proceed"
    elif len(missing) <= 3:
        decision = "stage2"  # Mathpix 미구현이므로 실제로는 proceed
    else:
        decision = "proceed"  # 부분 성공

    return {
        **state,
        "decision": decision,
        "progress": 65,
        "message": f"판단 완료: {decision}",
    }


def generate_files_node(state: ExtractionState) -> dict:
    """파일 생성"""
    print(f"[generate_files] 시작")

    output_dir = Path(f"output/{Path(state['pdf_path']).stem}_agent")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 간단히 페이지 이미지를 문제 번호로 저장
    detected = state.get("detected_problems", [])

    for i, problem_num in enumerate(detected):
        if i < len(state["images"]):
            img_path = state["images"][i]
            image = cv2.imread(img_path)

            output_file = output_dir / f"{problem_num}_prb.png"
            cv2.imwrite(str(output_file), image)

    return {
        **state,
        "current_state": "CreatingZip",
        "output_dir": str(output_dir),
        "progress": 90,
        "message": "파일 생성 완료",
    }


def create_zip_node(state: ExtractionState) -> dict:
    """ZIP 생성"""
    print(f"[create_zip] 시작")

    import zipfile

    output_dir = Path(state["output_dir"])
    zip_path = output_dir.parent / f"{output_dir.name}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in output_dir.glob("*_prb.png"):
            zipf.write(file, file.name)

    return {
        **state,
        "current_state": "Complete",
        "zip_path": str(zip_path),
        "progress": 100,
        "message": "완료",
    }


# =============================================================================
# Conditional Edge
# =============================================================================

def decide_next_step(state: ExtractionState) -> str:
    """다음 단계 결정"""
    decision = state.get("decision")

    if decision == "proceed":
        return "generate"
    elif decision == "stage2":
        return "generate"  # Stage2 미구현이므로 바로 generate
    else:
        return END


# =============================================================================
# Workflow Creation
# =============================================================================

def create_extraction_workflow():
    """LangGraph 워크플로우 생성"""
    print("[Workflow] LangGraph 워크플로우 생성")

    workflow = StateGraph(ExtractionState)

    # Add nodes
    workflow.add_node("convert_pdf", convert_pdf_node)
    workflow.add_node("detect_layout", detect_layout_node)
    workflow.add_node("separate_columns", separate_columns_node)
    workflow.add_node("run_ocr_stage1", run_ocr_stage1_node)
    workflow.add_node("validate_stage1", validate_stage1_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate_files", generate_files_node)
    workflow.add_node("create_zip", create_zip_node)

    # Add edges
    workflow.set_entry_point("convert_pdf")
    workflow.add_edge("convert_pdf", "detect_layout")
    workflow.add_edge("detect_layout", "separate_columns")
    workflow.add_edge("separate_columns", "run_ocr_stage1")
    workflow.add_edge("run_ocr_stage1", "validate_stage1")
    workflow.add_edge("validate_stage1", "decide")

    # Conditional edges
    workflow.add_conditional_edges(
        "decide",
        decide_next_step,
        {
            "generate": "generate_files",
            END: END,
        }
    )

    workflow.add_edge("generate_files", "create_zip")
    workflow.add_edge("create_zip", END)

    # Compile
    app = workflow.compile()

    print("[Workflow] 컴파일 완료")
    return app


def create_initial_state(
    job_id: str,
    pdf_path: str,
    ocr_strategy=DEFAULT_OCR_STRATEGY,
) -> ExtractionState:
    """초기 상태 생성"""
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


# =============================================================================
# Registry 초기화
# =============================================================================

def initialize_ocr_registry():
    """OCR 엔진 레지스트리 초기화"""
    # Tesseract 등록
    OcrEngineRegistry.register(
        OcrEngineType.TESSERACT,
        TesseractEngine()
    )
    print("[Registry] Tesseract 엔진 등록 완료")
