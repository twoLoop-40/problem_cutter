"""
OCR (Optical Character Recognition) integration

This module implements the OCR engine integration defined in System.OcrEngine.idr.
It provides functions for:
- Detecting text from PDF images
- Parsing problem numbers ("1.", "2.", "①", "②")
- Finding solution markers ("[정답]", "[해설]")
- Sorting OCR results by reading order

Implementation follows: .specs/System/OcrEngine.idr
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import re

from .base import BBox, Coord


class OcrEngine(Enum):
    """Supported OCR engines"""
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"
    CLAUDE_VISION = "claude_vision"


@dataclass
class Confidence:
    """OCR confidence score (0.0 to 1.0)"""
    value: float

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.value}")

    def is_high(self) -> bool:
        """Check if confidence is high (>= 0.7)"""
        return self.value >= 0.7

    def is_medium(self) -> bool:
        """Check if confidence is medium (0.4 ~ 0.7)"""
        return 0.4 <= self.value < 0.7


@dataclass
class OcrResult:
    """Single OCR detection result (one text block)"""
    text: str
    bbox: BBox
    confidence: Confidence
    language: str  # "kor", "eng", "kor+eng", etc.


@dataclass
class OcrExecution:
    """OCR execution specification for a region"""
    engine: OcrEngine
    input_region: BBox
    languages: List[str]
    results: List[OcrResult]


def filter_by_confidence(min_confidence: float, results: List[OcrResult]) -> List[OcrResult]:
    """
    Filter OCR results by minimum confidence

    Args:
        min_confidence: Minimum confidence threshold (0.0 ~ 1.0)
        results: List of OCR results

    Returns:
        Filtered list of OCR results
    """
    return [r for r in results if r.confidence.value >= min_confidence]


def find_text_pattern(pattern: str, results: List[OcrResult]) -> List[OcrResult]:
    """
    Find OCR results containing a specific substring

    Example:
        find_text_pattern("1.", results)  # finds "1.", "11.", etc.
        find_text_pattern("[정답]", results)

    Args:
        pattern: Substring to search for
        results: List of OCR results

    Returns:
        List of matching OCR results
    """
    return [r for r in results if pattern in r.text]


def find_regex_pattern(pattern: str, results: List[OcrResult]) -> List[OcrResult]:
    """
    Find OCR results matching a regex pattern

    Example:
        find_regex_pattern(r"^\\d+\\.", results)  # finds "1.", "2.", etc.

    Args:
        pattern: Regex pattern to match
        results: List of OCR results

    Returns:
        List of matching OCR results
    """
    compiled = re.compile(pattern)
    return [r for r in results if compiled.search(r.text)]


def parse_problem_number(text: str) -> Optional[int]:
    """
    Parse problem number from text

    Recognizes patterns:
    - "1.", "2.", "3." -> Arabic numbers with dot
    - "1,", "2," -> Arabic numbers with comma (OCR misread of ".")
    - "①", "②", "③" -> Circled numbers (Unicode)

    Filters out:
    - "[1.5점]", "[2점]" -> Score indicators (contains decimal or 점)
    - "[8~9]" -> Range indicators (will be handled separately)

    Args:
        text: Text to parse

    Returns:
        Problem number if found, None otherwise

    Examples:
        >>> parse_problem_number("1.")
        1
        >>> parse_problem_number("6,")
        6
        >>> parse_problem_number("[1.5점]")
        None
        >>> parse_problem_number("①")
        1
    """
    text = text.strip()

    # Filter out score indicators like "[1.5점]", "[2점]"
    # But allow problem numbers like "1.", "2."
    if '점' in text:
        return None

    # Filter out range indicators like "[8~9]"
    if '~' in text or '-' in text:
        return None

    # Pattern 1: "[1]", "[2]", "[3]" (bracketed numbers)
    match = re.match(r'^\[(\d+)\]$', text)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 100:
            return num

    # Pattern 2: "1.", "2.", "3." (dot notation)
    match = re.match(r'^(\d+)\.$', text)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 100:
            return num

    # Pattern 3: "1,", "2," (OCR misread comma as dot)
    match = re.match(r'^(\d+),$', text)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 100:
            return num

    # Pattern 4: "(1)", "(2)", "(3)" (parentheses notation)
    match = re.match(r'^\((\d+)\)$', text)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 100:
            return num

    # Pattern 5: Circled numbers ①②③④⑤⑥⑦⑧⑨⑩
    # Unicode range: U+2460 to U+2473
    if len(text) == 1:
        code = ord(text)
        if 0x2460 <= code <= 0x2473:  # ① to ⑳
            return code - 0x2460 + 1

    return None


def is_solution_marker(text: str) -> bool:
    """
    Detect if text is a solution marker

    Recognizes: "[정답]", "[해설]", "정답:", "해설:", etc.

    Args:
        text: Text to check

    Returns:
        True if text is a solution marker

    Examples:
        >>> is_solution_marker("[정답]")
        True
        >>> is_solution_marker("정답:")
        True
        >>> is_solution_marker("해설")
        True
        >>> is_solution_marker("문제")
        False
    """
    text = text.strip()

    # Common solution markers
    markers = [
        "정답", "해설", "풀이", "답",
        "[정답]", "[해설]", "[풀이]",
        "정답:", "해설:", "풀이:",
    ]

    for marker in markers:
        if marker in text:
            return True

    return False


def sort_by_reading_order(layout, results: List[OcrResult]) -> List[OcrResult]:
    """
    Sort OCR results by reading order (considering page layout)

    For multi-column layouts:
    - Sort by column first (left to right)
    - Then by vertical position within column (top to bottom)

    Args:
        layout: PageLayout object with column information
        results: List of OCR results

    Returns:
        Sorted list of OCR results
    """
    from .layout_detector import PageLayout

    def get_sort_key(result: OcrResult):
        """Calculate sort key for a result"""
        center = result.bbox.center()

        # Find which column this result belongs to
        column_index = 0
        if layout.columns:
            for i, col in enumerate(layout.columns):
                if col.left_x <= center.x <= col.right_x:
                    column_index = i
                    break
        # If no columns defined or center not in any column, use default 0

        # Sort by (column_index, y_position)
        return (column_index, center.y)

    return sorted(results, key=get_sort_key)


# Runtime validation functions (corresponding to proof types)

def check_all_high_confidence(results: List[OcrResult]) -> bool:
    """
    Check if all OCR results have high confidence

    Implements: AllHighConfidence proof type
    """
    return all(r.confidence.is_high() for r in results)


def check_ocr_results_no_overlap(results: List[OcrResult]) -> bool:
    """
    Check if OCR results don't overlap

    Implements: OcrResultsNoOverlap proof type
    """
    from .base import check_no_overlap
    boxes = [r.bbox for r in results]
    return check_no_overlap(boxes)


def validate_ocr_execution(execution: OcrExecution) -> bool:
    """
    Validate OCR execution result

    Implements: ValidOcrExecution proof type
    """
    return (
        check_all_high_confidence(execution.results) and
        check_ocr_results_no_overlap(execution.results)
    )


# -------------------------------------------------------------------------
# Tesseract OCR Integration
# -------------------------------------------------------------------------

def run_tesseract_ocr(image, lang: str = "kor+eng") -> List[OcrResult]:
    """
    Run Tesseract OCR on an image

    Args:
        image: numpy array (BGR or grayscale)
        lang: Language code (e.g., "kor", "eng", "kor+eng")

    Returns:
        List of OcrResult with text, bbox, and confidence
    """
    import pytesseract
    import cv2
    import numpy as np

    # Convert to RGB if needed
    if len(image.shape) == 3 and image.shape[2] == 3:
        # BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif len(image.shape) == 2:
        # Grayscale to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        image_rgb = image

    # Run Tesseract with detailed output
    data = pytesseract.image_to_data(
        image_rgb,
        lang=lang,
        output_type=pytesseract.Output.DICT
    )

    # Parse results
    ocr_results = []
    n_boxes = len(data['text'])

    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = int(data['conf'][i])

        # Skip empty text or low confidence
        if not text or conf < 0:
            continue

        # Create BBox
        x = data['left'][i]
        y = data['top'][i]
        w = data['width'][i]
        h = data['height'][i]

        bbox = BBox(
            top_left=Coord(x, y),
            width=w,
            height=h
        )

        # Normalize confidence to 0.0-1.0
        confidence = Confidence(conf / 100.0 if conf <= 100 else 1.0)

        ocr_results.append(OcrResult(
            text=text,
            bbox=bbox,
            confidence=confidence,
            language=lang
        ))

    return ocr_results


# -------------------------------------------------------------------------
# Mathpix OCR Integration (DEPRECATED - doesn't provide bbox)
# -------------------------------------------------------------------------

def run_mathpix_ocr(image, app_id: str = None, app_key: str = None) -> List[OcrResult]:
    """
    Run Mathpix OCR on an image using /v3/text API

    Args:
        image: numpy array (BGR or grayscale)
        app_id: Mathpix app ID (from .env if not provided)
        app_key: Mathpix app key (from .env if not provided)

    Returns:
        List of OcrResult with text, bbox, and confidence
    """
    import os
    import base64
    import cv2
    import numpy as np
    import requests
    from dotenv import load_dotenv

    load_dotenv()

    # Get credentials
    if app_id is None:
        app_id = os.getenv("MATHPIX_APP_ID")
    if app_key is None:
        app_key = os.getenv("MATHPIX_APP_KEY")

    if not app_id or not app_key:
        raise ValueError("Mathpix credentials not found in .env file")

    # Encode image to base64
    if len(image.shape) == 3:
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    # Encode to PNG
    _, buffer = cv2.imencode('.png', cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
    image_base64 = base64.b64encode(buffer).decode('utf-8')

    # Call Mathpix API
    url = "https://api.mathpix.com/v3/text"
    headers = {
        "app_id": app_id,
        "app_key": app_key,
        "Content-Type": "application/json"
    }

    data = {
        "src": f"data:image/png;base64,{image_base64}",
        "formats": ["text", "data"],  # Request text and structured data
        "data_options": {
            "include_asciimath": False,
            "include_latex": False
        }
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    result = response.json()

    # Debug: print response structure
    import json
    print(f"\n[DEBUG] Mathpix API response keys: {result.keys()}")
    if "data" in result:
        print(f"[DEBUG] Number of data blocks: {len(result['data'])}")
    if "text" in result:
        print(f"[DEBUG] Text field length: {len(result['text'])} chars")
        print(f"[DEBUG] Text preview: {result['text'][:200]}")

    # Parse results
    ocr_results = []

    # Extract from "data" field (structured text blocks)
    if "data" in result:
        for block in result.get("data", []):
            if "value" in block and "position" in block:
                text = block["value"]
                pos = block["position"]

                # Create BBox from position
                # Mathpix returns: {top_left_x, top_left_y, width, height}
                bbox = BBox(
                    top_left=Coord(
                        int(pos.get("top_left_x", 0)),
                        int(pos.get("top_left_y", 0))
                    ),
                    width=int(pos.get("width", 0)),
                    height=int(pos.get("height", 0))
                )

                # Use high confidence for Mathpix (it's generally accurate)
                confidence = Confidence(0.95)

                ocr_results.append(OcrResult(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    language="kor+eng"
                ))

    return ocr_results
