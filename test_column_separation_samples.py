"""
실제 샘플 파일을 사용한 단 분리 테스트
"""

from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.column_separator import (
    separate_columns,
    separate_two_columns_simple,
    merge_narrow_columns,
    get_column_count
)
from core.pdf_converter import pdf_to_images
from PIL import Image
import numpy as np


def test_sample_1():
    """통합과학_1_샘플.pdf 테스트"""
    print("=" * 80)
    print("테스트 1: 통합과학_1_샘플.pdf")
    print("=" * 80)

    pdf_path = project_root / "samples" / "통합과학_1_샘플.pdf"

    # 1. PDF를 이미지로 변환
    print("\n[1단계] PDF → 이미지 변환")
    images = pdf_to_images(str(pdf_path), dpi=200)
    print(f"  변환 완료: {len(images)}개 페이지")

    if not images:
        print("  ❌ 이미지 변환 실패")
        return

    # 첫 번째 페이지로 테스트
    first_page = images[0]
    print(f"  페이지 크기: {first_page.shape[1]}x{first_page.shape[0]}")

    # 2. 단 개수 확인
    print("\n[2단계] 단 개수 감지")
    column_count = get_column_count(first_page)
    print(f"  감지된 단 개수: {column_count}단")

    # 3. 자동 단 분리
    print("\n[3단계] 자동 단 분리")
    result = separate_columns(first_page)

    print(f"  전략: {result.strategy.value}")
    print(f"  분리된 단 개수: {result.column_count}")
    print(f"\n  각 단 정보:")

    for i, col in enumerate(result.columns):
        width_percent = (col.width / result.original_width) * 100
        print(f"    단 {i+1}:")
        print(f"      - 위치: x={col.left_x}~{col.right_x}")
        print(f"      - 크기: {col.width}x{col.height} ({width_percent:.1f}%)")

    # 4. 결과 저장
    print("\n[4단계] 결과 저장")
    output_dir = project_root / "output" / "column_test_통합과학"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 원본 이미지 저장
    original_path = output_dir / "00_original.png"
    Image.fromarray(first_page).save(original_path)
    print(f"  원본: {original_path}")

    # 각 단 저장
    saved_paths = result.save_columns(output_dir, prefix="auto")
    for i, path in enumerate(saved_paths):
        print(f"  단 {i+1}: {path}")

    # 5. 단순 중앙 분리 비교
    print("\n[5단계] 단순 중앙 분리 비교")
    simple_result = separate_two_columns_simple(first_page)
    simple_paths = simple_result.save_columns(output_dir, prefix="simple")

    print(f"  단순 분리: {len(simple_paths)}개 파일")
    for i, (col, path) in enumerate(zip(simple_result.columns, simple_paths)):
        width_percent = (col.width / simple_result.original_width) * 100
        print(f"    단 {i+1}: {col.width}px ({width_percent:.1f}%) → {path.name}")

    # 6. 선형화
    print("\n[6단계] 1단 선형화")
    linear = result.get_linearized_image()
    linear_path = output_dir / "linearized.png"
    Image.fromarray(linear).save(linear_path)

    height_ratio = linear.shape[0] / result.original_height
    print(f"  원본 높이: {result.original_height}px")
    print(f"  선형화 높이: {linear.shape[0]}px ({height_ratio:.2f}x)")
    print(f"  저장: {linear_path}")

    print("\n✅ 테스트 1 완료")
    print(f"   결과 확인: {output_dir}")


