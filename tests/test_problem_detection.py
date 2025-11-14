#!/usr/bin/env python3
"""
Test problem number detection from Tesseract OCR
"""

from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector, mk_layout_from_merged_lines
from core.ocr_engine import run_tesseract_ocr, sort_by_reading_order, parse_problem_number
from core.problem_extractor import detect_problem_markers

# Step 1: Load PDF
pdf_path = "samples/고3_과학탐구_생명과학Ⅰ_문항지.pdf"
images = pdf_to_images(pdf_path, dpi=200)
image = images[0]

# Step 2: Detect layout
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

print(f"Layout: {layout.column_count.value} columns")
print(f"Columns: {[(c.left_x, c.right_x) for c in layout.columns]}\n")

# Step 3: Run OCR
raw_ocr_results = run_tesseract_ocr(image, lang="kor+eng")
ocr_results = sort_by_reading_order(layout, raw_ocr_results)

print(f"Total OCR blocks: {len(ocr_results)}\n")

# Step 4: Find problem numbers
print("Searching for problem numbers...")
for result in ocr_results:
    num = parse_problem_number(result.text)
    if num is not None:
        center = result.bbox.center()
        print(f"  Found: '{result.text}' → Problem {num} @ (x={center.x}, y={center.y})")

# Step 5: Use detect_problem_markers
print("\nUsing detect_problem_markers:")
markers = detect_problem_markers(ocr_results, min_confidence=0.6)
for marker in markers:
    print(f"  Problem {marker.marker_number} @ (x={marker.position.x}, y={marker.position.y})")
    print(f"    OCR text: '{marker.ocr_source.text}' (conf={marker.ocr_source.confidence.value:.2f})")
