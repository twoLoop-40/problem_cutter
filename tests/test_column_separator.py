"""
Tests for column_separator module
"""

import pytest
import numpy as np
from pathlib import Path

from core.column_separator import (
    separate_columns,
    separate_two_columns_simple,
    merge_narrow_columns,
    get_column_count,
    split_to_linear,
    SeparationStrategy,
    ColumnRegion,
    SeparationResult
)


@pytest.fixture
def single_column_image():
    """1단 테스트 이미지 (600x800)"""
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255  # 흰색 배경
    # 텍스트 영역 (회색)
    img[100:300, 100:500] = [200, 200, 200]
    img[400:600, 100:500] = [200, 200, 200]
    return img


@pytest.fixture
def two_column_image():
    """2단 테스트 이미지 (1200x800, 중앙 구분선)"""
    img = np.ones((800, 1200, 3), dtype=np.uint8) * 255

    # 왼쪽 단
    img[100:300, 100:500] = [200, 200, 200]
    img[400:600, 100:500] = [200, 200, 200]

    # 오른쪽 단
    img[100:300, 700:1100] = [200, 200, 200]
    img[400:600, 700:1100] = [200, 200, 200]

    # 중앙 구분선 (x=600 근처)
    img[:, 598:602] = [0, 0, 0]

    return img


@pytest.fixture
def three_column_image():
    """3단 테스트 이미지 (1800x800)"""
    img = np.ones((800, 1800, 3), dtype=np.uint8) * 255

    # 첫 번째 단
    img[100:300, 100:450] = [200, 200, 200]

    # 두 번째 단
    img[100:300, 700:1050] = [200, 200, 200]

    # 세 번째 단
    img[100:300, 1300:1650] = [200, 200, 200]

    # 구분선
    img[:, 598:602] = [0, 0, 0]  # 첫 번째 구분선
    img[:, 1198:1202] = [0, 0, 0]  # 두 번째 구분선

    return img


class TestSeparateColumns:
    """separate_columns 함수 테스트"""

    def test_single_column(self, single_column_image):
        """1단 이미지는 분리하지 않음"""
        result = separate_columns(single_column_image)

        assert result.column_count == 1
        assert len(result.columns) == 1
        assert result.columns[0].width == 600
        assert result.columns[0].height == 800

    def test_two_columns(self, two_column_image):
        """2단 이미지를 올바르게 분리"""
        result = separate_columns(two_column_image)

        # 2단으로 감지되어야 함
        assert result.column_count >= 2
        assert len(result.columns) >= 2

        # 각 단의 크기가 합리적이어야 함
        for col in result.columns:
            assert col.width > 0
            assert col.height == 800

    def test_three_columns(self, three_column_image):
        """3단 이미지 분리"""
        result = separate_columns(three_column_image)

        # 최소 2단 이상으로 감지되어야 함
        assert result.column_count >= 2
        assert len(result.columns) >= 2

    def test_result_has_strategy(self, two_column_image):
        """결과에 전략 정보가 포함됨"""
        result = separate_columns(two_column_image)

        assert result.strategy in [
            SeparationStrategy.VERTICAL_LINES,
            SeparationStrategy.CONTENT_GAPS,
            SeparationStrategy.FIXED_MIDPOINT
        ]

    def test_original_dimensions_preserved(self, two_column_image):
        """원본 크기 정보가 보존됨"""
        result = separate_columns(two_column_image)

        assert result.original_width == 1200
        assert result.original_height == 800


class TestSeparateTwoColumnsSimple:
    """separate_two_columns_simple 함수 테스트"""

    def test_default_split(self, two_column_image):
        """기본 중앙 분리 (50:50)"""
        result = separate_two_columns_simple(two_column_image)

        assert result.column_count == 2
        assert len(result.columns) == 2

        # 정중앙에서 분리
        assert result.columns[0].right_x == 600
        assert result.columns[1].left_x == 600

    def test_custom_ratio(self, two_column_image):
        """사용자 지정 비율 (40:60)"""
        result = separate_two_columns_simple(two_column_image, split_ratio=0.4)

        assert result.column_count == 2
        assert result.columns[0].right_x == 480  # 1200 * 0.4
        assert result.columns[1].left_x == 480

    def test_strategy_is_fixed_midpoint(self, two_column_image):
        """전략이 FIXED_MIDPOINT로 설정됨"""
        result = separate_two_columns_simple(two_column_image)

        assert result.strategy == SeparationStrategy.FIXED_MIDPOINT


