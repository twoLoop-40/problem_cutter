"""
Mathpix 좌표 기반 문제 추출

명세: .specs/System/MathpixCoordinateExtraction.idr

이 모듈은 Mathpix .lines.json의 정확한 좌표를 사용하여
Tesseract가 놓친 문제를 직접 추출합니다.

워크플로우:
1. Mathpix .lines.json에서 문제 번호 찾기
2. 문제 번호의 bounding box 추출
3. 영역 전략 결정 (BetweenMarkers / ToPageEnd / FixedHeight)
4. 좌표로 이미지 자르기
"""

import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image

from .types import ToolResult, ToolDiagnostics


# ============================================================================
# 데이터 타입 (명세: MathpixCoordinateExtraction)
# ============================================================================

@dataclass
class MathpixBBox:
    """Mathpix 바운딩 박스 (명세: MathpixBBox)"""
    top_left_x: int
    top_left_y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, region: Dict[str, int]) -> 'MathpixBBox':
        """Dict에서 BBox 생성"""
        return cls(
            top_left_x=region['top_left_x'],
            top_left_y=region['top_left_y'],
            width=region['width'],
            height=region['height']
        )


@dataclass
class ProblemMarker:
    """문제 번호 마커 (명세: ProblemMarker)"""
    number: int
    bbox: MathpixBBox
    confidence: float
    source: str  # "mathpix"


# ============================================================================
# 문제 번호 매칭 (명세: matchesProblemPattern)
# ============================================================================

def matches_problem_pattern(text: str) -> Optional[int]:
    """
    텍스트가 문제 번호 패턴과 매칭되는가?

    명세: matchesProblemPattern
    패턴: "숫자." 또는 "숫자," (Tesseract 오인식 대비)

    Args:
        text: 검사할 텍스트

    Returns:
        문제 번호 (1~100) 또는 None

    Examples:
        >>> matches_problem_pattern("3. 다음은")
        3
        >>> matches_problem_pattern("3, 다음은")  # OCR 오인식
        3
        >>> matches_problem_pattern("문제 3번")
        None
    """
    text = text.strip()

    # 패턴: 줄 시작에 "숫자[.,]" (공백 포함)
    match = re.match(r'^(\d+)[.,]\s', text)

    if match:
        num = int(match.group(1))
        if 1 <= num <= 100:
            return num

    return None


# ============================================================================
# JSON에서 문제 마커 찾기 (명세: findProblemMarkers)
# ============================================================================

def find_problem_markers_from_json(
    mathpix_json: Dict[str, Any],
    missing_numbers: List[int],
    page_num: int = 1,
    column_image: Optional[np.ndarray] = None
) -> List[ProblemMarker]:
    """
    Mathpix .lines.json에서 문제 번호 마커 찾기 + 좌표 스케일링

    명세: Implementation.findProblemMarkers

    ⚠️ 중요: Mathpix 좌표는 원본 PDF 기준이므로 스케일링 필요!

    Args:
        mathpix_json: Mathpix .lines.json 데이터
        missing_numbers: 찾을 문제 번호 리스트
        page_num: 페이지 번호 (기본 1)
        column_image: 컬럼 이미지 (스케일링 계산용)

    Returns:
        발견된 ProblemMarker 리스트 (스케일링 적용됨)
    """
    markers = []

    # 페이지 찾기
    pages = mathpix_json.get('pages', [])
    target_page = None

    for page in pages:
        if page.get('page') == page_num:
            target_page = page
            break

    if not target_page:
        return markers

    # 스케일 팩터 계산
    page_width = target_page.get('page_width', 0)
    page_height = target_page.get('page_height', 0)

    scale_x = 1.0
    scale_y = 1.0

    if column_image is not None and page_width > 0 and page_height > 0:
        img_height, img_width = column_image.shape[:2]
        scale_x = img_width / page_width
        scale_y = img_height / page_height
        print(f"  📐 좌표 스케일 팩터: X={scale_x:.4f}, Y={scale_y:.4f}")

    # 각 line 검사
    lines = target_page.get('lines', [])

    for line in lines:
        text = line.get('text', '')
        problem_num = matches_problem_pattern(text)

        if problem_num and problem_num in missing_numbers:
            # 좌표 추출
            region = line.get('region')
            if not region:
                continue

            # 원본 좌표
            orig_bbox = MathpixBBox.from_dict(region)

            # 스케일링 적용
            scaled_bbox = MathpixBBox(
                top_left_x=int(orig_bbox.top_left_x * scale_x),
                top_left_y=int(orig_bbox.top_left_y * scale_y),
                width=int(orig_bbox.width * scale_x),
                height=int(orig_bbox.height * scale_y)
            )

            confidence = line.get('confidence', 0.0)

            marker = ProblemMarker(
                number=problem_num,
                bbox=scaled_bbox,
                confidence=confidence,
                source="mathpix"
            )

            markers.append(marker)

    return markers


# ============================================================================
# 좌표로 이미지 추출 (명세: cropImageRegion)
# ============================================================================

