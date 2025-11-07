||| PDF metadata extraction types
|||
||| This module defines types for extracting and representing
||| metadata from exam PDFs (subject, school, exam type, etc.)
module System.PdfMetadata

import System.Base

%default total

||| Subject area (e.g., Math, Science, etc.)
public export
data Subject = 
  Math 
  | Science 
  | Korean 
  | English 
  | SocialStudies
  | OtherSubject String

public export
Eq Subject where
  Math == Math = True
  Science == Science = True
  Korean == Korean = True
  English == English = True
  SocialStudies == SocialStudies = True
  OtherSubject s1 == OtherSubject s2 = s1 == s2
  _ == _ = False

||| School name
public export
School : Type
School = String

||| Exam type
public export
data ExamType =
  Midterm        -- 중간고사
  | Final        -- 기말고사
  | Monthly      -- 월말평가
  | Mock         -- 모의고사
  | Practice     -- 연습문제
  | OtherExam String

public export
Eq ExamType where
  Midterm == Midterm = True
  Final == Final = True
  Monthly == Monthly = True
  Mock == Mock = True
  Practice == Practice = True
  OtherExam s1 == OtherExam s2 = s1 == s2
  _ == _ = False

||| Grade level (e.g., 고3)
public export
data GradeLevel =
  Elementary Nat  -- 초등 1-6
  | Middle Nat    -- 중 1-3
  | High Nat      -- 고 1-3

public export
Eq GradeLevel where
  Elementary n1 == Elementary n2 = n1 == n2
  Middle n1 == Middle n2 = n1 == n2
  High n1 == High n2 = n1 == n2
  _ == _ = False

||| Complete metadata for an exam PDF
public export
record PdfMeta where
  constructor MkPdfMeta
  subject : Subject
  school : Maybe School
  examType : ExamType
  gradeLevel : Maybe GradeLevel
  year : Maybe Nat
  semester : Maybe Nat  -- 1 or 2
  ||| Region in PDF where metadata was found
  metadataRegion : Maybe BBox

||| Initial empty metadata
public export
emptyMeta : PdfMeta
emptyMeta = MkPdfMeta 
  (OtherSubject "Unknown")
  Nothing
  (OtherExam "Unknown")
  Nothing
  Nothing
  Nothing
  Nothing

||| Update metadata with newly found information
public export
updateMeta : PdfMeta -> PdfMeta -> PdfMeta
updateMeta old new = MkPdfMeta
  (case new.subject of
     OtherSubject "Unknown" => old.subject
     s => s)
  (new.school <|> old.school)
  (case new.examType of
     OtherExam "Unknown" => old.examType
     e => e)
  (new.gradeLevel <|> old.gradeLevel)
  (new.year <|> old.year)
  (new.semester <|> old.semester)
  (new.metadataRegion <|> old.metadataRegion)

