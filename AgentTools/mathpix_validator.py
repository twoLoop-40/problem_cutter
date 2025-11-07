"""
Mathpix 기반 검증 툴 - 누락된 문제 번호 재검증

Tesseract OCR이 놓친 문제 번호를 Mathpix API로 재검증합니다.
수학 기호나 복잡한 레이아웃에서도 높은 정확도를 보입니다.

워크플로우:
1. Tesseract로 1차 검증 → 누락 발견
2. 누락된 영역을 Mathpix로 재검증
3. 정규식으로 "3.", "4." 같은 패턴 탐색
4. 발견 시 해당 영역 추출
"""

import re
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import numpy as np
from PIL import Image
import sys
import importlib.util
import asyncio
import tempfile
import os

# Mathpix 클라이언트를 동적으로 로드
smartocr_root = Path(__file__).parent.parent.parent
mathpix_client_path = smartocr_root / "core" / "mathpix_client.py"

spec = importlib.util.spec_from_file_location("mathpix_client", mathpix_client_path)
mathpix_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mathpix_module)
MathpixClient = mathpix_module.MathpixClient
UploadRequest = mathpix_module.UploadRequest
ConversionFormat = mathpix_module.ConversionFormat
ApiStatus = mathpix_module.ApiStatus

from .types import ToolResult, ToolDiagnostics


