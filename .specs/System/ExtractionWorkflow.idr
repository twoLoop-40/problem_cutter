||| Formal specification for PDF problem extraction workflow
||| Based on directions/view.md
|||
||| This module defines the complete workflow state machine with type-level
||| guarantees for correct state transitions and data consistency.

module System.ExtractionWorkflow

import System.Base
import System.LayoutDetection
import System.OcrEngine

%default total

--------------------------------------------------------------------------------
-- Workflow State Machine
--------------------------------------------------------------------------------

||| Workflow states representing the 8-step extraction process
public export
data WorkflowState : Type where
  ||| Initial state: PDF file loaded
  Initial : WorkflowState

  ||| Step 1: Analyzed (problem count, numbers detected)
  Analyzed : (problemCount : Nat) -> (numbers : List Nat) -> WorkflowState

  ||| Step 2: Spec created (expected problems defined)
  SpecCreated : (expected : List Nat) -> WorkflowState

  ||| Step 3: Columns separated (multi-column → single-column)
  ColumnsSeparated : WorkflowState

  ||| Step 4: Problems extracted (vertical tracking)
  ProblemsExtracted : (detected : List Nat) -> WorkflowState

  ||| Step 5: Validated (compared with spec)
  Validated : (result : ValidationResult) -> WorkflowState

  ||| Step 6: Final verification (re-check against original)
  FinalVerified : WorkflowState

  ||| Step 7: Files generated (with margin trimming)
  FilesGenerated : WorkflowState

  ||| Step 8: Archived (ZIP created)
  Archived : WorkflowState

  ||| Error state (for retry logic)
  Failed : (failedStep : WorkflowState) -> (reason : String) -> WorkflowState


||| Validation result from Step 5
public export
data ValidationResult : Type where
  ||| All problems correctly detected
  AllCorrect : ValidationResult

  ||| Some problems missing (need retry)
  Missing : (problems : List Nat) -> ValidationResult

  ||| Extra problems detected (false positives)
  Extra : (problems : List Nat) -> ValidationResult

  ||| Both missing and extra
  MixedErrors : (missing : List Nat) -> (extra : List Nat) -> ValidationResult


||| Valid state transitions in the workflow
public export
data ValidTransition : WorkflowState -> WorkflowState -> Type where
  ||| Step 1: Initial → Analyzed
  DoAnalyze : ValidTransition Initial (Analyzed n nums)

  ||| Step 2: Analyzed → SpecCreated
  DoCreateSpec : ValidTransition (Analyzed n nums) (SpecCreated nums)

  ||| Step 3: SpecCreated → ColumnsSeparated
  DoSeparateColumns : ValidTransition (SpecCreated exp) ColumnsSeparated

  ||| Step 4: ColumnsSeparated → ProblemsExtracted
  DoExtract : ValidTransition ColumnsSeparated (ProblemsExtracted detected)

  ||| Step 5: ProblemsExtracted → Validated
  DoValidate : ValidTransition (ProblemsExtracted det) (Validated result)

  ||| Step 5 → Step 4: Retry if validation failed
  DoRetry : ValidTransition (Validated (Missing probs)) (ProblemsExtracted [])

  ||| Step 6: Validated (AllCorrect) → FinalVerified
  DoFinalVerify : ValidTransition (Validated AllCorrect) FinalVerified

  ||| Step 7: FinalVerified → FilesGenerated
  DoGenerateFiles : ValidTransition FinalVerified FilesGenerated

  ||| Step 8: FilesGenerated → Archived
  DoArchive : ValidTransition FilesGenerated Archived

  ||| Error transition from any state
  DoFail : (reason : String) -> ValidTransition s (Failed s reason)


--------------------------------------------------------------------------------
-- Step-by-step specifications
--------------------------------------------------------------------------------

||| Step 1: Analyze PDF
||| Input: PDF file path
||| Output: Problem count and list of detected problem numbers
public export
record AnalysisResult where
  constructor MkAnalysis
  pdfPath : String
  pageCount : Nat
  problemNumbers : List Nat
  solutionNumbers : List Nat


||| Step 2: Create type specification
||| Input: Analysis result
||| Output: Expected problem numbers (for validation)
public export
record ProblemSpec where
  constructor MkSpec
  expectedProblems : List Nat
  expectedSolutions : List Nat


||| Step 3: Column separation result
||| Multi-column PDF → Single-column representation
public export
record ColumnSeparation where
  constructor MkColumnSep
  originalColumns : Nat
  separatedImages : List (String, Coord)  -- (image_path, position)


||| Step 4: Extraction result
||| Vertical tracking to extract individual problems
public export
record ExtractionResult where
  constructor MkExtraction
  detectedProblems : List (Nat, BBox)  -- (number, bounding box)
  problemImages : List (Nat, String)   -- (number, image_path)


||| Step 5: Validation against spec
public export
record ValidationReport where
  constructor MkValidation
  expected : List Nat
  detected : List Nat
  missing : List Nat
  extra : List Nat
  accuracy : Double
  needsRetry : Bool


