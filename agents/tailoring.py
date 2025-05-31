
import logging
from typing import Optional, Tuple # Import Tuple for return type hint

from models import JobDescription, ResumeSections
from utils.llm_gemini import GeminiClient, get_section_prompt
import re
class TailoringAgent:
    """
    Agent to rewrite resume sections using an LLM, tailoring them to the Job Description,
    maintaining state of previously tailored sections for context, and utilizing ATS keywords
    and an optional master profile.
    """
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
        self.sections_to_tailor = ['summary', 'work_experience', 'technical_skills', 'projects']

    def _clean_llm_section_output(self, raw_text: str, section_name: str) -> str:
        # ... (your existing _clean_llm_section_output method) ...
        if not raw_text:
            return ""
        text = raw_text.strip()
        # Add cleaning logic here as previously discussed
        if text.startswith("```") and text.endswith("```"): # Basic example
            text = text[3:-3].strip()
            first_line_end = text.find('\n')
            if first_line_end != -1:
                first_line = text[:first_line_end].strip()
                if len(first_line) < 15 and not any(c.isalnum() for c in first_line if c not in ['_', '-']):
                    text = text[first_line_end+1:].strip()
            elif len(text) < 15 and not any(c.isalnum() for c in text if c not in ['_', '-']):
                 text = ""
        if section_name == 'summary':
            patterns = [r"^\s*Summary\s*:\s*", r"^\s*Professional Summary\s*:\s*", r"^\s*Responsibilities\s*:\s*"]
            for p in patterns:
                text = re.sub(p, "", text, flags=re.IGNORECASE).strip()
        # ... etc. for other sections
        return text


    def _format_section_for_accumulation(self, section_name: str, content: str) -> str:
        return f"## {section_name.upper().replace('_', ' ')}\n{content.strip()}"

    def run(self, 
            job_desc: JobDescription, 
            resume: ResumeSections, 
            master_profile_text: Optional[str] = None
           ) -> Tuple[ResumeSections, str]: # MODIFIED return type
        
        logging.info("TailoringAgent: Starting stateful resume section tailoring with LLM" + 
                     (", using master profile." if master_profile_text else ".")) # Updated log
        
        tailored_sections_dict = {}
        accumulated_tailored_text = "" 

        for section_name in self.sections_to_tailor:
            original_content = getattr(resume, section_name, None)
            current_section_output_for_accumulation = ""

            if original_content and original_content.strip():
                logging.info(f"Attempting to tailor section: '{section_name}'")
                
                current_ats_keywords = job_desc.ats_keywords if job_desc.ats_keywords is not None else []
                current_requirements = job_desc.requirements if job_desc.requirements is not None else []

                prompt = get_section_prompt(
                    section=section_name,
                    original=original_content,
                    job_title=job_desc.job_title or "the specified position",
                    requirements=current_requirements,
                    ats_keywords=current_ats_keywords,
                    master_profile_text=master_profile_text,
                    previously_tailored_sections_text=accumulated_tailored_text
                )
                
                max_tokens_for_section = 1024 
                if section_name == 'summary': max_tokens_for_section = 450 
                elif section_name == 'technical_skills': max_tokens_for_section = 600
                elif section_name == 'work_experience': max_tokens_for_section = 1500
                elif section_name == 'projects': max_tokens_for_section = 1200

                raw_llm_output = ""
                try:
                    raw_llm_output = self.llm.generate_text(
                        prompt, 
                        temperature=0.15, 
                        max_tokens=max_tokens_for_section
                    )
                except Exception as e:
                    logging.error(f"LLM call failed for section '{section_name}': {e}", exc_info=True)
                    raw_llm_output = original_content or "" 
                    logging.warning(f"Using original content for section '{section_name}' due to LLM error.")
                
                cleaned_content_for_section = self._clean_llm_section_output(raw_llm_output, section_name)
                
                tailored_sections_dict[section_name] = cleaned_content_for_section
                current_section_output_for_accumulation = cleaned_content_for_section
                logging.info(f"Successfully tailored and cleaned section: '{section_name}'.")
            else:
                tailored_sections_dict[section_name] = original_content or ''
                current_section_output_for_accumulation = original_content or f"(No content provided for {section_name})"
                logging.info(f"Section '{section_name}' has no original content; skipping LLM tailoring.")
            
            if current_section_output_for_accumulation or section_name in self.sections_to_tailor:
                accumulated_tailored_text += ("\n\n" if accumulated_tailored_text else "") + \
                                             self._format_section_for_accumulation(section_name, current_section_output_for_accumulation)

        logging.info("TailoringAgent: All resume sections processed.")
        
        return ResumeSections(**tailored_sections_dict), accumulated_tailored_text.strip()
