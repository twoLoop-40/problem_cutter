"""
Problem Cutter - Cut PDF problems into individual images

This module implements the problem cutting workflow:
1. Linearize multi-column layout to single column
2. Scan vertically to find problem number markers
3. Cut each problem region
4. Trim whitespace and save to individual files
"""

import os
import re
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import cv2
import numpy as np
import fitz  # PyMuPDF

from .ocr_engine import run_tesseract_ocr, parse_problem_number, sort_by_reading_order
from .layout_detector import LayoutDetector
from .base import BBox, Coord


@dataclass
class ProblemRegion:
    """A problem region in the linearized image"""
    number: int
    bbox: BBox
    y_start: int  # Start Y position in linearized image
    y_end: int    # End Y position in linearized image


def pdf_to_high_res_image(pdf_path: str, page_num: int = 0, dpi: int = 300) -> np.ndarray:
    """Convert PDF page to high-resolution image"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )

    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    doc.close()
    return img


def linearize_two_column(image: np.ndarray, layout) -> np.ndarray:
    """
    Linearize two-column layout to single column

    Stacks left column on top of right column

    Args:
        image: Original image
        layout: PageLayout with column information

    Returns:
        Linearized image (left column stacked on top of right column)
    """
    if not layout.columns or len(layout.columns) < 2:
        # Single column, no linearization needed
        return image

    height, width = image.shape[:2]

    # Get column boundaries
    left_col = layout.columns[0]
    right_col = layout.columns[1]

    # Extract columns
    left_img = image[:, left_col.left_x:left_col.right_x]
    right_img = image[:, right_col.left_x:right_col.right_x]

    # Make sure both columns have the same width
    max_width = max(left_img.shape[1], right_img.shape[1])

    if left_img.shape[1] < max_width:
        padding = np.full((left_img.shape[0], max_width - left_img.shape[1], 3), 255, dtype=np.uint8)
        left_img = np.hstack([left_img, padding])

    if right_img.shape[1] < max_width:
        padding = np.full((right_img.shape[0], max_width - right_img.shape[1], 3), 255, dtype=np.uint8)
        right_img = np.hstack([right_img, padding])

    # Stack vertically
    linearized = np.vstack([left_img, right_img])

    return linearized


def find_problem_markers(image: np.ndarray, layout) -> List[Tuple[int, int, int]]:
    """
    Find problem number markers in the image

    Returns:
        List of (problem_number, y_position, confidence*100)
    """
    print("  - OCR 실행하여 문제 번호 검색...")
    ocr_results = run_tesseract_ocr(image, lang="kor+eng")

    # Sort by reading order
    ocr_results = sort_by_reading_order(layout, ocr_results)

    markers = []
    for result in ocr_results:
        prob_num = parse_problem_number(result.text)
        if prob_num is not None:
            y_pos = result.bbox.top_left.y
            conf = int(result.confidence.value * 100)
            markers.append((prob_num, y_pos, conf))
            print(f"    ✓ 문제 {prob_num}번 (Y={y_pos}, 신뢰도={conf}%)")

    return markers


def segment_problems(
    image: np.ndarray,
    markers: List[Tuple[int, int, int]],
    min_height: int = 200
) -> List[ProblemRegion]:
    """
    Segment problems based on markers

    Args:
        image: Linearized image
        markers: List of (problem_number, y_position, confidence)
        min_height: Minimum problem height (to filter noise)

    Returns:
        List of ProblemRegion
    """
    if not markers:
        return []

    height, width = image.shape[:2]

    # Sort markers by Y position
    markers_sorted = sorted(markers, key=lambda m: m[1])

    # Filter: remove duplicate numbers, keep highest confidence
    unique_markers = {}
    for num, y, conf in markers_sorted:
        if num not in unique_markers or conf > unique_markers[num][1]:
            unique_markers[num] = (y, conf)

    # Sort by problem number
    markers_final = sorted(
        [(num, y, conf) for num, (y, conf) in unique_markers.items()],
        key=lambda m: m[0]
    )

    print(f"\n  - 유효한 문제 번호: {[m[0] for m in markers_final]}")

    # Create regions
    regions = []
    for i, (num, y, conf) in enumerate(markers_final):
        y_start = y - 50  # Add some padding above

        # Find y_end (start of next problem or end of image)
        if i + 1 < len(markers_final):
            y_end = markers_final[i + 1][1] - 50
        else:
            y_end = height

        # Skip if too small
        if y_end - y_start < min_height:
            print(f"    ⚠️  문제 {num}번 건너뛰기 (높이 {y_end - y_start} < {min_height})")
            continue

        bbox = BBox(
            top_left=Coord(0, y_start),
            width=width,
            height=y_end - y_start
        )

        regions.append(ProblemRegion(
            number=num,
            bbox=bbox,
            y_start=y_start,
            y_end=y_end
        ))

    return regions


def trim_whitespace(image: np.ndarray, padding: int = 20) -> np.ndarray:
    """
    Trim excessive whitespace from image edges

    Args:
        image: Input image
        padding: Padding to keep around content (pixels)

    Returns:
        Trimmed image
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Threshold
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return image

    # Get bounding box of all content
    x_min, y_min = image.shape[1], image.shape[0]
    x_max, y_max = 0, 0

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        x_min = min(x_min, x)
        y_min = min(y_min, y)
        x_max = max(x_max, x + w)
        y_max = max(y_max, y + h)

    # Add padding
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(image.shape[1], x_max + padding)
    y_max = min(image.shape[0], y_max + padding)

    # Crop
    trimmed = image[y_min:y_max, x_min:x_max]

    return trimmed


