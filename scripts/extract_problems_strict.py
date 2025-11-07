"""
단 분리된 이미지에서 문제 번호별로 개별 문제 추출 (엄격한 버전)

문제 번호 인식 규칙:
- "1.", "2.", "3." 등 왼쪽 상단에 위치한 아라비아 숫자 + 점(dot)만 인정
- "(1)", "①" 등 보기 번호는 제외
- 문제 번호는 반드시 왼쪽 여백 근처에 위치 (x < 150px)
"""

from pathlib import Path
import sys
from typing import List, Tuple, Optional
import cv2
import numpy as np
from PIL import Image
import pytesseract
import re

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.base import BBox, Coord


def is_problem_number_strict(text: str) -> Optional[int]:
    """엄격한 문제 번호 파싱 - "숫자." 형식만 인정

    Args:
        text: OCR 텍스트

    Returns:
        문제 번호 (1~100) 또는 None

    Examples:
        >>> is_problem_number_strict("1.")
        1
        >>> is_problem_number_strict("15.")
        15
        >>> is_problem_number_strict("①")
        None
        >>> is_problem_number_strict("(1)")
        None
        >>> is_problem_number_strict("[1]")
        None
    """
    text = text.strip()

    # 패턴: 정확히 "숫자." 형식만
    # ^ : 문자열 시작
    # (\d+) : 1개 이상의 숫자
    # \. : 점(dot) - 이스케이프 필요
    # $ : 문자열 끝
    match = re.match(r'^(\d+)\.$', text)

    if match:
        num = int(match.group(1))
        # 문제 번호는 1~100 범위
        if 1 <= num <= 100:
            return num

    return None


def detect_problem_numbers_strict(
    image: np.ndarray,
    max_x_position: int = 150
) -> List[Tuple[int, int, int]]:
    """엄격한 문제 번호 감지

    Args:
        image: 입력 이미지
        max_x_position: 문제 번호로 인정할 최대 X 좌표 (기본 150px)

    Returns:
        List of (problem_number, y_position, x_position) tuples
    """
    # Tesseract OCR 실행
    custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
    data = pytesseract.image_to_data(
        image,
        lang='kor+eng',
        config=custom_config,
        output_type=pytesseract.Output.DICT
    )

    markers = []
    seen_numbers = set()  # 중복 방지

    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = int(data['conf'][i]) if data['conf'][i] != -1 else 0

        # 낮은 신뢰도 무시
        if conf < 50:
            continue

        # 엄격한 문제 번호 파싱
        number = is_problem_number_strict(text)

        if number is not None:
            y_pos = data['top'][i]
            x_pos = data['left'][i]

            # 조건 1: 왼쪽 여백에 위치 (문제 번호는 왼쪽에 있음)
            if x_pos > max_x_position:
                print(f"  무시(x={x_pos}): '{text}' - 너무 오른쪽")
                continue

            # 조건 2: 중복 방지
            if number in seen_numbers:
                print(f"  무시(중복): '{text}' - 문제 {number}번 이미 감지됨")
                continue

            seen_numbers.add(number)
            markers.append((number, y_pos, x_pos))
            print(f"  ✓ 감지: '{text}' → 문제 {number}번 (y={y_pos}, x={x_pos})")

    return markers


def extract_problems_by_markers(
    image: np.ndarray,
    markers: List[Tuple[int, int, int]],
    margin_top: int = 50,
    margin_bottom: int = -20
) -> List[Tuple[int, np.ndarray, BBox]]:
    """문제 번호 마커를 기반으로 문제 영역 추출

    Args:
        image: 입력 이미지
        markers: (문제번호, y위치, x위치) 리스트
        margin_top: 위쪽 여백 (양수: 위로 확장)
        margin_bottom: 아래쪽 여백 (음수: 다음 문제 제외, 양수: 아래로 확장)

    Returns:
        List of (문제번호, 이미지, BBox) tuples
    """
    if not markers:
        return []

    height, width = image.shape[:2]

    # Y 위치 순서대로 정렬
    markers = sorted(markers, key=lambda x: x[1])

    problems = []

    for i, (num, y_start, x_pos) in enumerate(markers):
        # 다음 문제의 시작 위치 또는 페이지 끝
        if i + 1 < len(markers):
            # 다음 문제 시작 직전까지만 (다음 문제의 텍스트 포함 방지)
            y_end = markers[i + 1][1]
        else:
            y_end = height

        # 여백 적용
        y_start_crop = max(0, y_start - margin_top)
        # margin_bottom이 음수이면 다음 문제 전에 자르기
        y_end_crop = min(height, y_end + margin_bottom)

        # 최소 높이 확인 (너무 작으면 무시)
        if y_end_crop - y_start_crop < 100:
            print(f"  ⚠️ 문제 {num}번: 영역이 너무 작음 (높이={y_end_crop - y_start_crop}px)")
            continue

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


