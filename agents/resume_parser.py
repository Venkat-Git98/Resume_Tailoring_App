import logging
from utils import file_utils, nlp_utils
from models import ResumeSections

class ResumeParserAgent:
    """Agent to parse the resume PDF into structured sections."""
    def run(self, resume_pdf_path: str) -> ResumeSections:
        logging.info("ResumeParserAgent: Parsing resume PDF")
        pdf_text = file_utils.read_pdf_text(resume_pdf_path)
        sections = nlp_utils.split_resume_sections(pdf_text)
        resume = ResumeSections(**sections)
        logging.info(f"ResumeParserAgent: Parsed sections: {list(sections.keys())}")
        return resume 