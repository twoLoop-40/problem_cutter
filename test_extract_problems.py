#!/usr/bin/env python3
"""
Test full workflow: PDF → Layout → OCR → Extract → Crop → Save

This script extracts individual problems from PDF and saves them as separate images.
"""

from pathlib import Path
from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector, mk_layout_from_merged_lines
from core.ocr_engine import run_tesseract_ocr, sort_by_reading_order
from core.problem_extractor import extract_problems
from core.image_cropper import crop_image
import numpy as np

def test_extract_and_crop(pdf_path: str, output_dir: str = "output"):
    """
    Extract problems from PDF and save as individual images

    Args:
        pdf_path: Path to input PDF
        output_dir: Directory to save extracted problem images
    """
    print(f"\n{'='*60}")
    print(f"Testing: {pdf_path}")
    print(f"{'='*60}\n")

    # Create output directory
    pdf_name = Path(pdf_path).stem
    out_path = Path(output_dir) / pdf_name
    out_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Convert PDF to images
    print("Step 1: Converting PDF to images...")
    images = pdf_to_images(pdf_path, dpi=200)
    print(f"  → {len(images)} page(s) converted\n")

    for page_num, image in enumerate(images, start=1):
        print(f"Processing Page {page_num}...")
        print("-" * 60)

        # Step 2: Detect layout
        print("  Step 2: Detecting layout...")
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

        print(f"    → {layout.column_count.value} column(s)")
        print(f"    → Bounds: {[(c.left_x, c.right_x) for c in layout.columns]}\n")

        # Step 3: Run OCR
        print("  Step 3: Running OCR...")
        raw_ocr_results = run_tesseract_ocr(image, lang="kor+eng")
        ocr_results = sort_by_reading_order(layout, raw_ocr_results)
        print(f"    → {len(ocr_results)} text blocks detected\n")

        # Step 4: Collect all bounding boxes from OCR
        print("  Step 4: Collecting content boxes...")
        all_boxes = [result.bbox for result in ocr_results]
        print(f"    → {len(all_boxes)} boxes collected\n")

        # Step 5: Extract problems
        print("  Step 5: Extracting problems...")
        problems = extract_problems(
            pdf_path=pdf_path,
            page_num=page_num,
            layout=layout,
            ocr_results=ocr_results,
            all_boxes=all_boxes
        )

        print(f"    → Found {len(problems)} problem(s)\n")

        # Step 6: Crop and save problem images
        print("  Step 6: Saving problem images...")
        for problem in problems:
            # Crop image
            cropped = crop_image(image, problem.region)

            # Save as PNG
            problem_file = out_path / f"page{page_num}_problem{problem.number}.png"

            # Convert numpy array to PIL Image for saving
            from PIL import Image as PILImage
            pil_image = PILImage.fromarray(cropped)
            pil_image.save(problem_file)

            print(f"    ✓ Problem {problem.number:2d} → {problem_file.name}")
            print(f"        BBox: x={problem.region.top_left.x}, y={problem.region.top_left.y}, "
                  f"w={problem.region.width}, h={problem.region.height}")

        print()

    print(f"{'='*60}")
    print(f"✓ Extraction complete!")
    print(f"  Output: {out_path}/")
    print(f"{'='*60}\n")

    return out_path


if __name__ == "__main__":
    # Test both sample PDFs
    samples = [
        "samples/통합과학_1_샘플.pdf",
        "samples/고3_사회탐구_사회문화_1p.pdf"
    ]

    for sample in samples:
        if Path(sample).exists():
            try:
                test_extract_and_crop(sample)
            except Exception as e:
                print(f"❌ Error processing {sample}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️  File not found: {sample}")
