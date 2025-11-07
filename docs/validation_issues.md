# Validation Issues and Fixes

## Current Issues (2025-11-07)

### Issue 1: False Positive - Problem "1" is actually Problem "7"

**Symptom:**
- Detected problem labeled as "1"
- Expected: Problem 7
- Location: Left column, around y=1920

**Root Cause:**
OCR is detecting "7," as "1" or there's a score marker like "[1.5점]" being parsed as problem 1.

**Diagnosis Steps:**
1. Run debug script around y=1920:
   ```bash
   python scripts/debug_ocr.py samples/통합과학_1_샘플.pdf --region 0,1800,600,300
   ```
2. Check what OCR text exists at that position
3. Verify parse_problem_number() filtering logic

**Proposed Fixes:**
1. **Strengthen score marker filtering:**
   ```python
   # In core/ocr_engine.py: parse_problem_number()
   # Current: filters '점]'
   # Need: also filter brackets around single digits like "[1]"

   if re.match(r'^\[\d+\]$', text):  # Single digit in brackets
       return None
   ```

2. **Add position-based validation:**
   ```python
   # Problem 1 should be near top of page (y < 500)
   # If detecting "1" at y > 1500, likely wrong
   if number == 1 and marker_y > 1500:
       continue  # Skip this candidate
   ```

3. **Use column context:**
   ```python
   # If we already detected 6, 7 in left column
   # and see "1" in same column, it's likely "7" misread
   # Verify with PyMuPDF fallback
   ```

### Issue 2: Problem 9 boundary cuts off multiple choice options

**Symptom:**
- Problem 9 detected (using PyMuPDF fallback) ✅
- But boundary ends too early
- Multiple choice options at bottom are cut off

**Root Cause:**
Boundary detection uses "next marker position" or "page end" as end_y.
Since problem 9 is the last problem, it should extend to page end, but might be:
1. Cut off by a gap detection
2. Cut off by solution marker "[정답]"
3. Calculated end_y is wrong

**Diagnosis Steps:**
1. Check detected y positions:
   ```bash
   # Problem 9 starts at y=2035 (from PyMuPDF)
   # What is end_y?
   # Expected: should be close to page height (3300+)
   # Actual: likely y=2035 + 654 = 2689 (too short)
   ```

2. Check if there's a gap or marker after problem 9:
   ```bash
   python scripts/debug_ocr.py samples/통합과학_1_샘플.pdf --region 1100,2500,500,1000
   ```

**Proposed Fixes:**
1. **Extend last problem to page end:**
   ```python
   # In core/problem_extractor.py: detect_problem_boundaries()

   # After creating boundaries, check if last problem
   if i == len(markers) - 1:
       # This is the last problem
       # Extend to page bottom (minus small margin)
       end_y = page_height - 50
   ```

2. **Ignore gaps after last marker:**
   ```python
   # Don't use gap detection for last problem
   if i == len(markers) - 1:
       end_y = page_height - 50  # Ignore gaps
   else:
       # Use gaps for non-last problems
       if gaps:
           nearby_gaps = [g for g in gaps if start_y < g < end_y]
           if nearby_gaps:
               end_y = nearby_gaps[-1]
   ```

3. **Add minimum height validation:**
   ```python
   # Problem 9 should have reasonable height (at least 600px)
   if height < 600:
       print(f"   ⚠ Problem {problem_num} height too small: {height}")
       # Try extending to page end
       end_y = page_height - 50
       height = end_y - start_y
   ```

### Issue 3: Invalid boundary heights

**Symptom:**
- Problem 7 detected with height=4px (too small)
- This is clearly wrong

**Root Cause:**
- Problem 7 marker detected at y=1920
- Problem "1" (actually 7?) detected at y=1924
- Gap of only 4px causes wrong boundary

**This is actually the same issue as Issue 1** - the "1" is a duplicate/misdetection of "7".

**Fix:**
Resolve Issue 1 first, then this should disappear.

---

## Testing Strategy

### 1. Ground Truth File

Create `samples/통합과학_1_샘플_expected.json`:
```json
{
  "expected_problems": [6, 7, 8, 9],
  "problem_positions": {
    "6": {"y_start": 450, "y_end": 1816, "column": "left"},
    "7": {"y_start": 1920, "y_end": 3200, "column": "left"},
    "8": {"y_start": 450, "y_end": 1816, "column": "right"},
    "9": {"y_start": 2035, "y_end": 3200, "column": "right"}
  }
}
```

### 2. Validation Workflow

```bash
# Run detection
python -m core.workflow samples/통합과학_1_샘플.pdf

# Validate results
python -m core.result_validator output/통합과학_1_샘플 samples/통합과학_1_샘플.pdf

# If failed, debug
python scripts/debug_ocr.py samples/통합과학_1_샘플.pdf
```

### 3. Success Criteria

- ✅ Detects exactly [6, 7, 8, 9]
- ✅ No false positives (no problem 1)
- ✅ All boundaries valid (height > 600px)
- ✅ Problem 9 includes all multiple choice options
- ✅ Validation accuracy: 100%

---

## Implementation Priority

1. **[HIGH]** Fix Issue 1: Filter false positive "1"
2. **[HIGH]** Fix Issue 2: Extend problem 9 to page end
3. **[MEDIUM]** Add ground truth file for validation
4. **[MEDIUM]** Improve boundary validation logic
5. **[LOW]** Add visual debugging (draw boxes on image)

---

## Next Steps

1. User provides sample PDF or confirms location
2. Run debug script to analyze current OCR
3. Implement fixes based on diagnosis
4. Re-run validation until 100% accuracy
5. Then proceed to LangGraph agent implementation
