"""
단 분리된 이미지에서 문제 번호별로 개별 문제 추출

워크플로우:
1. 단 분리된 이미지 로드
2. OCR로 문제 번호 감지 (1., 2., 3., ...)
3. 문제 번호 마커의 Y 좌표 기반으로 영역 분리
4. 각 문제를 개별 이미지로 저장
"""

from pathlib import Path
import sys
from typing import List, Tuple
import cv2
import numpy as np
from PIL import Image
import pytesseract

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.base import BBox, Coord
from core.ocr_engine import OcrResult, Confidence, parse_problem_number


def detect_problem_numbers_tesseract(image: np.ndarray) -> List[Tuple[int, int]]:
    """Tesseract OCR로 문제 번호 감지

    Args:
        image: 입력 이미지

    Returns:
        List of (problem_number, y_position) tuples
    """
    # Tesseract로 OCR 실행
    custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
    data = pytesseract.image_to_data(image, lang='kor+eng',
                                     config=custom_config,
                                     output_type=pytesseract.Output.DICT)

    markers = []
    seen_positions = {}  # 중복 제거: {problem_number: y_position}

    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = int(data['conf'][i]) if data['conf'][i] != -1 else 0

        if conf < 40:  # 낮은 신뢰도 무시
            continue

        # 문제 번호 파싱
        number = parse_problem_number(text)
        if number is not None:
            y_pos = data['top'][i]
            x_pos = data['left'][i]

            # 중복 제거: 같은 문제 번호는 가장 위쪽(작은 y)만 유지
            if number in seen_positions:
                prev_y = seen_positions[number]
                # 이전 위치와 너무 가까우면 (100px 이내) 무시
                if abs(y_pos - prev_y) < 100:
                    continue
                # 더 위쪽에 있으면 업데이트
                if y_pos < prev_y:
                    # 기존 마커 제거
                    markers = [(n, y) for n, y in markers if n != number]
                    seen_positions[number] = y_pos
                    markers.append((number, y_pos))
                    print(f"  업데이트: '{text}' → 문제 {number}번 (y={y_pos})")
                else:
                    continue
            else:
                # 첫 번째 감지된 위치 저장
                seen_positions[number] = y_pos
                markers.append((number, y_pos))
                print(f"  감지: '{text}' → 문제 {number}번 (y={y_pos}, x={x_pos})")

    return markers


def extract_problems_by_markers(
    image: np.ndarray,
    markers: List[Tuple[int, int]],
    margin_top: int = 20,
    margin_bottom: int = 20
) -> List[Tuple[int, np.ndarray, BBox]]:
    """문제 번호 마커를 기반으로 문제 영역 추출

    Args:
        image: 입력 이미지
        markers: (문제번호, y위치) 리스트
        margin_top: 위쪽 여백
        margin_bottom: 아래쪽 여백

    Returns:
        List of (문제번호, 이미지, BBox) tuples
    """
    if not markers:
        return []

    height, width = image.shape[:2]

    # 문제 번호 순서대로 정렬
    markers = sorted(markers, key=lambda x: x[1])

    problems = []

    for i, (num, y_start) in enumerate(markers):
        # 다음 문제의 시작 위치 또는 페이지 끝
        if i + 1 < len(markers):
            y_end = markers[i + 1][1]
        else:
            y_end = height

        # 여백 적용
        y_start_crop = max(0, y_start - margin_top)
        y_end_crop = min(height, y_end + margin_bottom)

        # 문제 영역 추출
        problem_img = image[y_start_crop:y_end_crop, :]

        bbox = BBox(
            top_left=Coord(0, y_start_crop),
            width=width,
            height=y_end_crop - y_start_crop
        )

        problems.append((num, problem_img, bbox))
        print(f"  문제 {num}번: y={y_start_crop}~{y_end_crop} (높이={bbox.height}px)")

    return problems


