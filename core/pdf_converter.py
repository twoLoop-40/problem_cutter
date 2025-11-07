"""
PDF to Image conversion utilities
"""

import numpy as np
from pathlib import Path
from typing import List, Optional
import tempfile


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
    """
    Convert PDF to list of images (one per page)
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default 300 for high quality)
        
    Returns:
        List of images as numpy arrays (BGR format)
    """
    try:
        from pdf2image import convert_from_path
        import cv2
        
        # Convert PDF to PIL images
        pil_images = convert_from_path(pdf_path, dpi=dpi)
        
        # Convert PIL to numpy arrays (OpenCV format)
        images = []
        for pil_img in pil_images:
            # Convert PIL RGB to OpenCV BGR
            img_array = np.array(pil_img)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            images.append(img_bgr)
        
        return images
        
    except ImportError:
        print("pdf2image not installed. Trying PyMuPDF...")
        return pdf_to_images_pymupdf(pdf_path, dpi)


def pdf_to_images_pymupdf(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
    """
    Convert PDF to images using PyMuPDF (alternative method)
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion
        
    Returns:
        List of images as numpy arrays (BGR format)
    """
    try:
        import fitz  # PyMuPDF
        import cv2
        
        doc = fitz.open(pdf_path)
        images = []
        
        # Calculate zoom factor from DPI
        zoom = dpi / 72.0  # 72 DPI is default
        mat = fitz.Matrix(zoom, zoom)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array
            img_array = np.frombuffer(pix.samples, dtype=np.uint8)
            img_array = img_array.reshape(pix.height, pix.width, pix.n)
            
            # Convert RGB to BGR for OpenCV
            if pix.n == 3:  # RGB
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif pix.n == 4:  # RGBA
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            else:
                img_bgr = img_array
            
            images.append(img_bgr)
        
        doc.close()
        return images
        
    except ImportError:
        raise ImportError(
            "Neither pdf2image nor PyMuPDF is installed.\n"
            "Install one of them:\n"
            "  pip install pdf2image poppler-utils\n"
            "  OR\n"
            "  pip install PyMuPDF"
        )


def save_page_as_image(pdf_path: str, page_num: int, 
                       output_path: str, dpi: int = 300) -> None:
    """
    Save a single PDF page as an image
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        output_path: Output image path
        dpi: Resolution
    """
    import cv2
    
    images = pdf_to_images(pdf_path, dpi)
    
    if page_num >= len(images):
        raise ValueError(f"Page {page_num} not found (PDF has {len(images)} pages)")
    
    cv2.imwrite(output_path, images[page_num])


def get_pdf_page_count(pdf_path: str) -> int:
    """Get number of pages in PDF"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except ImportError:
        # Fallback: convert and count
        images = pdf_to_images(pdf_path)
        return len(images)

