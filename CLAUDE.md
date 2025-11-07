# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PDF Problem Cutter** - Automatically extracts individual problems and solutions from multi-column test PDF files and saves them as separate files.

**Goal**: PDF (test paper) → detect layout → extract problems/solutions → individual files (1_prb, 1_sol, ...) → ZIP archive

**Development Philosophy**: Formal Spec Driven Development
- Always write Idris2 specifications first → then implement Python code
- Type system guarantees data consistency
- Catch specification errors at compile time

## Development Commands

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_layout_detector.py

# Run with coverage
uv run pytest --cov=core

# Run test scripts
uv run python test_samples.py
uv run python test_extract_problems.py
uv run python test_new_extraction.py
```

### Verifying Idris2 Specifications
```bash
cd .specs

# Check individual spec files
idris2 --check System/Base.idr
idris2 --check System/LayoutDetection.idr
idris2 --check System/ProblemExtraction.idr
idris2 --check System/ExtractionWorkflow.idr
idris2 --check System/Workflow.idr
idris2 --check System/OutputFormat.idr
```

### Running Examples
```bash
# Detect layout from sample PDF
uv run python examples/detect_layout.py

# Full extraction workflow
uv run python run_full_extraction.py samples/통합과학_1_샘플.pdf
```

## Architecture

### Formal Specification Layer (.specs/System/)
Idris2 dependent types define the data model and provable properties:

- **Base.idr**: Core types (Coord, BBox, VLine, Region)
- **LayoutDetection.idr**: Column detection (1/2/3 columns), vertical line detection
- **OcrEngine.idr**: OCR result types, problem number parsing (1., ①, [정답])
- **ProblemExtraction.idr**: Problem/solution extraction with validity proofs
- **ExtractionWorkflow.idr**: 8-step workflow state machine with valid state transitions
- **OutputFormat.idr**: File naming (1_prb, 1_sol), ZIP packaging
- **Workflow.idr**: Top-level workflow orchestration

### Python Implementation (core/)
Implements the Idris2 specifications:

- **base.py**: Basic types (Coord, BBox, VLine)
- **layout_detector.py**: OpenCV-based column detection (vertical lines, content gaps)
- **ocr_engine.py**: OCR integration (Tesseract, EasyOCR, Claude Vision)
- **problem_extractor.py**: Extract problems using boundary strategies
- **problem_boundary.py**: Problem boundary detection algorithms
- **column_linearizer.py**: Multi-column → single-column conversion
- **result_validator.py**: Validate extraction against specifications
- **workflow.py**: Complete extraction workflow orchestration
- **output_generator.py**: File generation and ZIP packaging

### Agent-Friendly Wrappers (AgentTools/)
Standardized tool interface for LLM agents:

- **types.py**: ToolResult, ToolDiagnostics - standard return format
- **pdf.py**: summarize_pdf(), load_pdf_images()
- **layout.py**: detect_page_layout(), summarize_layout()
- **ocr.py**: OCR result filtering/sorting (stub)
- **extraction.py**: find_problem_boundaries(), crop_problems(), validate_extraction()
- **workflow.py**: run_layout_stage(), run_full_workflow_stub()

All AgentTools functions return `ToolResult` with:
- `success`: bool
- `message`: str
- `data`: dict
- `diagnostics`: ToolDiagnostics (warnings, errors, info)

## Workflow

### 8-Step Extraction Process (directions/view.md)

1. **Analyze**: Read PDF, detect problem count and numbers
2. **Create Spec**: Generate type specification from analysis
3. **Separate Columns**: Convert multi-column → single-column representation
4. **Extract Problems**: Track vertically to extract individual problems
5. **Validate**: Compare extracted vs. expected (from spec)
6. **Final Verification**: Re-check against original PDF
7. **Generate Files**: Create individual problem files with margin trimming
8. **Archive**: Package all files into ZIP

### State Transitions
```
Initial → Analyzed → SpecCreated → ColumnsSeparated → ProblemsExtracted
   → Validated → FinalVerified → FilesGenerated → Archived
                    ↓ (retry if validation fails)
               ProblemsExtracted
