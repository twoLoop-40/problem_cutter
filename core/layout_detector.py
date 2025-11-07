"""
Layout detection using OpenCV
Corresponds to: .specs/LayoutDetection.idr
"""

import cv2
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
from .base import Coord, BBox, VLine


class ColumnCount(Enum):
    """Number of columns in the layout"""
    ONE = 1
    TWO = 2
    THREE = 3


class DetectionMethod(Enum):
    """Method used to detect columns"""
    VERTICAL_LINES = "vertical_lines"
    CONTENT_GAPS = "content_gaps"
    PROBLEM_POSITIONS = "problem_positions"


@dataclass
class ColumnBound:
    """Column boundary (x-coordinate range)"""
    left_x: int
    right_x: int
    
    def is_valid(self) -> bool:
        """Check if left < right"""
        return self.left_x < self.right_x
    
    def contains_x(self, x: int) -> bool:
        """Check if x coordinate is within this column"""
        return self.left_x <= x <= self.right_x


@dataclass
class PageLayout:
    """Complete page layout information"""
    page_width: int
    page_height: int
    column_count: ColumnCount
    detection_method: DetectionMethod
    separator_lines: List[VLine]
    columns: List[ColumnBound]
    
    def find_column_index(self, point: Coord) -> Optional[int]:
        """Find which column a point belongs to"""
        for i, col in enumerate(self.columns):
            if col.contains_x(point.x):
                return i
        return None


