"""
Tests for core/ocr_engine.py

Tests the OCR integration functions.
"""

import pytest
from core.ocr_engine import (
    parse_problem_number,
    is_solution_marker,
    Confidence,
    OcrResult,
    OcrEngine,
    filter_by_confidence,
    find_text_pattern,
)
from core.base import BBox, Coord


class TestParseProblemNumber:
    """Test problem number parsing"""

    def test_arabic_dot(self):
        """Test parsing "1.", "2.", "3." format"""
        assert parse_problem_number("1.") == 1
        assert parse_problem_number("2.") == 2
        assert parse_problem_number("10.") == 10
        assert parse_problem_number("99.") == 99

    def test_bracketed(self):
        """Test parsing "[1]", "[2]" format"""
        assert parse_problem_number("[1]") == 1
        assert parse_problem_number("[2]") == 2
        assert parse_problem_number("[10]") == 10

    def test_circled(self):
        """Test parsing circled numbers ①②③"""
        assert parse_problem_number("①") == 1
        assert parse_problem_number("②") == 2
        assert parse_problem_number("③") == 3
        assert parse_problem_number("⑩") == 10

    def test_invalid(self):
        """Test invalid inputs return None"""
        assert parse_problem_number("text") is None
        assert parse_problem_number("1") is None  # Missing dot
        assert parse_problem_number("1.2") is None
        assert parse_problem_number("") is None


class TestIsSolutionMarker:
    """Test solution marker detection"""

    def test_korean_markers(self):
        """Test Korean solution markers"""
        assert is_solution_marker("[정답]") is True
        assert is_solution_marker("[해설]") is True
        assert is_solution_marker("정답:") is True
        assert is_solution_marker("해설:") is True
        assert is_solution_marker("풀이") is True

    def test_non_markers(self):
        """Test non-markers return False"""
        assert is_solution_marker("문제") is False
        assert is_solution_marker("1.") is False
        assert is_solution_marker("test") is False


class TestConfidence:
    """Test Confidence class"""

    def test_valid_confidence(self):
        """Test valid confidence values"""
        conf = Confidence(0.8)
        assert conf.value == 0.8
        assert conf.is_high() is True
        assert conf.is_medium() is False

    def test_medium_confidence(self):
        """Test medium confidence"""
        conf = Confidence(0.5)
        assert conf.is_high() is False
        assert conf.is_medium() is True

    def test_low_confidence(self):
        """Test low confidence"""
        conf = Confidence(0.2)
        assert conf.is_high() is False
        assert conf.is_medium() is False

    def test_invalid_confidence(self):
        """Test invalid confidence raises error"""
        with pytest.raises(ValueError):
            Confidence(1.5)
        with pytest.raises(ValueError):
            Confidence(-0.1)


class TestFilterByConfidence:
    """Test confidence filtering"""

    def test_filter(self):
        """Test filtering by confidence"""
        results = [
            OcrResult("1.", BBox(Coord(0, 0), 10, 10), Confidence(0.9), "kor"),
            OcrResult("2.", BBox(Coord(0, 20), 10, 10), Confidence(0.5), "kor"),
            OcrResult("3.", BBox(Coord(0, 40), 10, 10), Confidence(0.3), "kor"),
        ]

        filtered = filter_by_confidence(0.6, results)
        assert len(filtered) == 1
        assert filtered[0].text == "1."

        filtered = filter_by_confidence(0.4, results)
        assert len(filtered) == 2


class TestFindTextPattern:
    """Test text pattern finding"""

    def test_find_pattern(self):
        """Test finding text patterns"""
        results = [
            OcrResult("1.", BBox(Coord(0, 0), 10, 10), Confidence(0.9), "kor"),
            OcrResult("[정답]", BBox(Coord(0, 20), 10, 10), Confidence(0.9), "kor"),
            OcrResult("text", BBox(Coord(0, 40), 10, 10), Confidence(0.9), "kor"),
        ]

        found = find_text_pattern("정답", results)
        assert len(found) == 1
        assert found[0].text == "[정답]"

        found = find_text_pattern("1.", results)
        assert len(found) == 1
        assert found[0].text == "1."
