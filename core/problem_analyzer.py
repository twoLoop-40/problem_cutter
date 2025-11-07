"""
Problem Analyzer - Extract problem numbers and solution markers from PDFs

This module analyzes PDFs to identify:
- Problem numbers (1., 2., ①, ②, etc.)
- Solution markers ([정답], [해설], etc.)
- Page layout (single/two column)
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
import fitz  # PyMuPDF

from .ocr_engine import (
    run_tesseract_ocr,
    parse_problem_number,
    is_solution_marker,
    sort_by_reading_order,
    OcrResult
)
from .layout_detector import LayoutDetector


def pdf_to_images(pdf_path: str) -> List[np.ndarray]:
    """
    Convert PDF pages to images

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of images (numpy arrays, BGR format)
    """
    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render at 300 DPI for high quality
        zoom = 300 / 72  # 72 is the default DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to numpy array
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )

        # Convert RGBA to BGR if needed
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        images.append(img)

    doc.close()
    return images


def analyze_pdf_structure(pdf_path: str, output_dir: Optional[str] = None) -> dict:
    """
    Analyze PDF structure to extract problem numbers and solution markers

    Args:
        pdf_path: Path to PDF file
        output_dir: Optional directory to save debug images

    Returns:
        Dictionary with structure information:
        {
            'pdf_name': str,
            'num_pages': int,
            'problems': [1, 2, 3, ...],
            'solutions': [1, 2, 3, ...],
            'layout': 'single_column' | 'two_column',
            'pages': [
                {
                    'page_num': 0,
                    'layout': 'single_column' | 'two_column',
                    'problems_found': [1, 2],
                    'solutions_found': [1, 2],
                    'all_text': [...],  # All OCR results
                }
            ]
        }
    """
    print(f"[분석 시작] {pdf_path}")

    # Create output directory
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Convert PDF to images
    images = pdf_to_images(pdf_path)
    print(f"  - {len(images)}페이지 변환 완료")

    # Analyze each page
    all_problems = set()
    all_solutions = set()
    page_info = []
    overall_layout = None

    for page_num, image in enumerate(images):
        print(f"\n[페이지 {page_num + 1}/{len(images)}]")

        # Detect layout
        detector = LayoutDetector()
        layout = detector.detect_layout(image)

        if overall_layout is None:
            overall_layout = "two_column" if len(layout.columns) > 1 else "single_column"

        print(f"  - 레이아웃: {len(layout.columns)}단")

        # Run OCR
        print(f"  - OCR 실행 중...")
        ocr_results = run_tesseract_ocr(image, lang="kor+eng")
        print(f"  - OCR 결과: {len(ocr_results)}개 텍스트 블록")

        # Sort by reading order
        ocr_results = sort_by_reading_order(layout, ocr_results)

        # Extract problem numbers and solution markers
        problems_found = []
        solutions_found = []

        for result in ocr_results:
            # Check for problem number
            prob_num = parse_problem_number(result.text)
            if prob_num is not None:
                problems_found.append(prob_num)
                all_problems.add(prob_num)
                print(f"    ✓ 문제 번호: {prob_num} (신뢰도: {result.confidence.value:.2f})")

            # Check for solution marker
            if is_solution_marker(result.text):
                # Try to find adjacent number
                # (This is a heuristic - solution markers are often near problem numbers)
                solutions_found.append(result.text)
                print(f"    ✓ 솔루션 마커: {result.text} (신뢰도: {result.confidence.value:.2f})")

        # Save debug image
        if output_dir:
            debug_img = image.copy()

            # Draw bounding boxes
            for result in ocr_results:
                prob_num = parse_problem_number(result.text)
                if prob_num is not None:
                    # Red for problem numbers
                    color = (0, 0, 255)
                    thickness = 3
                elif is_solution_marker(result.text):
                    # Blue for solution markers
                    color = (255, 0, 0)
                    thickness = 3
                else:
                    # Gray for other text
                    color = (128, 128, 128)
                    thickness = 1

                bbox = result.bbox
                pt1 = (bbox.top_left.x, bbox.top_left.y)
                pt2 = (bbox.top_left.x + bbox.width, bbox.top_left.y + bbox.height)
                cv2.rectangle(debug_img, pt1, pt2, color, thickness)

                # Add label
                if prob_num is not None or is_solution_marker(result.text):
                    label = result.text
                    cv2.putText(
                        debug_img, label,
                        (pt1[0], pt1[1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, color, 2
                    )

            # Save
            debug_path = os.path.join(output_dir, f"page_{page_num + 1:02d}_analysis.png")
            cv2.imwrite(debug_path, debug_img)
            print(f"  - 디버그 이미지 저장: {debug_path}")

        # Store page info
        page_info.append({
            'page_num': page_num,
            'layout': "two_column" if len(layout.columns) > 1 else "single_column",
            'problems_found': sorted(problems_found),
            'solutions_found': solutions_found,
            'all_text': ocr_results,
        })

    # Compile results
    result = {
        'pdf_name': Path(pdf_path).stem,
        'num_pages': len(images),
        'problems': sorted(all_problems),
        'solutions': [],  # TODO: Better solution number extraction
        'layout': overall_layout,
        'pages': page_info,
    }

    print(f"\n[분석 완료]")
    print(f"  - 문제 번호: {result['problems']}")
    print(f"  - 레이아웃: {result['layout']}")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python problem_analyzer.py <pdf_path> [output_dir]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = analyze_pdf_structure(pdf_path, output_dir)

    print("\n" + "=" * 60)
    print("분석 결과 요약")
    print("=" * 60)
    print(f"파일: {result['pdf_name']}")
    print(f"페이지 수: {result['num_pages']}")
    print(f"레이아웃: {result['layout']}")
    print(f"문제 번호: {result['problems']}")
    print(f"문제 개수: {len(result['problems'])}")
