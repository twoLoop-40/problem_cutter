"""
Complete workflow for PDF problem extraction

This module implements the workflow defined in System.Workflow.idr.

Workflow steps:
1. Extract metadata
2. Detect layout
3. Run OCR
4. Extract problems
5. Extract solutions
6. Pair problems with solutions
7. Generate output files

Implementation follows: .specs/System/Workflow.idr
"""

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, List
import traceback

from .pdf_converter import pdf_to_images
from .layout_detector import LayoutDetector, mk_layout_from_merged_lines
from .ocr_engine import OcrResult, OcrEngine
from .problem_extractor import (
    extract_problems,
    extract_solutions,
    ExtractionResult,
    ProblemPair
)


class WorkflowState(Enum):
    """State of the extraction workflow"""
    INITIAL = "initial"
    METADATA_EXTRACTED = "metadata_extracted"
    LAYOUT_DETECTED = "layout_detected"
    OCR_COMPLETED = "ocr_completed"
    CONTENT_EXTRACTED = "content_extracted"
    OUTPUT_GENERATED = "output_generated"
    FAILED = "failed"


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    state: WorkflowState
    message: str
    output_path: Optional[Path] = None


def execute_pdf_extraction(pdf_path: str,
                           output_format: str = "png") -> WorkflowResult:
    """
    Execute complete PDF extraction workflow

    This is the main entry point that orchestrates all steps:
    1. Extract metadata (TODO)
    2. Detect layout
    3. Run OCR (TODO: integrate Tesseract/EasyOCR)
    4. Extract problems
    5. Extract solutions
    6. Pair problems with solutions
    7. Generate output files (TODO)

    Args:
        pdf_path: Path to input PDF
        output_format: Output format ("png", "jpg", "pdf")

    Returns:
        WorkflowResult with execution status
    """
    try:
        # Validate input
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            return WorkflowResult(
                success=False,
                state=WorkflowState.FAILED,
                message=f"PDF file not found: {pdf_path}"
            )

        # Step 1: Extract metadata (TODO)
        # For now, skip metadata extraction
        print("Step 1: Extract metadata - SKIPPED")

        # Step 2: Detect layout
        print("Step 2: Detecting layout...")
        images = pdf_to_images(pdf_path, dpi=200)
        if not images:
            return WorkflowResult(
                success=False,
                state=WorkflowState.FAILED,
                message="Failed to convert PDF to images"
            )

        # Process first page for now
        image = images[0]
        detector = LayoutDetector()
        raw_layout = detector.detect_layout(image)

        # Use improved layout detection with narrow column merging
        if raw_layout.separator_lines:
            layout = mk_layout_from_merged_lines(
                raw_layout.page_width,
                raw_layout.page_height,
                raw_layout.separator_lines
            )
        else:
            layout = raw_layout

        print(f"   Detected: {layout.column_count.value} columns")
        print(f"   Method: {layout.detection_method.value}")

        # Step 3: Run OCR
        print("Step 3: Running OCR with Tesseract...")
        from .ocr_engine import run_tesseract_ocr, sort_by_reading_order
        try:
            raw_ocr_results = run_tesseract_ocr(image, lang="kor+eng")
            print(f"   Detected {len(raw_ocr_results)} text blocks")

            # Sort by reading order (left column → right column)
            ocr_results = sort_by_reading_order(layout, raw_ocr_results)
            print(f"   ✅ Sorted by reading order ({layout.column_count.value} columns)")

            # Show sample results
            if ocr_results:
                print("   Sample OCR results (reading order):")
                for i, result in enumerate(ocr_results[:5]):
                    text_preview = result.text[:30] + "..." if len(result.text) > 30 else result.text
                    center = result.bbox.center()
                    print(f"      [{i+1}] '{text_preview}' @ (x={center.x}, y={center.y}, conf={result.confidence.value:.2f})")
        except Exception as e:
            import traceback
            print(f"   ⚠ OCR failed: {str(e)}")
            traceback.print_exc()
            ocr_results = []

        # Step 4: Detect problem boundaries
        print("Step 4: Detecting problem boundaries...")
        from .problem_extractor import detect_problem_boundaries
        try:
            # Get all bbox from OCR for gap analysis
            all_boxes = [r.bbox for r in ocr_results]

            problem_boundaries = detect_problem_boundaries(
                strategy="marker_based",  # Use marker-based detection
                layout=layout,
                ocr_results=ocr_results,
                all_boxes=all_boxes,
                pdf_path=pdf_path  # Enable PyMuPDF fallback for missing markers
            )

            print(f"   Detected {len(problem_boundaries)} problems")
            for prob_num, bbox in problem_boundaries[:5]:  # Show first 5
                print(f"      Problem {prob_num}: y={bbox.top_left.y}, height={bbox.height}")

        except Exception as e:
            import traceback
            print(f"   ⚠ Boundary detection failed: {str(e)}")
            traceback.print_exc()
            problem_boundaries = []

        # Step 5: Crop problem regions
        if problem_boundaries:
            print("Step 5: Cropping problem regions...")
            from .image_cropper import crop_problems_from_page, visualize_boundaries

            # Create output directory
            output_dir = Path("output") / Path(pdf_path).stem
            output_dir.mkdir(parents=True, exist_ok=True)

            # Crop problems
            problem_results = crop_problems_from_page(
                image,
                problem_boundaries,
                str(output_dir / "problems"),
                margin=20
            )

            # Visualize boundaries
            vis_path = output_dir / "boundaries_visualization.png"
            visualize_boundaries(image, problem_boundaries, str(vis_path))
            print(f"   ✅ Saved visualization: {vis_path}")

        else:
            print("Step 5: No problems detected, skipping crop")
            problem_results = []

        # Step 6: Generate output package (ZIP, metadata)
        if problem_results:
            print("Step 6: Packaging outputs...")
            from .output_generator import package_outputs

            package_results = package_outputs(
                output_dir=str(output_dir),
                problem_results=problem_results,
                solution_results=[],  # TODO: implement solution extraction
                pdf_path=pdf_path
            )

            print(f"   ✅ Generated:")
            for key, path in package_results.items():
                print(f"      - {key}: {path}")

            return WorkflowResult(
                success=True,
                state=WorkflowState.OUTPUT_GENERATED,
                message=f"Successfully extracted {len(problem_results)} problems",
                output_path=Path(package_results.get("zip", str(output_dir)))
            )
        else:
            return WorkflowResult(
                success=False,
                state=WorkflowState.FAILED,
                message="No problems extracted"
            )

    except Exception as e:
        return WorkflowResult(
            success=False,
            state=WorkflowState.FAILED,
            message=f"Workflow failed: {str(e)}"
        )


def main():
    """Main entry point for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m core.workflow <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"\n{'='*70}")
    print(f"PDF Problem Extraction Workflow")
    print(f"{'='*70}\n")
    print(f"Input: {pdf_path}\n")

    result = execute_pdf_extraction(pdf_path)

    print(f"\n{'='*70}")
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"State: {result.state.value}")
    print(f"Message: {result.message}")
    print(f"{'='*70}\n")

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