def cut_problems(
    pdf_path: str,
    output_dir: str,
    page_num: int = 0,
    dpi: int = 300,
    create_zip: bool = True
) -> dict:
    """
    Cut problems from PDF and save to individual files

    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory
        page_num: Page number to process (0-indexed)
        dpi: Resolution for rendering
        create_zip: Whether to create a zip file of results

    Returns:
        Dictionary with cutting results
    """
    print(f"\n{'='*60}")
    print(f"문제 자르기 시작: {Path(pdf_path).name}")
    print(f"{'='*60}\n")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Convert PDF to image
    print("[1단계] PDF를 이미지로 변환...")
    image = pdf_to_high_res_image(pdf_path, page_num, dpi)
    print(f"  - 이미지 크기: {image.shape[1]}x{image.shape[0]}")

    # Save original
    original_path = output_path / "00_original.png"
    cv2.imwrite(str(original_path), image)
    print(f"  - 원본 저장: {original_path}")

    # Step 2: Detect layout
    print("\n[2단계] 레이아웃 감지...")
    detector = LayoutDetector()
    layout = detector.detect_layout(image)
    print(f"  - 감지된 레이아웃: {len(layout.columns)}단")

    # Step 3: Linearize if needed
    print("\n[3단계] 단 분리 및 Linearization...")
    if len(layout.columns) > 1:
        linearized = linearize_two_column(image, layout)
        print(f"  - Linearized 크기: {linearized.shape[1]}x{linearized.shape[0]}")

        # Save linearized
        linearized_path = output_path / "01_linearized.png"
        cv2.imwrite(str(linearized_path), linearized)
        print(f"  - Linearized 이미지 저장: {linearized_path}")
    else:
        linearized = image
        print("  - 단일 단 레이아웃, linearization 불필요")

    # Step 4: Find problem markers
    print("\n[4단계] 문제 번호 검색...")
    # For marker detection, use single column layout
    single_col_layout = LayoutDetector().detect_layout(linearized)
    markers = find_problem_markers(linearized, single_col_layout)

    if not markers:
        print("  ⚠️  문제 번호를 찾을 수 없습니다!")
        return {
            'success': False,
            'error': 'No problem markers found',
            'output_dir': str(output_path)
        }

    # Step 5: Segment problems
    print("\n[5단계] 문제 영역 분할...")
    regions = segment_problems(linearized, markers)

    if not regions:
        print("  ⚠️  유효한 문제 영역을 찾을 수 없습니다!")
        return {
            'success': False,
            'error': 'No valid problem regions found',
            'output_dir': str(output_path)
        }

    print(f"  - 총 {len(regions)}개 문제 영역 생성")

    # Step 6: Cut and save each problem
    print("\n[6단계] 문제별로 자르기 및 저장...")
    problems_dir = output_path / "problems"
    problems_dir.mkdir(exist_ok=True)

    saved_files = []
    for region in regions:
        # Extract region
        problem_img = linearized[region.y_start:region.y_end, :]

        # Trim whitespace
        trimmed = trim_whitespace(problem_img, padding=20)

        # Save
        filename = f"problem_{region.number:02d}.png"
        filepath = problems_dir / filename
        cv2.imwrite(str(filepath), trimmed)
        saved_files.append(str(filepath))

        print(f"  ✓ 문제 {region.number}번 저장: {filename} ({trimmed.shape[1]}x{trimmed.shape[0]})")

    # Step 7: Create zip file
    if create_zip and saved_files:
        print("\n[7단계] ZIP 파일 생성...")
        zip_path = output_path / "problems.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filepath in saved_files:
                arcname = Path(filepath).name
                zipf.write(filepath, arcname)

        print(f"  ✓ ZIP 파일 생성: {zip_path}")

    print(f"\n{'='*60}")
    print("완료!")
    print(f"{'='*60}")

    return {
        'success': True,
        'num_problems': len(regions),
        'problems': [r.number for r in regions],
        'output_dir': str(output_path),
        'problems_dir': str(problems_dir),
        'zip_path': str(zip_path) if create_zip else None,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python problem_cutter.py <pdf_path> <output_dir>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]

    result = cut_problems(pdf_path, output_dir)

    if result['success']:
        print(f"\n성공적으로 {result['num_problems']}개 문제를 추출했습니다.")
        print(f"문제 번호: {result['problems']}")
        print(f"출력 디렉토리: {result['output_dir']}")
        if result.get('zip_path'):
            print(f"ZIP 파일: {result['zip_path']}")
    else:
        print(f"\n실패: {result.get('error', 'Unknown error')}")
        sys.exit(1)
