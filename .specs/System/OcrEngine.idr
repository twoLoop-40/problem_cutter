||| OCR (Optical Character Recognition) integration
|||
||| This module defines types for integrating OCR engines
||| to extract text from PDF images, which is essential for:
||| - Detecting problem numbers ("1.", "2.", "①", "②")
||| - Finding solution markers ("[정답]", "[해설]")
||| - Extracting metadata from headers
module System.OcrEngine

import System.Base
import System.LayoutDetection
import Data.List
import Data.List.Quantifiers

%default total

||| Supported OCR engines
public export
data OcrEngine =
  Tesseract      -- Google Tesseract OCR
  | EasyOCR      -- Deep learning based OCR
  | PaddleOCR    -- PaddlePaddle OCR
  | ClaudeVision -- Claude 3 Vision API (backup)

public export
Eq OcrEngine where
  Tesseract == Tesseract = True
  EasyOCR == EasyOCR = True
  PaddleOCR == PaddleOCR = True
  ClaudeVision == ClaudeVision = True
  _ == _ = False

||| Language code for OCR
public export
Language : Type
Language = String  -- "kor", "eng", "kor+eng", etc.

||| OCR confidence score (0.0 to 1.0)
public export
record Confidence where
  constructor MkConfidence
  value : Double

public export
isHighConfidence : Confidence -> Bool
isHighConfidence conf = conf.value >= 0.7

public export
isMediumConfidence : Confidence -> Bool
isMediumConfidence conf = conf.value >= 0.4 && conf.value < 0.7

||| Single OCR detection result (one text block)
public export
record OcrResult where
  constructor MkOcrResult
  text : String
  bbox : BBox
  confidence : Confidence
  language : Language

||| OCR execution specification for a region
public export
record OcrExecution where
  constructor MkOcrExecution
  engine : OcrEngine
  ||| Input image region to perform OCR on
  inputRegion : BBox
  ||| Expected language(s)
  languages : List Language
  ||| Detected text blocks
  results : List OcrResult

||| Filter OCR results by minimum confidence
public export
filterByConfidence : (minConfidence : Double) ->
                     List OcrResult ->
                     List OcrResult
filterByConfidence minConf = filter (\r => r.confidence.value >= minConf)

||| Find OCR results containing a specific substring
|||
||| Example: findTextPattern "1." results  -- finds "1.", "11.", etc.
|||          findTextPattern "[정답]" results
public export
findTextPattern : (pattern : String) ->
                  List OcrResult ->
                  List OcrResult
-- Implementation in Python: use `pattern in result.text`

||| Find OCR results matching a regex pattern
|||
||| Example: findRegexPattern "^\\d+\\." results  -- finds "1.", "2.", etc.
public export
findRegexPattern : (pattern : String) ->
                   List OcrResult ->
                   List OcrResult
-- Implementation in Python: use re.search(pattern, result.text)

||| Parse problem number from text
|||
||| Recognizes patterns:
||| - "1.", "2.", "3." -> Arabic numbers with dot
||| - "[1]", "[2]" -> Bracketed numbers
||| - "①", "②", "③" -> Circled numbers (Unicode)
public export
parseProblemNumber : String -> Maybe Nat
-- Implementation in Python:
--   if text.matches("^\d+\."):    # "1.", "2."
--     return int(text[:-1])
--   elif text.matches("^\[\d+\]"): # "[1]", "[2]"
--     return int(text[1:-1])
--   elif is_circled_number(text):  # "①", "②"
--     return circled_to_int(text)

||| Detect if text is a solution marker
|||
||| Recognizes: "[정답]", "[해설]", "정답:", "해설:", etc.
public export
isSolutionMarker : String -> Bool
-- Implementation: check if text contains "정답", "해설", or similar

||| Sort OCR results by reading order (considering page layout)
|||
||| For multi-column layouts:
||| - Sort by column first (left to right)
||| - Then by vertical position within column (top to bottom)
public export
partial
sortByReadingOrder : PageLayout -> List OcrResult -> List OcrResult
-- Implementation in Python: complex sorting logic
-- 1. Determine which column each result belongs to
-- 2. Sort by (column_index, bbox.topLeft.y)

||| Proof that OCR results are sorted by reading order
public export
data OcrInReadOrder : PageLayout -> List OcrResult -> Type where
  OcrOrderNil : OcrInReadOrder layout []
  OcrOrderOne : OcrInReadOrder layout [r]
  OcrOrderCons : (r : OcrResult) ->
                 (rs : List OcrResult) ->
                 (layout : PageLayout) ->
                 -- TODO: add proof that r comes before all rs in reading order
                 OcrInReadOrder layout rs ->
                 OcrInReadOrder layout (r :: rs)

||| Proof that all OCR results have high confidence
public export
data AllHighConfidence : List OcrResult -> Type where
  HighConfNil : AllHighConfidence []
  HighConfCons : (r : OcrResult) ->
                 (rs : List OcrResult) ->
                 (prf : isHighConfidence r.confidence = True) ->
                 AllHighConfidence rs ->
                 AllHighConfidence (r :: rs)

||| Proof that OCR results don't overlap
public export
data OcrResultsNoOverlap : List OcrResult -> Type where
  OcrNoOverlapNil : OcrResultsNoOverlap []
  OcrNoOverlapOne : OcrResultsNoOverlap [r]
  OcrNoOverlapCons : (r : OcrResult) ->
                     (rs : List OcrResult) ->
                     (prf : All (\r2 => overlaps r.bbox r2.bbox = False) rs) ->
                     OcrResultsNoOverlap rs ->
                     OcrResultsNoOverlap (r :: rs)

||| Valid OCR execution result
public export
data ValidOcrExecution : OcrExecution -> Type where
  MkValidOcrExecution : (exec : OcrExecution) ->
                        AllHighConfidence exec.results ->
                        OcrResultsNoOverlap exec.results ->
                        ValidOcrExecution exec