def trim_whitespace(image: np.ndarray, threshold: int = 250, padding: int = 15) -> np.ndarray:
    """이미지 가장자리 여백 제거

    Args:
        image: 입력 이미지
        threshold: 흰색 판단 기준
        padding: 여백 패딩

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

    # 패딩 추가
    y_min = max(0, y_min - padding)
    y_max = min(image.shape[0], y_max + padding + 1)
    x_min = max(0, x_min - padding)
    x_max = min(image.shape[1], x_max + padding + 1)

    return image[y_min:y_max, x_min:x_max]


def process_column_image(
    image_path: Path,
    output_dir: Path,
    prefix: str = "problem",
    trim: bool = True,
    max_x_position: int = 150
) -> List[Path]:
    """단 이미지에서 문제 추출 및 저장

    Args:
        image_path: 입력 이미지 경로
        output_dir: 출력 디렉토리
        prefix: 파일명 접두사
        trim: 여백 제거 여부
        max_x_position: 문제 번호로 인정할 최대 X 좌표

    Returns:
        저장된 파일 경로 리스트
    """
    print(f"\n{'='*80}")
    print(f"처리 중: {image_path.name}")
    print(f"{'='*80}")

    # 이미지 로드
    image = np.array(Image.open(image_path))
    height, width = image.shape[:2]
    print(f"이미지 크기: {width}x{height}")

    # 1. 엄격한 문제 번호 감지
    print(f"\n[1단계] 문제 번호 감지 (왼쪽 {max_x_position}px 이내, '숫자.' 형식만)")
    markers = detect_problem_numbers_strict(image, max_x_position=max_x_position)

    if not markers:
        print("  ❌ 문제 번호를 찾을 수 없습니다")
        return []

    print(f"\n  총 {len(markers)}개 문제 감지됨")

    # 2. 문제 영역 추출
    print(f"\n[2단계] 문제 영역 추출")
    problems = extract_problems_by_markers(image, markers)

    if not problems:
        print("  ❌ 추출된 문제가 없습니다")
        return []

    # 3. 저장
    print(f"\n[3단계] 파일 저장")
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
        print(f"  ✓ 문제 {num}번: {filepath.name} ({file_size:.1f}KB, {prob_img.shape[1]}x{prob_img.shape[0]})")

    return saved_paths


def extract_from_separated_columns(
    column_dir: Path,
    max_x_position: int = 150
) -> None:
    """단 분리된 디렉토리에서 모든 문제 추출

    Args:
        column_dir: 단 분리 결과 디렉토리
        max_x_position: 문제 번호로 인정할 최대 X 좌표
    """
    print("\n" + "=" * 80)
    print(f"단 분리 파일에서 문제 추출 (엄격 모드)")
    print(f"입력 디렉토리: {column_dir}")
    print(f"문제 번호 조건: 왼쪽 {max_x_position}px 이내, '숫자.' 형식만")
    print("=" * 80)

    # col_*.png 파일 찾기
    column_files = sorted(column_dir.glob("col_*.png"))

    if not column_files:
        print("\n❌ col_*.png 파일을 찾을 수 없습니다")
        return

    print(f"\n찾은 파일: {len(column_files)}개")
    for f in column_files:
        print(f"  - {f.name}")

    # 출력 디렉토리
    output_dir = column_dir / "problems_strict"

    all_saved_paths = []

    # 각 단 처리
    for col_file in column_files:
        col_name = col_file.stem  # "col_1", "col_2" 등
        prefix = f"{col_name}_prob"

        saved_paths = process_column_image(
            col_file,
            output_dir,
            prefix=prefix,
            trim=True,
            max_x_position=max_x_position
        )

        all_saved_paths.extend(saved_paths)

    # 요약
    print("\n" + "=" * 80)
    print("✅ 추출 완료!")
    print("=" * 80)
    print(f"\n총 {len(all_saved_paths)}개 문제 추출됨")
    print(f"저장 위치: {output_dir}")

    if all_saved_paths:
        print("\n추출된 파일:")
        for path in sorted(all_saved_paths):
            print(f"  - {path.name}")
    else:
        print("\n⚠️ 추출된 문제가 없습니다")


def main():
    """메인 실행 함수"""
    print("🔍 문제 번호별 추출 (엄격 모드)\n")
    print("규칙:")
    print("  - '1.', '2.', '3.' 등 아라비아 숫자 + 점(dot)만 인정")
    print("  - '①', '(1)', '[1]' 등 보기 번호는 제외")
    print("  - 왼쪽 여백 근처에만 위치 (x < 150px)")
    print()

    # 사회문화 샘플 처리
    column_dir = project_root / "output" / "column_test_사회문화"

    if not column_dir.exists():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {column_dir}")
        print("\n먼저 다음 명령을 실행하세요:")
        print("  uv run python test_column_separation_samples.py")
        return

    extract_from_separated_columns(column_dir, max_x_position=300)

    # 통합과학도 처리
    column_dir2 = project_root / "output" / "column_test_통합과학"

    if column_dir2.exists():
        # auto_*.png 파일명 변경 (col_*.png로)
        auto_files = list(column_dir2.glob("auto_*.png"))
        if auto_files:
            print(f"\n\nauto_*.png 파일을 col_*.png로 변경 중...")
            for auto_file in auto_files:
                new_name = auto_file.name.replace("auto_", "col_")
                new_path = auto_file.parent / new_name
                if not new_path.exists():
                    auto_file.rename(new_path)
                    print(f"  {auto_file.name} → {new_name}")

        extract_from_separated_columns(column_dir2, max_x_position=300)


if __name__ == "__main__":
    main()
