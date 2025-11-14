||| Complete workflow specification
|||
||| This module ties together all components into a complete
||| workflow for extracting problems from PDFs.
module System.Workflow

import System.Base
import System.PdfMetadata
import System.LayoutDetection
import System.OcrEngine
import System.ProblemExtraction
import System.OutputFormat

%default total

||| State of the extraction workflow
public export
data WorkflowState =
  Initial            -- Starting state
  | MetadataExtracted PdfMeta
  | LayoutDetected PageLayout PdfMeta
  | OcrCompleted (List OcrResult) PageLayout PdfMeta  -- NEW: OCR stage
  | ContentExtracted ExtractionResult PageLayout PdfMeta
  | OutputGenerated OutputPackage
  | Failed String    -- Error state

||| Workflow step
public export
data WorkflowStep =
  ExtractMetadata     -- Step 1: Extract metadata
  | DetectLayout      -- Step 2: Detect column layout
  | RunOCR            -- Step 3: Run OCR on PDF images (NEW!)
  | ExtractProblems   -- Step 4: Extract problems using OCR
  | ExtractSolutions  -- Step 5: Extract solutions using OCR
  | PairProblemsSolutions  -- Step 6: Pair problems with solutions
  | GenerateOutput    -- Step 7: Generate output files

||| Valid state transitions
public export
data ValidTransition : WorkflowState -> WorkflowStep -> WorkflowState -> Type where
  CanExtractMeta : ValidTransition Initial ExtractMetadata (MetadataExtracted meta)
  CanDetectLayout : ValidTransition (MetadataExtracted meta) DetectLayout (LayoutDetected layout meta)
  CanRunOCR : ValidTransition (LayoutDetected layout meta) RunOCR (OcrCompleted ocrResults layout meta)
  CanExtractContent : ValidTransition (OcrCompleted ocrResults layout meta) ExtractProblems (ContentExtracted result layout meta)
  CanGenerateOutput : ValidTransition (ContentExtracted result layout meta) GenerateOutput (OutputGenerated pkg)
  CanFail : ValidTransition state step (Failed msg)

||| Complete workflow execution record
public export
record WorkflowExecution where
  constructor MkWorkflowExecution
  sourcePdf : String
  initialState : WorkflowState
  steps : List WorkflowStep
  finalState : WorkflowState

||| Proof that a workflow execution is valid
public export
data ValidWorkflow : WorkflowExecution -> Type where
  ValidInit : ValidWorkflow (MkWorkflowExecution pdf Initial [] Initial)
  ValidStep : (exec : WorkflowExecution) ->
              (step : WorkflowStep) ->
              (newState : WorkflowState) ->
              ValidTransition exec.finalState step newState ->
              ValidWorkflow exec ->
              ValidWorkflow (MkWorkflowExecution 
                              exec.sourcePdf 
                              exec.initialState 
                              (exec.steps ++ [step]) 
                              newState)

||| Expected workflow steps in order
public export
expectedSteps : List WorkflowStep
expectedSteps = [
  ExtractMetadata,
  DetectLayout,
  RunOCR,              -- NEW: OCR step added
  ExtractProblems,
  ExtractSolutions,
  PairProblemsSolutions,
  GenerateOutput
]

||| Check if workflow is complete (reached output generation)
public export
isComplete : WorkflowState -> Bool
isComplete (OutputGenerated _) = True
isComplete _ = False

||| Check if workflow failed
public export
isFailed : WorkflowState -> Bool
isFailed (Failed _) = True
isFailed _ = False

||| Main workflow function signature
||| This would be implemented in Python, following this specification
public export
data WorkflowResult = Success OutputPackage | Failure String

public export
executePdfExtraction : (pdfPath : String) -> (format : FileFormat) -> WorkflowResult
-- Implementation in Python will follow this specification

