"""
Mathpix 좌표 디버깅 스크립트

목적: Mathpix가 반환하는 좌표가 어떤 기준인지 확인
- PDF 원본 기준 (72 DPI)인지
- 업로드한 이미지 기준인지
- 스케일링 필요 여부 확인
"""

from pathlib import Path
import sys
import os
import asyncio
import json
from dotenv import load_dotenv

# .env 파일 로드
project_root = Path(__file__).parent.parent
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path)

sys.path.insert(0, str(project_root))

from core.pdf_converter import pdf_to_images
from core.column_separator import separate_columns
from AgentTools.mathpix_validator import verify_missing_problems_with_mathpix
from PIL import Image


async def debug_coordinates():
    """Mathpix 좌표 디버깅"""

    print("=" * 80)
    print("Mathpix 좌표 디버깅")
    print("=" * 80)

    # API 키
    api_key = os.getenv("MATHPIX_APP_KEY")
    app_id = os.getenv("MATHPIX_APP_ID")

    if not api_key or not app_id:
        print("❌ Mathpix API 키가 필요합니다")
        return

    # 파일 경로
    pdf_path = project_root / "samples" / "고3_과학탐구_생명과학Ⅰ_문항지.pdf"
    output_base = project_root / "output" / "mathpix_coord_debug"
    output_base.mkdir(parents=True, exist_ok=True)

    # PDF → 이미지 (DPI=200)
    print("\n[1] PDF → 이미지 변환 (DPI=200)")
    images = pdf_to_images(str(pdf_path), dpi=200)
    page_image = images[0]  # 첫 페이지만

    print(f"  이미지 크기: {page_image.shape[1]}×{page_image.shape[0]} pixels")

    # 단 분리
    print("\n[2] 단 분리")
    result = separate_columns(page_image)
    col1 = result.columns[0]

    col1_path = output_base / "col_1.png"
    Image.fromarray(col1.image).save(col1_path)

    print(f"  컬럼 1 크기: {col1.image.shape[1]}×{col1.image.shape[0]} pixels")
    print(f"  저장: {col1_path}")

    # Mathpix OCR
    print("\n[3] Mathpix OCR + .lines.json")
    mathpix_result = await verify_missing_problems_with_mathpix(
        column_image_path=col1_path,
        missing_numbers=[3],  # 문제 3번만 테스트
        api_key=api_key,
        app_id=app_id
    )

    if not mathpix_result.success:
        print(f"  ❌ Mathpix 실패: {mathpix_result.message}")
        return

    lines_json = mathpix_result.data.get("mathpix_lines_json")

    if not lines_json:
        print("  ❌ .lines.json 없음")
        return

    # JSON 저장
    json_path = output_base / "lines.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(lines_json, f, indent=2, ensure_ascii=False)

    print(f"  ✅ .lines.json 저장: {json_path}")

    # 좌표 분석
    print("\n[4] 좌표 분석")

    pages = lines_json.get('pages', [])
    if not pages:
        print("  ❌ 페이지 없음")
        return

    page = pages[0]
    page_width = page.get('page_width')
    page_height = page.get('page_height')

    print(f"  Mathpix 페이지 크기: {page_width}×{page_height} (Mathpix 좌표계)")
    print(f"  우리 이미지 크기: {col1.image.shape[1]}×{col1.image.shape[0]} pixels (DPI=200)")

    # 스케일 팩터 계산
    if page_width and col1.image.shape[1]:
        scale_x = col1.image.shape[1] / page_width
        scale_y = col1.image.shape[0] / page_height
        print(f"\n  📐 스케일 팩터:")
        print(f"     X: {scale_x:.4f} (이미지너비 / Mathpix너비)")
        print(f"     Y: {scale_y:.4f} (이미지높이 / Mathpix높이)")

    # 문제 3번 좌표 찾기
    print(f"\n[5] 문제 3번 좌표 검색")

    lines = page.get('lines', [])
    found_3 = None

    for line in lines:
        text = line.get('text', '')
        if text.strip().startswith('3.'):
            found_3 = line
            break

    if found_3:
        region = found_3.get('region', {})
        print(f"  ✅ 문제 3번 발견:")
        print(f"     텍스트: {found_3.get('text')[:50]}...")
        print(f"     Mathpix 좌표 (원본):")
        print(f"       top_left_x: {region.get('top_left_x')}")
        print(f"       top_left_y: {region.get('top_left_y')}")
        print(f"       width: {region.get('width')}")
        print(f"       height: {region.get('height')}")

        # 스케일링 적용 후 좌표
        if page_width:
            scaled_x = region.get('top_left_x', 0) * scale_x
            scaled_y = region.get('top_left_y', 0) * scale_y
            scaled_w = region.get('width', 0) * scale_x
            scaled_h = region.get('height', 0) * scale_y

            print(f"\n     스케일링 적용 후 (우리 이미지 기준):")
            print(f"       top_left_x: {scaled_x:.0f}")
            print(f"       top_left_y: {scaled_y:.0f}")
            print(f"       width: {scaled_w:.0f}")
            print(f"       height: {scaled_h:.0f}")

            # 이 좌표로 잘라보기
            print(f"\n  [테스트] 스케일링 좌표로 이미지 자르기")
            x, y, w, h = int(scaled_x), int(scaled_y), int(scaled_w), int(scaled_h)

            # 범위 체크
            if 0 <= y < col1.image.shape[0] and 0 <= x < col1.image.shape[1]:
                # 잘라내기
                cropped = col1.image[y:min(y+h+500, col1.image.shape[0]),
                                     x:min(x+w+800, col1.image.shape[1])]

                crop_path = output_base / "prob_3_scaled.png"
                Image.fromarray(cropped).save(crop_path)

                print(f"  ✅ 저장: {crop_path}")
                print(f"     크기: {cropped.shape[1]}×{cropped.shape[0]} pixels")
            else:
                print(f"  ❌ 좌표가 이미지 범위를 벗어남")
    else:
        print(f"  ❌ 문제 3번 못 찾음")

    print(f"\n{'=' * 80}")
    print("디버깅 완료!")
    print(f"결과 확인: {output_base}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(debug_coordinates())
