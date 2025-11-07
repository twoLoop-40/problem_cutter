"""
생명과학 샘플 테스트 - Mathpix 검증 포함

워크플로우:
1. PDF → 이미지 변환
2. 페이지별 처리:
   - 단 분리
   - Tesseract로 1차 문제 번호 감지
   - 문제 추출
   - 검증 Agent 호출
   - 실패 시:
     a) 파라미터 조정 후 Tesseract 재시도 (최대 2회)
     b) 여전히 실패 시 Mathpix로 컬럼 재검증
3. 최종 보고서 생성
"""

from pathlib import Path
import sys
import os
import asyncio
from dotenv import load_dotenv

# .env 파일 로드
project_root = Path(__file__).parent
dotenv_path = project_root.parent / ".env"
load_dotenv(dotenv_path)

sys.path.insert(0, str(project_root))

from core.pdf_converter import pdf_to_images
from core.column_separator import separate_columns
from extract_problems_strict import (
    detect_problem_numbers_strict,
    extract_problems_by_markers,
    trim_whitespace
)
from AgentTools.validation import validate_problem_sequence, suggest_retry_params
from AgentTools.mathpix_validator import verify_missing_problems_with_mathpix
from PIL import Image


async def test_biology_with_mathpix():
    """생명과학 샘플 - Mathpix 검증 포함"""

    print("=" * 80)
    print("생명과학Ⅰ 문항지 테스트 (Mathpix 검증 포함)")
    print("=" * 80)

    # Mathpix API 키 확인
    api_key = os.getenv("MATHPIX_APP_KEY")
    app_id = os.getenv("MATHPIX_APP_ID")

    if not api_key or not app_id:
        print("\n⚠️ Mathpix API 키가 설정되지 않았습니다.")
        print("   환경 변수 MATHPIX_APP_KEY, MATHPIX_APP_ID를 설정하세요.")
        print("   Mathpix 검증 없이 Tesseract만 사용합니다.\n")
        use_mathpix = False
    else:
        print(f"\n✓ Mathpix API 키 확인됨 (App ID: {app_id[:20]}...)")
        use_mathpix = True

    # 파일 경로
    pdf_path = project_root / "samples" / "고3_과학탐구_생명과학Ⅰ_문항지.pdf"
    output_base = project_root / "output" / "생명과학_mathpix_test"

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    print(f"입력 파일: {pdf_path.name}\n")

    # 1단계: PDF → 이미지
    print(f"[1단계] PDF → 이미지 변환")
    images = pdf_to_images(str(pdf_path), dpi=200)

    if not images:
        print("❌ 이미지 변환 실패")
        return

    print(f"✓ 변환 완료: {len(images)}개 페이지\n")

    # 전체 통계
    total_problems = 0
    total_mathpix_calls = 0
    mathpix_recoveries = []

    # 각 페이지 처리
    for page_num, page_image in enumerate(images, 1):
        print(f"{'=' * 80}")
        print(f"[페이지 {page_num}/{len(images)}]")
        print(f"{'=' * 80}\n")

        # 출력 디렉토리
        page_output = output_base / f"page_{page_num}"
        page_output.mkdir(parents=True, exist_ok=True)

        # 원본 저장
        original_path = page_output / "00_original.png"
        Image.fromarray(page_image).save(original_path)

        # 2단계: 단 분리
        print(f"[2단계] 단 분리")
        result = separate_columns(page_image)
        print(f"  감지된 단: {result.column_count}개 ({result.strategy.value})\n")

        # 각 단 저장
        for i, col in enumerate(result.columns):
            col_path = page_output / f"col_{i + 1}.png"
            Image.fromarray(col.image).save(col_path)

        # 3단계: 문제 추출 (첫 시도 Tesseract, 이후 Mathpix)
        print(f"[3단계] 문제 번호별 추출")

        max_retries = 3
        retry_count = 0
        validation_passed = False

        # 현재 파라미터
        params = {"max_x_position": 300, "min_confidence": 50}

        problems_output = page_output / "problems"
        problems_output.mkdir(parents=True, exist_ok=True)

        page_problems = []

        # [3단계] 첫 시도는 항상 Tesseract
        print(f"\n[3단계] Tesseract OCR (첫 시도)")

        for col_idx, col in enumerate(result.columns, 1):
            col_name = f"col_{col_idx}"
            col_path = page_output / f"col_{col_idx}.png"

            print(f"\n  {col_name} 처리 중 (Tesseract)...")

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

        # [4단계] 검증
        print(f"\n[4단계] 검증 Agent 호출")
        validation_result = validate_problem_sequence(page_problems)

        print(f"  {validation_result.message}")

        if validation_result.success:
            validation_passed = True
            print(f"  ✅ 검증 통과!\n")
        else:
            # 이슈 출력
            missing = validation_result.data.get("missing", [])
            duplicates = validation_result.data.get("duplicates", [])

            if missing:
                print(f"     - 누락: {missing}")
            if duplicates:
                print(f"     - 중복: {duplicates}")

            # [5단계] 두 번째 시도: Mathpix로 누락된 문제 재검증
            if use_mathpix and missing:
                print(f"\n[5단계] Mathpix 재검증")

                # 컬럼별로 Mathpix 실행
                for col_idx, col in enumerate(result.columns, 1):
                    col_path = page_output / f"col_{col_idx}.png"

                    print(f"\n  {col_path.name} Mathpix 검증 중...")
                    total_mathpix_calls += 1

                    mathpix_result = await verify_missing_problems_with_mathpix(
                        column_image_path=col_path,
                        missing_numbers=missing,
                        api_key=api_key,
                        app_id=app_id
                    )

                    if mathpix_result.success:
                        found = mathpix_result.data["found_numbers"]
                        print(f"  ✅ Mathpix 발견: {found}")
                        page_problems.extend(found)
                        mathpix_recoveries.extend(found)
                    else:
                        print(f"  ❌ Mathpix: {mathpix_result.message}")

                # Mathpix 후 재검증
                final_validation = validate_problem_sequence(page_problems)
                if final_validation.success:
                    validation_passed = True
                    print(f"\n  ✅ Mathpix 검증 후 통과!")
                else:
                    print(f"\n  ❌ Mathpix로도 해결되지 않음")
            else:
                if not use_mathpix:
                    print(f"\n  ⚠️ Mathpix API 키가 없어 재시도 불가")
                elif not missing:
                    print(f"\n  ⚠️ 누락된 문제가 없어 Mathpix 검증 생략")

        total_problems += len(set(page_problems))

    # 최종 요약
    print(f"\n{'=' * 80}")
    print("✅ 전체 테스트 완료!")
    print(f"{'=' * 80}\n")
    print(f"총 페이지: {len(images)}개")
    print(f"총 문제: {total_problems}개")
    print(f"Mathpix API 호출: {total_mathpix_calls}회")
    if mathpix_recoveries:
        print(f"Mathpix로 복구: {len(mathpix_recoveries)}개 - {mathpix_recoveries}")
    print(f"\n저장 위치: {output_base}")


if __name__ == "__main__":
    asyncio.run(test_biology_with_mathpix())
