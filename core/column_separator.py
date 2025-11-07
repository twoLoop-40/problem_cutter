"""
다단 편집 PDF를 단별로 분리하는 모듈

주요 기능:
1. 다단 레이아웃 자동 감지 (1단/2단/3단)
2. 수직 구분선 또는 여백 기반 단 분리
3. 각 단을 개별 이미지로 추출
4. 선택적으로 1단으로 선형화

구현 기반:
- .specs/System/LayoutDetection.idr
- .specs/System/ProblemBoundary.idr
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image

from .base import VLine, Coord
from .layout_detector import LayoutDetector, PageLayout, ColumnCount


class SeparationStrategy(Enum):
    """단 분리 전략"""
    VERTICAL_LINES = "vertical_lines"  # 수직선 기반 (우선)
    CONTENT_GAPS = "content_gaps"      # 여백 기반 (대체)
    FIXED_MIDPOINT = "fixed_midpoint"  # 고정 중앙선 (단순)


@dataclass
class ColumnRegion:
    """분리된 단 영역 정보"""
    index: int              # 단 번호 (0부터 시작)
    left_x: int            # 왼쪽 경계 x 좌표
    right_x: int           # 오른쪽 경계 x 좌표
    width: int             # 단 너비
    height: int            # 단 높이
    image: np.ndarray      # 단 이미지

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (디버깅용)"""
        return {
            "index": self.index,
            "left_x": self.left_x,
            "right_x": self.right_x,
            "width": self.width,
            "height": self.height,
            "image_shape": self.image.shape
        }


