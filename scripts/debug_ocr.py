"""
Debug OCR Results

Helps diagnose OCR detection issues by:
1. Showing all OCR text near problem markers
2. Analyzing marker patterns and positions
3. Identifying potential false positives

Usage:
    python scripts/debug_ocr.py <pdf_path> [--region x,y,w,h]
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector, mk_layout_from_merged_lines
from core.ocr_engine import run_tesseract_ocr, sort_by_reading_order, parse_problem_number
from core.problem_extractor import detect_problem_markers
import re


def analyze_ocr_around_y(ocr_results, target_y, window=500):
    """Show all OCR results around a specific y coordinate"""
    print(f"\n=== OCR results around y={target_y} (±{window}px) ===")
    relevant = []
    for result in ocr_results:
        center = result.bbox.center()
        if abs(center.y - target_y) <= window:
            relevant.append((center.y, center.x, result.text, result.confidence.value))

    # Sort by y, then x
    relevant.sort()

    for y, x, text, conf in relevant:
        print(f"  y={y:4d}, x={x:4d}, conf={conf:.2f}: '{text}'")


def find_problem_marker_candidates(ocr_results):
    """Find all potential problem markers and analyze them"""
    print("\n=== Problem Marker Candidates ===")
    candidates = []

    for result in ocr_results:
        text = result.text.strip()
        center = result.bbox.center()
        x = result.bbox.top_left.x

        # Check various patterns
        is_candidate = False
        reason = ""

        # Pattern 1: parse_problem_number succeeds
        num = parse_problem_number(text)
        if num is not None:
            is_candidate = True
            reason = f"parse_problem_number → {num}"

        # Pattern 2: Looks like "N."
        elif re.match(r'^\d+\.$', text):
            is_candidate = True
            reason = "matches '^\\d+\\.$'"

        # Pattern 3: Looks like "N,"
        elif re.match(r'^\d+,$', text):
            is_candidate = True
            reason = "matches '^\\d+,$'"

        # Pattern 4: Range marker
        elif re.match(r'^\[\d+~\d+\]', text):
            is_candidate = True
            reason = "range marker"

        # Pattern 5: Score marker (should be filtered)
        elif '점]' in text:
            is_candidate = True
            reason = "SCORE MARKER (should be filtered)"

        if is_candidate:
            candidates.append({
                'text': text,
                'y': center.y,
                'x': x,
                'reason': reason,
                'conf': result.confidence.value
            })

    # Sort by y position
    candidates.sort(key=lambda c: c['y'])

    for c in candidates:
        print(f"  y={c['y']:4d}, x={c['x']:4d}: '{c['text']:15s}' → {c['reason']} (conf={c['conf']:.2f})")

    return candidates


def debug_pdf(pdf_path: str, region=None):
    """
    Debug OCR detection for a PDF

    Args:
        pdf_path: Path to PDF file
        region: Optional (x, y, w, h) to focus on specific area
    """
    print(f"\n{'='*70}")
    print(f"DEBUG OCR: {pdf_path}")
    print(f"{'='*70}")

    # Convert PDF to images
    print("\n[1] Converting PDF to images...")
    images = pdf_to_images(pdf_path, dpi=200)
    if not images:
        print("  ❌ Failed to convert PDF")
        return

    image = images[0]
    print(f"  ✅ Image size: {image.size}")

    # Detect layout
    print("\n[2] Detecting layout...")
    detector = LayoutDetector()
    raw_layout = detector.detect_layout(image)

    if raw_layout.separator_lines:
        layout = mk_layout_from_merged_lines(
            raw_layout.page_width,
            raw_layout.page_height,
            raw_layout.separator_lines
        )
    else:
        layout = raw_layout

    print(f"  ✅ Columns: {layout.column_count.value}")
    if layout.columns:
        for i, col in enumerate(layout.columns):
            print(f"     Column {i+1}: x={col.left_x}~{col.right_x}")

    # Run OCR
    print("\n[3] Running OCR...")
    raw_ocr_results = run_tesseract_ocr(image, lang="kor+eng")
    ocr_results = sort_by_reading_order(layout, raw_ocr_results)
    print(f"  ✅ Detected {len(ocr_results)} text blocks")

    # Analyze problem marker candidates
    candidates = find_problem_marker_candidates(ocr_results)

    # Detect markers using current algorithm
    print("\n[4] Running detect_problem_markers()...")
    markers = detect_problem_markers(ocr_results, pdf_path=pdf_path)
    print(f"  ✅ Detected {len(markers)} markers:")
    for m in markers:
        print(f"     Problem {m.marker_number} @ (x={m.position.x}, y={m.position.y})")

    # Show detailed context for each marker
    print("\n[5] Context around each marker:")
    for m in markers:
        analyze_ocr_around_y(ocr_results, m.position.y, window=300)

    # If region specified, show OCR in that region
    if region:
        x, y, w, h = region
        print(f"\n[6] OCR in specified region (x={x}, y={y}, w={w}, h={h}):")
        for result in ocr_results:
            cx, cy = result.bbox.center().x, result.bbox.center().y
            if x <= cx <= x+w and y <= cy <= y+h:
                print(f"  y={cy:4d}, x={cx:4d}: '{result.text}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Debug OCR detection")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--region", help="Region to focus on (x,y,w,h)")

    args = parser.parse_args()

    region = None
    if args.region:
        try:
            region = tuple(map(int, args.region.split(',')))
            if len(region) != 4:
                raise ValueError
        except:
            print("Error: --region must be in format x,y,w,h")
            sys.exit(1)

    # Check if PDF exists
    if not Path(args.pdf_path).exists():
        print(f"Error: PDF not found: {args.pdf_path}")
        sys.exit(1)

    debug_pdf(args.pdf_path, region)
