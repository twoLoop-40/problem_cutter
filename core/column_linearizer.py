"""
Column linearization module for problem extraction.

Implements the column separation and linearization strategy from ProblemBoundary.idr:
1. Detect column layout (SingleColumn, TwoColumns, MultiColumns)
2. Separate columns vertically
3. Concatenate into single linear image (top to bottom)
4. Preserve all content (no data loss)

Key insight from directions/view.md:
"3. 단을 잘라서 1단으로 만들고"
"4. 세로로 추적해가면서 각문제를 잘라낸다"
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np
from PIL import Image


class ColumnLayoutType(Enum):
    """Column layout detection result"""
    SINGLE_COLUMN = "single"
    TWO_COLUMNS = "two"
    MULTI_COLUMNS = "multi"


@dataclass
class ColumnLayout:
    """Detected column layout with boundaries"""
    layout_type: ColumnLayoutType
    width: int
    height: int
    boundaries: List[int]  # X-coordinates of column boundaries

    @classmethod
    def single_column(cls, width: int, height: int) -> "ColumnLayout":
        """Single column layout (no separation needed)"""
        return cls(ColumnLayoutType.SINGLE_COLUMN, width, height, [0, width])

    @classmethod
    def two_columns(cls, width: int, height: int, mid: int) -> "ColumnLayout":
        """Two columns detected (need separation at mid point)"""
        return cls(ColumnLayoutType.TWO_COLUMNS, width, height, [0, mid, width])


@dataclass
class LinearizedContent:
    """Result of column linearization

    After separation, all content is in single-column form.
    Original multi-column PDF is transformed into vertical strip.
    """
    original_width: int
    original_height: int
    linearized_image: np.ndarray  # Single vertical strip
    total_height: int
    column_images: List[Tuple[np.ndarray, int, int]]  # (image, width, height)

    def save(self, output_path: Path) -> None:
        """Save linearized image to file"""
        Image.fromarray(self.linearized_image).save(output_path)


def detect_column_layout(image: np.ndarray, layout_detector=None) -> ColumnLayout:
    """Detect column layout in image

    Strategy:
    1. Use layout_detector if provided
    2. Fallback: check if 2-column by analyzing content distribution
    3. Default: assume single column

    Args:
        image: Input image as numpy array
        layout_detector: Optional LayoutDetector instance

    Returns:
        ColumnLayout describing the detected structure
    """
    height, width = image.shape[:2]

    if layout_detector is not None:
        # Use existing layout detector
        page_layout = layout_detector.detect_layout(image)
        if page_layout.column_count.value == 2:  # TWO column
            # Get the boundary between columns
            if len(page_layout.columns) >= 2:
                # Mid point between first and second column
                col1 = page_layout.columns[0]
                col2 = page_layout.columns[1]
                mid = (col1.right_x + col2.left_x) // 2
                return ColumnLayout.two_columns(width, height, mid)
        # Fall through to default single column if not 2 columns

    # Fallback: analyze vertical projection to detect columns
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Vertical projection (sum along y-axis)
    projection = np.sum(gray < 200, axis=0)  # Count dark pixels

    # Smooth projection
    kernel_size = width // 50
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(projection, kernel, mode='same')

    # Find minimum in middle region (potential column gap)
    mid_start = width // 3
    mid_end = 2 * width // 3
    mid_region = smoothed[mid_start:mid_end]

    if len(mid_region) > 0:
        min_idx = np.argmin(mid_region) + mid_start
        min_val = smoothed[min_idx]
        avg_val = np.mean(smoothed)

        # If there's a significant gap in the middle → 2 columns
        if min_val < avg_val * 0.3:  # Gap threshold
            return ColumnLayout.two_columns(width, height, min_idx)

    # Default: single column
    return ColumnLayout.single_column(width, height)


def separate_columns(image: np.ndarray, layout: ColumnLayout) -> List[np.ndarray]:
    """Separate image into individual column images

    Args:
        image: Original image
        layout: Detected column layout

    Returns:
        List of column images (left to right order)
    """
    if layout.layout_type == ColumnLayoutType.SINGLE_COLUMN:
        # No separation needed
        return [image]

    # Split at boundaries
    columns = []
    for i in range(len(layout.boundaries) - 1):
        left_x = layout.boundaries[i]
        right_x = layout.boundaries[i + 1]
        column = image[:, left_x:right_x]
        columns.append(column)

    return columns


def linearize_columns(columns: List[np.ndarray], original_width: int, original_height: int) -> LinearizedContent:
    """Concatenate columns vertically into single linear image

    Workflow:
    1. Take each column image
    2. Stack vertically (top to bottom)
    3. Create single long vertical strip

    This ensures:
    - All content preserved (no data loss)
    - Problem markers appear in linear sequence
    - Vertical tracking works correctly

    Args:
        columns: List of column images (in reading order)
        original_width: Original page width
        original_height: Original page height

    Returns:
        LinearizedContent with concatenated image
    """
    if not columns:
        raise ValueError("No columns to linearize")

    # Store column info
    column_info = [(col, col.shape[1], col.shape[0]) for col in columns]

    # Concatenate vertically
    linearized = np.vstack(columns)
    total_height = linearized.shape[0]

    return LinearizedContent(
        original_width=original_width,
        original_height=original_height,
        linearized_image=linearized,
        total_height=total_height,
        column_images=column_info
    )


def process_image(image_path: Path, layout_detector=None) -> LinearizedContent:
    """Complete column separation and linearization workflow

    Implements ProblemBoundary.idr workflow:
    1. Detect column layout
    2. Separate columns if needed
    3. Linearize into single vertical strip

    Args:
        image_path: Path to input image
        layout_detector: Optional LayoutDetector instance

    Returns:
        LinearizedContent ready for problem marker detection
    """
    # Load image
    image = np.array(Image.open(image_path))
    height, width = image.shape[:2]

    # Detect layout
    layout = detect_column_layout(image, layout_detector)

    print(f"Detected layout: {layout.layout_type.value}")
    print(f"Boundaries: {layout.boundaries}")

    # Separate columns
    columns = separate_columns(image, layout)

    print(f"Separated into {len(columns)} column(s)")
    for i, col in enumerate(columns):
        print(f"  Column {i+1}: {col.shape[1]}x{col.shape[0]}")

    # Linearize
    linearized = linearize_columns(columns, width, height)

    print(f"Linearized: {linearized.linearized_image.shape[1]}x{linearized.total_height}")
    print(f"Height increase: {height} → {linearized.total_height} ({linearized.total_height / height:.1f}x)")

    return linearized


def crop_region(
    linearized: LinearizedContent,
    start_y: int,
    end_y: int
) -> np.ndarray:
    """Crop a region from linearized content

    Args:
        linearized: Linearized content
        start_y: Start Y coordinate (inclusive)
        end_y: End Y coordinate (exclusive)

    Returns:
        Cropped image region
    """
    return linearized.linearized_image[start_y:end_y, :]


def trim_whitespace(image: np.ndarray, threshold: int = 250) -> np.ndarray:
    """Trim whitespace from image edges

    Args:
        image: Input image
        threshold: Pixel value threshold for "white" (default 250)

    Returns:
        Trimmed image
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Find non-white pixels
    rows = np.any(gray < threshold, axis=1)
    cols = np.any(gray < threshold, axis=0)

    if not np.any(rows) or not np.any(cols):
        # Image is all white
        return image

    # Find bounding box
    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    # Crop with small padding
    padding = 10
    y_min = max(0, y_min - padding)
    y_max = min(image.shape[0], y_max + padding + 1)
    x_min = max(0, x_min - padding)
    x_max = min(image.shape[1], x_max + padding + 1)

    return image[y_min:y_max, x_min:x_max]
