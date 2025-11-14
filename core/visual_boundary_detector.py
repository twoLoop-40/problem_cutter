"""
Visual Problem Boundary Detection (OCR 없이 이미지 분석)

핵심 아이디어:
- OCR은 확인용으로만 사용
- 시각적으로 이미지를 분석하여 문제 경계 추정
- 수평 프로젝션 + 컨투어 분석

Idris2 명세: Specs/System/VisualBoundaryDetection.idr (TODO)
"""

from typing import List, Tuple, Optional
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class VisualBoundary:
    """시각적으로 감지된 경계"""
    y_start: int
    y_end: int
    confidence: float  # 0.0 ~ 1.0
    text_density: float  # 텍스트 밀도


def detect_boundaries_by_projection(
    image: np.ndarray,
    min_gap_height: int = 50,
    min_section_height: int = 100,
) -> List[VisualBoundary]:
    """
    수평 프로젝션으로 문제 경계 감지

    Args:
        image: 컬럼 이미지 (grayscale or BGR)
        min_gap_height: 최소 공백 높이 (경계로 인식)
        min_section_height: 최소 섹션 높이 (너무 작은 섹션 제외)

    Returns:
        경계 리스트 [(y_start, y_end), ...]
    """
    # 1. Grayscale 변환
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    height, width = gray.shape

    # 2. 이진화 (텍스트 영역 강조)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 3. 수평 프로젝션 (각 Y 좌표의 검은 픽셀 수)
    projection = np.sum(binary, axis=1)  # shape: (height,)

    # 4. 정규화 (0 ~ 1)
    if projection.max() > 0:
        projection = projection / projection.max()

    # 5. 공백 영역 찾기 (projection < threshold)
    threshold = 0.05  # 5% 미만이면 공백으로 간주
    is_gap = projection < threshold

    # 6. 연속된 공백 찾기
    gaps = []
    in_gap = False
    gap_start = 0

    for y in range(height):
        if is_gap[y] and not in_gap:
            # 공백 시작
            gap_start = y
            in_gap = True
        elif not is_gap[y] and in_gap:
            # 공백 끝
            gap_end = y
            gap_height = gap_end - gap_start

            if gap_height >= min_gap_height:
                gaps.append((gap_start, gap_end))

            in_gap = False

    # 마지막 공백 처리
    if in_gap:
        gaps.append((gap_start, height))

    # 7. 공백으로 섹션 나누기
    boundaries = []
    prev_end = 0

    for gap_start, gap_end in gaps:
        y_start = prev_end
        y_end = gap_start

        section_height = y_end - y_start

        if section_height >= min_section_height:
            # 텍스트 밀도 계산
            section_projection = projection[y_start:y_end]
            text_density = section_projection.mean()

            boundaries.append(VisualBoundary(
                y_start=y_start,
                y_end=y_end,
                confidence=min(1.0, text_density * 2),  # 임의의 신뢰도
                text_density=text_density,
            ))

        prev_end = gap_end

    # 마지막 섹션
    if prev_end < height:
        y_start = prev_end
        y_end = height
        section_height = y_end - y_start

        if section_height >= min_section_height:
            section_projection = projection[y_start:y_end]
            text_density = section_projection.mean()

            boundaries.append(VisualBoundary(
                y_start=y_start,
                y_end=y_end,
                confidence=min(1.0, text_density * 2),
                text_density=text_density,
            ))

    return boundaries


def visualize_projection(
    image: np.ndarray,
    boundaries: List[VisualBoundary],
    output_path: str,
) -> bool:
    """
    프로젝션 결과 시각화

    Args:
        image: 원본 이미지
        boundaries: 감지된 경계
        output_path: 출력 경로

    Returns:
        성공 여부
    """
    # 컬러 복사
    if len(image.shape) == 2:
        vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        vis = image.copy()

    # 경계선 그리기
    for i, boundary in enumerate(boundaries):
        # 시작선 (녹색)
        cv2.line(vis, (0, boundary.y_start), (vis.shape[1], boundary.y_start), (0, 255, 0), 2)

        # 끝선 (빨간색)
        cv2.line(vis, (0, boundary.y_end), (vis.shape[1], boundary.y_end), (0, 0, 255), 2)

        # 섹션 번호
        cv2.putText(
            vis,
            f"#{i+1}",
            (10, boundary.y_start + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 0, 0),
            2,
        )

    return cv2.imwrite(output_path, vis)
