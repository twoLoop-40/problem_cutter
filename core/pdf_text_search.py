"""
Direct PDF text search using PyMuPDF

Fallback for when OCR fails to detect problem numbers.
"""

import fitz
from typing import List, Tuple, Optional
from .base import Coord


def search_problem_numbers_in_pdf(pdf_path: str,
                                  numbers: List[int],
                                  page_num: int = 0,
                                  dpi: int = 200) -> dict[int, Coord]:
    """
    Search for problem numbers directly in PDF using PyMuPDF

    Args:
        pdf_path: Path to PDF file
        numbers: List of problem numbers to search (e.g., [8, 9])
        page_num: Page number (0-indexed)
        dpi: DPI used for image conversion (for coordinate scaling)

    Returns:
        Dict mapping problem number to Coord position in image space
        Example: {8: Coord(x=1156, y=862), 9: Coord(x=1156, y=2036)}
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    # Scale factor: PDF uses 72 DPI, image uses specified DPI
    scale = dpi / 72.0

    results = {}

    for num in numbers:
        # Search for "N." pattern
        search_text = f"{num}."
        rects = page.search_for(search_text)

        if rects:
            # Use first match
            rect = rects[0]

            # Convert PDF coordinates to image coordinates
            # PyMuPDF uses (x0, y0) as top-left
            x = int(rect.x0 * scale)
            y = int(rect.y0 * scale)

            results[num] = Coord(x, y)
            print(f"   [PDF Search] Found '{search_text}' @ PDF(x={rect.x0:.0f}, y={rect.y0:.0f}) → Image(x={x}, y={y})")

    doc.close()
    return results
