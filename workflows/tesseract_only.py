"""
생명과학 샘플 파일 테스트 - 전체 파이프라인

워크플로우:
1. PDF → 이미지 변환
2. 단 분리
3. 문제 번호별 추출
"""

from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.pdf_converter import pdf_to_images
from core.column_separator import separate_columns
from extract_problems_strict import (
    detect_problem_numbers_strict,
    extract_problems_by_markers,
    trim_whitespace,
    process_column_image
)
from PIL import Image
import numpy as np


def test_biology_sample():
    """생명과학 샘플 전체 테스트"""

    print("=" * 80)
    print("생명과학Ⅰ 문항지 테스트")
    print("=" * 80)

    # 파일 경로
    pdf_path = project_root / "samples" / "고3_과학탐구_생명과학Ⅰ_문항지.pdf"
    output_base = project_root / "output" / "생명과학"

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    print(f"\n입력 파일: {pdf_path.name}")

    # 1단계: PDF → 이미지
    print("\n" + "=" * 80)
    print("[1단계] PDF → 이미지 변환")
    print("=" * 80)

    images = pdf_to_images(str(pdf_path), dpi=200)

    if not images:
        print("❌ 이미지 변환 실패")
        return

    print(f"✓ 변환 완료: {len(images)}개 페이지")

    # 각 페이지 처리
    total_problems = 0

    for page_num, page_image in enumerate(images, 1):
        print(f"\n{'='*80}")
        print(f"[페이지 {page_num}/{len(images)}]")
        print(f"{'='*80}")

        height, width = page_image.shape[:2]
        print(f"이미지 크기: {width}×{height}px")

        # 출력 디렉토리
        page_output = output_base / f"page_{page_num}"
        page_output.mkdir(parents=True, exist_ok=True)

        # 원본 저장
        original_path = page_output / "00_original.png"
        Image.fromarray(page_image).save(original_path)
        print(f"원본 저장: {original_path.name}")

        # 2단계: 단 분리
        print(f"\n[2단계] 단 분리")
        result = separate_columns(page_image)

        print(f"  감지된 단: {result.column_count}개")
        print(f"  전략: {result.strategy.value}")

        # 각 단 저장
        for i, col in enumerate(result.columns):
            col_path = page_output / f"col_{i+1}.png"
            Image.fromarray(col.image).save(col_path)
            width_pct = (col.width / result.original_width) * 100
            print(f"  단 {i+1}: {col.width}×{col.height}px ({width_pct:.1f}%) → {col_path.name}")

        # 선형화 저장
        linear = result.get_linearized_image()
        linear_path = page_output / "linearized.png"
        Image.fromarray(linear).save(linear_path)
        print(f"  선형화: {linear.shape[1]}×{linear.shape[0]}px → {linear_path.name}")

        # 3단계: 문제 번호별 추출 (각 단마다)
        print(f"\n[3단계] 문제 번호별 추출")

        problems_output = page_output / "problems"
        problems_output.mkdir(parents=True, exist_ok=True)

        page_problems = 0

        for col_idx, col in enumerate(result.columns, 1):
            col_name = f"col_{col_idx}"
            print(f"\n  {col_name} 처리 중...")

            # 문제 번호 감지
            markers = detect_problem_numbers_strict(col.image, max_x_position=300)

            if not markers:
                print(f"    ⚠️ 문제 번호를 찾을 수 없습니다")
                continue

            print(f"    감지된 문제: {len(markers)}개")

            # 문제 추출
            problems = extract_problems_by_markers(col.image, markers)

            # 저장
            for num, prob_img, bbox in problems:
                # 여백 제거
                prob_img = trim_whitespace(prob_img)

                # 파일명
                filename = f"page{page_num}_{col_name}_prob_{num:02d}.png"
                filepath = problems_output / filename

                # 저장
                Image.fromarray(prob_img).save(filepath)

                file_size = filepath.stat().st_size / 1024
                print(f"    ✓ 문제 {num}번: {prob_img.shape[1]}×{prob_img.shape[0]}px ({file_size:.1f}KB)")

                page_problems += 1

        total_problems += page_problems
        print(f"\n  페이지 {page_num} 총: {page_problems}개 문제 추출")

    # 최종 요약
    print("\n" + "=" * 80)
    print("✅ 전체 테스트 완료!")
    print("=" * 80)
    print(f"\n총 페이지: {len(images)}개")
    print(f"총 문제: {total_problems}개")
    print(f"저장 위치: {output_base}")

    # 결과 파일 목록
    all_problems = sorted(output_base.rglob("*_prob_*.png"))
    if all_problems:
        print(f"\n추출된 문제 파일 ({len(all_problems)}개):")
        for prob_file in all_problems:
            rel_path = prob_file.relative_to(output_base)
            print(f"  - {rel_path}")


if __name__ == "__main__":
    test_biology_sample()
