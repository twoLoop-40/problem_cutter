"""문제/해설 추출 AgentTools"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np

from core.base import BBox
from core.image_cropper import crop_problems_from_page, visualize_boundaries
from core.problem_extractor import (
    BoundaryStrategy,
    ExtractionResult,
    detect_problem_boundaries,
    extract_problems,
    extract_solutions,
)
from core.ocr_engine import OcrResult
from core.result_validator import ValidationFeedback, validate_results

from .config import DEFAULT_MARGIN
from .types import AgentToolError, ToolDiagnostics, ToolResult

__all__ = [
    "find_problem_boundaries",
    "extract_problem_items",
    "extract_solution_items",
    "crop_problem_images",
    "validate_problem_numbers",
    "extract_problem_regions",
]


def find_problem_boundaries(
    strategy: BoundaryStrategy,
    layout,
    ocr_results: Sequence[OcrResult],
    all_boxes: Sequence[BBox],
) -> ToolResult:
    """문제 경계 탐지"""

    diagnostics = ToolDiagnostics()

    if not ocr_results:
        diagnostics.add_warning("OCR 결과가 비어 있습니다.")

    boundaries = detect_problem_boundaries(
        strategy,
        layout,
        list(ocr_results),
        list(all_boxes),
    )

    diagnostics.extras.update(
        {
            "boundary_count": len(boundaries),
            "strategy": strategy.value,
        }
    )

    if not boundaries:
        diagnostics.add_warning("문제 경계를 찾지 못했습니다.")

    result = ToolResult.ok(
        "문제 경계 탐지",
        boundaries=boundaries,
    )
    result.diagnostics = diagnostics
    return result


def extract_problem_items(
    pdf_path: str,
    page_num: int,
    layout,
    ocr_results: Sequence[OcrResult],
    all_boxes: Sequence[BBox],
) -> ToolResult:
    """문제 아이템 추출"""

    diagnostics = ToolDiagnostics()

    problems = extract_problems(
        pdf_path,
        page_num,
        layout,
        list(ocr_results),
        list(all_boxes),
    )

    diagnostics.extras.update({"problem_count": len(problems)})

    if not problems:
        diagnostics.add_warning("문제가 추출되지 않았습니다.")

    result = ToolResult.ok("문제 추출 완료", problems=problems)
    result.diagnostics = diagnostics
    return result


def extract_solution_items(
    pdf_path: str,
    page_num: int,
    layout,
    ocr_results: Sequence[OcrResult],
    all_boxes: Sequence[BBox],
) -> ToolResult:
    """해설 아이템 추출"""

    diagnostics = ToolDiagnostics()

    solutions = extract_solutions(
        pdf_path,
        page_num,
        layout,
        list(ocr_results),
        list(all_boxes),
    )

    diagnostics.extras.update({"solution_count": len(solutions)})

    if not solutions:
        diagnostics.add_warning("해설 추출 로직이 아직 구현되지 않았습니다.")

    result = ToolResult.ok("해설 추출", solutions=solutions)
    result.diagnostics = diagnostics
    return result


def crop_problem_images(
    image: np.ndarray,
    boundaries: Iterable[tuple[int, BBox]],
    output_dir: str,
    *,
    margin: int = DEFAULT_MARGIN,
    visualize: bool = False,
) -> ToolResult:
    """문제 영역을 잘라 이미지 저장"""

    diagnostics = ToolDiagnostics()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    boundary_list = list(boundaries)

    crop_results = crop_problems_from_page(
        image,
        boundary_list,
        str(output_path),
        margin=margin,
    )

    diagnostics.extras.update(
        {
            "saved": sum(1 for r in crop_results if r["success"]),
            "failed": sum(1 for r in crop_results if not r["success"]),
            "margin": margin,
        }
    )

    if visualize and boundary_list:
        vis_path = output_path / "boundaries_visualization.png"
        if not visualize_boundaries(image, boundary_list, str(vis_path)):
            diagnostics.add_warning("경계 시각화 저장에 실패했습니다.")
        else:
            diagnostics.extras["visualization"] = str(vis_path)

    result = ToolResult.ok(
        "문제 크롭 완료",
        results=crop_results,
        output_dir=str(output_path),
    )
    result.diagnostics = diagnostics
    return result


def validate_problem_numbers(
    pdf_path: str,
    detected_numbers: Sequence[int],
    expected_numbers: Optional[Sequence[int]] = None,
    metadata_path: Optional[str] = None,
) -> ToolResult:
    """문제 번호 검증"""

    diagnostics = ToolDiagnostics()

    feedback: ValidationFeedback = validate_results(
        pdf_path=pdf_path,
        detected_problems=list(detected_numbers),
        expected_problems=list(expected_numbers) if expected_numbers else None,
        metadata_path=metadata_path,
    )

    diagnostics.extras.update(
        {
            "accuracy": feedback.accuracy,
            "missing": feedback.missing_problems,
            "false_positives": feedback.false_positives,
        }
    )

    if not feedback.success:
        diagnostics.add_warning(feedback.message)

    result = ToolResult.ok("문제 번호 검증", feedback=feedback)
    result.diagnostics = diagnostics
    return result


def extract_problem_regions(
    image_path: str,
    found_problems: List[int],
) -> ToolResult:
    """
    이미지에서 문제 영역 추출 (LangGraph 워크플로우용)

    Idris2 명세: Specs/System/ProjectReorganization.idr

    Args:
        image_path: 컬럼 이미지 경로
        found_problems: 이 컬럼에서 발견된 문제 번호 리스트

    Returns:
        ToolResult with data:
            - regions: List[(problem_num, cropped_image)]
            - marker_count: 발견된 마커 수
    """
    import cv2
    from core.ocr_engine import parse_problem_number
    from core.ocr.interface import OcrInput
    from core.ocr.tesseract_plugin import TesseractEngine

    diagnostics = ToolDiagnostics()

    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        diagnostics.add_error(f"이미지 로드 실패: {image_path}")
        return ToolResult.fail("이미지 로드 실패", diagnostics=diagnostics)

    height, width = image.shape[:2]

    # Tesseract로 OCR 실행
    engine = TesseractEngine()
    ocr_input = OcrInput(image_path=image_path, languages=["kor", "eng"], dpi=300)

    try:
        ocr_output = engine.execute(ocr_input)
    except Exception as e:
        diagnostics.add_error(f"OCR 실행 실패: {str(e)}")
        return ToolResult.fail("OCR 실행 실패", diagnostics=diagnostics)

    # 문제 번호 마커 찾기
    markers = []  # (problem_num, y_pos, bbox)
    for block in ocr_output.blocks:
        prob_num = parse_problem_number(block.text)
        if prob_num is not None and prob_num in found_problems:
            y_pos = block.bbox[1]  # y1 (top)
            markers.append((prob_num, y_pos, block.bbox))

    diagnostics.extras["marker_count"] = len(markers)
    diagnostics.extras["found_problems"] = found_problems

    if not markers:
        diagnostics.add_warning(
            f"문제 번호 마커를 찾지 못했습니다. "
            f"OCR blocks: {len(ocr_output.blocks)}, "
            f"Expected: {found_problems}"
        )
        return ToolResult.ok(
            "마커 없음",
            regions=[],
            marker_count=0,
            diagnostics=diagnostics,
        )

    # Y 위치 순서로 정렬
    markers.sort(key=lambda m: m[1])

    # 문제 영역 추출
    problem_regions = []
    for i, (prob_num, y_pos, bbox) in enumerate(markers):
        # 시작 y: 문제 번호 위치에서 약간 위
        y_start = max(0, bbox[1] - 30)

        # 끝 y: 다음 문제 번호 직전 or 이미지 끝
        if i + 1 < len(markers):
            y_end = markers[i + 1][2][1] - 30
        else:
            y_end = height

        # 최소 높이 체크 (너무 작은 영역 제외)
        if y_end - y_start < 100:
            diagnostics.add_warning(
                f"문제 {prob_num}번 영역이 너무 작음 (높이: {y_end - y_start}px)"
            )
            continue

        # 문제 영역 crop
        problem_img = image[y_start:y_end, :]
        problem_regions.append((prob_num, problem_img))

    diagnostics.extras["region_count"] = len(problem_regions)

    if not problem_regions:
        diagnostics.add_warning("추출된 문제 영역이 없습니다.")

    result = ToolResult.ok(
        f"{len(problem_regions)}개 문제 영역 추출",
        regions=problem_regions,
        marker_count=len(markers),
    )
    result.diagnostics = diagnostics
    return result








