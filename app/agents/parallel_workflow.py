"""
LangGraph Parallel Workflow Implementation

Idris2 명세: Specs/System/LangGraphWorkflow.idr

병렬 처리 아키텍처:
- PageLevel: 페이지별 병렬 처리
- ColumnLevel: 컬럼별 병렬 처리
- Sequential: 순차 처리

핵심:
1. 페이지별로 독립적으로 컬럼 분리 (asyncio.gather)
2. 컬럼별로 독립적으로 OCR 실행 (asyncio.gather)
3. 결과 순서만 유지 (페이지 번호, 컬럼 인덱스로 정렬)
"""

import asyncio
from pathlib import Path
from typing import List, Tuple
import cv2

from langgraph.graph import StateGraph, END

from .state import ExtractionState, PageState, ColumnState
from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector
from core.ocr import OcrEngineRegistry, OcrInput
from core.ocr.parser import ocr_output_to_execution_result
from core.ocr.interface import DEFAULT_OCR_STRATEGY


# =============================================================================
# Helper Functions
# =============================================================================

async def process_page_column_separation(
    page_num: int, img_path: str, temp_dir: Path
) -> PageState:
    """
    단일 페이지의 컬럼 분리 (비동기)

    Returns:
        PageState with separated column images
    """
    print(f"[PageLevel] 페이지 {page_num} 컬럼 분리 시작")

    image = cv2.imread(img_path)
    detector = LayoutDetector()
    layout = detector.detect_layout(image)

    column_states: List[ColumnState] = []

    if layout.column_count.value >= 2:
        # 2단 이상: 컬럼별로 분리
        for col_idx, col_bound in enumerate(layout.columns):
            col_img = image[:, col_bound.left_x:col_bound.right_x]
            col_path = temp_dir / f"page_{page_num}_col_{col_idx}.png"
            cv2.imwrite(str(col_path), col_img)

            column_states.append(ColumnState(
                column_index=col_idx,
                image_path=str(col_path),
                found_problems=[],
                problem_bboxes=None,
                extracted_count=0,
                mathpix_verified=False,
                success=False,
            ))

        print(f"  → 페이지 {page_num}: {layout.column_count.value}단 분리 완료")
    else:
        # 1단: 원본 그대로 사용
        column_states.append(ColumnState(
            column_index=0,
            image_path=img_path,
            found_problems=[],
            problem_bboxes=None,
            extracted_count=0,
            mathpix_verified=False,
            success=False,
        ))

        print(f"  → 페이지 {page_num}: 1단 (분리 없음)")

    return PageState(
        page_num=page_num,
        image_path=img_path,
        column_count=layout.column_count.value,
        column_states=column_states,
        validated=False,
        completed=False,
    )


