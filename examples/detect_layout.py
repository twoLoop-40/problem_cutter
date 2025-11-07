"""
Example: Detect layout in a PDF using OpenCV

Usage:
    python examples/detect_layout.py <pdf_path>
    python examples/detect_layout.py samples/sample.pdf
"""

import sys
import cv2
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pdf_converter import pdf_to_images
from core.layout_detector import LayoutDetector


def main():
    if len(sys.argv) < 2:
        print("Usage: python detect_layout.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Processing PDF: {pdf_path}")
    print("Converting PDF to images...")
    
    # Convert PDF to images
    images = pdf_to_images(pdf_path, dpi=200)
    print(f"Found {len(images)} pages")
    
    # Create layout detector
    detector = LayoutDetector(
        min_line_length=100,
        line_thickness_threshold=5,
        gap_threshold=50
    )
    
    # Process each page
    for page_num, image in enumerate(images):
        print(f"\n=== Page {page_num + 1} ===")
        
        # Detect layout
        layout = detector.detect_layout(image)
        
        # Print results
        print(f"Detection method: {layout.detection_method.value}")
        print(f"Column count: {layout.column_count.value}")
        print(f"Page size: {layout.page_width}x{layout.page_height}")
        
        if layout.separator_lines:
            print(f"Separator lines: {len(layout.separator_lines)}")
            for i, vline in enumerate(layout.separator_lines):
                print(f"  Line {i+1}: x={vline.x}, length={vline.length()}")
        
        print(f"Columns:")
        for i, col in enumerate(layout.columns):
            print(f"  Column {i+1}: x=[{col.left_x}, {col.right_x}], width={col.right_x - col.left_x}")
        
        # Visualize
        vis = detector.visualize_layout(image, layout)
        
        # Save visualization
        output_path = f"output_page_{page_num + 1}.jpg"
        cv2.imwrite(output_path, vis)
        print(f"Saved visualization: {output_path}")
        
        # Show (optional, comment out if running headless)
        # cv2.imshow(f"Page {page_num + 1}", vis)
        # cv2.waitKey(0)
    
    # cv2.destroyAllWindows()
    print("\nDone!")


if __name__ == "__main__":
    main()

