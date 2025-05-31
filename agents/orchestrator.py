# Resume_Tailoring/agents/orchestrator.py
import logging
from typing import Optional, Dict, Tuple

# Project-internal imports
from utils.llm_gemini import GeminiClient
from models import TailoringState, ResumeSections, JobDescription, ResumeCritique
from .jd_analysis import JDAnalysisAgent # Relative import within 'agents' package
from .resume_parser import ResumeParserAgent # Relative import within 'agents' package
from .resume_judge_agent import ResumeJudgeAgent # Relative import within 'agents' package
from .tailoring import TailoringAgent # Relative import within 'agents' package
from .cover_letter_agent import CoverLetterAgent # Relative import within 'agents' package

class OrchestratorAgent:
    def __init__(self, llm_client: GeminiClient):
        self.jd_agent = JDAnalysisAgent(llm_client=llm_client)
        self.resume_agent = ResumeParserAgent()
        self.tailoring_agent = TailoringAgent(llm_client=llm_client)
        self.cover_letter_agent = CoverLetterAgent(llm_client=llm_client)
        self.resume_judge_agent = ResumeJudgeAgent(llm_client=llm_client)

    # *** MODIFIED run method signature and call to jd_agent.run ***
    def run(self,
            resume_pdf_path: str,
            contact_info_for_cl: Dict[str, str], # For Cover Letter and Judge Agent
            jd_txt_path: Optional[str] = None,   # Path to JD file (optional)
            jd_text: Optional[str] = None,       # Raw JD text (optional)
            master_profile_text: Optional[str] = None,
            company_name_for_cl: Optional[str] = None  # Explicit company name for CL
           ) -> TailoringState:

        logging.info("OrchestratorAgent: Starting full tailoring pipeline...")
        state = TailoringState()

        # Input validation for job description
        if not jd_text and not jd_txt_path:
            logging.error("OrchestratorAgent: Critical - Job description input missing. Both jd_text and jd_txt_path are None.")
            # Create a JobDescription object indicating the error
            state.job_description = JobDescription(job_title="Error: No JD Input", requirements=["No job description was provided to the orchestrator."], ats_keywords=[])
            # You might want to return early or handle this state appropriately downstream
            # For now, we'll let it proceed, but JD-dependent steps will be skipped.
            # return state # Option to abort early
        else:
            logging.info("OrchestratorAgent: Analyzing job description...")
            # DEBUG: Log what we're passing to JDAnalysisAgent
            logging.info(f"ORCHESTRATOR DEBUG: jd_txt_path: {repr(jd_txt_path)}")
            logging.info(f"ORCHESTRATOR DEBUG: jd_text type: {type(jd_text)}")
            if jd_text:
                logging.info(f"ORCHESTRATOR DEBUG: jd_text length: {len(jd_text)}")
                logging.info(f"ORCHESTRATOR DEBUG: jd_text first 200 chars: {repr(jd_text[:200])}")
            else:
                logging.warning(f"ORCHESTRATOR DEBUG: jd_text is None or empty: {repr(jd_text)}")
            
            # Pass both jd_txt_path and jd_text to jd_agent.run()
            # JDAnalysisAgent.run() will prioritize jd_text if available.
            job_description_obj = self.jd_agent.run(
                jd_txt_path=jd_txt_path,
                jd_text=jd_text
            )
            if not isinstance(job_description_obj, JobDescription):
                logging.error(f"JDAnalysisAgent did not return a JobDescription object. Got: {type(job_description_obj)}. Aborting further JD-dependent steps.")
                # Ensure state.job_description is at least an empty JobDescription or error state
                state.job_description = JobDescription(job_title="Error: JD Analysis Failed", requirements=[], ats_keywords=[])
            else:
                state.job_description = job_description_obj
                logging.info(f"Job description analyzed. Title: '{state.job_description.job_title}', ATS Keywords count: {len(state.job_description.ats_keywords)}")

        # Proceed only if JD analysis was somewhat successful (or handle error state)
        if not state.job_description or "Error:" in (state.job_description.job_title or ""):
             logging.warning("OrchestratorAgent: Skipping further processing due to JD analysis failure or missing JD.")
             return state # Return the state with the error

        # 2. Parse Resume
        logging.info("OrchestratorAgent: Parsing resume...")
        try:
            original_resume_obj = self.resume_agent.run(resume_pdf_path)
            if not isinstance(original_resume_obj, ResumeSections):
                logging.error(f"ResumeParserAgent did not return a ResumeSections object. Got: {type(original_resume_obj)}. Aborting.")
                return state # Or handle more gracefully
            state.original_resume = original_resume_obj
            logging.info("Resume parsed successfully.")
        except Exception as e_resume_parse:
            logging.error(f"Error during resume parsing: {e_resume_parse}", exc_info=True)
            return state # Abort

        # 3. Tailor Resume Sections
        logging.info("OrchestratorAgent: Tailoring resume sections...")
        if state.job_description and state.original_resume:
            try:
                tailored_resume_object, final_accumulated_text = self.tailoring_agent.run(
                    state.job_description,
                    state.original_resume,
                    master_profile_text=master_profile_text
                )
                state.tailored_resume = tailored_resume_object
                state.accumulated_tailored_text = final_accumulated_text
                logging.info("Resume sections tailored successfully.")
            except Exception as e_tailor:
                logging.error(f"Error during resume tailoring: {e_tailor}", exc_info=True)
                state.tailored_resume = state.original_resume # Fallback to original if tailoring errors out
                state.accumulated_tailored_text = "Error during tailoring. Using original resume sections."
        else:
            logging.warning("Skipping resume tailoring: Missing job description or original resume object.")
            state.tailored_resume = ResumeSections()
            state.accumulated_tailored_text = ""

        # 4. Generate Cover Letter
        if state.job_description and state.tailored_resume and \
           (state.tailored_resume.summary or state.tailored_resume.work_experience or state.tailored_resume.projects):
            logging.info("OrchestratorAgent: Generating cover letter...")
            try:
                state.generated_cover_letter_text = self.cover_letter_agent.run(
                    job_desc=state.job_description,
                    tailored_resume=state.tailored_resume,
                    contact_info=contact_info_for_cl,
                    master_profile_text=master_profile_text,
                    company_name_override=company_name_for_cl
                )
                if state.generated_cover_letter_text:
                    logging.info("Cover letter generated successfully.")
                else:
                    logging.warning("Cover letter generation returned empty or failed.")
            except Exception as e_cl:
                logging.error(f"Error during cover letter generation: {e_cl}", exc_info=True)
                state.generated_cover_letter_text = "Error generating cover letter."
        else:
            logging.warning("Skipping cover letter generation: Missing JD, or tailored resume is empty.")

        # 5. Critique Tailored Resume
        if state.job_description and state.tailored_resume and \
           (state.tailored_resume.summary or state.tailored_resume.work_experience or state.tailored_resume.projects):
            logging.info("OrchestratorAgent: Critiquing tailored resume...")
            try:
                raw_critique, parsed_critique_obj = self.resume_judge_agent.run(
                    job_desc=state.job_description,
                    tailored_resume=state.tailored_resume,
                    candidate_name=contact_info_for_cl.get("name")
                )
                state.raw_critique_text = raw_critique
                state.resume_critique = parsed_critique_obj
                if state.resume_critique and state.resume_critique.ats_score is not None:
                    logging.info(f"Resume critique complete. ATS Score: {state.resume_critique.ats_score:.1f}%")
                elif raw_critique:
                     logging.warning("Resume critique text generated, but parsing into structured object failed or was incomplete.")
                else:
                    logging.warning("Resume critique generation returned no text.")
            except Exception as e_judge:
                logging.error(f"Error during resume critique: {e_judge}", exc_info=True)
                state.raw_critique_text = "Error generating resume critique."
        else:
            logging.warning("Skipping resume critique: Missing JD, or tailored resume is empty.")

        logging.info("OrchestratorAgent: Full pipeline process completed.")
        return state