async def process_column_ocr(
    page_num: int, column_state: ColumnState, ocr_strategy
) -> ColumnState:
    """
    단일 컬럼의 OCR 실행 (비동기)

    Returns:
        Updated ColumnState with OCR results
    """
    col_idx = column_state["column_index"]
    img_path = column_state["image_path"]

    print(f"[ColumnLevel] 페이지 {page_num}, 컬럼 {col_idx} OCR 시작")

    # OCR 엔진 가져오기
    engine = OcrEngineRegistry.get(ocr_strategy.stage1_engine)
    if not engine:
        print(f"  → OCR 엔진 없음: {ocr_strategy.stage1_engine}")
        return {**column_state, "success": False}

    # OCR 실행 (동기 함수를 비동기로 실행)
    ocr_input = OcrInput(
        image_path=img_path,
        languages=["kor", "eng"],
        dpi=300,
    )

    # Vision 기반 경계 감지 (OCR 대신)
    from core.vision_boundary_detector import detect_boundaries_with_vision
    import cv2
    import os

    image = cv2.imread(img_path)
    if image is None:
        print(f"  → 이미지 로드 실패: {img_path}")
        return {**column_state, "success": False}

    # Vision으로 문제 경계 감지
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        problem_bboxes = await asyncio.to_thread(
            detect_boundaries_with_vision,
            image,
            num_slices=3,  # 컬럼 이미지는 작으므로 3조각만
            api_key=api_key,
        )

        # 감지된 문제 번호 추출
        detected_problems = list(problem_bboxes.keys())

        print(f"  → 페이지 {page_num}, 컬럼 {col_idx}: [Vision] {len(problem_bboxes)}개 문제 감지")

    except Exception as e:
        print(f"  → Vision 실패, OCR로 대체: {str(e)}")

        # Fallback: OCR 사용
        ocr_output = await asyncio.to_thread(engine.execute, ocr_input)
        execution_result = ocr_output_to_execution_result(
            ocr_output, ocr_strategy.stage1_engine
        )

        from core.ocr_engine import parse_problem_number

        height = image.shape[0]
        all_markers = []

        for block in ocr_output.blocks:
            prob_num = parse_problem_number(block.text)
            if prob_num is not None:
                y_top = block.bbox[1]
                y_bottom = block.bbox[3]
                all_markers.append((prob_num, y_top, y_bottom))

        all_markers.sort(key=lambda m: m[1])

        problem_bboxes = {}
        for i, (prob_num, y_top, y_bottom) in enumerate(all_markers):
            if i == 0:
                y_start = max(0, y_top - 50)
            else:
                prev_end = all_markers[i-1][2]
                y_start = max(0, (prev_end + y_top) // 2 - 30)

            if i + 1 < len(all_markers):
                next_start = all_markers[i + 1][1]
                y_end = min(height, (y_bottom + next_start) // 2 + 30)
            else:
                y_end = height

            if y_end - y_start >= 80:
                problem_bboxes[prob_num] = (y_start, y_end)

        detected_problems = execution_result.detected_problems
        print(f"  → 페이지 {page_num}, 컬럼 {col_idx}: [OCR Fallback] {len(problem_bboxes)}개 영역 계산")

    return ColumnState(
        column_index=col_idx,
        image_path=img_path,
        found_problems=detected_problems,
        problem_bboxes=problem_bboxes,
        extracted_count=len(detected_problems),
        mathpix_verified=False,
        success=True,
    )


# =============================================================================
# Node Implementations (병렬 처리)
# =============================================================================

def convert_pdf_node(state: ExtractionState) -> dict:
    """
    PDF → 이미지 변환 (Sequential)

    Idris2: ConvertPdfNode (parallelLevel = Sequential)
    """
    print(f"[Sequential] PDF 변환 시작: {state['pdf_path']}")

    images = pdf_to_images(state["pdf_path"], dpi=state.get("dpi", 300))

    # 이미지를 임시 파일로 저장
    temp_dir = Path(f"output/temp_{state['job_id']}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for i, img in enumerate(images):
        img_path = temp_dir / f"page_{i+1}.png"
        cv2.imwrite(str(img_path), img)
        image_paths.append(str(img_path))

    print(f"  → {len(images)}페이지 변환 완료")

    return {
        **state,
        "current_state": "SeparatingColumns",
        "images": image_paths,
        "total_pages": len(images),
        "page_states": None,  # 아직 초기화 안됨
        "progress": 10,
        "message": f"PDF 변환 완료: {len(images)}페이지",
    }


async def separate_columns_node_async(state: ExtractionState) -> dict:
    """
    컬럼 분리 (PageLevel 병렬)

    Idris2: SeparateColumnsNode (parallelLevel = PageLevel)

    각 페이지별로 병렬 처리:
    - asyncio.gather()로 모든 페이지 동시 처리
    - 결과는 페이지 번호 순서로 정렬
    """
    print(f"[PageLevel] 컬럼 분리 시작: {len(state['images'])}페이지")

    temp_dir = Path(f"output/temp_{state['job_id']}")

    # 페이지별 병렬 처리
    tasks = [
        process_page_column_separation(i + 1, img_path, temp_dir)
        for i, img_path in enumerate(state["images"])
    ]

    page_states = await asyncio.gather(*tasks)

    # 페이지 번호 순서로 정렬 (보장)
    page_states = sorted(page_states, key=lambda p: p["page_num"])

    total_columns = sum(len(p["column_states"]) for p in page_states)

    print(f"  → 컬럼 분리 완료: {total_columns}개 컬럼")

    return {
        **state,
        "current_state": "RunningOcrStage1",
        "page_states": page_states,
        "progress": 30,
        "message": f"컬럼 분리 완료: {total_columns}개 컬럼",
    }


def separate_columns_node(state: ExtractionState) -> dict:
    """동기 래퍼 (LangGraph는 동기 함수만 지원)"""
    return asyncio.run(separate_columns_node_async(state))


async def run_ocr_stage1_node_async(state: ExtractionState) -> dict:
    """
    Stage1 OCR (ColumnLevel 병렬)

    Idris2: DetectProblemsNode (parallelLevel = ColumnLevel)

    각 컬럼별로 병렬 처리:
    - asyncio.gather()로 모든 컬럼 동시 OCR
    - 결과는 페이지 번호 → 컬럼 인덱스 순서로 정렬
    """
    print(f"[ColumnLevel] OCR 시작")

    ocr_strategy = state["ocr_strategy"]
    tasks = []

    # 모든 페이지의 모든 컬럼에 대해 태스크 생성
    for page_state in state["page_states"]:
        page_num = page_state["page_num"]
        for col_state in page_state["column_states"]:
            tasks.append(process_column_ocr(page_num, col_state, ocr_strategy))

    # 병렬 실행
    all_column_results = await asyncio.gather(*tasks)

    # 결과를 페이지별로 재구성
    updated_page_states = []
    result_idx = 0

    for page_state in state["page_states"]:
        col_count = len(page_state["column_states"])
        updated_columns = all_column_results[result_idx:result_idx + col_count]
        result_idx += col_count

        # 디버깅: bbox 확인
        for i, col in enumerate(updated_columns):
            has_bbox = "problem_bboxes" in col and col["problem_bboxes"] is not None
            bbox_count = len(col["problem_bboxes"]) if has_bbox else 0
            print(f"    [DEBUG OCR] 페이지 {page_state['page_num']}, 컬럼 {i}: bbox={bbox_count}개")

        # TypedDict는 dict처럼 업데이트
        updated_page = dict(page_state)
        updated_page["column_states"] = updated_columns
        updated_page_states.append(updated_page)

    # 모든 문제 번호 수집
    all_problems = []
    for page_state in updated_page_states:
        for col_state in page_state["column_states"]:
            all_problems.extend(col_state["found_problems"])

    # 중복 제거 및 정렬
    all_problems = sorted(set(all_problems))

    print(f"  → OCR 완료: 총 {len(all_problems)}개 문제 감지")

    return {
        **state,
        "current_state": "ValidatingStage1",
        "page_states": updated_page_states,
        "detected_problems": all_problems,
        "progress": 60,
        "message": f"OCR 완료: {len(all_problems)}개 문제 감지",
    }


def run_ocr_stage1_node(state: ExtractionState) -> dict:
    """동기 래퍼"""
    return asyncio.run(run_ocr_stage1_node_async(state))


def validate_stage1_node(state: ExtractionState) -> dict:
    """
    Stage1 검증 (Sequential)

    Idris2: ValidateNode (parallelLevel = Sequential)
    """
    print(f"[Sequential] 검증 시작")

    detected = state.get("detected_problems", [])
    expected = state.get("expected_problems")
    if expected is None:
        expected = list(range(1, 21))  # 기본: 1-20

    missing = [n for n in expected if n not in detected]

    print(f"  → 검출: {len(detected)}개, 누락: {len(missing)}개")

    return {
        **state,
        "current_state": "DecidingNextAction",
        "expected_problems": expected,
        "missing_problems": missing,
        "progress": 70,
        "message": f"검증 완료: {len(missing)}개 누락",
    }


def decide_node(state: ExtractionState) -> dict:
    """
    Agent 판단 (Sequential)

    Idris2: DecideNode
    """
    print(f"[Sequential] Agent 판단 시작")

    missing = state.get("missing_problems", [])

    if len(missing) == 0:
        decision = "proceed"
    elif len(missing) <= 3:
        decision = "stage2"  # Mathpix (미구현)
    else:
        decision = "proceed"  # 부분 성공

    print(f"  → 판단: {decision}")

    return {
        **state,
        "current_state": "GeneratingFiles",
        "decision": decision,
        "progress": 75,
        "message": f"판단 완료: {decision}",
    }


def generate_files_node(state: ExtractionState) -> dict:
    """
    파일 생성 (Sequential)

    Idris2: MergeResultsNode (parallelLevel = Sequential)

    핵심: 컬럼 이미지에서 crop한 후, 같은 문제는 수평으로 병합
    """
    import numpy as np

    print(f"[Sequential] 파일 생성 시작")

    output_dir = Path(f"output/{Path(state['pdf_path']).stem}_parallel")
    output_dir.mkdir(parents=True, exist_ok=True)

    file_count = 0

    # 페이지별로 처리
    for page_state in state["page_states"]:
        page_num = page_state["page_num"]

        # 1. 문제별로 컬럼 조각들 수집
        problem_pieces = {}  # {prob_num: [(col_idx, cropped_img), ...]}

        for col_state in page_state["column_states"]:
            col_idx = col_state["column_index"]
            col_img_path = col_state.get("image_path")
            problem_bboxes = col_state.get("problem_bboxes")

            if not col_img_path or not problem_bboxes:
                continue

            # 컬럼 이미지 로드
            col_img = cv2.imread(col_img_path)
            if col_img is None:
                continue

            # 문제별로 crop
            for prob_num, (y_start, y_end) in problem_bboxes.items():
                if y_end - y_start < 80:
                    continue

                # 컬럼 이미지에서 crop
                cropped = col_img[y_start:y_end, :]

                if prob_num not in problem_pieces:
                    problem_pieces[prob_num] = []
                problem_pieces[prob_num].append((col_idx, cropped))

        # 2. 문제별로 컬럼 조각들을 수평 병합
        for prob_num in sorted(problem_pieces.keys()):
            pieces = problem_pieces[prob_num]

            # 컬럼 인덱스 순서로 정렬
            pieces.sort(key=lambda x: x[0])

            if len(pieces) == 1:
                # 단일 컬럼: 그대로 사용
                final_img = pieces[0][1]
            else:
                # 여러 컬럼: 수평 병합 (높이 맞추기)
                max_height = max(p[1].shape[0] for p in pieces)

                # 높이를 맞춰서 병합
                aligned_pieces = []
                for col_idx, img in pieces:
                    h, w = img.shape[:2]
                    if h < max_height:
                        # 위아래에 흰색 여백 추가
                        pad_top = 0
                        pad_bottom = max_height - h
                        img = cv2.copyMakeBorder(
                            img, pad_top, pad_bottom, 0, 0,
                            cv2.BORDER_CONSTANT, value=(255, 255, 255)
                        )
                    aligned_pieces.append(img)

                # 수평으로 연결
                final_img = np.hstack(aligned_pieces)

            # 파일 저장
            output_file = output_dir / f"{prob_num}_prb.png"
            cv2.imwrite(str(output_file), final_img)
            file_count += 1

            height = final_img.shape[0]
            col_count = len(pieces)
            print(f"    ✓ 페이지 {page_num}, 문제 {prob_num}번 저장 ({height}px, {col_count}개 컬럼)")

    print(f"  → 파일 생성 완료: {file_count}개")

    return {
        **state,
        "current_state": "CreatingZip",
        "output_dir": str(output_dir),
        "progress": 90,
        "message": f"파일 생성 완료: {file_count}개",
    }


def create_zip_node(state: ExtractionState) -> dict:
    """
    ZIP 생성 (Sequential)

    Idris2: EndNode (parallelLevel = Sequential)
    """
    print(f"[Sequential] ZIP 생성 시작")

    import zipfile

    output_dir = Path(state["output_dir"])
    zip_path = output_dir.parent / f"{output_dir.name}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in output_dir.glob("*_prb.png"):
            zipf.write(file, file.name)

    print(f"  → ZIP 생성 완료: {zip_path}")

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
        return "generate"  # Stage2 미구현
    else:
        return END


# =============================================================================
# Workflow Creation
# =============================================================================

def create_parallel_extraction_workflow():
    """
    병렬 처리 LangGraph 워크플로우 생성

    Idris2: LangGraphWorkflow (defaultWorkflow)
    """
    print("[Workflow] 병렬 처리 LangGraph 워크플로우 생성")

    workflow = StateGraph(ExtractionState)

    # Add nodes
    workflow.add_node("convert_pdf", convert_pdf_node)
    workflow.add_node("separate_columns", separate_columns_node)
    workflow.add_node("run_ocr_stage1", run_ocr_stage1_node)
    workflow.add_node("validate_stage1", validate_stage1_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate_files", generate_files_node)
    workflow.add_node("create_zip", create_zip_node)

    # Add edges
    workflow.set_entry_point("convert_pdf")
    workflow.add_edge("convert_pdf", "separate_columns")
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

    print("[Workflow] 병렬 처리 워크플로우 컴파일 완료")
    return app


def create_initial_state(
    job_id: str,
    pdf_path: str,
    ocr_strategy=DEFAULT_OCR_STRATEGY,
    dpi: int = 300,
) -> ExtractionState:
    """초기 상태 생성"""
    return ExtractionState(
        job_id=job_id,
        pdf_path=pdf_path,
        ocr_strategy=ocr_strategy,
        current_state="Initial",
        images=None,
        layouts=None,
        page_states=None,
        total_pages=0,
        dpi=dpi,
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
    from core.ocr.interface import OcrEngineType
    from core.ocr.tesseract_plugin import TesseractEngine

    OcrEngineRegistry.register(
        OcrEngineType.TESSERACT,
        TesseractEngine()
    )
    print("[Registry] Tesseract 엔진 등록 완료")
