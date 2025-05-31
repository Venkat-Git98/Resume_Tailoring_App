# Resume_Tailoring/main.py
import sys
import argparse
import logging
import os
import json # Kept for --savejson functionality

# --- Agent and Model Imports ---
from agents.orchestrator import OrchestratorAgent
from utils.llm_gemini import GeminiClient
from models import ResumeSections # For type hinting and checking
from src.docx_to_pdf_generator import generate_cover_letter_pdf # NEW IMPORT
# --- PDF Generation Imports ---
try:
    from src.docx_to_pdf_generator import generate_styled_resume_pdf
    PDF_GENERATOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"src.docx_to_pdf_generator not found or error importing: {e}. PDF generation will be skipped.")
    generate_styled_resume_pdf = None # type: ignore
    PDF_GENERATOR_AVAILABLE = False

# --- Configuration Import ---
# Attempt to load paths and constants from config.py
CONFIG_LOADED = False
try:
    import config
    DEFAULT_RESUME_PATH = getattr(config, 'DEFAULT_BASE_RESUME_PDF_PATH', 'data/Shanmugam_AI_2025_4_YOE.pdf')
    DEFAULT_JOB_PATH = getattr(config, 'DEFAULT_JOB_DESC_PATH', 'data/job.txt')
    DEFAULT_PDF_OUTPUT_DIR = os.path.dirname(getattr(config, 'DEFAULT_TAILORED_PDF_PATH', 'data/Venkatesh_Shanmugam_Tailored_Resume.pdf'))
    DEFAULT_MASTER_PROFILE_PATH = getattr(config, "DEFAULT_MASTER_PROFILE_PATH", None)
    
    # For PDF Filename generation
    DEFAULT_TARGET_COMPANY = getattr(config, "DEFAULT_TARGET_COMPANY", "TargetCompany")
    DEFAULT_YOE = getattr(config, "DEFAULT_YOE", 4)
    DEFAULT_FILENAME_KEYWORD = getattr(config, "DEFAULT_FILENAME_KEYWORD", "AI")

    # For predefined contact/education if not parsing dynamically
    PREDEFINED_CONTACT_INFO = getattr(config, "PREDEFINED_CONTACT_INFO", {})
    PREDEFINED_EDUCATION_INFO = getattr(config, "PREDEFINED_EDUCATION_INFO", [])
    CONFIG_LOADED = True
except ImportError:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_RESUME_PATH = os.path.join(script_dir, "data", "Shanmugam_AI_2025_4_YOE.pdf") # Ensure this example file exists
    DEFAULT_JOB_PATH = os.path.join(script_dir, "data", "job.txt") # Ensure this example file exists
    DEFAULT_PDF_OUTPUT_DIR = os.path.join(script_dir, "data")
    DEFAULT_MASTER_PROFILE_PATH = None
    DEFAULT_TARGET_COMPANY = "TargetCompany"
    DEFAULT_YOE = 4
    DEFAULT_FILENAME_KEYWORD = "AI"
    PREDEFINED_CONTACT_INFO = {
        "name": "Venkatesh Shanmugam",
        "line1_info": "Virginia US | svenkatesh.js@gmail.com | +1 (703) 216-2540",
        "linkedin_text": "LinkedIn", "linkedin_url": "https://www.linkedin.com/in/svenkatesh-js/",
        "github_text": "GitHub", "github_url": "https://github.com/Venkat-Git98",
        "portfolio_text": "Portfolio", "portfolio_url": "https://venkatjs.netlify.app/"
    } # Fallback
    PREDEFINED_EDUCATION_INFO = [
        {"degree_line": "Master of Science in Computer Science (3.81 / 4.0)", "university_line": "George Washington University", "dates_line": "August 2023 - May 2025"},
        {"degree_line": "Bachelor of Technology in Computer Science (3.5/4.0)", "university_line": "SRM University", "dates_line": "August 2016 - May 2020"}
    ] # Fallback

def setup_logging():
    """Configures basic logging for the application."""
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s"
    # Example: Set logging level based on an environment variable or config
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(level=log_level, format=log_format)
    # Suppress overly verbose loggers from libraries if needed
    # logging.getLogger(" برخی_کتابخانه_ها").setLevel(logging.WARNING)