def test_sample_2():
    """고3_사회탐구_사회문화_1p.pdf 테스트"""
    print("\n" + "=" * 80)
    print("테스트 2: 고3_사회탐구_사회문화_1p.pdf")
    print("=" * 80)

    pdf_path = project_root / "samples" / "고3_사회탐구_사회문화_1p.pdf"

    # 1. PDF → 이미지
    print("\n[1단계] PDF → 이미지 변환")
    images = pdf_to_images(str(pdf_path), dpi=200)
    print(f"  변환 완료: {len(images)}개 페이지")

    if not images:
        print("  ❌ 이미지 변환 실패")
        return

    first_page = images[0]
    print(f"  페이지 크기: {first_page.shape[1]}x{first_page.shape[0]}")

    # 2. 단 개수 확인
    print("\n[2단계] 단 개수 감지")
    column_count = get_column_count(first_page)
    print(f"  감지된 단 개수: {column_count}단")

    # 3. 자동 단 분리
    print("\n[3단계] 자동 단 분리")
    result = separate_columns(first_page)

    print(f"  전략: {result.strategy.value}")
    print(f"  분리된 단 개수: {result.column_count}")

    for i, col in enumerate(result.columns):
        width_percent = (col.width / result.original_width) * 100
        print(f"    단 {i+1}: {col.width}x{col.height} ({width_percent:.1f}%)")

    # 4. 좁은 단 병합 시도
    if result.column_count > 2:
        print("\n[4단계] 좁은 단 병합")
        merged = merge_narrow_columns(result, min_width_ratio=0.15)
        print(f"  병합 전: {result.column_count}단")
        print(f"  병합 후: {merged.column_count}단")

        if merged.column_count < result.column_count:
            print("  ✅ 좁은 단 병합 성공")
            result = merged
        else:
            print("  ℹ️ 병합할 좁은 단 없음")

    # 5. 결과 저장
    print("\n[5단계] 결과 저장")
    output_dir = project_root / "output" / "column_test_사회문화"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 원본
    original_path = output_dir / "00_original.png"
    Image.fromarray(first_page).save(original_path)
    print(f"  원본: {original_path}")

    # 각 단
    saved_paths = result.save_columns(output_dir, prefix="col")
    for i, path in enumerate(saved_paths):
        print(f"  단 {i+1}: {path}")

    # 선형화
    linear = result.get_linearized_image()
    linear_path = output_dir / "linearized.png"
    Image.fromarray(linear).save(linear_path)
    print(f"  선형화: {linear_path}")

    print("\n✅ 테스트 2 완료")
    print(f"   결과 확인: {output_dir}")


def compare_strategies():
    """여러 전략 비교"""
    print("\n" + "=" * 80)
    print("보너스: 분리 전략 비교")
    print("=" * 80)

    pdf_path = project_root / "samples" / "통합과학_1_샘플.pdf"

    print("\n[이미지 로드]")
    images = pdf_to_images(str(pdf_path), dpi=200)

    if not images:
        print("  이미지 변환 실패")
        return

    first_page = images[0]
    height, width = first_page.shape[:2]
    print(f"  페이지 크기: {width}x{height}")

    output_dir = project_root / "output" / "column_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 전략 1: 자동 감지
    print("\n[전략 1] 자동 감지")
    result_auto = separate_columns(first_page)
    paths_auto = result_auto.save_columns(output_dir, prefix="strategy1_auto")
    print(f"  단 개수: {result_auto.column_count}")
    print(f"  전략: {result_auto.strategy.value}")

    # 전략 2: 단순 중앙 (50:50)
    print("\n[전략 2] 중앙선 (50:50)")
    result_mid = separate_two_columns_simple(first_page, split_ratio=0.5)
    paths_mid = result_mid.save_columns(output_dir, prefix="strategy2_mid50")
    print(f"  단 개수: {result_mid.column_count}")
    print(f"  왼쪽: {result_mid.columns[0].width}px")
    print(f"  오른쪽: {result_mid.columns[1].width}px")

    # 전략 3: 45:55 비율
    print("\n[전략 3] 45:55 비율")
    result_45 = separate_two_columns_simple(first_page, split_ratio=0.45)
    paths_45 = result_45.save_columns(output_dir, prefix="strategy3_45-55")
    print(f"  왼쪽: {result_45.columns[0].width}px ({result_45.columns[0].width/width*100:.1f}%)")
    print(f"  오른쪽: {result_45.columns[1].width}px ({result_45.columns[1].width/width*100:.1f}%)")

    print("\n✅ 전략 비교 완료")
    print(f"   결과 확인: {output_dir}")

    # 요약
    print("\n📊 요약:")
    print(f"  자동 감지: {result_auto.column_count}단, {result_auto.strategy.value}")
    print(f"  중앙선 50%: 2단, 고정")
    print(f"  비율 45%: 2단, 고정")


def main():
    """모든 테스트 실행"""
    print("🔍 샘플 파일 단 분리 테스트")
    print("=" * 80)

    try:
        test_sample_1()
    except Exception as e:
        print(f"\n❌ 테스트 1 오류: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_sample_2()
    except Exception as e:
        print(f"\n❌ 테스트 2 오류: {e}")
        import traceback
        traceback.print_exc()

    try:
        compare_strategies()
    except Exception as e:
        print(f"\n❌ 전략 비교 오류: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("🎉 모든 테스트 완료!")
    print("=" * 80)
    print("\n결과 파일 위치:")
    print("  - output/column_test_통합과학/")
    print("  - output/column_test_사회문화/")
    print("  - output/column_comparison/")


if __name__ == "__main__":
    main()