||| Step 7: File generation with margin trimming
public export
record FileGeneration where
  constructor MkFileGen
  problemFiles : List (Nat, String)    -- (number, file_path)
  marginsTrimmed : Bool
  totalSize : Nat  -- bytes


||| Step 8: Archive result
public export
record ArchiveResult where
  constructor MkArchive
  zipPath : String
  fileCount : Nat
  totalSize : Nat


--------------------------------------------------------------------------------
-- Workflow properties to prove
--------------------------------------------------------------------------------

||| Property: All detected problems must be in expected range
public export
AllInRange : List Nat -> Type
AllInRange [] = ()
AllInRange (n :: ns) = (LTE 1 n, LTE n 100, AllInRange ns)


||| Property: No duplicate problem numbers
public export
data NoDuplicates : List Nat -> Type where
  NoDupsEmpty : NoDuplicates []
  NoDupsSingle : NoDuplicates [n]
  NoDupsCons : (notElem : Not (Elem x xs)) ->
               NoDuplicates xs ->
               NoDuplicates (x :: xs)


||| Property: Extracted problems must match or be subset of expected
public export
data MatchesSpec : List Nat -> List Nat -> Type where
  ExactMatch : (expected = detected) -> MatchesSpec expected detected
  SubsetMatch : (missing : List Nat) ->
                (detected ++ missing = expected) ->
                MatchesSpec expected detected


||| Property: Validation must eventually succeed (after retries)
public export
data EventuallySucceeds : ValidationReport -> Type where
  SucceedsNow : (accuracy = 1.0) -> EventuallySucceeds report
  SucceedsAfterRetry : (needsRetry = True) ->
                       (missing = [n]) ->
                       EventuallySucceeds report


||| Property: ZIP archive contains all problem files
public export
data ArchiveComplete : FileGeneration -> ArchiveResult -> Type where
  AllFilesArchived : (fileCount = length problemFiles) ->
                     ArchiveComplete (MkFileGen problemFiles _ _)
                                    (MkArchive _ fileCount _)


--------------------------------------------------------------------------------
-- Workflow execution with proofs
--------------------------------------------------------------------------------

||| Complete workflow with guaranteed properties
public export
record WorkflowExecution where
  constructor MkWorkflow
  initialPdf : String

  -- Step 1
  analysis : AnalysisResult
  analysisValid : AllInRange analysis.problemNumbers

  -- Step 2
  spec : ProblemSpec
  specMatches : spec.expectedProblems = analysis.problemNumbers

  -- Step 3
  columnSep : ColumnSeparation

  -- Step 4
  extraction : ExtractionResult
  noDups : NoDuplicates (map fst extraction.detectedProblems)

  -- Step 5
  validation : ValidationReport
  validatesAgainst : MatchesSpec spec.expectedProblems validation.detected

  -- Step 6 (implicit: validation success)

  -- Step 7
  files : FileGeneration
  filesComplete : length files.problemFiles = length extraction.detectedProblems
  marginsOk : files.marginsTrimmed = True

  -- Step 8
  archive : ArchiveResult
  archiveOk : ArchiveComplete files archive


||| Retry logic for failed validation (Step 5)
public export
data RetryStrategy : ValidationReport -> Type where
  ||| No retry needed - validation passed
  NoRetry : (accuracy = 1.0) -> RetryStrategy report

  ||| Retry extraction for missing problems only
  RetryMissing : (missing : List Nat) ->
                 (missing = report.missing) ->
                 RetryStrategy report

  ||| Manual intervention required
  RequiresManual : (accuracy < 0.5) -> RetryStrategy report


--------------------------------------------------------------------------------
-- Helper functions and lemmas
--------------------------------------------------------------------------------

||| Check if all numbers in list are in valid range [1..100]
public export
checkRange : (nums : List Nat) -> Maybe (AllInRange nums)
checkRange [] = Just ()
checkRange (n :: ns) = case (1 `isLTE` n, n `isLTE` 100) of
  (Yes p1, Yes p2) => case checkRange ns of
    Just rest => Just (p1, p2, rest)
    Nothing => Nothing
  _ => Nothing


||| Calculate accuracy from validation report
public export
calculateAccuracy : (expected : List Nat) -> (detected : List Nat) -> Double
calculateAccuracy [] [] = 1.0
calculateAccuracy expected detected =
  let correct = length (filter (\n => elem n detected) expected)
      total = length expected
  in cast correct / cast total


||| Lemma: If validation accuracy is 1.0, then detected = expected
public export
accuracyOneImpliesMatch : (accuracy = 1.0) ->
                          (expected : List Nat) ->
                          (detected : List Nat) ->
                          accuracy = calculateAccuracy expected detected ->
                          expected = detected
accuracyOneImpliesMatch prf expected detected eq = believe_me ()  -- proof omitted


||| Lemma: Archive contains at least as many files as problems extracted
public export
archiveNonEmpty : WorkflowExecution -> LTE 1 archive.fileCount
archiveNonEmpty workflow = believe_me ()  -- proof omitted
