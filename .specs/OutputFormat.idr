||| Output format specification
|||
||| This module defines the output format for extracted problems:
||| - File naming conventions (1_prb, 1_sol)
||| - Output types (image, PDF)
||| - ZIP packaging
module OutputFormat

import Base
import ProblemExtraction
import PdfMetadata
import Data.List.Quantifiers

%default total

||| Output file format
public export
data FileFormat =
  PNG        -- PNG image
  | JPEG     -- JPEG image  
  | PDF      -- PDF document
  | SVG      -- SVG vector

public export
Eq FileFormat where
  PNG == PNG = True
  JPEG == JPEG = True
  PDF == PDF = True
  SVG == SVG = True
  _ == _ = False

||| File extension for each format
public export
formatExtension : FileFormat -> String
formatExtension PNG = "png"
formatExtension JPEG = "jpg"
formatExtension PDF = "pdf"
formatExtension SVG = "svg"

||| Output file type
public export
data OutputType =
  ProblemFile      -- _prb
  | SolutionFile   -- _sol

public export
Eq OutputType where
  ProblemFile == ProblemFile = True
  SolutionFile == SolutionFile = True
  _ == _ = False

||| Output file suffix
public export
typeSuffix : OutputType -> String
typeSuffix ProblemFile = "prb"
typeSuffix SolutionFile = "sol"

||| Generate filename for a problem/solution
||| Format: {number}_{type}.{extension}
||| Example: "1_prb.png", "2_sol.pdf"
public export
generateFilename : ProblemNum -> OutputType -> FileFormat -> String
generateFilename num typ fmt =
  show num ++ "_" ++ typeSuffix typ ++ "." ++ formatExtension fmt

||| Output file specification
public export
record OutputFile where
  constructor MkOutputFile
  number : ProblemNum
  fileType : OutputType
  format : FileFormat
  filename : String
  ||| Source region in original PDF
  sourceRegion : BBox
  sourcePage : Nat

||| Create output file spec for a problem
public export
mkProblemOutput : ProblemItem -> FileFormat -> OutputFile
mkProblemOutput prob fmt = MkOutputFile
  (number prob)
  ProblemFile
  fmt
  (generateFilename (number prob) ProblemFile fmt)
  (region prob)
  (pageNum prob)

||| Create output file spec for a solution
public export
mkSolutionOutput : SolutionItem -> FileFormat -> OutputFile
mkSolutionOutput sol fmt = MkOutputFile
  (number sol)
  SolutionFile
  fmt
  (generateFilename (number sol) SolutionFile fmt)
  (region sol)
  (pageNum sol)

||| Complete output package
public export
record OutputPackage where
  constructor MkOutputPackage
  ||| Source PDF filename
  sourcePdf : String
  ||| Metadata extracted from PDF
  metadata : PdfMeta
  ||| Individual output files
  files : List OutputFile
  ||| ZIP filename for packaging
  zipFilename : String

||| Generate output package from extraction result
public export
mkOutputPackage : String -> PdfMeta -> ExtractionResult -> FileFormat -> OutputPackage
mkOutputPackage sourcePdf meta result fmt =
  let problemFiles = map (\p => mkProblemOutput p fmt) result.problems
      solutionFiles = map (\s => mkSolutionOutput s fmt) result.solutions
      allFiles = problemFiles ++ solutionFiles
      zipName = sourcePdf ++ "_extracted.zip"
  in MkOutputPackage sourcePdf meta allFiles zipName

||| Predicate: filenames are different
public export
DifferentFilenames : OutputFile -> OutputFile -> Type
DifferentFilenames f1 f2 = Not (filename f1 = filename f2)

||| Proof that all output filenames are unique
public export
data UniqueFilenames : List OutputFile -> Type where
  UniqueNil : UniqueFilenames []
  UniqueOne : UniqueFilenames [f]
  UniqueCons : (f : OutputFile) ->
               (fs : List OutputFile) ->
               (prf : All (DifferentFilenames f) fs) ->
               UniqueFilenames fs ->
               UniqueFilenames (f :: fs)

||| Proof that output package is valid
public export
data ValidOutput : OutputPackage -> Type where
  MkValidOutput : (pkg : OutputPackage) ->
                  UniqueFilenames pkg.files ->
                  ValidOutput pkg

||| Proof that all problems have corresponding output files
public export
data CompleteOutput : ExtractionResult -> List OutputFile -> Type where
  MkCompleteOutput : (result : ExtractionResult) ->
                     (files : List OutputFile) ->
                     (probPrf : length result.problems = 
                                length (filter (\f => f.fileType == ProblemFile) files)) ->
                     (solPrf : length result.solutions = 
                               length (filter (\f => f.fileType == SolutionFile) files)) ->
                     CompleteOutput result files

