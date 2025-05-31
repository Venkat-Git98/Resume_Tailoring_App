from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class JobDescription(BaseModel):
    # job_title: Optional[str] = Field(None, description="Title of the job role")
    # requirements: List[str] = Field(..., description="List of key requirements or responsibilities from the JD")
    job_title: Optional[str] = Field(None, description="Title of the job role")
    requirements: List[str] = Field(..., description="List of key requirements or responsibilities from the JD")
    ats_keywords: List[str] = Field(default_factory=list, description="Specific ATS keywords extracted from the JD") # NEW FIELD
class ResumeSections(BaseModel):
    summary: Optional[str] = None
    work_experience: Optional[str] = None
    technical_skills: Optional[str] = None
    projects: Optional[str] = None

# In models.py
class ResumeCritique(BaseModel):
    ats_score: Optional[float] = Field(None, description="ATS-like score (0-100%)")
    ats_pass_assessment: Optional[str] = Field(None, description="Brief assessment of ATS pass likelihood")
    recruiter_impression_assessment: Optional[str] = Field(None, description="Brief assessment of recruiter impression")
    potential_length_concern: Optional[str] = Field(None, description="Assessment of text volume regarding one-page target")
    content_structure_and_clarity: Optional[str] = Field(None, description="Notes on content organization, clarity, and awkward phrasing")
    formatting_consistency_from_text: Optional[str] = Field(None, description="Observations on textual consistency implying formatting discipline")
class TailoringState(BaseModel):
    job_description: Optional[JobDescription] = None
    original_resume: Optional[ResumeSections] = None
    tailored_resume: Optional[ResumeSections] = None 
    accumulated_tailored_text: str = ""
    generated_cover_letter_text: Optional[str] = None
    resume_critique: Optional[ResumeCritique] = None # Uses the updated ResumeCritique
    raw_critique_text: Optional[str] = None 

# UPDATED/SIMPLIFIED ResumeCritique Model
