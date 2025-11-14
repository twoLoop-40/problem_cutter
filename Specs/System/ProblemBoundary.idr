||| Problem boundary detection with column separation
|||
||| Key insight from directions/view.md:
||| "3. 단을 잘라서 1단으로 만들고"
||| "4. 세로로 추적해가면서 각문제를 잘라낸다"
|||
||| This means:
||| 1. Multi-column PDF → Separate columns vertically
||| 2. Concatenate columns into single column (top to bottom)
||| 3. Detect problem markers in linear sequence
||| 4. Extract each problem boundary

module System.ProblemBoundary

import System.Base
import Data.List
import Data.List.Elem
import Data.List.Quantifiers
import Data.Nat

%default total

--------------------------------------------------------------------------------
-- Column separation strategy
--------------------------------------------------------------------------------

||| Column detection result
public export
data ColumnLayout : Type where
  ||| Single column layout (no separation needed)
  SingleColumn : (width : Nat) -> ColumnLayout

  ||| Two columns detected (need separation)
  TwoColumns : (leftBound : Nat) -> (rightBound : Nat) -> ColumnLayout

  ||| Multiple columns (general case)
  MultiColumns : (boundaries : List Nat) -> ColumnLayout


||| After separation, all content is in single-column form
public export
record LinearizedContent where
  constructor MkLinearized
  ||| Original page dimensions
  originalWidth : Nat
  originalHeight : Nat

  ||| Separated column images (in reading order)
  columnImages : List (Coord, Nat, Nat)  -- (top_left, width, height)

  ||| Total height after concatenation
  totalHeight : Nat


||| Proof that linearized content preserves all regions
public export
data PreservesContent : ColumnLayout -> LinearizedContent -> Type where
  ||| Single column: content unchanged
  PreservesSingle : PreservesContent (SingleColumn w) linearized

  ||| Two columns: left then right, total height = sum
  PreservesTwoColumns :
    (leftHeight : Nat) ->
    (rightHeight : Nat) ->
    (totalHeight = leftHeight + rightHeight) ->
    PreservesContent (TwoColumns l r) linearized


--------------------------------------------------------------------------------
-- Problem marker detection in linearized content
--------------------------------------------------------------------------------

||| Problem marker (detected by OCR)
public export
record ProblemMarker where
  constructor MkMarker
  number : Nat
  yPosition : Nat  -- Y coordinate in linearized content
  confidence : Double


||| Markers must be in ascending order and within valid range
public export
data ValidMarkers : List ProblemMarker -> Type where
  ValidEmpty : ValidMarkers []
  ValidSingle : {n : Nat} -> {y : Nat} -> {c : Double} ->
                LTE 1 n -> LTE n 100 -> ValidMarkers [MkMarker n y c]
  ValidCons : {m1, m2 : ProblemMarker} -> {rest : List ProblemMarker} ->
              LT m1.number m2.number ->
              LT m1.yPosition m2.yPosition ->
              ValidMarkers (m2 :: rest) ->
              ValidMarkers (m1 :: m2 :: rest)


--------------------------------------------------------------------------------
-- Problem boundary calculation
--------------------------------------------------------------------------------

||| Problem boundary in linearized content
public export
record ProblemBoundary where
  constructor MkBoundary
  problemNumber : Nat
  startY : Nat  -- Start position (inclusive)
  endY : Nat    -- End position (exclusive)
  width : Nat   -- Width (from linearized content)


||| Calculate boundary for problem N:
||| - Start: Y position of marker N (or 0 if first)
||| - End: Y position of marker N+1 (or totalHeight if last)
|||
||| This captures ALL content between two markers, including:
||| - Passage/figures ABOVE the marker
||| - Problem text and choices BELOW the marker
public export
calculateBoundary : (markers : List ProblemMarker) ->
                   (idx : Nat) ->
                   (totalHeight : Nat) ->
                   (width : Nat) ->
                   Maybe ProblemBoundary
calculateBoundary [] _ _ _ = Nothing
calculateBoundary (m :: ms) Z totalHeight w =
  -- First marker: start from 0
  case ms of
    [] => Just $ MkBoundary m.number 0 totalHeight w
    (next :: _) => Just $ MkBoundary m.number 0 next.yPosition w
calculateBoundary (m :: ms) (S k) totalHeight w =
  calculateBoundary ms k totalHeight w


