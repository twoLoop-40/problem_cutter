"""
Image cropping utilities

Crops problem/solution regions from PDF images based on detected bounding boxes.
"""

from typing import List
import cv2
import numpy as np
from pathlib import Path

from .base import BBox, Coord


def crop_image(image: np.ndarray, bbox: BBox, margin: int = 10) -> np.ndarray:
    """
    Crop a region from an image

    Args:
        image: Source image (numpy array)
        bbox: Bounding box to crop
        margin: Extra margin around bbox (pixels)

    Returns:
        Cropped image
    """
    # Add margin
    x1 = max(0, bbox.top_left.x - margin)
    y1 = max(0, bbox.top_left.y - margin)
    x2 = min(image.shape[1], bbox.top_left.x + bbox.width + margin)
    y2 = min(image.shape[0], bbox.top_left.y + bbox.height + margin)

    # Crop
    cropped = image[y1:y2, x1:x2]

    return cropped


def crop_and_save(image: np.ndarray,
                  bbox: BBox,
                  output_path: str,
                  margin: int = 10) -> bool:
    """
    Crop a region and save to file

    Args:
        image: Source image
        bbox: Bounding box to crop
        output_path: Output file path
        margin: Extra margin (pixels)

    Returns:
        True if successful
    """
    try:
        cropped = crop_image(image, bbox, margin)
        cv2.imwrite(output_path, cropped)
        return True
    except Exception as e:
        print(f"Failed to crop and save: {e}")
        return False


def crop_problems_from_page(image: np.ndarray,
                            problem_boundaries: List[tuple[int, BBox]],
                            output_dir: str,
                            margin: int = 10) -> List[dict]:
    """
    Crop all problems from a page

    Args:
        image: Page image
        problem_boundaries: List of (problem_number, bbox) tuples
        output_dir: Output directory
        margin: Extra margin (pixels)

    Returns:
        List of dicts with problem info:
        [
            {
                "problem_num": 1,
                "file_path": "output/1_prb.png",
                "bbox": BBox(...),
                "success": True
            },
            ...
        ]
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for problem_num, bbox in problem_boundaries:
        # Output filename: 1_prb.png, 2_prb.png, etc.
        filename = f"{problem_num}_prb.png"
        output_path = output_dir / filename

        success = crop_and_save(image, bbox, str(output_path), margin)

        results.append({
            "problem_num": problem_num,
            "file_path": str(output_path),
            "bbox": bbox,
            "success": success
        })

        if success:
            print(f"  ✅ Saved: {filename} (size: {bbox.width}x{bbox.height})")
        else:
            print(f"  ❌ Failed: {filename}")

    return results


def visualize_boundaries(image: np.ndarray,
                         boundaries: List[tuple[int, BBox]],
                         output_path: str) -> bool:
    """
    Draw bounding boxes on image for visualization

    Args:
        image: Source image
        boundaries: List of (problem_number, bbox) tuples
        output_path: Output file path

    Returns:
        True if successful
    """
    try:
        # Copy image to avoid modifying original
        vis = image.copy()

        # Draw each bbox
        for problem_num, bbox in boundaries:
            x1 = bbox.top_left.x
            y1 = bbox.top_left.y
            x2 = x1 + bbox.width
            y2 = y1 + bbox.height

            # Draw rectangle (green)
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 3)

            # Draw label
            label = f"{problem_num}"
            cv2.putText(vis, label, (x1 + 10, y1 + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.imwrite(output_path, vis)
        return True
    except Exception as e:
        print(f"Failed to visualize: {e}")
        return False