def trim_whitespace(image: np.ndarray, threshold: int = 250) -> np.ndarray:
    """이미지 가장자리 여백 제거

    Args:
        image: 입력 이미지
        threshold: 흰색 판단 기준 (기본 250)

    Returns:
        여백이 제거된 이미지
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # 텍스트가 있는 영역 찾기
    rows = np.any(gray < threshold, axis=1)
    cols = np.any(gray < threshold, axis=0)

    if not np.any(rows) or not np.any(cols):
        return image

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    # 약간의 패딩 추가
    padding = 15
    y_min = max(0, y_min - padding)
    y_max = min(image.shape[0], y_max + padding + 1)
    x_min = max(0, x_min - padding)
    x_max = min(image.shape[1], x_max + padding + 1)

    return image[y_min:y_max, x_min:x_max]


def process_column_image(
    image_path: Path,
    output_dir: Path,
    prefix: str = "problem",
    trim: bool = True
) -> List[Path]:
    """단 이미지에서 문제 추출 및 저장

    Args:
        image_path: 입력 이미지 경로
        output_dir: 출력 디렉토리
        prefix: 파일명 접두사
        trim: 여백 제거 여부

    Returns:
        저장된 파일 경로 리스트
    """
    print(f"\n처리 중: {image_path.name}")

    # 이미지 로드
    image = np.array(Image.open(image_path))
    height, width = image.shape[:2]
    print(f"  이미지 크기: {width}x{height}")

    # 1. OCR로 문제 번호 감지
    print("\n[1단계] 문제 번호 감지")
    markers = detect_problem_numbers_tesseract(image)

    if not markers:
        print("  ⚠️ 문제 번호를 찾을 수 없습니다")
        return []

    print(f"  감지된 문제: {len(markers)}개")

    # 2. 문제 영역 추출
    print("\n[2단계] 문제 영역 추출")
    problems = extract_problems_by_markers(image, markers)

    # 3. 저장
    print("\n[3단계] 파일 저장")
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for num, prob_img, bbox in problems:
        # 여백 제거
        if trim:
            prob_img = trim_whitespace(prob_img)

        # 파일명 생성
        filename = f"{prefix}_{num:02d}.png"
        filepath = output_dir / filename

        # 저장
        Image.fromarray(prob_img).save(filepath)
        saved_paths.append(filepath)

        file_size = filepath.stat().st_size / 1024  # KB
        print(f"  문제 {num}번: {filepath.name} ({file_size:.1f}KB, {prob_img.shape[1]}x{prob_img.shape[0]})")

    return saved_paths


def extract_from_separated_columns(column_dir: Path) -> None:
    """단 분리된 디렉토리에서 모든 문제 추출

    Args:
        column_dir: 단 분리 결과 디렉토리 (col_1.png, col_2.png 포함)
    """
    print("=" * 80)
    print(f"단 분리 파일에서 문제 추출")
    print(f"입력 디렉토리: {column_dir}")
    print("=" * 80)

    # col_1.png, col_2.png 등 찾기
    column_files = sorted(column_dir.glob("col_*.png"))

    if not column_files:
        print("\n❌ col_*.png 파일을 찾을 수 없습니다")
        return

    print(f"\n찾은 파일: {len(column_files)}개")
    for f in column_files:
        print(f"  - {f.name}")

    # 출력 디렉토리
    output_dir = column_dir / "problems"

    all_saved_paths = []

    # 각 단 처리
    for col_file in column_files:
        col_name = col_file.stem  # "col_1", "col_2" 등
        prefix = f"{col_name}_prob"

        saved_paths = process_column_image(
            col_file,
            output_dir,
            prefix=prefix,
            trim=True
        )

        all_saved_paths.extend(saved_paths)

    # 요약
    print("\n" + "=" * 80)
    print("✅ 추출 완료!")
    print("=" * 80)
    print(f"\n총 {len(all_saved_paths)}개 문제 추출됨")
    print(f"저장 위치: {output_dir}")
    print("\n추출된 파일:")
    for path in sorted(all_saved_paths):
        print(f"  - {path.name}")


def main():
    """메인 실행 함수"""

    # 사회문화 샘플 처리
    print("🔍 문제 번호별 추출 시작\n")

    column_dir = project_root / "output" / "column_test_사회문화"

    if not column_dir.exists():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {column_dir}")
        print("\n먼저 다음 명령을 실행하세요:")
        print("  uv run python test_column_separation_samples.py")
        return

    extract_from_separated_columns(column_dir)

    # 통합과학도 처리
    print("\n\n")
    column_dir2 = project_root / "output" / "column_test_통합과학"

    if column_dir2.exists():
        extract_from_separated_columns(column_dir2)


if __name__ == "__main__":
    main()