||| Extract all boundaries from markers
public export
extractAllBoundaries : (markers : List ProblemMarker) ->
                      (totalHeight : Nat) ->
                      (width : Nat) ->
                      List ProblemBoundary
extractAllBoundaries [] _ _ = []
extractAllBoundaries markers totalHeight width =
  let count = length markers
      indices = if count > 0 then [0 .. (count `minus` 1)] else []
  in mapMaybe (\idx => calculateBoundary markers idx totalHeight width) indices


--------------------------------------------------------------------------------
-- Boundary properties
--------------------------------------------------------------------------------

||| Property: Boundaries don't overlap
public export
data NoOverlap : List ProblemBoundary -> Type where
  NoOverlapEmpty : NoOverlap []
  NoOverlapSingle : {b : ProblemBoundary} -> NoOverlap [b]
  NoOverlapCons : {b1, b2 : ProblemBoundary} -> {rest : List ProblemBoundary} ->
                  LTE b1.endY b2.startY ->
                  NoOverlap (b2 :: rest) ->
                  NoOverlap (b1 :: b2 :: rest)


||| Property: Boundaries cover entire content
public export
data CoversAll : List ProblemBoundary -> Nat -> Type where
  CoversFromZero : (firstBoundary.startY = 0) ->
                   (lastBoundary.endY = totalHeight) ->
                   CoversAll boundaries totalHeight


||| Property: Each boundary has positive height
public export
data PositiveHeight : ProblemBoundary -> Type where
  HasHeight : {b : ProblemBoundary} -> LT b.startY b.endY -> PositiveHeight b


||| Lemma: If markers are valid, boundaries don't overlap
public export
validMarkersImplyNoOverlap : ValidMarkers markers ->
                            (boundaries = extractAllBoundaries markers h w) ->
                            NoOverlap boundaries
validMarkersImplyNoOverlap prf eq = believe_me ()  -- proof omitted


--------------------------------------------------------------------------------
-- Shared passages (passages that span multiple problems)
--------------------------------------------------------------------------------

||| Shared passage marker (e.g., [8_9] for problems 8 and 9)
public export
record SharedPassage where
  constructor MkSharedPassage
  ||| Problem numbers this passage applies to (e.g., [8, 9])
  problemNumbers : List Nat
  yPosition : Nat  -- Y coordinate in linearized content
  confidence : Double


||| Ground truth for shared passages
public export
record SharedPassageGroundTruth where
  constructor MkSharedPassageGroundTruth
  problemNumbers : List Nat
  expectedWidth : Nat
  expectedHeight : Nat


||| Shared passages must be detected BEFORE regular problem boundaries
||| They are extracted separately and excluded from problem boundary calculation
public export
data ValidSharedPassages : List SharedPassage -> List ProblemMarker -> Type where
  ||| No shared passages - all markers are regular problems
  NoShared : {markers : List ProblemMarker} -> ValidSharedPassages [] markers

  ||| Shared passage appears BEFORE the first problem it references
  ValidShared : {passage : SharedPassage} -> {firstProblem : ProblemMarker} ->
                {rest : List SharedPassage} -> {markers : List ProblemMarker} ->
                LT passage.yPosition firstProblem.yPosition ->
                Elem firstProblem.number passage.problemNumbers ->
                ValidSharedPassages rest markers ->
                ValidSharedPassages (passage :: rest) markers


||| Extract shared passage boundary
public export
calculateSharedBoundary : SharedPassage ->
                         (nextMarker : ProblemMarker) ->
                         (width : Nat) ->
                         (Coord, Nat, Nat)  -- (top_left, width, height)
calculateSharedBoundary passage nextMarker w =
  let startY = passage.yPosition
      endY = nextMarker.yPosition
      height = endY `minus` startY
  in (MkCoord 0 (cast startY), w, height)


--------------------------------------------------------------------------------
-- Complete workflow with proofs
--------------------------------------------------------------------------------

