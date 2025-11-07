"""
다단 편집 분리 데모 스크립트

이 스크립트는 column_separator.py의 사용법을 보여줍니다.
"""

from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.column_separator import (
    separate_columns,
    separate_two_columns_simple,
    split_and_save,
    split_to_linear,
    get_column_count,
    merge_narrow_columns
)
from PIL import Image
import numpy as np


def demo_basic_separation():
    """기본 사용: 자동 감지 및 분리"""
    print("=" * 60)
    print("Demo 1: 기본 단 분리 (자동 감지)")
    print("=" * 60)

    # 샘플 파일 경로
    sample_path = project_root / "samples" / "통합과학_1_샘플.pdf.png"

    if not sample_path.exists():
        # PNG가 없으면 PDF에서 이미지 추출 필요
        print(f"Sample not found: {sample_path}")
        print("PDF를 이미지로 변환해야 합니다.")
        return

    # 단 분리 실행
    result = separate_columns(sample_path)

    print(f"\n결과:")
    print(f"  원본 크기: {result.original_width}x{result.original_height}")
    print(f"  감지된 단 개수: {result.column_count}")
    print(f"  사용된 전략: {result.strategy.value}")
    print(f"\n각 단 정보:")

    for col in result.columns:
        print(f"  단 {col.index + 1}:")
        print(f"    - 위치: x={col.left_x}~{col.right_x}")
        print(f"    - 크기: {col.width}x{col.height}")

    # 결과 저장
    output_dir = project_root / "output" / "column_separation_demo"
    saved_paths = result.save_columns(output_dir, prefix="demo1_col")

    print(f"\n저장된 파일:")
    for path in saved_paths:
        print(f"  - {path}")

    return result


def demo_simple_split():
    """간단한 2단 분리 (중앙선 기준)"""
    print("\n" + "=" * 60)
    print("Demo 2: 간단한 2단 분리 (중앙선)")
    print("=" * 60)

    sample_path = project_root / "samples" / "통합과학_1_샘플.pdf.png"

    if not sample_path.exists():
        print(f"Sample not found: {sample_path}")
        return

    # 정중앙에서 분리
    result = separate_two_columns_simple(sample_path, split_ratio=0.5)

    print(f"\n결과:")
    print(f"  단 개수: {result.column_count}")
    print(f"  전략: {result.strategy.value}")

    for col in result.columns:
        print(f"  단 {col.index + 1}: {col.width}x{col.height}")

    # 저장
    output_dir = project_root / "output" / "column_separation_demo"
    saved_paths = result.save_columns(output_dir, prefix="demo2_simple")

    print(f"\n저장 완료: {len(saved_paths)}개 파일")


def demo_linearization():
    """1단으로 선형화"""
    print("\n" + "=" * 60)
    print("Demo 3: 다단 → 1단 선형화")
    print("=" * 60)

    sample_path = project_root / "samples" / "통합과학_1_샘플.pdf.png"

    if not sample_path.exists():
        print(f"Sample not found: {sample_path}")
        return

    # 단 분리
    result = separate_columns(sample_path)

    print(f"원본: {result.column_count}단")

    # 선형화
    linear_image = result.get_linearized_image()

    print(f"선형화 결과: {linear_image.shape[1]}x{linear_image.shape[0]}")
    print(f"높이 증가: {result.original_height} → {linear_image.shape[0]} "
          f"({linear_image.shape[0] / result.original_height:.2f}x)")

    # 저장
    output_dir = project_root / "output" / "column_separation_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "demo3_linear.png"

    Image.fromarray(linear_image).save(output_path)
    print(f"\n저장: {output_path}")