```

## Key Design Patterns

### Column Detection Strategy
1. **Vertical lines detection** (primary): Find strong vertical separators using OpenCV
2. **Content gaps** (fallback): Analyze white space between text blocks
3. **Problem positions** (validation): Use detected problem locations

Always use page midpoint (width // 2) for 2-column layouts when vertical lines are unclear.

### Problem Number Patterns
- Arabic: `1.`, `2.`, `3.`
- Circled: `①`, `②`, `③`
- Bracketed: `[1]`, `[2]`, `[3]`
- Solution markers: `[정답]`, `[해설]`

### Boundary Strategies (core/problem_boundary.py)
- **MARKER_ONLY**: Use problem number markers only
- **MARKER_WITH_WHITESPACE**: Markers + whitespace gaps
- **COMBINED**: Markers + whitespace + heuristics (recommended)

## Proofs and Invariants

The Idris2 specifications define properties that must hold:

1. **NoOverlap**: Problem regions don't overlap
2. **ValidLayout**: Layout has valid column count and non-overlapping columns
3. **ProblemsInOrder**: Problem numbers are in ascending order
4. **UniqueFilenames**: Output filenames are unique (no collisions)
5. **CompleteOutput**: All problems have corresponding output files
6. **ValidTransition**: Workflow state transitions are valid

Python implementations should maintain these invariants at runtime.

## Common Patterns

### When implementing from specs:
1. Read the corresponding `.specs/System/*.idr` file first
2. Understand the data types and proofs required
3. Implement Python code maintaining the type invariants
4. Add runtime validation matching the proof requirements
5. Write tests verifying the invariants

### When debugging extraction issues:
1. Check layout detection results first (column boundaries)
2. Verify OCR results (problem numbers detected)
3. Examine boundary detection strategy
4. Validate against spec (expected vs. detected)
5. Check for overlapping regions (NoOverlap violation)

### Working with AgentTools:
```python
from AgentTools import pdf, layout, extraction
from AgentTools.types import ToolResult

# All functions return ToolResult
result: ToolResult = pdf.summarize_pdf("sample.pdf")
if not result.success:
    print(f"Error: {result.message}")
    for error in result.diagnostics.errors:
        print(f"  - {error}")
    return

# Access data from successful result
page_count = result.data["page_count"]
```

## Critical Implementation Notes

1. **Column Detection**: Always detect layout before extraction. Multi-column PDFs must be linearized first.

2. **Reading Order**: Korean test papers typically use left-to-right, top-to-bottom order within columns. Process left column completely before right column.

3. **Margin Trimming**: Trim white space around extracted problems but preserve enough context. Default margin: 10-20 pixels.

4. **OCR Confidence**: Filter low-confidence results (< 0.4). Problem numbers should have high confidence (>= 0.7).

5. **Validation Retry Logic**: If validation fails, retry extraction for missing problems only (don't re-extract everything).

6. **File Naming**: Use format `{number}_prb.png` for problems, `{number}_sol.png` for solutions. Pad numbers if needed (01_prb vs 1_prb).

## Directory Structure Reference

```
problem_cutter/
├── .specs/System/        # Idris2 specifications (design source of truth)
├── core/                 # Python implementation (matches specs)
├── AgentTools/          # LLM-agent friendly wrappers
├── tests/               # pytest test suite
├── samples/             # Test PDF samples
├── output/              # Extraction results (gitignored)
├── directions/          # Workflow documentation
└── run_full_extraction.py  # Main entry point
```

## Important Files to Reference

- **directions/view.md**: 8-step workflow overview
- **directions/cutting_pdf.md**: Original requirements and design rationale
- **OPENCV_GUIDE.md**: OpenCV techniques for layout detection
- **TEST_RESULTS.md**: Test results and known issues
- **README.md**: Project overview and Idris2 specifications guide