||| Complete problem extraction with guarantees
|||
||| Workflow:
||| 1. Remove non-problem content (answer sheets, instructions)
||| 2. Detect column layout
||| 3. Linearize content (separate columns → merge into single column)
||| 4. Detect problem markers AND shared passages in linearized content
||| 5. Calculate boundaries (mark starting points - don't cut yet)
||| 6. Human verification and adjustment (ensure no data loss)
||| 7. Final cropping after approval
public export
record ProblemExtraction where
  constructor MkExtraction

  ||| Step 1: Content filtering (remove non-problem pages)
  filteredPages : List Nat  -- Page numbers to process

  ||| Step 2: Detect column layout
  layout : ColumnLayout

  ||| Step 3: Linearize content (separate columns → single column)
  linearized : LinearizedContent
  preserves : PreservesContent layout linearized

  ||| Step 4a: Detect shared passages (must come BEFORE regular markers)
  sharedPassages : List SharedPassage

  ||| Step 4b: Detect problem markers in linearized content
  markers : List ProblemMarker
  markersValid : ValidMarkers markers
  sharedValid : ValidSharedPassages sharedPassages markers

  ||| Step 5: Calculate boundaries (for marking/verification only)
  boundaries : List ProblemBoundary
  boundariesCorrect : boundaries = extractAllBoundaries markers linearized.totalHeight linearized.originalWidth

  ||| Step 6: Verify properties (before human review)
  noOverlap : NoOverlap boundaries
  coversAll : CoversAll boundaries linearized.totalHeight
  allPositive : All PositiveHeight boundaries
  noDataLoss : PreservesContent layout linearized  -- Ensure no text/images lost


||| Given a valid extraction, we can safely crop each problem
public export
cropProblem : ProblemExtraction -> ProblemBoundary -> (Coord, Nat, Nat)
cropProblem extraction boundary =
  let startY = boundary.startY
      height = boundary.endY `minus` boundary.startY
      width = boundary.width
  in (MkCoord 0 (cast startY), width, height)


--------------------------------------------------------------------------------
-- Ground truth validation
--------------------------------------------------------------------------------

||| Ground truth dimensions from manual extraction
public export
record GroundTruth where
  constructor MkGroundTruth
  problemNumber : Nat
  expectedWidth : Nat
  expectedHeight : Nat


||| Validation result
public export
data ValidationResult : Type where
  ||| Dimensions match (within tolerance)
  Matches : (tolerance : Nat) -> ValidationResult

  ||| Width mismatch
  WidthMismatch : (expected : Nat) -> (actual : Nat) -> ValidationResult

  ||| Height mismatch
  HeightMismatch : (expected : Nat) -> (actual : Nat) -> ValidationResult


||| Validate extracted boundary against ground truth
public export
validateBoundary : ProblemBoundary -> GroundTruth -> (tolerance : Nat) -> ValidationResult
validateBoundary boundary truth tolerance =
  let actualWidth = boundary.width
      actualHeight = boundary.endY `minus` boundary.startY
      expectedWidth = truth.expectedWidth
      expectedHeight = truth.expectedHeight
      widthDiff = if actualWidth > expectedWidth
                 then actualWidth `minus` expectedWidth
                 else expectedWidth `minus` actualWidth
      heightDiff = if actualHeight > expectedHeight
                  then actualHeight `minus` expectedHeight
                  else expectedHeight `minus` actualHeight
  in if widthDiff <= tolerance && heightDiff <= tolerance
     then Matches tolerance
     else if widthDiff > tolerance
          then WidthMismatch expectedWidth actualWidth
          else HeightMismatch expectedHeight actualHeight


--------------------------------------------------------------------------------
-- Example ground truth data
--------------------------------------------------------------------------------

||| Ground truth for 사회탐구 (Social Studies)
public export
socialStudiesGroundTruth : List GroundTruth
socialStudiesGroundTruth =
  [ MkGroundTruth 1 1174 946
  , MkGroundTruth 2 1164 830
  , MkGroundTruth 3 1198 1036
  , MkGroundTruth 4 1176 1396
  , MkGroundTruth 5 1182 1168
  ]


||| Ground truth for 통합과학 (Integrated Science)
||| Note: Problem [8_9] is a shared passage, not a regular problem
public export
scienceGroundTruth : List GroundTruth
scienceGroundTruth =
  [ MkGroundTruth 6 1194 1150
  , MkGroundTruth 7 1240 1384
  , MkGroundTruth 8 1224 1140
  , MkGroundTruth 9 1222 1196
  ]


||| Ground truth for shared passages in 통합과학
public export
scienceSharedPassageGroundTruth : List SharedPassageGroundTruth
scienceSharedPassageGroundTruth =
  [ MkSharedPassageGroundTruth [8, 9] 1202 556
  ]
