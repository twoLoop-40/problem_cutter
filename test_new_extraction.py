"""
Test new extraction workflow with column linearization.

Workflow:
1. Load PDF page as image
2. Detect column layout
3. Linearize columns (2-column → 1-column vertical strip)
4. Detect problem markers in linearized image
5. Calculate boundaries (Problem N = marker N ~ marker N+1)
6. Extract and validate against ground truth
"""

from pathlib import Path
import sys
import numpy as np
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.column_linearizer import process_image
from core.problem_boundary import (
    detect_markers_in_linearized,
    calculate_boundaries,
    extract_problems,
    validate_all_boundaries,
    SOCIAL_STUDIES_GROUND_TRUTH,
    SCIENCE_GROUND_TRUTH
)
from core.ocr_engine import OcrEngine
from core.layout_detector import LayoutDetector


def test_sample(sample_name: str, pdf_path: Path, ground_truth: list):
    """Test extraction on a sample PDF"""
    print(f"\n{'='*80}")
    print(f"Testing: {sample_name}")
    print(f"{'='*80}\n")

    output_dir = Path(f"output/{sample_name}_new")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Convert PDF to image (using first page)
    print("Step 1: Loading PDF page...")
    from pdf2image import convert_from_path
    images = convert_from_path(pdf_path, dpi=300)

    if not images:
        print("❌ Failed to load PDF")
        return

    page_image = np.array(images[0])
    print(f"  Page size: {page_image.shape[1]}x{page_image.shape[0]}")

    # Save original
    original_path = output_dir / "01_original.png"
    Image.fromarray(page_image).save(original_path)
    print(f"  Saved: {original_path}")

    # Step 2-3: Column linearization
    print("\nStep 2-3: Column linearization...")
    layout_detector = LayoutDetector()
    linearized = process_image(original_path, layout_detector)

    # Save linearized image
    linearized_path = output_dir / "02_linearized.png"
    linearized.save(linearized_path)
    print(f"  Saved: {linearized_path}")

    # Step 4: Detect problem markers
    print("\nStep 4: Detecting problem markers...")
    ocr_engine = OcrEngine()
    markers = detect_markers_in_linearized(linearized, ocr_engine)

    if not markers:
        print("❌ No markers detected!")
        return

    # Step 5: Calculate boundaries
    print("\nStep 5: Calculating boundaries...")
    boundaries = calculate_boundaries(
        markers,
        linearized.total_height,
        linearized.linearized_image.shape[1]
    )

    # Step 6: Validate against ground truth
    print("\nStep 6: Validating against ground truth...")
    validation_results = validate_all_boundaries(boundaries, ground_truth, tolerance=100)

    # Step 7: Extract problems
    print("\nStep 7: Extracting problems...")
    extraction_results = extract_problems(
        linearized,
        boundaries,
        output_dir / "problems",
        trim_whitespace=True
    )

    # Summary
    print(f"\n{'='*80}")
    print(f"Summary for {sample_name}:")
    print(f"  Markers detected: {len(markers)}")
    print(f"  Boundaries calculated: {len(boundaries)}")
    print(f"  Validation: {validation_results['matches']}/{validation_results['validated']} matches")
    print(f"  Problems extracted: {len(extraction_results)}")
    print(f"  Output: {output_dir}")
    print(f"{'='*80}\n")

    return validation_results


def main():
    """Run tests on all samples"""
    # Sample 1: 사회탐구 (Social Studies) - should have 5 problems
    social_pdf = Path("samples/고3_사회탐구_사회문화_1p.pdf")
    if social_pdf.exists():
        test_sample("사회탐구", social_pdf, SOCIAL_STUDIES_GROUND_TRUTH)
    else:
        print(f"⚠️  Sample not found: {social_pdf}")

    # Sample 2: 통합과학 (Integrated Science) - should have 4 problems + 1 shared passage
    science_pdf = Path("samples/통합과학_1_샘플.pdf")
    if science_pdf.exists():
        test_sample("통합과학", science_pdf, SCIENCE_GROUND_TRUTH)
    else:
        print(f"⚠️  Sample not found: {science_pdf}")


if __name__ == "__main__":
    main()
