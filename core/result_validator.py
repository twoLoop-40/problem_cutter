"""
Result Validator

Validates detected problems against expected problem numbers.
Provides detailed feedback for refinement.

This implements the validation logic for AgentWorkflow.
"""

from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from pathlib import Path
import json


@dataclass
class ValidationFeedback:
    """Feedback from validation"""
    success: bool
    message: str
    detected_problems: List[int]
    expected_problems: List[int]
    missing_problems: List[int]
    false_positives: List[int]
    invalid_boundaries: List[int]
    accuracy: float  # Percentage of correct detections


def load_expected_problems(pdf_path: str) -> Optional[List[int]]:
    """
    Load expected problem numbers for a PDF

    This can be:
    1. From a ground truth file (e.g., samples/expected.json)
    2. Manually specified in code
    3. Inferred from PDF filename pattern

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of expected problem numbers, or None if not available
    """
    # Strategy 1: Look for ground truth file
    pdf_file = Path(pdf_path)
    expected_file = pdf_file.parent / f"{pdf_file.stem}_expected.json"

    if expected_file.exists():
        with open(expected_file) as f:
            data = json.load(f)
            return data.get("expected_problems", [])

    # Strategy 2: Known samples (hardcoded for now)
    if "통합과학_1_샘플" in pdf_path:
        # Based on visual inspection of the PDF:
        # - Problems 6, 7 in left column
        # - Problems 8, 9 in right column
        return [6, 7, 8, 9]

    elif "사회문화" in pdf_path:
        # Based on visual inspection
        return [1, 2, 3, 4, 5]

    # Strategy 3: No ground truth available
    return None


def validate_results(pdf_path: str,
                     detected_problems: List[int],
                     expected_problems: Optional[List[int]] = None,
                     metadata_path: Optional[str] = None) -> ValidationFeedback:
    """
    Validate extraction results against expected problems

    Args:
        pdf_path: Path to source PDF
        detected_problems: List of detected problem numbers
        expected_problems: Optional list of expected problem numbers
        metadata_path: Optional path to metadata.json for boundary validation

    Returns:
        ValidationFeedback with detailed analysis
    """
    # Load expected problems if not provided
    if expected_problems is None:
        expected_problems = load_expected_problems(pdf_path)
        if expected_problems is None:
            return ValidationFeedback(
                success=False,
                message="No expected problems available for validation",
                detected_problems=detected_problems,
                expected_problems=[],
                missing_problems=[],
                false_positives=[],
                invalid_boundaries=[],
                accuracy=0.0
            )

    # Convert to sets for comparison
    detected_set = set(detected_problems)
    expected_set = set(expected_problems)

    # Find missing and false positives
    missing = sorted(expected_set - detected_set)
    false_positives = sorted(detected_set - expected_set)
    correct = sorted(detected_set & expected_set)

    # Check for invalid boundaries if metadata available
    invalid_boundaries = []
    if metadata_path and Path(metadata_path).exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
            for prob in metadata.get("problems", []):
                bbox = prob.get("bbox", {})
                height = bbox.get("height", 0)
                # Invalid if height is too small (likely wrong detection)
                if height < 50:
                    invalid_boundaries.append(prob["num"])

    # Calculate accuracy
    total_expected = len(expected_problems)
    total_correct = len(correct)
    accuracy = (total_correct / total_expected * 100) if total_expected > 0 else 0.0

    # Determine success
    success = (len(missing) == 0 and len(false_positives) == 0 and
               len(invalid_boundaries) == 0)

    # Generate message
    if success:
        message = f"✅ Validation passed! All {total_expected} problems correctly detected."
    else:
        issues = []
        if missing:
            issues.append(f"Missing: {missing}")
        if false_positives:
            issues.append(f"False positives: {false_positives}")
        if invalid_boundaries:
            issues.append(f"Invalid boundaries: {invalid_boundaries}")
        message = f"❌ Validation failed: {', '.join(issues)}"

    return ValidationFeedback(
        success=success,
        message=message,
        detected_problems=sorted(detected_problems),
        expected_problems=sorted(expected_problems),
        missing_problems=missing,
        false_positives=false_positives,
        invalid_boundaries=invalid_boundaries,
        accuracy=accuracy
    )


def print_validation_report(feedback: ValidationFeedback):
    """Print detailed validation report"""
    print("\n" + "="*70)
    print("VALIDATION REPORT")
    print("="*70)
    print(f"\nStatus: {'✅ PASS' if feedback.success else '❌ FAIL'}")
    print(f"Accuracy: {feedback.accuracy:.1f}%")
    print(f"\nExpected problems: {feedback.expected_problems}")
    print(f"Detected problems: {feedback.detected_problems}")

    if feedback.missing_problems:
        print(f"\n⚠ Missing problems: {feedback.missing_problems}")
        print("   → These problems were expected but not detected")

    if feedback.false_positives:
        print(f"\n⚠ False positives: {feedback.false_positives}")
        print("   → These problems were detected but should not exist")

    if feedback.invalid_boundaries:
        print(f"\n⚠ Invalid boundaries: {feedback.invalid_boundaries}")
        print("   → These problems have suspicious boundaries (too small)")

    print(f"\n{feedback.message}")
    print("="*70 + "\n")


def validate_workflow_output(output_dir: str, pdf_path: str) -> ValidationFeedback:
    """
    Validate complete workflow output

    Convenience function that loads metadata and validates.

    Args:
        output_dir: Path to output directory (contains metadata.json)
        pdf_path: Path to source PDF

    Returns:
        ValidationFeedback
    """
    output_path = Path(output_dir)
    metadata_path = output_path / "metadata.json"

    if not metadata_path.exists():
        return ValidationFeedback(
            success=False,
            message=f"Metadata not found: {metadata_path}",
            detected_problems=[],
            expected_problems=[],
            missing_problems=[],
            false_positives=[],
            invalid_boundaries=[],
            accuracy=0.0
        )

    # Load detected problems from metadata
    with open(metadata_path) as f:
        metadata = json.load(f)
        detected_problems = [p["num"] for p in metadata.get("problems", [])]

    # Validate
    feedback = validate_results(
        pdf_path=pdf_path,
        detected_problems=detected_problems,
        metadata_path=str(metadata_path)
    )

    return feedback


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m core.result_validator <output_dir> <pdf_path>")
        print("\nExample:")
        print("  python -m core.result_validator output/통합과학_1_샘플 samples/통합과학_1_샘플.pdf")
        sys.exit(1)

    output_dir = sys.argv[1]
    pdf_path = sys.argv[2]

    feedback = validate_workflow_output(output_dir, pdf_path)
    print_validation_report(feedback)

    # Exit with error if validation failed
    if not feedback.success:
        sys.exit(1)
