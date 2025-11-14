"""
Unit tests for base types
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.base import Coord, BBox, VLine, overlaps, contains, check_no_overlap, check_all_contained


class TestCoord:
    def test_create_coord(self):
        coord = Coord(10, 20)
        assert coord.x == 10
        assert coord.y == 20
    
    def test_to_tuple(self):
        coord = Coord(15, 25)
        assert coord.to_tuple() == (15, 25)


class TestBBox:
    def test_create_bbox(self):
        bbox = BBox(Coord(0, 0), 100, 50)
        assert bbox.x == 0
        assert bbox.y == 0
        assert bbox.width == 100
        assert bbox.height == 50
    
    def test_bottom_right(self):
        bbox = BBox(Coord(10, 20), 100, 50)
        br = bbox.bottom_right()
        assert br.x == 110
        assert br.y == 70
    
    def test_center(self):
        bbox = BBox(Coord(0, 0), 100, 50)
        center = bbox.center()
        assert center.x == 50
        assert center.y == 25
    
    def test_from_cv2_rect(self):
        bbox = BBox.from_cv2_rect(10, 20, 100, 50)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 50


class TestVLine:
    def test_create_vline(self):
        vline = VLine(100, 0, 500)
        assert vline.x == 100
        assert vline.y_start == 0
        assert vline.y_end == 500
    
    def test_length(self):
        vline = VLine(100, 50, 200)
        assert vline.length() == 150
    
    def test_is_significant(self):
        vline = VLine(100, 0, 200)
        assert vline.is_significant(100) == True
        assert vline.is_significant(250) == False


class TestOverlaps:
    def test_no_overlap_separate(self):
        """두 박스가 완전히 분리됨"""
        b1 = BBox(Coord(0, 0), 50, 50)
        b2 = BBox(Coord(100, 0), 50, 50)
        assert overlaps(b1, b2) == False
    
    def test_overlap_partial(self):
        """두 박스가 부분적으로 겹침"""
        b1 = BBox(Coord(0, 0), 100, 100)
        b2 = BBox(Coord(50, 50), 100, 100)
        assert overlaps(b1, b2) == True
    
    def test_overlap_complete(self):
        """한 박스가 다른 박스를 완전히 포함"""
        b1 = BBox(Coord(0, 0), 100, 100)
        b2 = BBox(Coord(10, 10), 20, 20)
        assert overlaps(b1, b2) == True
    
    def test_no_overlap_adjacent(self):
        """두 박스가 인접해 있지만 겹치지 않음"""
        b1 = BBox(Coord(0, 0), 50, 50)
        b2 = BBox(Coord(50, 0), 50, 50)
        assert overlaps(b1, b2) == False


class TestContains:
    def test_contains_fully(self):
        """외부 박스가 내부 박스를 완전히 포함"""
        outer = BBox(Coord(0, 0), 100, 100)
        inner = BBox(Coord(10, 10), 20, 20)
        assert contains(outer, inner) == True
    
    def test_not_contains_outside(self):
        """내부 박스가 외부 박스 밖에 있음"""
        outer = BBox(Coord(0, 0), 100, 100)
        inner = BBox(Coord(150, 150), 20, 20)
        assert contains(outer, inner) == False
    
    def test_not_contains_partial(self):
        """내부 박스가 부분적으로만 포함"""
        outer = BBox(Coord(0, 0), 100, 100)
        inner = BBox(Coord(50, 50), 60, 60)
        assert contains(outer, inner) == False
    
    def test_contains_same(self):
        """같은 크기의 박스"""
        outer = BBox(Coord(0, 0), 100, 100)
        inner = BBox(Coord(0, 0), 100, 100)
        assert contains(outer, inner) == True


class TestNoOverlap:
    def test_empty_list(self):
        """빈 리스트는 NoOverlap"""
        assert check_no_overlap([]) == True
    
    def test_single_box(self):
        """하나의 박스는 NoOverlap"""
        boxes = [BBox(Coord(0, 0), 50, 50)]
        assert check_no_overlap(boxes) == True
    
    def test_two_separate_boxes(self):
        """분리된 두 박스"""
        boxes = [
            BBox(Coord(0, 0), 50, 50),
            BBox(Coord(100, 0), 50, 50)
        ]
        assert check_no_overlap(boxes) == True
    
    def test_two_overlapping_boxes(self):
        """겹치는 두 박스"""
        boxes = [
            BBox(Coord(0, 0), 100, 100),
            BBox(Coord(50, 50), 100, 100)
        ]
        assert check_no_overlap(boxes) == False
    
    def test_multiple_boxes_no_overlap(self):
        """여러 박스가 겹치지 않음"""
        boxes = [
            BBox(Coord(0, 0), 50, 50),
            BBox(Coord(60, 0), 50, 50),
            BBox(Coord(120, 0), 50, 50)
        ]
        assert check_no_overlap(boxes) == True


class TestAllContained:
    def test_all_contained(self):
        """모든 박스가 부모 박스 안에 포함"""
        parent = BBox(Coord(0, 0), 200, 200)
        boxes = [
            BBox(Coord(10, 10), 50, 50),
            BBox(Coord(100, 10), 50, 50),
            BBox(Coord(10, 100), 50, 50)
        ]
        assert check_all_contained(parent, boxes) == True
    
    def test_one_outside(self):
        """하나의 박스가 부모 박스 밖에 있음"""
        parent = BBox(Coord(0, 0), 100, 100)
        boxes = [
            BBox(Coord(10, 10), 20, 20),
            BBox(Coord(150, 150), 20, 20)  # 밖에 있음
        ]
        assert check_all_contained(parent, boxes) == False
    
    def test_empty_list(self):
        """빈 리스트는 AllContained"""
        parent = BBox(Coord(0, 0), 100, 100)
        assert check_all_contained(parent, []) == True


