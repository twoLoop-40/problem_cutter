||| PDF layout detection
|||
||| This module handles detection of PDF layout structure:
||| - Number of columns (1, 2, or 3)
||| - Vertical separator lines
||| - Column boundaries
module System.LayoutDetection

import System.Base
import Data.List
import Data.List.Quantifiers
import Data.Fin

%default total

||| Number of columns in the layout
public export
data ColumnCount = OneColumn | TwoColumn | ThreeColumn

public export
Eq ColumnCount where
  OneColumn == OneColumn = True
  TwoColumn == TwoColumn = True
  ThreeColumn == ThreeColumn = True
  _ == _ = False

||| Method used to detect columns
public export
data DetectionMethod =
  VerticalLines        -- Using separator lines
  | ContentGaps        -- Using whitespace between content
  | ProblemPositions   -- Using problem number positions

||| Column boundary (x-coordinate range)
public export
record ColumnBound where
  constructor MkColumnBound
  leftX : Nat
  rightX : Nat

||| Proof that a column bound is valid (left < right)
public export
IsValidBound : ColumnBound -> Type
IsValidBound col = LT col.leftX col.rightX

||| Page layout information
public export
record PageLayout where
  constructor MkPageLayout
  pageWidth : Nat
  pageHeight : Nat
  columnCount : ColumnCount
  detectionMethod : DetectionMethod
  ||| Vertical separator lines found (if any)
  separatorLines : List VLine
  ||| Column boundaries
  columns : List ColumnBound

||| Helper: Convert ColumnCount to Nat
public export
columnCountToNat : ColumnCount -> Nat
columnCountToNat OneColumn = 1
columnCountToNat TwoColumn = 2
columnCountToNat ThreeColumn = 3

||| Proof that the number of columns matches column boundaries
public export
data ValidColumnBounds : ColumnCount -> List ColumnBound -> Type where
  ValidOne : (c : ColumnBound) -> ValidColumnBounds OneColumn [c]
  ValidTwo : (c1, c2 : ColumnBound) -> ValidColumnBounds TwoColumn [c1, c2]
  ValidThree : (c1, c2, c3 : ColumnBound) -> ValidColumnBounds ThreeColumn [c1, c2, c3]

||| Columns don't overlap (one ends before next starts)
public export
ColumnsNotOverlap : ColumnBound -> ColumnBound -> Type
ColumnsNotOverlap c1 c2 = (rightX c1) `LTE` (leftX c2)

||| Proof that column boundaries don't overlap
public export
data NonOverlappingColumns : List ColumnBound -> Type where
  NonOverlapNil : NonOverlappingColumns []
  NonOverlapOne : NonOverlappingColumns [c]
  NonOverlapCons : (c : ColumnBound) ->
                   (cs : List ColumnBound) ->
                   (prf : All (ColumnsNotOverlap c) cs) ->
                   NonOverlappingColumns cs ->
                   NonOverlappingColumns (c :: cs)

||| Proof that a valid layout has correct number of non-overlapping columns
public export
data ValidLayout : PageLayout -> Type where
  MkValidLayout : (layout : PageLayout) ->
                  ValidColumnBounds layout.columnCount layout.columns ->
                  NonOverlappingColumns layout.columns ->
                  ValidLayout layout

||| Check if a point is within a column
public export
inColumn : Coord -> ColumnBound -> Bool
inColumn point col = 
  leftX col <= x point && x point <= rightX col

||| Find which column a point belongs to
public export
findColumn : Coord -> (cols : List ColumnBound) -> Maybe (Fin (length cols))
findColumn point [] = Nothing
findColumn point (col :: cols) = 
  if inColumn point col
    then Just FZ
    else map FS (findColumn point cols)

||| Create a single-column layout (simplest case)
public export
mkSingleColumn : (width : Nat) -> (height : Nat) -> PageLayout
mkSingleColumn width height = MkPageLayout
  width
  height
  OneColumn
  ContentGaps
  []
  [MkColumnBound 0 width]

||| Create a two-column layout from a vertical line
public export
mkTwoColumnFromVLine : (width : Nat) -> (height : Nat) -> (vline : VLine) -> PageLayout
mkTwoColumnFromVLine width height vline = MkPageLayout
  width
  height
  TwoColumn
  VerticalLines
  [vline]
  [MkColumnBound 0 (x vline),
   MkColumnBound (x vline) width]

-------------------------------------------------------------------------
-- Narrow column merging (to handle thick separator lines)
-------------------------------------------------------------------------

||| Calculate column width
public export
columnWidth : ColumnBound -> Nat
columnWidth col = col.rightX `minus` col.leftX

||| Check if a column is narrower than threshold
|||
||| Narrow columns (< 100px typically) are likely separator lines,
||| not actual content columns
public export
isNarrowColumn : (threshold : Nat) -> ColumnBound -> Bool
isNarrowColumn threshold col = columnWidth col < threshold

||| Merge nearby vertical lines into one
|||
||| When a separator line has thickness (e.g., two lines at x=275 and x=295),
||| they should be treated as a single separator
|||
||| @mergeThreshold Maximum distance between lines to merge (typically 20-50px)
public export
partial
mergeNearbyVLines : (mergeThreshold : Nat) -> List VLine -> List VLine
-- Implementation in Python:
-- Group lines where abs(line1.x - line2.x) <= threshold
-- Take average x position of the group

||| Filter out columns narrower than threshold
|||
||| Returns only content columns, removing separator regions
|||
||| @minWidth Minimum column width (typically 100px)
public export
filterNarrowColumns : (minWidth : Nat) -> List ColumnBound -> List ColumnBound
filterNarrowColumns minWidth = filter (not . isNarrowColumn minWidth)

||| Proof that all columns are wide enough
public export
data AllWideEnough : (minWidth : Nat) -> List ColumnBound -> Type where
  WideNil : AllWideEnough minWidth []
  WideCons : (col : ColumnBound) ->
             (cols : List ColumnBound) ->
             (prf : minWidth `LTE` columnWidth col) ->
             AllWideEnough minWidth cols ->
             AllWideEnough minWidth (col :: cols)

||| Create layout from merged lines
|||
||| This is the recommended way to create layouts:
||| 1. Detect all vertical lines
||| 2. Merge nearby lines (thick separators)
||| 3. Create column boundaries
||| 4. Filter out narrow "columns" (actual separators)
public export
partial
mkLayoutFromMergedLines : (width : Nat) ->
                         (height : Nat) ->
                         List VLine ->
                         PageLayout
-- Implementation:
-- 1. mergedLines = mergeNearbyVLines 20 lines
-- 2. Create column bounds from merged lines
-- 3. allColumns = create columns between (0, line1.x, line2.x, ..., width)
-- 4. contentColumns = filterNarrowColumns 100 allColumns
-- 5. Determine ColumnCount based on length contentColumns
-- 6. Return PageLayout with contentColumns