class TestColumnRegion:
    """ColumnRegion 데이터 클래스 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환"""
        img = np.ones((800, 600, 3), dtype=np.uint8) * 255
        col = ColumnRegion(
            index=0,
            left_x=0,
            right_x=600,
            width=600,
            height=800,
            image=img
        )

        d = col.to_dict()

        assert d["index"] == 0
        assert d["left_x"] == 0
        assert d["right_x"] == 600
        assert d["width"] == 600
        assert d["height"] == 800
        assert d["image_shape"] == (800, 600, 3)


class TestSeparationResult:
    """SeparationResult 클래스 테스트"""

    def test_get_linearized_image_single_column(self, single_column_image):
        """1단 선형화 (변화 없음)"""
        result = separate_columns(single_column_image)
        linear = result.get_linearized_image()

        # 크기 변화 없음
        assert linear.shape[0] == 800  # 높이
        assert linear.shape[1] == 600  # 너비

    def test_get_linearized_image_two_columns(self, two_column_image):
        """2단 선형화 (높이 2배)"""
        result = separate_two_columns_simple(two_column_image)
        linear = result.get_linearized_image()

        # 높이가 약 2배가 되어야 함
        assert linear.shape[0] >= 1600  # 800 * 2
        # 너비는 가장 넓은 단 기준
        assert linear.shape[1] <= 1200

    def test_save_columns(self, two_column_image, tmp_path):
        """단 저장 기능"""
        result = separate_two_columns_simple(two_column_image)
        saved_paths = result.save_columns(tmp_path, prefix="test")

        assert len(saved_paths) == 2
        assert all(path.exists() for path in saved_paths)
        assert saved_paths[0].name == "test_1.png"
        assert saved_paths[1].name == "test_2.png"


class TestMergeNarrowColumns:
    """merge_narrow_columns 함수 테스트"""

    def test_merge_narrow_columns(self):
        """좁은 단 병합"""
        # 3개 단 생성 (중간 단이 매우 좁음)
        img1 = np.ones((800, 500, 3), dtype=np.uint8) * 255
        img2 = np.ones((800, 50, 3), dtype=np.uint8) * 200  # 좁은 단
        img3 = np.ones((800, 500, 3), dtype=np.uint8) * 255

        columns = [
            ColumnRegion(0, 0, 500, 500, 800, img1),
            ColumnRegion(1, 500, 550, 50, 800, img2),
            ColumnRegion(2, 550, 1050, 500, 800, img3),
        ]

        result = SeparationResult(
            original_width=1050,
            original_height=800,
            column_count=3,
            strategy=SeparationStrategy.VERTICAL_LINES,
            columns=columns
        )

        # 15% 미만 너비 병합 (50px < 1050 * 0.15 = 157.5px)
        merged = merge_narrow_columns(result, min_width_ratio=0.15)

        # 좁은 단이 병합되어 2단으로 줄어들어야 함
        assert merged.column_count < 3

    def test_no_merge_needed(self, two_column_image):
        """병합이 필요 없는 경우"""
        result = separate_two_columns_simple(two_column_image)
        original_count = result.column_count

        merged = merge_narrow_columns(result, min_width_ratio=0.15)

        # 단 개수 변화 없음
        assert merged.column_count == original_count


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_get_column_count(self, single_column_image, two_column_image):
        """get_column_count 함수"""
        count1 = get_column_count(single_column_image)
        count2 = get_column_count(two_column_image)

        assert count1 == 1
        assert count2 >= 2

    def test_split_to_linear(self, two_column_image):
        """split_to_linear 함수"""
        linear = split_to_linear(two_column_image)

        assert isinstance(linear, np.ndarray)
        assert linear.shape[0] >= 800  # 높이가 원본보다 크거나 같음


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_image(self):
        """빈 이미지 처리"""
        empty = np.array([])

        with pytest.raises((ValueError, IndexError, TypeError)):
            separate_columns(empty)

    def test_very_small_image(self):
        """매우 작은 이미지"""
        small = np.ones((10, 10, 3), dtype=np.uint8) * 255

        # 에러 없이 처리되어야 함
        result = separate_columns(small)
        assert result.column_count >= 1

    def test_grayscale_image(self):
        """그레이스케일 이미지"""
        gray = np.ones((800, 600), dtype=np.uint8) * 255
        gray[100:300, 100:500] = 200

        result = separate_columns(gray)
        assert result.column_count >= 1

    def test_very_wide_image(self):
        """매우 넓은 이미지 (다단 가능성 높음)"""
        wide = np.ones((800, 3000, 3), dtype=np.uint8) * 255

        # 텍스트 영역 3개 배치
        wide[100:300, 300:600] = [200, 200, 200]
        wide[100:300, 1200:1500] = [200, 200, 200]
        wide[100:300, 2100:2400] = [200, 200, 200]

        result = separate_columns(wide)

        # 여러 단으로 감지될 가능성이 높음
        assert result.column_count >= 1