def main():
    setup_logging()
    logger = logging.getLogger(__name__) # Get a logger for the main module

    if CONFIG_LOADED:
        logger.info("Configuration loaded successfully from config.py.")
    else:
        logger.warning("config.py not found or failed to import. Using default paths and settings defined in main.py.")

    parser = argparse.ArgumentParser(description="Tailor a resume to a job description using a Gemini LLM and generate a PDF.")
    parser.add_argument("--resume", "-r", default=DEFAULT_RESUME_PATH,
                        help=f"Path to the resume file (.pdf). Default: '{DEFAULT_RESUME_PATH}'")
    parser.add_argument("--job", "-j", default=DEFAULT_JOB_PATH,
                        help=f"Path to the job description file (.txt). Default: '{DEFAULT_JOB_PATH}'")
    parser.add_argument("--outputdir", "-od", default=DEFAULT_PDF_OUTPUT_DIR,
                        help=f"Directory to save the final tailored resume PDF. Default: '{DEFAULT_PDF_OUTPUT_DIR}'")
    parser.add_argument("--masterprofile", "-mp", default=DEFAULT_MASTER_PROFILE_PATH,
                        help=f"Path to the master profile text file (optional). Default: '{DEFAULT_MASTER_PROFILE_PATH}'")
    parser.add_argument("--company", "-c", default=DEFAULT_TARGET_COMPANY, 
                        help=f"Target company name for PDF filename. Default: '{DEFAULT_TARGET_COMPANY}'")
    parser.add_argument("--yoe", "-y", type=int, default=DEFAULT_YOE, 
                        help=f"Years of experience for PDF filename. Default: {DEFAULT_YOE}")
    parser.add_argument("--keyword", "-k", default=DEFAULT_FILENAME_KEYWORD, 
                        help=f"Keyword for PDF filename (e.g., AI, DataScience). Default: '{DEFAULT_FILENAME_KEYWORD}'")
    parser.add_argument("--savejson", action="store_true", 
                        help="Save the intermediate tailored JSON data from LLM (for debugging).")
    parser.add_argument("--outputcoverletter", "-ocl", default=None,
                        help="Path to save the generated cover letter (.txt file). If not provided, cover letter won't be saved to a separate file.")
    # --- NEW ARGUMENT FOR EXPLICIT COMPANY NAME FOR COVER LETTER (OPTIONAL) ---
    parser.add_argument("--clcompany", default=None,
                        help="Explicit company name to use in the cover letter (overrides extraction from job title).")

    args = parser.parse_args()

    # Resolve to absolute paths to avoid ambiguity
    resume_path = os.path.abspath(args.resume)
    jd_path = os.path.abspath(args.job)
    output_pdf_dir = os.path.abspath(args.outputdir)

    # --- Validate Inputs and Setup Directories ---
    if not resume_path.lower().endswith(".pdf"):
        logger.error(f"Invalid resume file format. Please provide a .pdf file. Path: {resume_path}")
        sys.exit(1)
    if not os.path.isfile(resume_path):
        logger.error(f"Resume PDF file not found: {resume_path}")
        sys.exit(1)

    if not jd_path.lower().endswith(".txt"):
        logger.error(f"Invalid job description file format. Please provide a .txt file. Path: {jd_path}")
        sys.exit(1)
    if not os.path.isfile(jd_path):
        logger.error(f"Job description file not found: {jd_path}")
        sys.exit(1)

    try:
        os.makedirs(output_pdf_dir, exist_ok=True)
        logger.info(f"Output directory set to: {output_pdf_dir}")
    except OSError as e:
        logger.error(f"Error creating output directory '{output_pdf_dir}': {e}", exc_info=True)
        sys.exit(1)

    # --- Load Master Profile Text (if provided) ---
    master_profile_content = None
    if args.masterprofile:
        master_profile_path = os.path.abspath(args.masterprofile)
        if os.path.isfile(master_profile_path):
            try:
                with open(master_profile_path, 'r', encoding='utf-8') as f:
                    master_profile_content = f.read()
                logger.info(f"Successfully loaded master profile from: {master_profile_path}")
            except Exception as e:
                logger.error(f"Failed to read master profile from '{master_profile_path}': {e}", exc_info=True)
                # Decide behavior: proceed without it, or exit? For now, proceed with None.
                logger.warning("Proceeding without master profile due to load error.")
        else:
            logger.warning(f"Master profile file specified ('{args.masterprofile}') but not found at resolved path: '{master_profile_path}'. Proceeding without it.")
    else:
        logger.info("No master profile file specified. Proceeding without master profile context.")


    # --- Initialize LLM Client ---
    try:
        logger.info("Initializing Gemini LLM client...")
        # API key should be handled by GeminiClient via environment variable or parameter
        llm_client = GeminiClient() 
    except Exception as e:
        logger.error(f"Failed to initialize Gemini LLM client: {e}", exc_info=True)
        sys.exit(1)
    
    contact_details_for_cl = PREDEFINED_CONTACT_INFO if CONFIG_LOADED and hasattr(config, 'PREDEFINED_CONTACT_INFO') else \
        {"name": "Your Name"} # Minimal fallback if config/attribute is missing
    if not contact_details_for_cl.get("name"):
        logger.warning("Candidate name not found in PREDEFINED_CONTACT_INFO for cover letter. Using placeholder.")
        contact_details_for_cl["name"] = "Valued Candidate"
    # --- Run Resume Tailoring Orchestration ---

    # original_resume_sections_data will be populated if OrchestratorAgent.run returns it
    orchestrator = OrchestratorAgent(llm_client)
    final_state = None # This will be TailoringState object

    try:
        logger.info(f"Running resume tailoring and cover letter generation...") # Updated log
        final_state = orchestrator.run(
            resume_pdf_path=args.resume, 
            jd_txt_path=args.job,
            contact_info_for_cl=contact_details_for_cl,
            master_profile_text=master_profile_content,
            company_name_for_cl=args.clcompany # From argparse
        )
        # ... (check final_state and tailored_resume as before) ...
        # ... (save optional debug JSON) ...
        # ... (generate resume PDF using generate_styled_resume_pdf as before) ...

        # --- NEW: Generate Cover Letter PDF ---
        if final_state and final_state.generated_cover_letter_text and PDF_GENERATOR_AVAILABLE and generate_cover_letter_pdf:
            logger.info("Attempting to generate Cover Letter PDF...")
            try:
                # company_name for CL PDF filename and potentially header
                # If args.clcompany is provided, use it. Otherwise, try to get from job_desc or fallback.
                cl_company_name_for_file = args.clcompany or \
                                       (final_state.job_description.job_title.split(" at ")[-1].strip().title() 
                                        if final_state.job_description and final_state.job_description.job_title and " at " in final_state.job_description.job_title.lower() 
                                        else args.company) # Fallback to general company arg

                cl_job_title_for_file = (final_state.job_description.job_title 
                                        if final_state.job_description and final_state.job_description.job_title 
                                        else "Position")


                cover_letter_pdf_path = generate_cover_letter_pdf(
                    cover_letter_body_text=final_state.generated_cover_letter_text,
                    contact_info=contact_details_for_cl, # Your predefined contact info
                    job_title=cl_job_title_for_file,
                    company_name=cl_company_name_for_file,
                    output_pdf_directory=args.outputdir, # Use the same output directory as resume
                    filename_keyword="CoverLetter", # Or make this configurable
                    years_of_experience=args.yoe # Using YOE from resume args
                )
                if cover_letter_pdf_path:
                    logger.info(f"Cover Letter PDF generated successfully: '{cover_letter_pdf_path}'")
                else:
                    logger.error("Cover Letter PDF generation failed.")
            except Exception as e_cl_pdf:
                logger.error(f"Error during Cover Letter PDF generation: {e_cl_pdf}", exc_info=True)
        elif final_state and final_state.generated_cover_letter_text:
            # Save as .txt if PDF generation not available or desired (old behavior)
            if args.outputcoverletter: # If user specifically wants a .txt output path for CL
                cover_letter_txt_path = os.path.abspath(args.outputcoverletter)
                try:
                    os.makedirs(os.path.dirname(cover_letter_txt_path), exist_ok=True)
                    with open(cover_letter_txt_path, "w", encoding='utf-8') as f:
                        f.write(final_state.generated_cover_letter_text)
                    logger.info(f"Generated cover letter text saved to: {cover_letter_txt_path}")
                except Exception as e:
                    logger.error(f"Failed to save cover letter text to '{cover_letter_txt_path}': {e}", exc_info=True)
            else:
                logger.info("Cover letter text generated but PDF generation skipped (generator not available or an issue occurred). No .txt output path specified.")
        elif not (final_state and final_state.generated_cover_letter_text):
            logger.info("No cover letter text was generated by the agent.")

        if final_state and final_state.resume_critique:
            critique = final_state.resume_critique
            logger.info("--- Resume Judge Verdict ---")
            logger.info(f"  ATS Score: {critique.ats_score if critique.ats_score is not None else 'N/A'}%")
            logger.info(f"  ATS Pass Assessment: {critique.ats_pass_assessment or 'N/A'}")
            logger.info(f"  Recruiter Impression: {critique.recruiter_impression_assessment or 'N/A'}")
            logger.info("--------------------------")
        elif final_state and final_state.raw_critique_text: # If parsing failed but we have raw text
            logger.info("--- Raw Resume Critique Text (Parsing Failed/Incomplete) ---")
            logger.info(final_state.raw_critique_text)
            logger.info("-------------------------------------------------------")
        else:
            logger.info("No resume critique was generated or an error occurred during critique.")
    except Exception as e:
        logger.error(f"Main pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
  
    from utils.llm_gemini import GeminiClient # For type hints if needed
    from agents.orchestrator import OrchestratorAgent
    from models import ResumeSections, JobDescription, TailoringState, ResumeCritique
    try:
        from src.docx_to_pdf_generator import generate_styled_resume_pdf, generate_cover_letter_pdf
        PDF_GENERATOR_AVAILABLE = True
    except ImportError:
        PDF_GENERATOR_AVAILABLE = False
        generate_styled_resume_pdf = None # type: ignore
        generate_cover_letter_pdf = None # type: ignore
    
    if not CONFIG_LOADED: # Fallback for direct script run without config.py fully loaded
        PREDEFINED_CONTACT_INFO = {"name": "Default User", "email": "user@example.com"} # Minimal example
        PREDEFINED_EDUCATION_INFO = []
    
    main()
# if __name__ == "__main__":
#     # Ensure necessary imports are available if run as script
#     from models import ResumeSections, JobDescription, TailoringState
#     from utils.llm_gemini import GeminiClient # Not strictly needed here if main only calls orchestrator
#     from agents.orchestrator import OrchestratorAgent
#     try:
#         from src.docx_to_pdf_generator import generate_styled_resume_pdf
#         PDF_GENERATOR_AVAILABLE = True
#     except ImportError:
#         PDF_GENERATOR_AVAILABLE = False
#         generate_styled_resume_pdf = None # type: ignore
    
#     # To load PREDEFINED_CONTACT_INFO, PREDEFINED_EDUCATION_INFO if config.py not found
#     if not CONFIG_LOADED:
#         PREDEFINED_CONTACT_INFO = {
#             "name": "Venkatesh Shanmugam", # Replace with your actual details
#             "line1_info": "Your City, ST | your.email@example.com | (555) 123-4567",
#             "linkedin_text": "LinkedIn", "linkedin_url": "#",
#             "github_text": "GitHub", "github_url": "#",
#             "portfolio_text": "Portfolio", "portfolio_url": "#"
#         }
#         PREDEFINED_EDUCATION_INFO = [
#             {"degree_line": "Your Degree (GPA)", "university_line": "Your University", "dates_line": "Year - Year"}
#         ]

#     main()
    # try:
    #     logger.info(f"Running resume tailoring process for resume: '{resume_path}' and JD: '{jd_path}'...")
        
    #     # OrchestratorAgent.run should return a tuple: (tailored_resume_model, original_resume_sections_model)
    #     # original_resume_sections_model is used if you dynamically parse contact/education from original resume.
    #     # For now, we are using predefined contact/education from config.py.
    #     tailored_resume_model, _ = orchestrator.run( # We might not need original_resume_sections_data here if using predefined
    #         resume_pdf_path=resume_path, 
    #         jd_txt_path=jd_path,
    #         master_profile_text=master_profile_content
    #     )
        
#         if isinstance(tailored_resume_model, ResumeSections):
#             try: 
#                 tailored_resume_data_dict = tailored_resume_model.model_dump(exclude_none=True) # Pydantic v2
#             except AttributeError: 
#                 tailored_resume_data_dict = tailored_resume_model.dict(exclude_none=True) # Pydantic v1
#         elif isinstance(tailored_resume_model, dict): # If orchestrator directly returns a dict
#             tailored_resume_data_dict = tailored_resume_model
#         else:
#             logger.error(f"Orchestrator did not return a usable tailored resume. Expected ResumeSections model or dict, got: {type(tailored_resume_model)}")
#             sys.exit(1) # Critical failure if no tailored data

#         logger.info("Resume tailoring process completed successfully by orchestrator.")

#     except Exception as e:
#         logger.error(f"Resume tailoring pipeline failed during orchestration: {e}", exc_info=True)
#         sys.exit(1)

#     # --- Save Tailored Resume JSON Output (Optional for Debugging) ---
#     if args.savejson and tailored_resume_data_dict:
#         # Construct a unique name for the debug JSON if multiple JDs are processed
#         base_jd_name = os.path.splitext(os.path.basename(jd_path))[0]
#         debug_json_filename = f"tailored_resume_debug_{base_jd_name}.json"
#         debug_json_path = os.path.join(output_pdf_dir, debug_json_filename)
#         try:
#             with open(debug_json_path, "w", encoding="utf-8") as f:
#                 json.dump(tailored_resume_data_dict, f, indent=4, ensure_ascii=False)
#             logger.info(f"Intermediate tailored resume JSON (for debugging) saved to: '{debug_json_path}'")
#         except Exception as e:
#             logger.warning(f"Could not save intermediate tailored resume JSON to '{debug_json_path}': {e}", exc_info=True)
    
#     # --- Sourcing Contact and Education Information ---
#     # Using predefined data from config.py as per user's preference for personal use.
#     # If dynamic parsing from original_resume_sections_data was implemented, it would happen here.
#     contact_details_to_use = PREDEFINED_CONTACT_INFO
#     education_details_to_use = PREDEFINED_EDUCATION_INFO

#     if not contact_details_to_use or not education_details_to_use:
#         logger.warning(
#             "PREDEFINED_CONTACT_INFO or PREDEFINED_EDUCATION_INFO from config.py (or fallbacks) is empty. "
#             "The contact/education sections in the DOCX/PDF may be missing or incomplete."
#         )


#     # --- Generate PDF from the Tailored Data ---
#     if PDF_GENERATOR_AVAILABLE and tailored_resume_data_dict and generate_styled_resume_pdf:
#         logger.info(f"Attempting to generate PDF. Output PDF will be saved in: '{output_pdf_dir}'")
#         try:
#             final_pdf_path = generate_styled_resume_pdf(
#                 tailored_data=tailored_resume_data_dict,
#                 contact_info=contact_details_to_use,
#                 education_info=education_details_to_use,
#                 output_pdf_directory=output_pdf_dir,
#                 target_company_name=args.company,
#                 years_of_experience=args.yoe,
#                 filename_keyword=args.keyword
#             )
#             if final_pdf_path:
#                 logger.info(f"PDF resume generated successfully: '{final_pdf_path}'")
#             else:
#                 logger.error("PDF generation function reported failure (returned None or False). Check previous logs from the generator.")
#         except Exception as e:
#             logger.error(f"An unexpected error occurred during the PDF generation stage: {e}", exc_info=True)
#     elif not PDF_GENERATOR_AVAILABLE:
#         logger.info("PDF generation skipped as the PDF generator module (src.docx_to_pdf_generator) was not available or imported correctly.")
#     elif not tailored_resume_data_dict:
#          logger.warning("Skipping PDF generation as tailored resume data was not successfully created or is empty.")
#     else: # Should not happen if PDF_GENERATOR_AVAILABLE is True and generate_styled_resume_pdf is not None
#         logger.error("PDF generation skipped due to an unknown issue with PDF generator availability.")


# if __name__ == "__main__":
#     # These imports are needed here if main() calls functions that depend on them
#     # and main() itself is not part of a package that pre-imports them.
#     # from models import ResumeSections # For type hint of tailored_resume_model
#     # from src.docx_to_pdf_generator import generate_styled_resume_pdf, PDF_GENERATOR_AVAILABLE
#     main()