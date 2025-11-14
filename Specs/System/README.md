# Idris2 Type Specifications

This directory contains the formal type specifications for the PDF Problem Cutter project.

## 📋 Files Overview

| File | Purpose | Status | Lines |
|------|---------|--------|-------|
| `Base.idr` | Basic types (Coord, BBox, VLine, proofs) | ✅ Compiles | ~110 |
| `PdfMetadata.idr` | PDF metadata types (Subject, ExamType, etc.) | ✅ Compiles | ~90 |
| `LayoutDetection.idr` | Layout detection (columns, boundaries) | ✅ Compiles | ~135 |
| `ProblemExtraction.idr` | Problem/solution extraction | ✅ Compiles | ~170 |
| `OutputFormat.idr` | Output file format specification | ✅ Compiles | ~150 |
| `Workflow.idr` | Complete workflow state machine | ✅ Compiles | ~80 |

**Total**: 6 modules, ~735 lines of specifications

## 🔍 Module Dependencies

```
Base.idr (foundational)
  ↓
  ├─→ PdfMetadata.idr
  ├─→ LayoutDetection.idr
  │     ↓
  │     └─→ ProblemExtraction.idr
  │           ↓
  │           ├─→ OutputFormat.idr
  │           └─→ Workflow.idr
  └─→ Workflow.idr
```

## ✅ Compilation Verification

All specifications compile successfully:

```bash
idris2 --check Base.idr               # ✅ OK
idris2 --check PdfMetadata.idr        # ✅ OK
idris2 --check LayoutDetection.idr    # ✅ OK
idris2 --check ProblemExtraction.idr  # ✅ OK
idris2 --check OutputFormat.idr       # ✅ OK
idris2 --check Workflow.idr           # ✅ OK
```

## 🎯 Key Proof Types

### Base.idr
- `NoOverlap : List BBox -> Type` - Bounding boxes don't overlap
- `AllContained : BBox -> List BBox -> Type` - All boxes contained in parent
- `NotOverlapping : BBox -> BBox -> Type` - Two boxes don't overlap

### LayoutDetection.idr
- `IsValidBound : ColumnBound -> Type` - Column bound is valid (left < right)
- `ValidColumnBounds : ColumnCount -> List ColumnBound -> Type` - Correct number of columns
- `NonOverlappingColumns : List ColumnBound -> Type` - Columns don't overlap
- `ValidLayout : PageLayout -> Type` - Complete layout validation

### ProblemExtraction.idr
- `ValidProblem : ProblemItem -> Type` - Problem has valid structure
- `ValidSolution : SolutionItem -> Type` - Solution has valid structure
- `ProblemsInOrder : List ProblemItem -> Type` - Problems are sorted

### OutputFormat.idr
- `DifferentFilenames : OutputFile -> OutputFile -> Type` - Files have different names
- `UniqueFilenames : List OutputFile -> Type` - All filenames are unique
- `ValidOutput : OutputPackage -> Type` - Output package is valid
- `CompleteOutput : ExtractionResult -> List OutputFile -> Type` - All problems/solutions have files

### Workflow.idr
- `ValidTransition : WorkflowState -> WorkflowStep -> WorkflowState -> Type` - State transitions are valid
- `ValidWorkflow : WorkflowExecution -> Type` - Workflow execution is valid

## 📖 Reading Guide

### Understanding Idris2 Syntax

1. **Data Types** - Define structure
```idris
data ColumnCount = OneColumn | TwoColumn | ThreeColumn
```

2. **Records** - Product types with named fields
```idris
record BBox where
  constructor MkBBox
  topLeft : Coord
  width : Nat
  height : Nat
```

3. **Dependent Types** - Types that depend on values
```idris
data NoOverlap : List BBox -> Type where
  NoOverlapNil : NoOverlap []
  NoOverlapOne : (box : BBox) -> NoOverlap [box]
```

4. **Proof Construction** - Building evidence
```idris
data ValidLayout : PageLayout -> Type where
  MkValidLayout : (layout : PageLayout) ->
                  ValidColumnBounds layout.columnCount layout.columns ->
                  NonOverlappingColumns layout.columns ->
                  ValidLayout layout
```

## 🔧 Implementation Guide

When implementing in Python, maintain these type invariants:

### Base Types
```python
@dataclass
class Coord:
    x: int  # Nat in Idris2
    y: int  # Nat in Idris2

@dataclass
class BBox:
    top_left: Coord
    width: int
    height: int
```

### Proofs as Runtime Checks
```python
def check_no_overlap(boxes: list[BBox]) -> bool:
    """Runtime check for NoOverlap proof"""
    for i, b1 in enumerate(boxes):
        for b2 in boxes[i+1:]:
            if overlaps(b1, b2):
                return False
    return True
```

### State Machines
```python
class WorkflowState(Enum):
    INITIAL = "initial"
    METADATA_EXTRACTED = "metadata_extracted"
    LAYOUT_DETECTED = "layout_detected"
    # ... follow Workflow.idr
```

## 🎓 Design Principles

1. **Type Safety First** - If it compiles, it's structurally correct
2. **Proof-Carrying Code** - Proofs document invariants
3. **Separation of Concerns** - Each module has a single responsibility
4. **Progressive Refinement** - Build complex types from simple ones

## 🚀 Next Steps for Implementation

1. **core/base.py** - Implement Base.idr types
2. **core/metadata.py** - Implement PdfMetadata.idr
3. **core/layout.py** - Implement LayoutDetection.idr
4. **core/extraction.py** - Implement ProblemExtraction.idr
5. **core/output.py** - Implement OutputFormat.idr
6. **core/workflow.py** - Implement Workflow.idr

## 📝 Notes

- All functions marked `partial` need careful runtime handling
- Functions without implementations are placeholders for Python
- Proofs may be relaxed to runtime checks in Python
- Follow the type signatures exactly for API compatibility

---

**Specification Status**: Complete ✅  
**Compilation Status**: All modules compile ✅  
**Implementation Status**: Pending 🔨

