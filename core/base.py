"""
Base types implementation
Corresponds to: .specs/Base.idr
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np


@dataclass
class Coord:
    """2D coordinate in PDF/image space"""
    x: int
    y: int
    
    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)


@dataclass
class BBox:
    """Bounding box defined by top-left corner and dimensions"""
    top_left: Coord
    width: int
    height: int
    
    @property
    def x(self) -> int:
        return self.top_left.x
    
    @property
    def y(self) -> int:
        return self.top_left.y
    
    def bottom_right(self) -> Coord:
        """Get bottom-right coordinate"""
        return Coord(
            self.top_left.x + self.width,
            self.top_left.y + self.height
        )
    
    def center(self) -> Coord:
        """Get center coordinate"""
        return Coord(
            self.top_left.x + self.width // 2,
            self.top_left.y + self.height // 2
        )
    
    def to_cv2_rect(self) -> Tuple[int, int, int, int]:
        """Convert to OpenCV rect format (x, y, w, h)"""
        return (self.x, self.y, self.width, self.height)
    
    def to_cv2_points(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Convert to OpenCV point pair format"""
        br = self.bottom_right()
        return (self.top_left.to_tuple(), br.to_tuple())
    
    @staticmethod
    def from_cv2_rect(x: int, y: int, w: int, h: int) -> 'BBox':
        """Create from OpenCV rect format"""
        return BBox(Coord(x, y), w, h)
    
    @staticmethod
    def from_cv2_contour(contour: np.ndarray) -> 'BBox':
        """Create from OpenCV contour"""
        x, y, w, h = cv2.boundingRect(contour)
        return BBox.from_cv2_rect(x, y, w, h)


@dataclass
class VLine:
    """Vertical line in PDF (for column separation)"""
    x: int
    y_start: int
    y_end: int
    
    def length(self) -> int:
        """Get line length"""
        return self.y_end - self.y_start
    
    def is_significant(self, min_length: int) -> bool:
        """Check if line is significant (long enough)"""
        return self.length() >= min_length
    
    def to_cv2_line(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Convert to OpenCV line format"""
        return ((self.x, self.y_start), (self.x, self.y_end))


def overlaps(b1: BBox, b2: BBox) -> bool:
    """Check if two bounding boxes overlap"""
    br1 = b1.bottom_right()
    br2 = b2.bottom_right()
    
    return not (
        b1.top_left.x >= br2.x or
        br1.x <= b2.top_left.x or
        b1.top_left.y >= br2.y or
        br1.y <= b2.top_left.y
    )


def contains(outer: BBox, inner: BBox) -> bool:
    """Check if outer box contains inner box"""
    br_outer = outer.bottom_right()
    br_inner = inner.bottom_right()
    
    return (
        outer.top_left.x <= inner.top_left.x and
        outer.top_left.y <= inner.top_left.y and
        br_outer.x >= br_inner.x and
        br_outer.y >= br_inner.y
    )


def check_no_overlap(boxes: List[BBox]) -> bool:
    """
    Runtime check for NoOverlap proof
    Corresponds to: NoOverlap : List BBox -> Type
    """
    for i, b1 in enumerate(boxes):
        for b2 in boxes[i+1:]:
            if overlaps(b1, b2):
                return False
    return True


def check_all_contained(parent: BBox, boxes: List[BBox]) -> bool:
    """
    Runtime check for AllContained proof
    Corresponds to: AllContained : BBox -> List BBox -> Type
    """
    return all(contains(parent, box) for box in boxes)


# Import cv2 here to avoid circular import
try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: OpenCV not installed. Install with: pip install opencv-python")