def estimate_problem_region(
    marker: ProblemMarker,
    next_marker: Optional[ProblemMarker],
    page_height: int,
    default_height: int = 800
) -> Tuple[int, int, int, int]:
    """
    문제 영역 추정

    명세: calculateRegion

    전략:
    - BetweenMarkers: marker부터 next_marker 직전까지
    - ToPageEnd: marker부터 페이지 끝까지
    - FixedHeight: marker부터 고정 높이

    Args:
        marker: 현재 문제 마커
        next_marker: 다음 문제 마커 (없으면 None)
        page_height: 페이지 전체 높이
        default_height: 기본 높이 (마커만 있을 때)

    Returns:
        (x, y, width, height) tuple
    """
    x = 0  # 컬럼 전체 너비 사용
    y = marker.bbox.top_left_y
    width = 1000  # 컬럼 전체 너비 (실제 이미지 너비로 조정)

    if next_marker:
        # 전략 1: BetweenMarkers
        height = next_marker.bbox.top_left_y - y
    elif y + default_height <= page_height:
        # 전략 3: FixedHeight
        height = default_height
    else:
        # 전략 2: ToPageEnd
        height = page_height - y

    return (x, y, width, height)


def extract_problem_by_coordinates(
    column_image: np.ndarray,
    marker: ProblemMarker,
    next_marker: Optional[ProblemMarker] = None,
    default_height: int = 800
) -> np.ndarray:
    """
    좌표로 직접 이미지 자르기

    명세: coordinateExtractionSucceeds

    Args:
        column_image: 컬럼 이미지 (numpy array)
        marker: 문제 번호 마커
        next_marker: 다음 문제 마커 (옵션)
        default_height: 기본 높이

    Returns:
        추출된 문제 이미지 (numpy array)
    """
    img_height, img_width = column_image.shape[:2]

    # 영역 계산
    x, y, width, height = estimate_problem_region(
        marker, next_marker, img_height, default_height
    )

    # 이미지 범위 내로 클리핑
    x = max(0, min(x, img_width))
    y = max(0, min(y, img_height))
    width = min(width, img_width - x)
    height = min(height, img_height - y)

    # 이미지 자르기
    cropped = column_image[y:y+height, x:x+width]

    return cropped


# ============================================================================
# 통합 함수
# ============================================================================

def extract_problems_with_mathpix_coordinates(
    column_image: np.ndarray,
    mathpix_json: Dict[str, Any],
    missing_numbers: List[int],
    page_num: int = 1
) -> ToolResult:
    """
    Mathpix 좌표로 문제 추출 (통합 함수)

    Args:
        column_image: 컬럼 이미지
        mathpix_json: Mathpix .lines.json 데이터
        missing_numbers: 추출할 문제 번호 리스트
        page_num: 페이지 번호

    Returns:
        ToolResult with extracted problems
    """
    diagnostics = ToolDiagnostics()
    diagnostics.add_info(f"Mathpix 좌표 기반 추출 시작: {len(missing_numbers)}개 문제")

    try:
        # 1. JSON에서 마커 찾기
        markers = find_problem_markers_from_json(mathpix_json, missing_numbers, page_num)

        if not markers:
            return ToolResult(
                success=False,
                message=f"Mathpix JSON에서 문제 번호를 찾을 수 없습니다: {missing_numbers}",
                data={"extracted": []},
                diagnostics=diagnostics
            )

        diagnostics.add_success(f"발견된 마커: {[m.number for m in markers]}")

        # 2. 마커를 번호 순으로 정렬
        markers.sort(key=lambda m: m.number)

        # 3. 각 마커로 이미지 추출
        extracted = []

        for i, marker in enumerate(markers):
            # 다음 마커 (영역 추정용)
            next_marker = markers[i + 1] if i + 1 < len(markers) else None

            # 이미지 자르기
            problem_img = extract_problem_by_coordinates(
                column_image,
                marker,
                next_marker
            )

            extracted.append({
                "number": marker.number,
                "image": problem_img,
                "bbox": (0, marker.bbox.top_left_y, problem_img.shape[1], problem_img.shape[0]),
                "source": "mathpix_coordinates",
                "confidence": marker.confidence
            })

            diagnostics.add_success(
                f"✓ 문제 {marker.number}번: {problem_img.shape[1]}×{problem_img.shape[0]}px"
            )

        return ToolResult(
            success=True,
            message=f"✅ Mathpix 좌표로 {len(extracted)}개 문제 추출 성공",
            data={"extracted": extracted},
            diagnostics=diagnostics
        )

    except Exception as e:
        diagnostics.add_error(f"추출 오류: {str(e)}")
        return ToolResult(
            success=False,
            message=f"Mathpix 좌표 추출 실패: {str(e)}",
            data={"extracted": []},
            diagnostics=diagnostics
        )


if __name__ == "__main__":
    print("=" * 80)
    print("Mathpix 좌표 기반 추출 툴")
    print("=" * 80)
    print("\n명세: .specs/System/MathpixCoordinateExtraction.idr")
    print("\n사용 예시:")
    print("""
from AgentTools.mathpix_coordinate import extract_problems_with_mathpix_coordinates

# Mathpix .lines.json 데이터와 컬럼 이미지로 직접 추출
result = extract_problems_with_mathpix_coordinates(
    column_image=col_image,
    mathpix_json=lines_json,
    missing_numbers=[3, 4],
    page_num=1
)

if result.success:
    for item in result.data["extracted"]:
        print(f"문제 {item['number']}번: {item['image'].shape}")
""")