class LayoutDetector:
    """Detect PDF layout using OpenCV"""
    
    def __init__(self, 
                 min_line_length: int = 100,
                 line_thickness_threshold: int = 5,
                 gap_threshold: int = 50):
        """
        Initialize layout detector
        
        Args:
            min_line_length: Minimum length for a line to be considered significant
            line_thickness_threshold: Max thickness for separator lines
            gap_threshold: Minimum gap width to consider as column boundary
        """
        self.min_line_length = min_line_length
        self.line_thickness_threshold = line_thickness_threshold
        self.gap_threshold = gap_threshold
    
    def detect_layout(self, image: np.ndarray) -> PageLayout:
        """
        Detect page layout from image
        
        Args:
            image: Grayscale or BGR image
            
        Returns:
            PageLayout with detected columns
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        height, width = gray.shape
        
        # Try to detect vertical separator lines first
        vlines = self._detect_vertical_lines(gray)
        
        if vlines:
            # Use vertical lines to determine columns
            layout = self._layout_from_vlines(width, height, vlines)
            layout.detection_method = DetectionMethod.VERTICAL_LINES
            return layout
        else:
            # Fall back to content gap analysis
            layout = self._layout_from_gaps(gray, width, height)
            layout.detection_method = DetectionMethod.CONTENT_GAPS
            return layout
    
    def _detect_vertical_lines(self, gray: np.ndarray) -> List[VLine]:
        """
        Detect vertical separator lines using Hough Line Transform
        
        Returns:
            List of significant vertical lines
        """
        height, width = gray.shape
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Hough Line Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=100,
            minLineLength=self.min_line_length,
            maxLineGap=20
        )
        
        if lines is None:
            return []
        
        vlines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            # Check if line is vertical (small x difference)
            if abs(x2 - x1) <= self.line_thickness_threshold:
                # Line is vertical
                x = (x1 + x2) // 2
                y_start = min(y1, y2)
                y_end = max(y1, y2)
                
                vline = VLine(x, y_start, y_end)
                
                if vline.is_significant(self.min_line_length):
                    vlines.append(vline)
        
        # Merge nearby vertical lines
        vlines = self._merge_nearby_vlines(vlines, threshold=10)
        
        # Filter lines that span most of the page height
        min_span = height * 0.3  # At least 30% of page height
        vlines = [vl for vl in vlines if vl.length() >= min_span]
        
        return vlines
    
    def _merge_nearby_vlines(self, vlines: List[VLine], threshold: int) -> List[VLine]:
        """Merge vertical lines that are close to each other"""
        if not vlines:
            return []
        
        # Sort by x coordinate
        vlines = sorted(vlines, key=lambda vl: vl.x)
        
        merged = [vlines[0]]
        
        for vl in vlines[1:]:
            last = merged[-1]
            
            if abs(vl.x - last.x) <= threshold:
                # Merge: use average x and extend y range
                merged[-1] = VLine(
                    (last.x + vl.x) // 2,
                    min(last.y_start, vl.y_start),
                    max(last.y_end, vl.y_end)
                )
            else:
                merged.append(vl)
        
        return merged
    
    def _layout_from_vlines(self, width: int, height: int, 
                           vlines: List[VLine]) -> PageLayout:
        """
        Create layout from detected vertical lines
        
        Strategy:
        - 0 lines → 1 column
        - 1 line → 2 columns (split at line)
        - 2 lines → 3 columns
        - 3+ lines → use prominent ones
        """
        if not vlines:
            return PageLayout(
                width, height,
                ColumnCount.ONE,
                DetectionMethod.VERTICAL_LINES,
                [],
                [ColumnBound(0, width)]
            )
        
        # Sort lines by x coordinate
        vlines = sorted(vlines, key=lambda vl: vl.x)
        
        if len(vlines) == 1:
            # Two columns
            x = vlines[0].x
            return PageLayout(
                width, height,
                ColumnCount.TWO,
                DetectionMethod.VERTICAL_LINES,
                vlines,
                [
                    ColumnBound(0, x),
                    ColumnBound(x, width)
                ]
            )
        elif len(vlines) >= 2:
            # Three columns (use first two lines)
            x1 = vlines[0].x
            x2 = vlines[1].x
            return PageLayout(
                width, height,
                ColumnCount.THREE,
                DetectionMethod.VERTICAL_LINES,
                vlines[:2],
                [
                    ColumnBound(0, x1),
                    ColumnBound(x1, x2),
                    ColumnBound(x2, width)
                ]
            )
    
    def _layout_from_gaps(self, gray: np.ndarray, 
                         width: int, height: int) -> PageLayout:
        """
        Create layout by analyzing content gaps (whitespace)
        
        Strategy:
        1. Create vertical projection (sum of pixels per column)
        2. Find large gaps in content
        3. Determine column boundaries
        """
        # Threshold to binary
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Vertical projection: sum each column
        v_projection = np.sum(binary, axis=0)
        
        # Smooth the projection
        kernel_size = width // 100  # Adaptive kernel
        if kernel_size % 2 == 0:
            kernel_size += 1
        if kernel_size < 3:
            kernel_size = 3
        
        v_projection_smooth = cv2.GaussianBlur(
            v_projection.astype(np.float32).reshape(1, -1),
            (kernel_size, 1),
            0
        ).flatten()
        
        # Find gaps (local minima)
        gaps = self._find_gaps(v_projection_smooth, threshold=0.2)
        
        # Filter significant gaps
        gaps = [g for g in gaps if self._is_significant_gap(v_projection_smooth, g, width)]
        
        if not gaps:
            # No gaps found → single column
            return PageLayout(
                width, height,
                ColumnCount.ONE,
                DetectionMethod.CONTENT_GAPS,
                [],
                [ColumnBound(0, width)]
            )
        elif len(gaps) == 1:
            # One gap → two columns
            x = gaps[0]
            return PageLayout(
                width, height,
                ColumnCount.TWO,
                DetectionMethod.CONTENT_GAPS,
                [],
                [
                    ColumnBound(0, x),
                    ColumnBound(x, width)
                ]
            )
        else:
            # Multiple gaps → use page center as fallback for 2-column
            # (more reliable than using gap positions)
            center_x = width // 2
            return PageLayout(
                width, height,
                ColumnCount.TWO,
                DetectionMethod.CONTENT_GAPS,
                [],
                [
                    ColumnBound(0, center_x),
                    ColumnBound(center_x, width)
                ]
            )
    
    def _find_gaps(self, projection: np.ndarray, threshold: float) -> List[int]:
        """Find local minima in projection (potential gaps)"""
        # Normalize projection
        proj_max = np.max(projection)
        if proj_max == 0:
            return []
        
        proj_norm = projection / proj_max
        
        # Find positions where projection is below threshold
        gaps = []
        in_gap = False
        gap_start = 0
        
        for i, val in enumerate(proj_norm):
            if val < threshold and not in_gap:
                # Start of gap
                in_gap = True
                gap_start = i
            elif val >= threshold and in_gap:
                # End of gap
                in_gap = False
                gap_center = (gap_start + i) // 2
                gaps.append(gap_center)
        
        return gaps
    
    def _is_significant_gap(self, projection: np.ndarray, 
                           gap_x: int, width: int) -> bool:
        """Check if a gap is significant enough to be a column boundary"""
        # Gap should be at least gap_threshold pixels wide
        # and not too close to edges
        
        margin = width // 10
        if gap_x < margin or gap_x > width - margin:
            return False
        
        # Check gap width
        window = self.gap_threshold // 2
        start = max(0, gap_x - window)
        end = min(len(projection), gap_x + window)
        
        gap_values = projection[start:end]
        gap_avg = np.mean(gap_values)
        overall_avg = np.mean(projection)
        
        # Gap should have significantly less content
        return gap_avg < overall_avg * 0.3
    
    def visualize_layout(self, image: np.ndarray, 
                        layout: PageLayout) -> np.ndarray:
        """
        Visualize detected layout on image
        
        Args:
            image: Original image
            layout: Detected layout
            
        Returns:
            Image with layout visualization
        """
        vis = image.copy()
        if len(vis.shape) == 2:
            vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
        
        height = vis.shape[0]
        
        # Draw separator lines
        for vline in layout.separator_lines:
            pt1, pt2 = vline.to_cv2_line()
            cv2.line(vis, pt1, pt2, (0, 0, 255), 2)
        
        # Draw column boundaries
        for col in layout.columns:
            # Left boundary
            cv2.line(vis, (col.left_x, 0), (col.left_x, height), (0, 255, 0), 1)
            # Right boundary
            cv2.line(vis, (col.right_x, 0), (col.right_x, height), (0, 255, 0), 1)
        
        # Add text
        method_text = f"Method: {layout.detection_method.value}"
        col_text = f"Columns: {layout.column_count.value}"
        
        cv2.putText(vis, method_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(vis, col_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        return vis


# -------------------------------------------------------------------------
# Narrow column merging (to handle thick separator lines)
# Implements: LayoutDetection.idr:139-203
# -------------------------------------------------------------------------

def column_width(col: ColumnBound) -> int:
    """Calculate column width"""
    return col.right_x - col.left_x


def is_narrow_column(threshold: int, col: ColumnBound) -> bool:
    """
    Check if a column is narrower than threshold

    Narrow columns (< 100px typically) are likely separator lines,
    not actual content columns
    """
    return column_width(col) < threshold


def filter_narrow_columns(min_width: int, columns: List[ColumnBound]) -> List[ColumnBound]:
    """
    Filter out columns narrower than threshold

    Returns only content columns, removing separator regions

    Args:
        min_width: Minimum column width (typically 100px)
        columns: List of all column boundaries

    Returns:
        Filtered list of content columns only
    """
    return [col for col in columns if not is_narrow_column(min_width, col)]


def check_all_wide_enough(min_width: int, columns: List[ColumnBound]) -> bool:
    """
    Check if all columns are wide enough

    Implements: AllWideEnough proof type
    """
    return all(column_width(col) >= min_width for col in columns)


def mk_layout_from_merged_lines(width: int,
                                height: int,
                                vlines: List[VLine],
                                merge_threshold: int = 20,
                                min_width: int = 100) -> PageLayout:
    """
    Create layout from merged lines

    This is the recommended way to create layouts:
    1. Merge nearby lines (thick separators)
    2. Create column boundaries
    3. Filter out narrow "columns" (actual separators)
    4. Determine final column count

    Args:
        width: Page width
        height: Page height
        vlines: Detected vertical lines
        merge_threshold: Max distance to merge lines (default 20px)
        min_width: Min column width to keep (default 100px)

    Returns:
        PageLayout with correctly merged columns
    """
    detector = LayoutDetector()

    # Step 1: Merge nearby lines
    merged_lines = detector._merge_nearby_vlines(vlines, threshold=merge_threshold)

    # Step 2: Create initial column boundaries
    if not merged_lines:
        # No lines → single column
        return PageLayout(
            width, height,
            ColumnCount.ONE,
            DetectionMethod.VERTICAL_LINES,
            [],
            [ColumnBound(0, width)]
        )

    # Sort lines by x
    merged_lines = sorted(merged_lines, key=lambda vl: vl.x)

    # Create boundaries between (0, line1, line2, ..., width)
    x_positions = [0] + [vl.x for vl in merged_lines] + [width]
    all_columns = []
    for i in range(len(x_positions) - 1):
        all_columns.append(ColumnBound(x_positions[i], x_positions[i+1]))

    # Step 3: Filter out narrow columns (separators)
    content_columns = filter_narrow_columns(min_width, all_columns)

    # Step 4: Fallback if no content columns found
    if not content_columns:
        # If filtering removed all columns, use original columns
        # This happens when all gaps are narrow (thick separators only)
        content_columns = all_columns

    # Step 5: Determine column count
    num_cols = len(content_columns)
    if num_cols == 1:
        col_count = ColumnCount.ONE
    elif num_cols == 2:
        col_count = ColumnCount.TWO
    else:
        col_count = ColumnCount.THREE

    return PageLayout(
        width, height,
        col_count,
        DetectionMethod.VERTICAL_LINES,
        merged_lines,
        content_columns
    )

