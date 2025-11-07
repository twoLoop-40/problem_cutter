"""
Output file generation and packaging

Generates final output files (cropped images, ZIP archive, metadata).
"""

import json
import zipfile
from pathlib import Path
from typing import List, Dict
from datetime import datetime


def generate_metadata(problem_results: List[dict],
                     solution_results: List[dict],
                     pdf_path: str,
                     output_path: str) -> bool:
    """
    Generate metadata JSON file

    Args:
        problem_results: List of problem extraction results
        solution_results: List of solution extraction results
        pdf_path: Source PDF path
        output_path: Output JSON path

    Returns:
        True if successful
    """
    try:
        metadata = {
            "source_pdf": pdf_path,
            "extraction_date": datetime.now().isoformat(),
            "total_problems": len(problem_results),
            "total_solutions": len(solution_results),
            "problems": [
                {
                    "num": int(r["problem_num"]),
                    "file": Path(r["file_path"]).name,
                    "bbox": {
                        "x": int(r["bbox"].top_left.x),
                        "y": int(r["bbox"].top_left.y),
                        "width": int(r["bbox"].width),
                        "height": int(r["bbox"].height)
                    },
                    "success": r["success"]
                }
                for r in problem_results
            ],
            "solutions": [
                {
                    "num": r["solution_num"] if "solution_num" in r else r.get("problem_num"),
                    "file": Path(r["file_path"]).name,
                    "bbox": {
                        "x": r["bbox"].top_left.x,
                        "y": r["bbox"].top_left.y,
                        "width": r["bbox"].width,
                        "height": r["bbox"].height
                    } if "bbox" in r else None,
                    "success": r["success"]
                }
                for r in solution_results
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"Failed to generate metadata: {e}")
        return False


def create_zip_archive(output_dir: str,
                       zip_path: str,
                       include_pattern: str = "*.png") -> bool:
    """
    Create ZIP archive of all output files

    Args:
        output_dir: Directory containing files to archive
        zip_path: Output ZIP file path
        include_pattern: File pattern to include (default: *.png)

    Returns:
        True if successful
    """
    try:
        output_dir = Path(output_dir)
        zip_path = Path(zip_path)

        # Find files to include (recursively search subdirectories)
        files = list(output_dir.rglob(include_pattern))

        if not files:
            print(f"No files found matching pattern: {include_pattern}")
            return False

        # Create ZIP
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in files:
                # Add file with relative path from output_dir
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)
                print(f"  Added to ZIP: {arcname}")

        print(f"\n✅ Created ZIP archive: {zip_path}")
        print(f"   Total files: {len(files)}")
        print(f"   ZIP size: {zip_path.stat().st_size / 1024:.1f} KB")

        return True
    except Exception as e:
        print(f"Failed to create ZIP: {e}")
        return False


def generate_summary_report(problem_results: List[dict],
                           solution_results: List[dict],
                           output_path: str) -> bool:
    """
    Generate text summary report

    Args:
        problem_results: Problem extraction results
        solution_results: Solution extraction results
        output_path: Output text file path

    Returns:
        True if successful
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("PDF Problem Extraction Report\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Problems
            f.write(f"Problems Extracted: {len(problem_results)}\n")
            f.write("-" * 70 + "\n")
            for r in problem_results:
                status = "✅" if r["success"] else "❌"
                f.write(f"  {status} Problem {r['problem_num']:2d}: {Path(r['file_path']).name}\n")

            f.write("\n")

            # Solutions
            if solution_results:
                f.write(f"Solutions Extracted: {len(solution_results)}\n")
                f.write("-" * 70 + "\n")
                for r in solution_results:
                    status = "✅" if r["success"] else "❌"
                    num = r.get("solution_num", r.get("problem_num", "?"))
                    f.write(f"  {status} Solution {num:2d}: {Path(r['file_path']).name}\n")

            f.write("\n" + "=" * 70 + "\n")

        return True
    except Exception as e:
        print(f"Failed to generate report: {e}")
        return False


def package_outputs(output_dir: str,
                   problem_results: List[dict],
                   solution_results: List[dict],
                   pdf_path: str) -> Dict[str, str]:
    """
    Package all outputs (ZIP, metadata, report)

    Args:
        output_dir: Output directory
        problem_results: Problem extraction results
        solution_results: Solution extraction results
        pdf_path: Source PDF path

    Returns:
        Dict with paths to generated files:
        {
            "zip": "path/to/archive.zip",
            "metadata": "path/to/metadata.json",
            "report": "path/to/report.txt"
        }
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Generate metadata
    metadata_path = output_dir / "metadata.json"
    if generate_metadata(problem_results, solution_results, pdf_path, str(metadata_path)):
        results["metadata"] = str(metadata_path)

    # Generate report
    report_path = output_dir / "report.txt"
    if generate_summary_report(problem_results, solution_results, str(report_path)):
        results["report"] = str(report_path)

    # Create ZIP
    zip_path = output_dir / "extracted.zip"
    if create_zip_archive(output_dir, str(zip_path), "*.png"):
        results["zip"] = str(zip_path)

    return results