def demo_narrow_column_merge():
    """좁은 단 병합"""
    print("\n" + "=" * 60)
    print("Demo 4: 좁은 단 병합")
    print("=" * 60)

    sample_path = project_root / "samples" / "통합과학_1_샘플.pdf.png"

    if not sample_path.exists():
        print(f"Sample not found: {sample_path}")
        return

    # 단 분리
    result = separate_columns(sample_path)

    print(f"병합 전: {result.column_count}단")
    for col in result.columns:
        print(f"  단 {col.index + 1}: 너비 {col.width}px "
              f"({col.width / result.original_width * 100:.1f}%)")

    # 너무 좁은 단 병합 (전체 너비의 15% 미만)
    merged_result = merge_narrow_columns(result, min_width_ratio=0.15)

    print(f"\n병합 후: {merged_result.column_count}단")
    for col in merged_result.columns:
        print(f"  단 {col.index + 1}: 너비 {col.width}px "
              f"({col.width / merged_result.original_width * 100:.1f}%)")

    # 저장
    output_dir = project_root / "output" / "column_separation_demo"
    saved_paths = merged_result.save_columns(output_dir, prefix="demo4_merged")

    print(f"\n저장 완료: {len(saved_paths)}개 파일")


def demo_convenience_functions():
    """편의 함수들"""
    print("\n" + "=" * 60)
    print("Demo 5: 편의 함수")
    print("=" * 60)

    sample_path = project_root / "samples" / "통합과학_1_샘플.pdf.png"

    if not sample_path.exists():
        print(f"Sample not found: {sample_path}")
        return

    # 1. 단 개수만 확인
    count = get_column_count(sample_path)
    print(f"감지된 단 개수: {count}")

    # 2. 분리 + 저장 (한 번에)
    output_dir = project_root / "output" / "column_separation_demo"
    paths = split_and_save(sample_path, output_dir, prefix="demo5_quick")
    print(f"\n빠른 저장: {len(paths)}개 파일")

    # 3. 선형화 (한 번에)
    linear = split_to_linear(sample_path)
    print(f"빠른 선형화: {linear.shape}")


def create_test_image():
    """테스트용 2단 이미지 생성"""
    print("\n" + "=" * 60)
    print("보너스: 테스트 이미지 생성")
    print("=" * 60)

    # 2단 테스트 이미지 생성 (800x600, 중앙에 구분선)
    width, height = 800, 600
    image = np.ones((height, width, 3), dtype=np.uint8) * 255  # 흰색 배경

    # 왼쪽 단에 텍스트 영역 (회색 박스)
    image[50:200, 50:350] = [200, 200, 200]
    image[250:400, 50:350] = [200, 200, 200]

    # 오른쪽 단에 텍스트 영역
    image[50:200, 450:750] = [200, 200, 200]
    image[250:400, 450:750] = [200, 200, 200]

    # 중앙 구분선 (검은색)
    image[:, 398:402] = [0, 0, 0]

    # 저장
    output_dir = project_root / "output" / "column_separation_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    test_path = output_dir / "test_two_columns.png"

    Image.fromarray(image).save(test_path)
    print(f"테스트 이미지 생성: {test_path}")

    # 테스트 이미지로 분리 시연
    result = separate_columns(test_path)
    print(f"\n테스트 이미지 분리 결과:")
    print(f"  단 개수: {result.column_count}")
    print(f"  전략: {result.strategy.value}")

    saved_paths = result.save_columns(output_dir, prefix="test_col")
    print(f"  저장: {len(saved_paths)}개 파일")


def main():
    """모든 데모 실행"""
    print("다단 편집 분리 데모")
    print("=" * 60)

    # 테스트 이미지 생성 (실제 샘플이 없을 경우 대체)
    create_test_image()

    # 각 데모 실행
    try:
        demo_basic_separation()
    except Exception as e:
        print(f"Demo 1 실패: {e}")

    try:
        demo_simple_split()
    except Exception as e:
        print(f"Demo 2 실패: {e}")

    try:
        demo_linearization()
    except Exception as e:
        print(f"Demo 3 실패: {e}")

    try:
        demo_narrow_column_merge()
    except Exception as e:
        print(f"Demo 4 실패: {e}")

    try:
        demo_convenience_functions()
    except Exception as e:
        print(f"Demo 5 실패: {e}")

    print("\n" + "=" * 60)
    print("데모 완료!")
    print("결과 확인: output/column_separation_demo/")
    print("=" * 60)


if __name__ == "__main__":
    main()
