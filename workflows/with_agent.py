"""
생명과학 샘플 테스트 - Agent 검증 포함

워크플로우:
1. PDF → 이미지 변환
2. 페이지별 처리:
   - 단 분리
   - 문제 번호 감지
   - 문제 추출
   - 검증 Agent 호출
   - 실패 시 파라미터 조정 후 재시도 (최대 3회)
3. 최종 보고서 생성
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
    trim_whitespace
)
from AgentTools.validation import validate_problem_sequence, suggest_retry_params
from PIL import Image


def test_biology_with_agent():
    """생명과학 샘플 - Agent 검증 포함"""

    print("=" * 80)
    print("생명과학Ⅰ 문항지 테스트 (Agent 검증 포함)")
    print("=" * 80)

    # 파일 경로
    pdf_path = project_root / "samples" / "고3_과학탐구_생명과학Ⅰ_문항지.pdf"
    output_base = project_root / "output" / "생명과학_agent_test"

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    print(f"\n입력 파일: {pdf_path.name}")

    # 1단계: PDF → 이미지
    print(f"\n[1단계] PDF → 이미지 변환")
    images = pdf_to_images(str(pdf_path), dpi=200)

    if not images:
        print("❌ 이미지 변환 실패")
        return

    print(f"✓ 변환 완료: {len(images)}개 페이지")

    # 전체 통계
    total_problems = 0
    total_retries = 0
    all_issues = []

    # 각 페이지 처리
    for page_num, page_image in enumerate(images, 1):
        print(f"\n{'=' * 80}")
        print(f"[페이지 {page_num}/{len(images)}]")
        print(f"{'=' * 80}")

        # 출력 디렉토리
        page_output = output_base / f"page_{page_num}"
        page_output.mkdir(parents=True, exist_ok=True)

        # 원본 저장
        original_path = page_output / "00_original.png"
        Image.fromarray(page_image).save(original_path)

        # 2단계: 단 분리
        print(f"\n[2단계] 단 분리")
        result = separate_columns(page_image)
        print(f"  감지된 단: {result.column_count}개 ({result.strategy.value})")

        # 각 단 저장
        for i, col in enumerate(result.columns):
            col_path = page_output / f"col_{i + 1}.png"
            Image.fromarray(col.image).save(col_path)

        # 3단계: 문제 추출 (재시도 포함)
        print(f"\n[3단계] 문제 번호별 추출 (재시도 포함)")

        max_retries = 3
        retry_count = 0
        validation_passed = False

        # 현재 파라미터
        params = {"max_x_position": 300, "min_confidence": 50}

        while retry_count <= max_retries and not validation_passed:
            if retry_count > 0:
                print(f"\n⚠️ 재시도 {retry_count}/{max_retries}회")
                print(f"   파라미터: max_x={params['max_x_position']}, min_conf={params['min_confidence']}")

            problems_output = page_output / "problems"
            problems_output.mkdir(parents=True, exist_ok=True)

            page_problems = []

            for col_idx, col in enumerate(result.columns, 1):
                col_name = f"col_{col_idx}"
                print(f"\n  {col_name} 처리 중...")

                # 문제 번호 감지
                markers = detect_problem_numbers_strict(
                    col.image,
                    max_x_position=params["max_x_position"]
                )

                if not markers:
                    print(f"    ⚠️ 문제 번호를 찾을 수 없습니다")
                    continue

                print(f"    감지된 문제: {[num for num, _, _ in markers]}")

                # 문제 추출
                problems = extract_problems_by_markers(col.image, markers)

                # 저장
                for num, prob_img, bbox in problems:
                    prob_img = trim_whitespace(prob_img)
                    filename = f"page{page_num}_{col_name}_prob_{num:02d}.png"
                    filepath = problems_output / filename
                    Image.fromarray(prob_img).save(filepath)

                    file_size = filepath.stat().st_size / 1024
                    print(f"    ✓ 문제 {num}번: {prob_img.shape[1]}×{prob_img.shape[0]}px ({file_size:.1f}KB)")

                    page_problems.append(num)

            # 4단계: 검증
            print(f"\n[4단계] 검증 Agent 호출")
            validation_result = validate_problem_sequence(page_problems)

            print(f"  {validation_result.message}")

            if validation_result.success:
                validation_passed = True
                print(f"  ✅ 검증 통과!")
            else:
                # 이슈 출력
                for issue in validation_result.data["issues"]:
                    if issue == "missing":
                        print(f"     - 누락: {validation_result.data['missing']}")
                    elif issue == "duplicate":
                        print(f"     - 중복: {validation_result.data['duplicates']}")

                all_issues.extend(validation_result.data["issues"])

                # 재시도 파라미터 조정
                if retry_count < max_retries:
                    retry_result = suggest_retry_params(validation_result.data, params)
                    params = retry_result.data["new_params"]
                    retry_count += 1
                    total_retries += 1
                else:
                    print(f"  ❌ 최대 재시도 횟수 도달")
                    break

        total_problems += len(page_problems)

    # 최종 요약
    print(f"\n{'=' * 80}")
    print("✅ 전체 테스트 완료!")
    print(f"{'=' * 80}")
    print(f"\n총 페이지: {len(images)}개")
    print(f"총 문제: {total_problems}개")
    print(f"총 재시도: {total_retries}회")
    print(f"발견된 이슈: {len(set(all_issues))}종류 - {set(all_issues)}")
    print(f"저장 위치: {output_base}")


if __name__ == "__main__":
    test_biology_with_agent()
