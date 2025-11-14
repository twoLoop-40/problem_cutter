||| Problem extraction from PDF
|||
||| This module defines types for extracting problems and solutions
||| from exam PDFs, including numbering detection and region classification.
module System.ProblemExtraction

import System.Base
import System.LayoutDetection
import System.OcrEngine
import Data.List
import Data.List.Quantifiers
import Data.Fin

%default total

||| Content type in the PDF
public export
data ContentType =
  ProblemContent   -- 문제 (1., 2., etc.)
  | SolutionContent  -- 정답/해설 ([정답], [해설])
  | Header        -- 헤더/메타데이터
  | Unknown

public export
Eq ContentType where
  ProblemContent == ProblemContent = True
  SolutionContent == SolutionContent = True
  Header == Header = True
  Unknown == Unknown = True
  _ == _ = False

||| Marker for problem/solution numbering
public export
data NumberMarker =
  ArabicDot Nat       -- 1., 2., 3., ...
  | SquareBracket Nat -- [1], [2], ...
  | Circled Nat       -- ①, ②, ...
  | NoMarker

public export
Eq NumberMarker where
  ArabicDot n1 == ArabicDot n2 = n1 == n2
  SquareBracket n1 == SquareBracket n2 = n1 == n2
  Circled n1 == Circled n2 = n1 == n2
  NoMarker == NoMarker = True
  _ == _ = False

||| Extract number from marker
public export
markerNumber : NumberMarker -> Maybe Nat
markerNumber (ArabicDot n) = Just n
markerNumber (SquareBracket n) = Just n
markerNumber (Circled n) = Just n
markerNumber NoMarker = Nothing

||| Content region in PDF
public export
record ContentRegion where
  constructor MkContentRegion
  bbox : BBox
  contentType : ContentType
  numberMarker : NumberMarker
  ||| Column index (for multi-column layouts)
  columnIndex : Maybe Nat
  ||| Reading order within the page
  readOrder : ReadOrder

||| Problem item (question)
public export
record ProblemItem where
  constructor MkProblemItem
  number : ProblemNum
  region : BBox
  ||| Sub-regions (text, images, etc.)
  subRegions : List BBox
  ||| Original page number in PDF
  pageNum : Nat

||| Solution item (answer/explanation)
public export
record SolutionItem where
  constructor MkSolutionItem
  number : ProblemNum
  region : BBox
  ||| Sub-regions (text, images, etc.)
  subRegions : List BBox
  ||| Original page number in PDF
  pageNum : Nat

||| Paired problem and solution
public export
record ProblemPair where
  constructor MkProblemPair
  number : ProblemNum
  problem : ProblemItem
  solution : Maybe SolutionItem

||| Complete extraction result for a PDF
public export
record ExtractionResult where
  constructor MkExtractionResult
  problems : List ProblemItem
  solutions : List SolutionItem
  ||| Problems paired with their solutions
  paired : List ProblemPair
  ||| Unpaired problems (missing solutions)
  unpairedProblems : List ProblemNum
  ||| Unpaired solutions (missing problems)
  unpairedSolutions : List ProblemNum

||| Proof that a problem has no overlapping sub-regions
public export
data ValidProblem : ProblemItem -> Type where
  MkValidProblem : (p : ProblemItem) ->
                   NoOverlap p.subRegions ->
                   AllContained p.region p.subRegions ->
                   ValidProblem p

||| Proof that a solution has no overlapping sub-regions
public export
data ValidSolution : SolutionItem -> Type where
  MkValidSolution : (s : SolutionItem) ->
                    NoOverlap s.subRegions ->
                    AllContained s.region s.subRegions ->
                    ValidSolution s

||| Proof that problems are in correct order
public export
data ProblemsInOrder : List ProblemItem -> Type where
  OrderNil : ProblemsInOrder []
  OrderOne : ProblemsInOrder [p]
  OrderCons : (p : ProblemItem) ->
              (ps : List ProblemItem) ->
              (prf : All (\p2 => LT p.number p2.number) ps) ->
              ProblemsInOrder ps ->
              ProblemsInOrder (p :: ps)

||| Helper: Sort content regions by reading order
||| Note: Implementation delegated to runtime (not proven total here)
public export
sortByReadOrder : List ContentRegion -> List ContentRegion
-- This would be implemented in Python using standard sorting

||| Helper: Group regions by problem number
||| Note: Implementation delegated to runtime
public export
groupByNumber : List ContentRegion -> List (ProblemNum, List ContentRegion)
-- This would be implemented in Python using groupby or similar

||| Calculate reading order based on column layout and y-position
||| For two-column: left column top-to-bottom, then right column
||| Note: This is a simplified version; full implementation in Python
public export
partial
calculateReadOrder : PageLayout -> Coord -> ReadOrder
calculateReadOrder layout point = y point  -- Simplified; actual logic in Python runtime

