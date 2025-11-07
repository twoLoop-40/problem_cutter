"""
Problem boundary detection in linearized content.

Implements ProblemBoundary.idr:
1. Detect problem markers (OCR) in linearized image
2. Calculate boundaries: Problem N = marker N ~ marker N+1
3. Handle shared passages (e.g., [8_9])
4. Validate against ground truth

Key insight:
- Problem N includes ALL content between two markers
- This captures passages/figures ABOVE the marker
- And problem text/choices BELOW the marker
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np
from PIL import Image

from .column_linearizer import LinearizedContent
from .ocr_engine import parse_problem_number, run_tesseract_ocr


@dataclass
class ProblemMarker:
    """Problem marker detected by OCR"""
    number: int
    y_position: int  # Y coordinate in linearized content
    confidence: float

    def __repr__(self) -> str:
        return f"Marker({self.number}, y={self.y_position}, conf={self.confidence:.2f})"


@dataclass
class SharedPassage:
    """Shared passage marker (e.g., [8_9] for problems 8 and 9)"""
    problem_numbers: List[int]
    y_position: int
    confidence: float

    def __repr__(self) -> str:
        nums = '_'.join(map(str, self.problem_numbers))
        return f"SharedPassage([{nums}], y={self.y_position})"


@dataclass
class ProblemBoundary:
    """Problem boundary in linearized content"""
    problem_number: int
    start_y: int  # Start position (inclusive)
    end_y: int    # End position (exclusive)
    width: int    # Width from linearized content

    @property
    def height(self) -> int:
        """Height of the boundary"""
        return self.end_y - self.start_y

    def __repr__(self) -> str:
        return f"Boundary({self.problem_number}, y={self.start_y}~{self.end_y}, h={self.height})"


@dataclass
class GroundTruth:
    """Ground truth dimensions from manual extraction"""
    problem_number: int
    expected_width: int
    expected_height: int


# Ground truth data from results/
SOCIAL_STUDIES_GROUND_TRUTH = [
    GroundTruth(1, 1174, 946),
    GroundTruth(2, 1164, 830),
    GroundTruth(3, 1198, 1036),
    GroundTruth(4, 1176, 1396),
    GroundTruth(5, 1182, 1168),
]

SCIENCE_GROUND_TRUTH = [
    GroundTruth(6, 1194, 1150),
    GroundTruth(7, 1240, 1384),
    GroundTruth(8, 1224, 1140),
    GroundTruth(9, 1222, 1196),
]

SCIENCE_SHARED_PASSAGE_GROUND_TRUTH = [
    GroundTruth(89, 1202, 556),  # [8_9] shared passage
]


def detect_markers_in_linearized(
    linearized: LinearizedContent,
    lang: str = "kor+eng"
) -> List[ProblemMarker]:
    """Detect problem markers in linearized content using OCR

    Strategy: Find consecutive number pairs (n, n+1) to avoid false positives
    - "1." followed by "2." → Problem 1 confirmed
    - "2." followed by "3." → Problem 2 confirmed
    - Last number → extends to end of content

    Args:
        linearized: Linearized content
        lang: OCR language (default "kor+eng")

    Returns:
        List of validated problem markers (sorted by y_position)
    """
    # Run OCR on linearized image
    ocr_results = run_tesseract_ocr(linearized.linearized_image, lang)

    # Extract ALL potential markers
    all_markers = []
    for result in ocr_results:
        text = result.text
        number = parse_problem_number(text)

        if number is not None:
            y_pos = result.bbox.top_left.y
            conf = result.confidence.value if hasattr(result.confidence, 'value') else result.confidence
            all_markers.append(ProblemMarker(number, y_pos, conf))

    # Sort by y_position
    all_markers.sort(key=lambda m: m.y_position)

    # Remove duplicates within same number (keep highest confidence)
    unique_by_number = {}
    for m in all_markers:
        if m.number not in unique_by_number or m.confidence > unique_by_number[m.number].confidence:
            unique_by_number[m.number] = m

    # Sort by Y position again
    candidates = sorted(unique_by_number.values(), key=lambda m: m.y_position)

    print(f"\nFound {len(candidates)} candidate markers:")
    for m in candidates:
        print(f"  {m}")

    # Find consecutive pairs: (n, n+1)
    # Strategy: Find all pairs, then extract unique markers
    validated_set = set()

    for i in range(len(candidates) - 1):
        current = candidates[i]
        next_marker = candidates[i + 1]

        if next_marker.number == current.number + 1:
            # Consecutive pair found!
            validated_set.add(current.number)
            validated_set.add(next_marker.number)
            print(f"  ✅ Pair found: {current.number} → {next_marker.number}")

    # If no pairs found but we have candidates, validate the single marker
    if not validated_set and len(candidates) == 1:
        validated_set.add(candidates[0].number)
        print(f"  ✅ Single marker: {candidates[0].number}")

    # Build final list with validated markers only
    validated = [m for m in candidates if m.number in validated_set]

    print(f"\n✅ Validated {len(validated)} problem markers:")
    for m in validated:
        print(f"  {m}")

    return validated


def detect_shared_passages(
    linearized: LinearizedContent,
    lang: str = "kor+eng"
) -> List[SharedPassage]:
    """Detect shared passages like [8_9] in linearized content

    Args:
        linearized: Linearized content
        lang: OCR language (default "kor+eng")

    Returns:
        List of detected shared passages
    """
    ocr_results = run_tesseract_ocr(linearized.linearized_image, lang)

    passages = []
    for result in ocr_results:
        text = result.text.strip()

        # Look for patterns like [8_9], [1-2], etc.
        import re
        # Pattern 1: [8_9]
        match = re.match(r'^\[(\d+)_(\d+)\]$', text)
        if match:
            num1, num2 = int(match.group(1)), int(match.group(2))
            y_pos = result.bbox.top_left.y
            conf = result.confidence.value if hasattr(result.confidence, 'value') else result.confidence
            passages.append(SharedPassage([num1, num2], y_pos, conf))
            continue

        # Pattern 2: [8-9]
        match = re.match(r'^\[(\d+)-(\d+)\]$', text)
        if match:
            num1, num2 = int(match.group(1)), int(match.group(2))
            y_pos = result.bbox.top_left.y
            conf = result.confidence.value if hasattr(result.confidence, 'value') else result.confidence
            passages.append(SharedPassage([num1, num2], y_pos, conf))

    if passages:
        print(f"\nDetected {len(passages)} shared passages:")
        for p in passages:
            print(f"  {p}")

    return passages


def calculate_boundaries(
    markers: List[ProblemMarker],
    total_height: int,
    width: int
) -> List[ProblemBoundary]:
    """Calculate problem boundaries from markers

    Strategy from ProblemBoundary.idr:
    - Problem N: marker N ~ marker N+1
    - First problem: 0 ~ marker 2
    - Last problem: marker N ~ total_height

    This captures ALL content between markers, including:
    - Passages/figures ABOVE the marker
    - Problem text and choices BELOW the marker

    Args:
        markers: List of detected problem markers
        total_height: Total height of linearized content
        width: Width of linearized content

    Returns:
        List of problem boundaries
    """
    if not markers:
        print("Warning: No markers detected!")
        return []

    boundaries = []

    for i, marker in enumerate(markers):
        # Start Y: 0 if first, otherwise current marker position
        if i == 0:
            start_y = 0
        else:
            start_y = marker.y_position

        # End Y: next marker position (or totalHeight if last)
        if i < len(markers) - 1:
            end_y = markers[i + 1].y_position
        else:
            end_y = total_height

        boundary = ProblemBoundary(
            problem_number=marker.number,
            start_y=start_y,
            end_y=end_y,
            width=width
        )

        boundaries.append(boundary)

    print(f"\nCalculated {len(boundaries)} boundaries:")
    for b in boundaries:
        print(f"  {b}")

    return boundaries


def validate_boundary(
    boundary: ProblemBoundary,
    ground_truth: GroundTruth,
    tolerance: int = 100
) -> Tuple[bool, str]:
    """Validate extracted boundary against ground truth

    Args:
        boundary: Extracted boundary
        ground_truth: Expected dimensions
        tolerance: Tolerance in pixels (default 100px)

    Returns:
        (is_valid, message) tuple
    """
    actual_width = boundary.width
    actual_height = boundary.height
    expected_width = ground_truth.expected_width
    expected_height = ground_truth.expected_height

    width_diff = abs(actual_width - expected_width)
    height_diff = abs(actual_height - expected_height)

    if width_diff <= tolerance and height_diff <= tolerance:
        return True, f"✅ Match (w±{width_diff}, h±{height_diff})"

    elif width_diff > tolerance:
        return False, f"❌ Width mismatch: expected {expected_width}, got {actual_width} (diff={width_diff})"

    else:
        return False, f"❌ Height mismatch: expected {expected_height}, got {actual_height} (diff={height_diff})"


def validate_all_boundaries(
    boundaries: List[ProblemBoundary],
    ground_truth_list: List[GroundTruth],
    tolerance: int = 100
) -> Dict[str, any]:
    """Validate all boundaries against ground truth

    Args:
        boundaries: Extracted boundaries
        ground_truth_list: Expected dimensions
        tolerance: Tolerance in pixels

    Returns:
        Dictionary with validation results
    """
    ground_truth_map = {gt.problem_number: gt for gt in ground_truth_list}

    results = {
        "total": len(boundaries),
        "validated": 0,
        "matches": 0,
        "mismatches": 0,
        "details": []
    }

    print("\n=== Validation Results ===")

    for boundary in boundaries:
        if boundary.problem_number not in ground_truth_map:
            print(f"⚠️  Problem {boundary.problem_number}: No ground truth")
            continue

        gt = ground_truth_map[boundary.problem_number]
        is_valid, message = validate_boundary(boundary, gt, tolerance)

        results["validated"] += 1
        if is_valid:
            results["matches"] += 1
        else:
            results["mismatches"] += 1

        results["details"].append({
            "problem_number": boundary.problem_number,
            "is_valid": is_valid,
            "message": message,
            "actual": {"width": boundary.width, "height": boundary.height},
            "expected": {"width": gt.expected_width, "height": gt.expected_height}
        })

        print(f"Problem {boundary.problem_number}: {message}")

    print(f"\nSummary: {results['matches']}/{results['validated']} matches ({results['mismatches']} mismatches)")

    return results


def extract_problems(
    linearized: LinearizedContent,
    boundaries: List[ProblemBoundary],
    output_dir: Path,
    trim_whitespace: bool = True
) -> List[Dict]:
    """Extract problem images from linearized content

    Args:
        linearized: Linearized content
        boundaries: Problem boundaries
        output_dir: Output directory
        trim_whitespace: Whether to trim whitespace from edges

    Returns:
        List of extraction results
    """
    from .column_linearizer import crop_region, trim_whitespace as trim_fn

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    print(f"\n=== Extracting Problems ===")

    for boundary in boundaries:
        # Crop region
        cropped = crop_region(linearized, boundary.start_y, boundary.end_y)

        # Trim whitespace if requested
        if trim_whitespace:
            cropped = trim_fn(cropped)

        # Save
        filename = f"{boundary.problem_number:02d}_prb.png"
        output_path = output_dir / filename

        Image.fromarray(cropped).save(output_path)

        results.append({
            "problem_number": boundary.problem_number,
            "file_path": str(output_path),
            "dimensions": {"width": cropped.shape[1], "height": cropped.shape[0]},
            "boundary": boundary
        })

        print(f"  ✅ Saved: {filename} ({cropped.shape[1]}x{cropped.shape[0]})")

    return results