@dataclass
class SeparationResult:
    """단 분리 결과"""
    original_width: int
    original_height: int
    column_count: int
    strategy: SeparationStrategy
    columns: List[ColumnRegion]

    def save_columns(self, output_dir: Path, prefix: str = "column") -> List[Path]:
        """각 단을 개별 파일로 저장

        Args:
            output_dir: 출력 디렉토리
            prefix: 파일명 접두사

        Returns:
            저장된 파일 경로 리스트
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []

        for col in self.columns:
            filename = f"{prefix}_{col.index + 1}.png"
            filepath = output_dir / filename
            Image.fromarray(col.image).save(filepath)
            saved_paths.append(filepath)

        return saved_paths

    def get_linearized_image(self) -> np.ndarray:
        """모든 단을 세로로 연결하여 1단 이미지 생성

        Returns:
            선형화된 단일 이미지 (세로로 긴 형태)
        """
        if not self.columns:
            raise ValueError("No columns to linearize")

        # 모든 단을 같은 너비로 맞춤 (최대 너비 기준)
        max_width = max(col.width for col in self.columns)

        padded_columns = []
        for col in self.columns:
            img = col.image

            # 너비가 부족하면 오른쪽에 흰색 패딩 추가
            if col.width < max_width:
                pad_width = max_width - col.width
                if len(img.shape) == 3:
                    # 컬러 이미지
                    padding = np.full((col.height, pad_width, img.shape[2]), 255, dtype=img.dtype)
                else:
                    # 그레이스케일 이미지
                    padding = np.full((col.height, pad_width), 255, dtype=img.dtype)
                img = np.hstack([img, padding])

            padded_columns.append(img)

        # 세로로 연결
        return np.vstack(padded_columns)


def separate_columns(
    image: Union[np.ndarray, str, Path],
    strategy: Optional[SeparationStrategy] = None,
    layout_detector: Optional[LayoutDetector] = None
) -> SeparationResult:
    """다단 편집 이미지를 단별로 분리

    주요 작동 방식:
    1. 이미지 로드 (경로 또는 numpy array)
    2. 레이아웃 감지 (단 개수 및 경계 파악)
    3. 분리 전략에 따라 단 분리
    4. 각 단을 개별 이미지로 추출

    Args:
        image: 입력 이미지 (numpy array, 파일 경로, Path 객체)
        strategy: 분리 전략 (None이면 자동 선택)
        layout_detector: LayoutDetector 인스턴스 (None이면 기본 설정 사용)

    Returns:
        SeparationResult 객체 (분리된 단들 포함)

    Examples:
        >>> # 기본 사용 (자동 감지)
        >>> result = separate_columns("test.png")
        >>> print(f"Detected {result.column_count} columns")
        >>>
        >>> # 각 단을 파일로 저장
        >>> result.save_columns(Path("output/columns"))
        >>>
        >>> # 1단으로 선형화
        >>> linearized = result.get_linearized_image()
    """
    # 1. 이미지 로드
    if isinstance(image, (str, Path)):
        image = np.array(Image.open(image))
    elif not isinstance(image, np.ndarray):
        raise TypeError(f"Unsupported image type: {type(image)}")

    height, width = image.shape[:2]

    # 2. 레이아웃 감지
    if layout_detector is None:
        layout_detector = LayoutDetector(
            min_line_length=height // 3,  # 페이지 높이의 1/3 이상
            line_thickness_threshold=5,
            gap_threshold=50
        )

    page_layout = layout_detector.detect_layout(image)

    # 3. 분리 전략 결정
    if strategy is None:
        # 감지 방법에 따라 자동 선택
        if page_layout.separator_lines:
            strategy = SeparationStrategy.VERTICAL_LINES
        else:
            strategy = SeparationStrategy.CONTENT_GAPS

    # 4. 단 분리 실행
    if page_layout.column_count == ColumnCount.ONE:
        # 1단 - 분리 불필요
        columns = [
            ColumnRegion(
                index=0,
                left_x=0,
                right_x=width,
                width=width,
                height=height,
                image=image
            )
        ]
    else:
        # 2단 이상 - 경계에 따라 분리
        columns = _split_by_boundaries(image, page_layout)

    return SeparationResult(
        original_width=width,
        original_height=height,
        column_count=len(columns),
        strategy=strategy,
        columns=columns
    )


def separate_two_columns_simple(
    image: Union[np.ndarray, str, Path],
    split_ratio: float = 0.5
) -> SeparationResult:
    """2단 편집을 간단하게 중앙선으로 분리

    복잡한 감지 없이 페이지를 정확히 중앙에서 분리합니다.
    확실히 2단 편집인 경우 빠르고 안정적입니다.

    Args:
        image: 입력 이미지
        split_ratio: 분리 비율 (0.5 = 정중앙)

    Returns:
        SeparationResult 객체

    Example:
        >>> # 정중앙에서 분리
        >>> result = separate_two_columns_simple("test.png")
        >>>
        >>> # 약간 왼쪽으로 치우쳐 분리 (왼쪽:오른쪽 = 45:55)
        >>> result = separate_two_columns_simple("test.png", split_ratio=0.45)
    """
    # 이미지 로드
    if isinstance(image, (str, Path)):
        image = np.array(Image.open(image))

    height, width = image.shape[:2]
    mid_x = int(width * split_ratio)

    # 왼쪽 단
    left_column = ColumnRegion(
        index=0,
        left_x=0,
        right_x=mid_x,
        width=mid_x,
        height=height,
        image=image[:, 0:mid_x]
    )

    # 오른쪽 단
    right_column = ColumnRegion(
        index=1,
        left_x=mid_x,
        right_x=width,
        width=width - mid_x,
        height=height,
        image=image[:, mid_x:width]
    )

    return SeparationResult(
        original_width=width,
        original_height=height,
        column_count=2,
        strategy=SeparationStrategy.FIXED_MIDPOINT,
        columns=[left_column, right_column]
    )


def _split_by_boundaries(image: np.ndarray, layout: PageLayout) -> List[ColumnRegion]:
    """레이아웃 정보를 기반으로 이미지를 단별로 분리

    Args:
        image: 입력 이미지
        layout: 감지된 페이지 레이아웃

    Returns:
        분리된 단 리스트
    """
    height = image.shape[0]
    columns = []

    for i, col_bound in enumerate(layout.columns):
        left_x = col_bound.left_x
        right_x = col_bound.right_x

        # 경계 보정 (이미지 범위 내로 제한)
        left_x = max(0, left_x)
        right_x = min(image.shape[1], right_x)

        if left_x >= right_x:
            continue  # 유효하지 않은 경계

        # 단 이미지 추출
        col_image = image[:, left_x:right_x]

        column = ColumnRegion(
            index=i,
            left_x=left_x,
            right_x=right_x,
            width=right_x - left_x,
            height=height,
            image=col_image
        )
        columns.append(column)

    return columns


def merge_narrow_columns(
    result: SeparationResult,
    min_width_ratio: float = 0.15
) -> SeparationResult:
    """너무 좁은 단을 인접 단과 병합

    잘못 감지된 좁은 단(예: 페이지 번호, 여백)을 제거합니다.

    Args:
        result: 원본 분리 결과
        min_width_ratio: 최소 단 너비 비율 (전체 너비 대비)

    Returns:
        병합된 새로운 SeparationResult
    """
    min_width = result.original_width * min_width_ratio
    filtered_columns = []

    pending_merge: Optional[ColumnRegion] = None

    for col in result.columns:
        if col.width < min_width:
            # 너무 좁음 - 다음 단과 병합 대기
            if pending_merge is None:
                pending_merge = col
            else:
                # 이전 대기 중인 단과 현재 단 병합
                pending_merge = _merge_two_columns(pending_merge, col)
        else:
            if pending_merge is not None:
                # 대기 중인 좁은 단을 현재 단과 병합
                merged = _merge_two_columns(pending_merge, col)
                filtered_columns.append(merged)
                pending_merge = None
            else:
                # 정상 단 추가
                filtered_columns.append(col)

    # 마지막에 대기 중인 단 처리
    if pending_merge is not None:
        if filtered_columns:
            # 마지막 단과 병합
            last_col = filtered_columns.pop()
            merged = _merge_two_columns(last_col, pending_merge)
            filtered_columns.append(merged)
        else:
            # 병합할 단이 없으면 그대로 추가
            filtered_columns.append(pending_merge)

    # 인덱스 재할당
    for i, col in enumerate(filtered_columns):
        col.index = i

    return SeparationResult(
        original_width=result.original_width,
        original_height=result.original_height,
        column_count=len(filtered_columns),
        strategy=result.strategy,
        columns=filtered_columns
    )


def _merge_two_columns(col1: ColumnRegion, col2: ColumnRegion) -> ColumnRegion:
    """두 단을 하나로 병합

    Args:
        col1: 첫 번째 단
        col2: 두 번째 단

    Returns:
        병합된 단
    """
    left_x = min(col1.left_x, col2.left_x)
    right_x = max(col1.right_x, col2.right_x)

    # 이미지도 병합 (가로로 연결)
    # 높이가 다르면 더 큰 높이에 맞춰 패딩
    max_height = max(col1.height, col2.height)

    def pad_height(img: np.ndarray, target_height: int) -> np.ndarray:
        if img.shape[0] >= target_height:
            return img
        pad_height = target_height - img.shape[0]
        if len(img.shape) == 3:
            padding = np.full((pad_height, img.shape[1], img.shape[2]), 255, dtype=img.dtype)
        else:
            padding = np.full((pad_height, img.shape[1]), 255, dtype=img.dtype)
        return np.vstack([img, padding])

    img1 = pad_height(col1.image, max_height)
    img2 = pad_height(col2.image, max_height)
    merged_image = np.hstack([img1, img2])

    return ColumnRegion(
        index=col1.index,  # 첫 번째 단의 인덱스 유지
        left_x=left_x,
        right_x=right_x,
        width=right_x - left_x,
        height=max_height,
        image=merged_image
    )


# 편의 함수들

def split_and_save(
    image_path: Union[str, Path],
    output_dir: Union[str, Path],
    prefix: str = "column"
) -> List[Path]:
    """이미지를 단 분리하고 바로 저장

    Args:
        image_path: 입력 이미지 경로
        output_dir: 출력 디렉토리
        prefix: 파일명 접두사

    Returns:
        저장된 파일 경로 리스트

    Example:
        >>> paths = split_and_save("test.png", "output", prefix="page1_col")
        >>> # output/page1_col_1.png, output/page1_col_2.png 생성
    """
    result = separate_columns(image_path)
    output_dir = Path(output_dir)
    return result.save_columns(output_dir, prefix)


def split_to_linear(
    image_path: Union[str, Path]
) -> np.ndarray:
    """이미지를 단 분리 후 1단으로 선형화

    Args:
        image_path: 입력 이미지 경로

    Returns:
        선형화된 1단 이미지 (세로로 긴 형태)

    Example:
        >>> linear_img = split_to_linear("test.png")
        >>> Image.fromarray(linear_img).save("linear.png")
    """
    result = separate_columns(image_path)
    return result.get_linearized_image()


def get_column_count(
    image: Union[np.ndarray, str, Path],
    layout_detector: Optional[LayoutDetector] = None
) -> int:
    """이미지의 단 개수만 빠르게 확인

    Args:
        image: 입력 이미지
        layout_detector: LayoutDetector 인스턴스 (선택)

    Returns:
        감지된 단 개수 (1, 2, 3)

    Example:
        >>> count = get_column_count("test.png")
        >>> print(f"This page has {count} column(s)")
    """
    result = separate_columns(image, layout_detector=layout_detector)
    return result.column_count
