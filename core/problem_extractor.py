"""
Problem extraction from PDF using OCR

This module implements the problem/solution extraction logic defined in
System.ProblemExtraction.idr.

It uses OCR results to:
- Detect problem numbers ("1.", "2.", "①", "②")
- Find solution markers ("[정답]", "[해설]")
- Determine problem boundaries
- Extract individual problems and solutions

Implementation follows: .specs/System/ProblemExtraction.idr
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional

from .base import BBox, Coord
from .layout_detector import PageLayout
from .ocr_engine import OcrResult, parse_problem_number, is_solution_marker


class BoundaryStrategy(Enum):
    """Strategy for detecting problem boundaries"""
    MARKER_BASED = "marker_based"           # Use number markers (1., 2., etc.)
    VERTICAL_GAP_BASED = "vertical_gap"     # Use vertical whitespace
    COMBINED = "combined"                    # Use both markers and gaps


@dataclass
class DetectedMarker:
    """Detected problem marker with its location"""
    marker_number: int  # Parsed problem number
    position: Coord
    ocr_source: OcrResult


@dataclass
class ProblemItem:
    """Problem item (question)"""
    number: int
    region: BBox
    sub_regions: List[BBox]
    page_num: int


@dataclass
class SolutionItem:
    """Solution item (answer/explanation)"""
    number: int
    region: BBox
    sub_regions: List[BBox]
    page_num: int


@dataclass
class ProblemPair:
    """Paired problem and solution"""
    number: int
    problem: ProblemItem
    solution: Optional[SolutionItem]


@dataclass
class ExtractionResult:
    """Complete extraction result for a PDF"""
    problems: List[ProblemItem]
    solutions: List[SolutionItem]
    paired: List[ProblemPair]
    unpaired_problems: List[int]
    unpaired_solutions: List[int]


def detect_problem_markers(ocr_results: List[OcrResult],
                           min_confidence: float = 0.7,
                           pdf_path: Optional[str] = None) -> List[DetectedMarker]:
    """
    Detect problem markers from OCR results

    Finds patterns like "1.", "2.", "①", "②" etc.

    Implementation strategy:
    1. Filter OCR results by high confidence
    2. Parse each text with parse_problem_number
    3. Create DetectedMarker for successful parses

    Args:
        ocr_results: List of OCR text detections
        min_confidence: Minimum confidence threshold

    Returns:
        List of detected problem markers
    """
    import re
    markers = []
    range_markers = {}  # Track range markers: {start_num: (start_num, end_num, y_position)}

    for result in ocr_results:
        # Filter by confidence
        if result.confidence.value < min_confidence:
            continue

        # Pattern 1: Range marker like "[8~9]" - marks START of common passage
        # Only create marker for first number, will find subsequent numbers later
        range_match = re.match(r'^\[(\d+)\s*~\s*(\d+)\]', result.text.strip())
        if range_match:
            start_num = int(range_match.group(1))
            end_num = int(range_match.group(2))
            if 1 <= start_num <= end_num <= 50:
                # Create marker only for first number (start of common passage)
                marker = DetectedMarker(
                    marker_number=start_num,
                    position=result.bbox.center(),
                    ocr_source=result
                )
                markers.append(marker)
                # Remember this range for second pass
                range_markers[start_num] = (start_num, end_num, result.bbox.center().y)
                print(f"   Found range marker [{start_num}~{end_num}] → starting with {start_num}")
            continue

        # Pattern 2: Exact match (e.g., "6,", "7,")
        number = parse_problem_number(result.text)
        if number is not None:
            marker = DetectedMarker(
                marker_number=number,
                position=result.bbox.center(),
                ocr_source=result
            )
            markers.append(marker)
            continue

        # Pattern 3: "N. " or "N, " at start of longer text (e.g., "8. 그림은")
        match = re.match(r'^(\d+)[.,]\s+', result.text)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 50:
                marker = DetectedMarker(
                    marker_number=number,
                    position=result.bbox.center(),
                    ocr_source=result
                )
                markers.append(marker)

    # Second pass: Find remaining numbers in range markers
    # Use PyMuPDF to find exact positions when OCR fails
    if range_markers and pdf_path:
        from .pdf_text_search import search_problem_numbers_in_pdf

        # Collect all numbers we need to find in range markers
        numbers_to_find = []
        for start_num, (start, end, range_y) in range_markers.items():
            for target_num in range(start + 1, end + 1):
                already_found = any(m.marker_number == target_num for m in markers)
                if not already_found:
                    numbers_to_find.append(target_num)

        # Search in PDF
        pdf_positions = search_problem_numbers_in_pdf(pdf_path, numbers_to_find)

        # Create markers from PDF positions
        for num, coord in pdf_positions.items():
            # Use dummy OCR result
            dummy_result = ocr_results[0] if ocr_results else None
            if dummy_result:
                marker = DetectedMarker(
                    marker_number=num,
                    position=coord,
                    ocr_source=dummy_result
                )
                markers.append(marker)

    elif range_markers:
        # Fallback when PDF path not provided
        for start_num, (start, end, range_y) in range_markers.items():
            # Look for numbers start+1 to end
            for target_num in range(start + 1, end + 1):
                # Check if already found
                already_found = any(m.marker_number == target_num for m in markers)
                if already_found:
                    continue

                # Strategy 1: Try OCR results
                found_in_ocr = False
                for result in ocr_results:
                    center = result.bbox.center()
                    text = result.text.strip()

                    # Below range marker, reasonable distance
                    if center.y > range_y + 100 and center.y < range_y + 2000:
                        # Exact match or single digit at left edge
                        is_match = False

                        # Try exact match first
                        num = parse_problem_number(text)
                        if num == target_num:
                            is_match = True
                        # Try "N. " pattern
                        elif re.match(rf'^{target_num}[.,]\s+', text):
                            is_match = True
                        # Try standalone digit at reasonable x position
                        elif text == str(target_num):
                            rx = result.bbox.top_left.x
                            if (rx < 600) or (1100 < rx < 1600):
                                is_match = True

                        if is_match:
                            marker = DetectedMarker(
                                marker_number=target_num,
                                position=center,
                                ocr_source=result
                            )
                            markers.append(marker)
                            print(f"   Found problem {target_num} from range [{start}~{end}] @ y={center.y} (OCR)")
                            found_in_ocr = True
                            break

                # Strategy 2: If not found in OCR, estimate position
                # (Fallback when OCR completely misses the marker)
                if not found_in_ocr:
                    # Estimate: assume evenly spaced within range
                    # This is a simple heuristic
                    estimated_y = range_y + (target_num - start) * 600  # ~600px per problem

                    # Create dummy OCR result for this estimated position
                    dummy_result = ocr_results[0] if ocr_results else None
                    if dummy_result:
                        from .base import Coord
                        marker = DetectedMarker(
                            marker_number=target_num,
                            position=Coord(1200, int(estimated_y)),  # x=1200 for right column
                            ocr_source=dummy_result
                        )
                        markers.append(marker)
                        print(f"   Estimated problem {target_num} from range [{start}~{end}] @ y={estimated_y} (fallback)")

    # Do NOT sort - preserve reading order from input
    # ocr_results should already be sorted by sort_by_reading_order()
    return markers


def detect_solution_markers(ocr_results: List[OcrResult],
                            min_confidence: float = 0.7) -> List[DetectedMarker]:
    """
    Detect solution markers from OCR results

    Finds "[정답]", "[해설]", "정답:", "해설:" etc.

    This addresses: "[정답] 과 번호를 이용해서 정답도 번호별로 파악"

    Args:
        ocr_results: List of OCR text detections
        min_confidence: Minimum confidence threshold

    Returns:
        List of detected solution markers
    """
    markers = []

    for result in ocr_results:
        # Filter by confidence
        if result.confidence.value < min_confidence:
            continue

        # Check if this is a solution marker
        if is_solution_marker(result.text):
            # Try to find problem number nearby
            # For now, use 0 as placeholder
            # TODO: Look for nearby numbers in OCR results
            marker = DetectedMarker(
                marker_number=0,  # Will be refined later
                position=result.bbox.center(),
                ocr_source=result
            )
            markers.append(marker)

    # Sort by position
    markers.sort(key=lambda m: m.position.y)

    return markers


def detect_vertical_gaps(boxes: List[BBox], min_gap_size: int = 30) -> List[int]:
    """
    Detect vertical gaps (whitespace) between content

    Large vertical gaps often indicate problem boundaries

    Args:
        boxes: All content bounding boxes
        min_gap_size: Minimum gap height to consider (typically 20-50px)

    Returns:
        List of y-coordinates where gaps occur
    """
    if not boxes:
        return []

    # Sort boxes by y position
    sorted_boxes = sorted(boxes, key=lambda b: b.top_left.y)

    gaps = []

    for i in range(len(sorted_boxes) - 1):
        current_box = sorted_boxes[i]
        next_box = sorted_boxes[i + 1]

        # Calculate gap between bottom of current and top of next
        current_bottom = current_box.top_left.y + current_box.height
        next_top = next_box.top_left.y

        gap_size = next_top - current_bottom

        if gap_size >= min_gap_size:
            # Record the gap position (middle of gap)
            gap_y = (current_bottom + next_top) // 2
            gaps.append(gap_y)

    return gaps


def detect_problem_boundaries(strategy: BoundaryStrategy,
                              layout: PageLayout,
                              ocr_results: List[OcrResult],
                              all_boxes: List[BBox],
                              pdf_path: Optional[str] = None) -> List[Tuple[int, BBox]]:
    """
    Detect problem boundaries using markers and gaps

    Main function for problem extraction:
    1. Detect problem markers from OCR
    2. Detect vertical gaps
    3. Combine to determine problem boundaries
    4. Return list of (problem number, bounding box)

    Implementation algorithm:
    1. markers = detect_problem_markers(ocr_results)
    2. gaps = detect_vertical_gaps(all_boxes)
    3. For each marker at position p:
       - Find next marker position (or page end)
       - Problem boundary = from p.y to next marker y
       - Create bounding box covering that region
    4. Adjust boundaries using gap information

    Args:
        strategy: Detection strategy to use
        layout: Page layout (for column information)
        ocr_results: OCR text detections
        all_boxes: All content boxes (for gap analysis)
        pdf_path: Optional PDF path (for fallback search when OCR fails)

    Returns:
        List of (problem_number, bounding_box) tuples
    """
    markers = detect_problem_markers(ocr_results, pdf_path=pdf_path)
    gaps = detect_vertical_gaps(all_boxes)

    if not markers:
        # No markers found - cannot detect problems
        return []

    boundaries = []
    page_height = layout.page_height
    page_width = layout.page_width

    for i, marker in enumerate(markers):
        problem_num = marker.marker_number
        start_y = marker.position.y

        # Find which column this marker belongs to
        marker_x = marker.position.x
        column_x_start = 0
        column_x_end = page_width

        if layout.columns:
            for col in layout.columns:
                if col.left_x <= marker_x <= col.right_x:
                    column_x_start = col.left_x
                    column_x_end = col.right_x
                    break

        # Find end position (next marker or page end)
        if i + 1 < len(markers):
            end_y = markers[i + 1].position.y
        else:
            end_y = page_height

        # Adjust using nearby gaps (if available)
        if gaps:
            # Find closest gap between start_y and end_y
            nearby_gaps = [g for g in gaps if start_y < g < end_y]
            if nearby_gaps:
                # Use the last gap before next marker as boundary
                end_y = nearby_gaps[-1]

        # Create bounding box for this problem
        # Use column width (not full page width) to avoid mixing columns
        height = end_y - start_y

        # Skip invalid boxes (negative height)
        if height <= 0:
            print(f"   ⚠ Skipping problem {problem_num}: invalid height {height}")
            continue

        bbox = BBox(
            top_left=Coord(column_x_start, start_y),
            width=column_x_end - column_x_start,
            height=height
        )

        boundaries.append((problem_num, bbox))

    return boundaries


def extract_problems(pdf_path: str,
                    page_num: int,
                    layout: PageLayout,
                    ocr_results: List[OcrResult],
                    all_boxes: List[BBox]) -> List[ProblemItem]:
    """
    Extract problems from OCR results

    Complete extraction pipeline:
    1. Detect problem boundaries
    2. Group content regions by problem number
    3. Create ProblemItem for each

    Args:
        pdf_path: Path to source PDF
        page_num: Page number (1-indexed)
        layout: Page layout
        ocr_results: OCR results
        all_boxes: All content boxes

    Returns:
        List of extracted problems
    """
    boundaries = detect_problem_boundaries(
        BoundaryStrategy.COMBINED,
        layout,
        ocr_results,
        all_boxes
    )

    problems = []

    for problem_num, bbox in boundaries:
        # Find all boxes within this problem's region
        from .base import contains
        sub_regions = [box for box in all_boxes if contains(bbox, box)]

        problem = ProblemItem(
            number=problem_num,
            region=bbox,
            sub_regions=sub_regions,
            page_num=page_num
        )
        problems.append(problem)

    return problems


def extract_solutions(pdf_path: str,
                     page_num: int,
                     layout: PageLayout,
                     ocr_results: List[OcrResult],
                     all_boxes: List[BBox]) -> List[SolutionItem]:
    """
    Extract solutions from OCR results

    Similar to extract_problems but looks for solution markers

    Args:
        pdf_path: Path to source PDF
        page_num: Page number (1-indexed)
        layout: Page layout
        ocr_results: OCR results
        all_boxes: All content boxes

    Returns:
        List of extracted solutions
    """
    solution_markers = detect_solution_markers(ocr_results)

    if not solution_markers:
        return []

    solutions = []

    # TODO: Implement solution extraction logic
    # Similar to extract_problems but:
    # 1. Find "[정답]" markers
    # 2. Extract regions after each marker
    # 3. Match with problem numbers

    return solutions


# Runtime validation functions (corresponding to proof types)

def check_valid_problem_boundaries(boundaries: List[Tuple[int, BBox]]) -> bool:
    """
    Check if detected problem boundaries don't overlap

    Implements: ValidProblemBoundaries proof type
    """
    from .base import check_no_overlap

    boxes = [bbox for _, bbox in boundaries]
    return check_no_overlap(boxes)


def check_all_valid_markers(markers: List[DetectedMarker]) -> bool:
    """
    Check if all detected markers have valid problem numbers (> 0)

    Implements: AllValidMarkers proof type
    """
    return all(m.marker_number > 0 for m in markers)
