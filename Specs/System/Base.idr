||| Base types for PDF problem extraction
|||
||| This module defines fundamental types for representing
||| PDF coordinates, bounding boxes, and regions.
module System.Base

import Data.Nat
import Data.List.Quantifiers
import Decidable.Equality

%default total

||| 2D coordinate in PDF space
||| Origin is typically top-left corner
public export
record Coord where
  constructor MkCoord
  x : Nat
  y : Nat

||| Bounding box defined by top-left corner and dimensions
public export
record BBox where
  constructor MkBBox
  topLeft : Coord
  width : Nat
  height : Nat

||| Helper to get bottom-right coordinate
public export
bottomRight : BBox -> Coord
bottomRight box = MkCoord 
  (box.topLeft.x + box.width) 
  (box.topLeft.y + box.height)

||| Helper to get center coordinate
public export
center : BBox -> Coord
center box = MkCoord
  (box.topLeft.x + (box.width `Prelude.div` 2))
  (box.topLeft.y + (box.height `Prelude.div` 2))

||| Check if two bounding boxes overlap
public export
overlaps : BBox -> BBox -> Bool
overlaps b1 b2 =
  let br1 = bottomRight b1
      br2 = bottomRight b2
  in not (b1.topLeft.x >= br2.x || 
          br1.x <= b2.topLeft.x ||
          b1.topLeft.y >= br2.y ||
          br1.y <= b2.topLeft.y)

||| Check if box1 contains box2
public export
contains : BBox -> BBox -> Bool
contains outer inner =
  let brOuter = bottomRight outer
      brInner = bottomRight inner
  in outer.topLeft.x <= inner.topLeft.x &&
     outer.topLeft.y <= inner.topLeft.y &&
     brOuter.x >= brInner.x &&
     brOuter.y >= brInner.y

||| Vertical line in PDF (for column separation)
public export
record VLine where
  constructor MkVLine
  x : Nat
  yStart : Nat
  yEnd : Nat

||| Check if a vertical line is "significant" (long enough)
||| Returns True if line length is at least minLength
public export
isSignificantVLine : (minLength : Nat) -> VLine -> Bool
isSignificantVLine minLen vline = 
  minLen <= (vline.yEnd `minus` vline.yStart)

||| Problem number (1-based)
public export
ProblemNum : Type
ProblemNum = Nat

||| Reading order (0-based, for sorting)
public export
ReadOrder : Type
ReadOrder = Nat

||| Predicate: two boxes do not overlap
public export
NotOverlapping : BBox -> BBox -> Type
NotOverlapping b1 b2 = overlaps b1 b2 = False

||| Proof that a list has no overlapping bounding boxes
public export
data NoOverlap : List BBox -> Type where
  NoOverlapNil : NoOverlap []
  NoOverlapOne : (box : BBox) -> NoOverlap [box]
  NoOverlapCons : (box : BBox) -> 
                  (xs : List BBox) -> 
                  (prf : All (NotOverlapping box) xs) ->
                  NoOverlap xs ->
                  NoOverlap (box :: xs)

||| Proof that all boxes in a list are contained in a parent box
public export
data AllContained : BBox -> List BBox -> Type where
  AllContainedNil : AllContained parent []
  AllContainedCons : (parent : BBox) ->
                     (x : BBox) ->
                     (xs : List BBox) ->
                     (prf : contains parent x = True) ->
                     AllContained parent xs ->
                     AllContained parent (x :: xs)

