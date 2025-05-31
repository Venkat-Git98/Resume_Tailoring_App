# Resume_Tailoring/agents/resume_judge_agent.py
import logging
import re
from typing import List, Optional, Tuple # Added Tuple

from models import JobDescription, ResumeSections, ResumeCritique
from utils.llm_gemini import GeminiClient, get_resume_critique_prompt

class ResumeJudgeAgent:
    """Agent to critique a tailored resume against a job description using an LLM."""
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client

    def _parse_critique_text(self, critique_text: str) -> ResumeCritique:
        """
        Parses the structured text output from the LLM judge into the simplified ResumeCritique object.
        Expects format:
        ATS_SCORE: [score]
        ATS_PASS: [assessment]
        RECRUITER_IMPRESSION: [assessment]
        """
        critique = ResumeCritique()
        lines = critique_text.strip().split('\n')
        data = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip().upper()] = value.strip() # Store keys in uppercase for consistent access

        try:
            score_str = data.get("ATS_SCORE")
            if score_str:
                # Extract just the number, removing any '%' or other trailing characters if LLM adds them
                score_match = re.search(r"([\d.]+)", score_str)
                if score_match:
                    critique.ats_score = float(score_match.group(1))
                else:
                    logging.warning(f"Could not parse ATS_SCORE value: {score_str}")
        except (ValueError, TypeError) as e:
            logging.warning(f"Error converting ATS_SCORE '{data.get('ATS_SCORE')}' to float: {e}")

        critique.ats_pass_assessment = data.get("ATS_PASS")
        critique.recruiter_impression_assessment = data.get("RECRUITER_IMPRESSION")

        if not critique.ats_score and not critique.ats_pass_assessment and not critique.recruiter_impression_assessment:
            logging.warning(f"Could not parse any structured data from critique text. Raw text: {critique_text[:200]}...")
            # Optionally, store the raw text in one of the fields if all parsing fails,
            # or rely on raw_critique_text being stored in TailoringState separately.

        return critique

    def run(self, 
            job_desc: JobDescription,
            tailored_resume: ResumeSections,
            candidate_name: Optional[str] = "The Candidate"
           ) -> Tuple[Optional[str], Optional[ResumeCritique]]:
        logging.info("ResumeJudgeAgent: Starting simplified resume critique.")

        if not all([job_desc, tailored_resume]):
            logging.error("ResumeJudgeAgent: Missing job_description or tailored_resume. Cannot generate critique.")
            return None, None

        resume_parts = [
            f"## SUMMARY\n{tailored_resume.summary}" if tailored_resume.summary else "",
            f"## WORK EXPERIENCE\n{tailored_resume.work_experience}" if tailored_resume.work_experience else "",
            f"## TECHNICAL SKILLS\n{tailored_resume.technical_skills}" if tailored_resume.technical_skills else "",
            f"## PROJECTS\n{tailored_resume.projects}" if tailored_resume.projects else ""
        ]
        tailored_resume_text = "\n\n".join(filter(None, resume_parts)).strip()
        job_description_text = "\n".join(job_desc.requirements) if job_desc.requirements else "Job description details not available."

        if not tailored_resume_text:
            logging.warning("ResumeJudgeAgent: Tailored resume text is empty. Cannot generate critique.")
            return None, None
        
        raw_critique_text_output = None # To store raw output even if parsing fails later

        try:
            prompt = get_resume_critique_prompt(
                job_title=job_desc.job_title or "Not specified",
                job_description_text=job_description_text,
                ats_keywords=job_desc.ats_keywords or [],
                tailored_resume_text=tailored_resume_text,
                candidate_name=candidate_name
            )

            raw_critique_text_output = self.llm.generate_text(prompt, temperature=0.1, max_tokens=300) # Reduced max_tokens for concise output
            
            # --- ADDED DEBUG LOGGING --- 
            logging.info(f"ResumeJudgeAgent DEBUG: Raw LLM output for critique:\n---\n{raw_critique_text_output}\n---")
            # --- END ADDED DEBUG LOGGING ---

            cleaned_critique_text = raw_critique_text_output.strip()
            
            parsed_critique = self._parse_critique_text(cleaned_critique_text)

            logging.info(f"ResumeJudgeAgent: Successfully generated and parsed resume critique. ATS Score: {parsed_critique.ats_score}")
            return cleaned_critique_text, parsed_critique

        except Exception as e:
            logging.error(f"ResumeJudgeAgent: Failed to generate or parse critique: {e}", exc_info=True)
            # Return raw text if it was fetched before an error in parsing
            return raw_critique_text_output, None