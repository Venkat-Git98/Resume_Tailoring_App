# Resume_Tailoring/agents/cover_letter_agent.py
import logging
from typing import Dict, List, Optional
import re # For parsing project titles from tailored_projects_text

from models import JobDescription, ResumeSections
from utils.llm_gemini import GeminiClient, get_cover_letter_prompt

class CoverLetterAgent:
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
        # You might want to pass project_hyperlinks from config or main.py if it's dynamic
        # For now, let's define a similar structure here or assume it's passed.
        # This should ideally come from a shared configuration or be passed in.
        self.project_hyperlinks_config = { # Example structure
            "Intelligent Building Code QA": "https://virginia-building-codes.streamlit.app/",
            # "AI-Text Discriminator": f"{github_base_url}/AI-Content-Filter" # Needs github_base_url
        }


    def _get_project_details_for_cl(self, tailored_projects_text: Optional[str], github_base_url: Optional[str]) -> List[Dict[str, str]]:
        project_details = []
        if not tailored_projects_text:
            return project_details

        # This parsing needs to be robust, similar to add_projects_docx,
        # to extract project titles correctly.
        # Assuming tailored_projects_text has titles and then bullets.
        # A simple split by double newline might separate projects.
        raw_project_entries = re.split(r'\n\s*\n+(?=\s*(?:(?:##|###)\s+)?\s*(?:\*\*)?\s*[A-Z0-9])', tailored_projects_text)

        temp_hyperlinks = self.project_hyperlinks_config.copy()
        if github_base_url: # Add dynamic GitHub links if base URL is known
            temp_hyperlinks["AI-Text Discriminator"] = f"{github_base_url}/AI-Content-Filter" # Example

        for entry_text in raw_project_entries:
            entry_text = entry_text.strip()
            if not entry_text:
                continue
            
            lines = [line.strip() for line in entry_text.split('\n') if line.strip()]
            if not lines:
                continue

            title_line_from_llm = lines[0]
            cleaned_project_title = re.sub(r"^\s*#+\s*", "", title_line_from_llm).strip()
            title_parts = cleaned_project_title.split('|', 1)
            project_name = title_parts[0].replace("**", "").strip()

            if project_name:
                details = {"title": project_name}
                if project_name in temp_hyperlinks:
                    details["url"] = temp_hyperlinks[project_name]
                project_details.append(details)
        
        return project_details


    def run(self, 
            job_desc: JobDescription, 
            tailored_resume: ResumeSections, 
            contact_info: Dict[str, str], 
            master_profile_text: Optional[str] = None,
            company_name_override: Optional[str] = None
           ) -> Optional[str]:
        # ... (candidate_name, job_title_str, company_name derivation as before) ...
        logging.info("CoverLetterAgent: Starting cover letter generation.")

        if not all([job_desc, tailored_resume, contact_info]):
            logging.error("CoverLetterAgent: Missing critical data. Cannot generate cover letter.")
            return None

        candidate_name = contact_info.get("name", "The Candidate")
        
        job_title_str = job_desc.job_title or "the advertised position"
        company_name = company_name_override 
        if not company_name:
            if " at " in job_title_str.lower():
                parts = job_title_str.lower().split(" at ")
                if len(parts) > 1: company_name = parts[-1].strip().title()
            elif " - " in job_title_str: 
                parts = job_title_str.split(" - ")
                if len(parts) > 1: company_name = parts[-1].strip().title()
        if not company_name:
            company_name = "the Hiring Company"; logging.warning(f"Using fallback company name: '{company_name}'")
        
        job_req_summary = ""
        if job_desc.requirements:
            summary_lines = [f"- {req}" for req in job_desc.requirements[:5]]
            job_req_summary = "\n".join(summary_lines)
            if len(job_desc.requirements) > 5: job_req_summary += "\n- ... and other key qualifications."
        else: job_req_summary = "Not specified."

        ats_keywords_string = ", ".join(job_desc.ats_keywords) if job_desc.ats_keywords else "Not specifically extracted."

        # Get project details with URLs
        project_details_for_cl = self._get_project_details_for_cl(
            tailored_resume.projects,
            contact_info.get("github_url") # Pass base GitHub URL if available in contact_info
        )

        try:
            prompt = get_cover_letter_prompt(
                candidate_name=candidate_name,
                candidate_contact_info=contact_info, 
                job_title=job_title_str,
                company_name=company_name, 
                job_requirements_summary=job_req_summary,
                ats_keywords_str=ats_keywords_string,   
                tailored_resume_summary_text=tailored_resume.summary,
                tailored_work_experience_text=tailored_resume.work_experience, 
                tailored_projects_text=tailored_resume.projects,             
                master_profile_text=master_profile_text,
                project_details_for_cl=project_details_for_cl, # NEW
                hiring_manager_name=None 
            )

            cover_letter_text = self.llm.generate_text(prompt, temperature=0.35, max_tokens=1500) # Slightly higher temp for CL
            
            cleaned_cover_letter = cover_letter_text.strip()
            if cleaned_cover_letter.lower().startswith("cover letter:"):
                cleaned_cover_letter = cleaned_cover_letter[len("cover letter:"):].strip()
            # Further cleanup: remove any "--- BEGIN COVER LETTER ---" if LLM includes it
            if "--- BEGIN COVER LETTER ---" in cleaned_cover_letter:
                cleaned_cover_letter = cleaned_cover_letter.split("--- BEGIN COVER LETTER ---", 1)[-1].strip()
            
            logging.info("CoverLetterAgent: Successfully generated cover letter.")
            return cleaned_cover_letter

        except Exception as e:
            logging.error(f"CoverLetterAgent: Failed to generate cover letter via LLM: {e}", exc_info=True)
            return None