||| Problem extraction from PDF
|||
||| This module defines types for extracting problems and solutions
||| from exam PDFs, including numbering detection and region classification.
module ProblemExtraction

import Base
import LayoutDetection
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