async def verify_missing_problems_with_mathpix(
    column_image_path: Path,
    missing_numbers: List[int],
    api_key: str,
    app_id: str
) -> ToolResult:
    """Mathpix로 누락된 문제 번호 재검증 (컬럼 단위)

    Args:
        column_image_path: 검증할 컬럼 이미지 파일 경로 (col_1.png, col_2.png 등)
        missing_numbers: 누락된 것으로 추정되는 문제 번호들
        api_key: Mathpix App Key
        app_id: Mathpix App ID

    Returns:
        발견된 문제 번호와 위치를 담은 ToolResult
    """
    diagnostics = ToolDiagnostics()
    diagnostics.add_info(f"Mathpix 검증 시작: 누락 {len(missing_numbers)}개")
    diagnostics.add_info(f"API Key: {api_key[:20]}..., App ID: {app_id}")

    # Mathpix 클라이언트 (app_id, app_key 순서)
    client = MathpixClient(app_id=app_id, app_key=api_key)

    # 컬럼 이미지 파일 확인
    if not column_image_path.exists():
        return ToolResult(
            success=False,
            message=f"컬럼 이미지 파일을 찾을 수 없습니다: {column_image_path}",
            data={"found": []},
            diagnostics=diagnostics
        )

    diagnostics.add_info(f"검증 대상: {column_image_path.name}")

    try:
        # Mathpix OCR 실행
        diagnostics.add_info("Mathpix OCR 실행 중...")

        # PNG를 PDF로 변환 (Mathpix는 PDF를 기대함)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            pdf_temp_path = tmp_pdf.name

        # PNG 이미지를 PDF로 변환
        img = Image.open(column_image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(pdf_temp_path, 'PDF', resolution=100.0)
        diagnostics.add_info(f"임시 PDF 생성: {pdf_temp_path}")

        # 이미지 업로드 (PDF로 변환된 파일) - UploadRequest 객체 생성
        upload_request = UploadRequest(
            pdf_path=pdf_temp_path,
            formats=[ConversionFormat.MD]
        )
        upload_response = await client.upload_pdf(upload_request)

        pdf_id = upload_response.pdf_id
        diagnostics.add_info(f"PDF ID: {pdf_id}")

        # 처리 대기
        max_wait = 60  # 60초
        wait_interval = 2  # 2초마다 확인
        waited = 0

        while waited < max_wait:
            try:
                status_response = await client.check_status(pdf_id)
                print(f"  상태 확인: {status_response.status.value}, 진행률: {status_response.progress.percent_done}%")
                diagnostics.add_info(f"상태: {status_response.status.value}, 진행률: {status_response.progress.percent_done}%")

                if status_response.status == ApiStatus.COMPLETED:
                    diagnostics.add_success("Mathpix 처리 완료")
                    print(f"  ✓ Mathpix 처리 완료!")
                    break
                elif status_response.status == ApiStatus.ERROR:
                    print(f"  ✗ Mathpix ERROR 상태 감지")
                    return ToolResult(
                        success=False,
                        message="Mathpix 처리 중 오류 발생 (API ERROR 상태)",
                        data={"found": []},
                        diagnostics=diagnostics
                    )

                await asyncio.sleep(wait_interval)
                waited += wait_interval
            except Exception as e:
                diagnostics.add_error(f"상태 확인 오류: {str(e)}")
                return ToolResult(
                    success=False,
                    message=f"Mathpix 상태 확인 실패: {str(e)}",
                    data={"found": []},
                    diagnostics=diagnostics
                )

        if waited >= max_wait:
            return ToolResult(
                success=False,
                message="Mathpix 처리 시간 초과",
                data={"found": []},
                diagnostics=diagnostics
            )

        # 결과 다운로드
        download_result = await client.download_result(pdf_id, ConversionFormat.MD)

        text_content = download_result.content
        diagnostics.add_info(f"Mathpix 텍스트 길이: {len(text_content)}자")

        # 정규식으로 문제 번호 찾기
        found_problems = []

        for num in missing_numbers:
            # 패턴: "숫자." (단독으로)
            pattern = rf'\b{num}\.\s'

            matches = re.finditer(pattern, text_content)
            match_positions = list(matches)

            if match_positions:
                diagnostics.add_success(f"✓ 문제 {num}번 발견 (Mathpix)")
                found_problems.append({
                    "number": num,
                    "match_count": len(match_positions),
                    "context": text_content[max(0, match_positions[0].start() - 50):
                                           min(len(text_content), match_positions[0].end() + 50)]
                })
            else:
                diagnostics.add_warning(f"✗ 문제 {num}번 미발견 (Mathpix)")

        # 결과
        found_numbers = [p["number"] for p in found_problems]
        still_missing = [num for num in missing_numbers if num not in found_numbers]

        result_data = {
            "found": found_problems,
            "found_numbers": found_numbers,
            "still_missing": still_missing,
            "mathpix_text": text_content[:500]  # 처음 500자만
        }

        if found_numbers:
            message = f"✅ Mathpix로 {len(found_numbers)}개 문제 발견: {found_numbers}"
            success = True
        else:
            message = f"❌ Mathpix로도 문제 번호 발견 못함"
            success = False

        return ToolResult(
            success=success,
            message=message,
            data=result_data,
            diagnostics=diagnostics
        )

    except Exception as e:
        diagnostics.add_error(f"Mathpix 검증 오류: {str(e)}")
        return ToolResult(
            success=False,
            message=f"Mathpix 검증 오류: {str(e)}",
            data={"found": [], "error": str(e)},
            diagnostics=diagnostics
        )

    finally:
        # 임시 PDF 파일 정리
        if 'pdf_temp_path' in locals() and os.path.exists(pdf_temp_path):
            os.unlink(pdf_temp_path)
            diagnostics.add_info(f"임시 PDF 삭제: {pdf_temp_path}")


def extract_problem_regions_from_text(
    text: str,
    problem_numbers: List[int]
) -> Dict[int, str]:
    """Mathpix 텍스트에서 문제별 영역 추출

    Args:
        text: Mathpix가 추출한 전체 텍스트
        problem_numbers: 추출할 문제 번호들

    Returns:
        {문제번호: 문제 텍스트} 딕셔너리
    """
    result = {}

    # 문제 번호로 분할
    for i, num in enumerate(problem_numbers):
        # 현재 문제 번호 찾기
        pattern = rf'\b{num}\.\s'
        match = re.search(pattern, text)

        if not match:
            continue

        start_pos = match.start()

        # 다음 문제 번호 찾기
        if i + 1 < len(problem_numbers):
            next_num = problem_numbers[i + 1]
            next_pattern = rf'\b{next_num}\.\s'
            next_match = re.search(next_pattern, text[start_pos + 10:])  # 현재 위치 이후부터

            if next_match:
                end_pos = start_pos + 10 + next_match.start()
            else:
                end_pos = len(text)
        else:
            end_pos = len(text)

        # 문제 텍스트 추출
        problem_text = text[start_pos:end_pos].strip()
        result[num] = problem_text

    return result


if __name__ == "__main__":
    import asyncio

    print("=" * 80)
    print("Mathpix 검증 툴 테스트")
    print("=" * 80)

    print("\n이 모듈은 실제 Mathpix API 키가 필요합니다.")
    print("테스트 시 환경 변수 MATHPIX_API_KEY, MATHPIX_APP_ID를 설정하세요.")

    # 예시 (실제 실행은 API 키 필요)
    print("\n사용 예시:")
    print("""
    import asyncio
    from AgentTools.mathpix_validator import verify_missing_problems_with_mathpix

    # 누락된 문제 3, 4번을 Mathpix로 재검증
    result = await verify_missing_problems_with_mathpix(
        image=column_image,
        missing_numbers=[3, 4],
        api_key=os.getenv("MATHPIX_API_KEY"),
        app_id=os.getenv("MATHPIX_APP_ID")
    )

    if result.success:
        print(f"발견된 문제: {result.data['found_numbers']}")
    """)
