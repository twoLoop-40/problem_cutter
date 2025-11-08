"""
페이지 1만 테스트 - Mathpix 텍스트 확인용
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
from scripts.extract_problems_strict import (
    detect_problem_numbers_strict,
    extract_problems_by_markers,
    trim_whitespace
)
from AgentTools.validation import validate_problem_sequence
from AgentTools.mathpix_validator import verify_missing_problems_with_mathpix
from PIL import Image


async def test_page1_only():
    """페이지 1번만 테스트"""

    print("=" * 80)
    print("페이지 1 테스트 - Mathpix 텍스트 확인")
    print("=" * 80)

    # Mathpix API 키 확인
    api_key = os.getenv("MATHPIX_APP_KEY")
    app_id = os.getenv("MATHPIX_APP_ID")

    if not api_key or not app_id:
        print("\n❌ Mathpix API 키가 필요합니다.")
        return

    print(f"\n✓ Mathpix API 키 확인됨\n")

    # 파일 경로
    pdf_path = project_root.parent / "samples" / "고3_과학탐구_생명과학Ⅰ_문항지.pdf"
    output_base = project_root.parent / "output" / "생명과학_page1_test"

    # PDF → 이미지
    images = pdf_to_images(str(pdf_path), dpi=200)
    page_image = images[0]  # 페이지 1만

    # 출력 디렉토리
    page_output = output_base / "page_1"
    page_output.mkdir(parents=True, exist_ok=True)

    # 원본 저장
    original_path = page_output / "00_original.png"
    Image.fromarray(page_image).save(original_path)

    # 단 분리
    print(f"[1단계] 단 분리")
    result = separate_columns(page_image)
    print(f"  감지된 단: {result.column_count}개\n")

    # 각 단 저장
    for i, col in enumerate(result.columns):
        col_path = page_output / f"col_{i + 1}.png"
        Image.fromarray(col.image).save(col_path)

    # Tesseract로 문제 번호 감지
    print(f"[2단계] Tesseract로 문제 번호 감지")
    page_problems = []

    for col_idx, col in enumerate(result.columns, 1):
        markers = detect_problem_numbers_strict(col.image, max_x_position=300)
        detected = [num for num, _, _ in markers]
        print(f"  col_{col_idx}: {detected}")
        page_problems.extend(detected)

    # 검증
    print(f"\n[3단계] 검증")
    validation_result = validate_problem_sequence(page_problems)
    print(f"  {validation_result.message}")

    if not validation_result.success:
        missing = validation_result.data.get("missing", [])
        print(f"  누락: {missing}\n")

        # Mathpix로 재검증
        print(f"[4단계] Mathpix로 col_1 재검증")
        col_path = page_output / "col_1.png"

        mathpix_result = await verify_missing_problems_with_mathpix(
            column_image_path=col_path,
            missing_numbers=missing,
            api_key=api_key,
            app_id=app_id
        )

        if mathpix_result.success:
            found = mathpix_result.data["found_numbers"]
            print(f"\n✅ Mathpix 발견: {found}")

            # 텍스트 저장
            mathpix_text = mathpix_result.data.get("mathpix_full_text", "")
            if mathpix_text:
                mathpix_text_path = page_output / "mathpix_col_1.txt"
                mathpix_text_path.write_text(mathpix_text, encoding='utf-8')
                print(f"📝 Mathpix 텍스트 저장: {mathpix_text_path}")
                print(f"\n=== Mathpix 텍스트 미리보기 (처음 1000자) ===")
                print(mathpix_text[:1000])
                print(f"=== (총 {len(mathpix_text)}자) ===\n")

    print(f"\n저장 위치: {output_base}")


if __name__ == "__main__":
    asyncio.run(test_page1_only())