-------------------------------------------------------------------------
-- OCR-based problem boundary detection
-------------------------------------------------------------------------

||| Strategy for detecting problem boundaries
|||
||| This addresses the requirement: "1., 2. 와 여백을 이용해서 문제를 파악"
public export
data BoundaryStrategy =
  MarkerBased        -- Use number markers (1., 2., etc.) from OCR
  | VerticalGapBased -- Use vertical whitespace
  | Combined         -- Use both markers and gaps

||| Detected problem marker with its location
public export
record DetectedMarker where
  constructor MkDetectedMarker
  marker : NumberMarker
  position : Coord
  ocrSource : OcrResult

||| Detect problem markers from OCR results
|||
||| Finds patterns like "1.", "2.", "①", "②" etc.
|||
||| Implementation strategy:
||| 1. Filter OCR results by high confidence
||| 2. Parse each text with parseProblemNumber
||| 3. Create DetectedMarker for successful parses
public export
partial
detectProblemMarkers : List OcrResult -> List DetectedMarker
-- Implementation in Python using parseProblemNumber from OcrEngine

||| Detect solution markers from OCR results
|||
||| Finds "[정답]", "[해설]", "정답:", "해설:" etc.
|||
||| This addresses: "[정답] 과 번호를 이용해서 정답도 번호별로 파악"
public export
partial
detectSolutionMarkers : List OcrResult -> List DetectedMarker
-- Implementation in Python using isSolutionMarker from OcrEngine

||| Detect vertical gaps (whitespace) between content
|||
||| Large vertical gaps often indicate problem boundaries
|||
||| @minGapSize Minimum gap height to consider (typically 20-50px)
public export
partial
detectVerticalGaps : (minGapSize : Nat) -> List BBox -> List Nat
-- Implementation: analyze y-positions of boxes, find gaps
-- Returns: list of y-coordinates where gaps occur

||| Detect problem boundaries using markers and gaps
|||
||| Main function for problem extraction:
||| 1. Detect problem markers from OCR
||| 2. Detect vertical gaps
||| 3. Combine to determine problem boundaries
||| 4. Return list of (problem number, bounding box)
|||
||| @strategy Detection strategy to use
||| @layout Page layout (for column information)
||| @ocrResults OCR text detections
||| @allBoxes All content boxes (for gap analysis)
public export
partial
detectProblemBoundaries : BoundaryStrategy ->
                         PageLayout ->
                         List OcrResult ->
                         List BBox ->
                         List (ProblemNum, BBox)
-- Implementation algorithm:
-- 1. markers = detectProblemMarkers ocrResults
-- 2. gaps = detectVerticalGaps 30 allBoxes
-- 3. For each marker at position p:
--    - Find next marker position (or page end)
--    - Problem boundary = from p.y to next marker y
--    - Create bounding box covering that region
-- 4. Adjust boundaries using gap information

||| Extract problems from OCR results
|||
||| Complete extraction pipeline:
||| 1. Detect problem boundaries
||| 2. Group content regions by problem number
||| 3. Create ProblemItem for each
public export
partial
extractProblems : (pdfPath : String) ->
                  PageLayout ->
                  List OcrResult ->
                  List BBox ->
                  List ProblemItem
-- Implementation:
-- boundaries = detectProblemBoundaries Combined layout ocrResults allBoxes
-- For each (num, bbox) in boundaries:
--   subRegions = filter boxes within bbox
--   create ProblemItem

||| Extract solutions from OCR results
|||
||| Similar to extractProblems but looks for solution markers
public export
partial
extractSolutions : (pdfPath : String) ->
                   PageLayout ->
                   List OcrResult ->
                   List BBox ->
                   List SolutionItem
-- Implementation:
-- solutionMarkers = detectSolutionMarkers ocrResults
-- Group by problem number
-- Create SolutionItem for each

||| Proof that detected problem boundaries don't overlap
public export
data ValidProblemBoundaries : List (ProblemNum, BBox) -> Type where
  BoundariesNil : ValidProblemBoundaries []
  BoundariesOne : ValidProblemBoundaries [(n, box)]
  BoundariesCons : (n : ProblemNum) ->
                   (box : BBox) ->
                   (rest : List (ProblemNum, BBox)) ->
                   (prf : All (\pair => overlaps box (snd pair) = False) rest) ->
                   ValidProblemBoundaries rest ->
                   ValidProblemBoundaries ((n, box) :: rest)

||| Proof that all detected markers have valid problem numbers (> 0)
public export
data AllValidMarkers : List DetectedMarker -> Type where
  MarkersNil : AllValidMarkers []
  MarkersCons : (m : DetectedMarker) ->
                (ms : List DetectedMarker) ->
                (prf : case markerNumber m.marker of
                        Just n => LT 0 n
                        Nothing => Void) ->
                AllValidMarkers ms ->
                AllValidMarkers (m :: ms)

