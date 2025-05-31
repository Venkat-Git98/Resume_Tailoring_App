import streamlit as st
import os
import json
import tempfile
import base64
from pathlib import Path
import sys # For debugging prints
from datetime import datetime

# --- Initial Imports and Configuration Setup ---
CONFIG_MODE = None 
ImportedConfigHolder = None 

print(f"--- Debug Info ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Python sys.path:")
for p in sys.path:
    print(f"  - {p}")
print(f"Location of streamlit_app.py (__file__): {os.path.abspath(__file__)}")
print(f"--- End Debug Info ---")

try:
    import config as config_module 
    print(f"Successfully imported 'config' module from: {config_module.__file__}")
    _Config_attr = getattr(config_module, "Config", None)

    if _Config_attr is None:
        st.warning("The name 'Config' is NOT DEFINED in your 'config.py' module. Using 'config.py' as a direct source of global constants (fallback mode).")
        CONFIG_MODE = 'module_globals'
        ImportedConfigHolder = config_module
    elif not isinstance(_Config_attr, type): 
        st.error(f"CRITICAL: 'Config' found in 'config.py' is NOT A CLASS. Its type is: {type(_Config_attr)}.")
        st.error("This often happens if 'Config=...' is defined in your .env file, which overwrites the class definition.")
        st.error("Please REMOVE or RENAME any 'Config=...' line in your .env file.")
        st.warning("Attempting to use 'config.py' as a direct source of global constants (fallback mode).")
        CONFIG_MODE = 'module_globals'
        ImportedConfigHolder = config_module
    else:
        print("'Config' is a class. Proceeding with class-based configuration.")
        CONFIG_MODE = 'class'
        ImportedConfigHolder = _Config_attr 
    
    print(f"Configuration mode set to: {CONFIG_MODE}")

except ImportError as e:
    st.error(f"Failed to import the 'config.py' module itself. Error: {e}")
    st.error(f"Please ensure 'config.py' is in the same directory as 'streamlit_app.py': {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')}")
    CONFIG_MODE = 'error'
    st.stop()
except Exception as e:
    st.error(f"An unexpected error occurred during initial import of 'config': {e}")
    CONFIG_MODE = 'error'
    st.stop()

# --- Subsequent Imports (these will only run if Config import stage is passed) ---
if CONFIG_MODE != 'error':
    try:
        from agents.jd_analysis import JDAnalysisAgent
        from agents.resume_parser import ResumeParserAgent
        from agents.tailoring import TailoringAgent # CORRECTED from ResumeTailoringAgent
        from agents.cover_letter_agent import CoverLetterAgent
        from src.pdf_generator import generate_pdf_from_json_xhtml2pdf # CORRECTED: Import function
        from src.docx_to_pdf_generator import generate_styled_resume_pdf, generate_pdf_via_google_drive, generate_cover_letter_pdf as generate_styled_cover_letter_pdf # Import actual functions including sophisticated cover letter function
        from utils.llm_gemini import GeminiClient
        from utils.gcs_utils import get_gcs_client, upload_file_to_gcs # CORRECTED: Import functions
        from models import ResumeSections, JobDescription # CORRECTED: Removed Resume
        print("Successfully imported other project modules (agents, src, utils, models).")
    except ImportError as e:
        st.error(f"Failed to import one of the project's sub-modules (agents, src, utils, models). Error: {e}")
        st.error("Ensure these folders are in the same directory as streamlit_app.py and each contains an __init__.py file.")
        st.stop()

# --- Configuration Loading Function ---
def load_final_config():
    cfg_obj = type('AppConfig', (object,), {})() 

    if CONFIG_MODE == 'class' and ImportedConfigHolder:
        try:
            default_cfg_instance = ImportedConfigHolder() 
            for attr in dir(default_cfg_instance):
                if not attr.startswith('__') and not callable(getattr(default_cfg_instance, attr)):
                    setattr(cfg_obj, attr, getattr(default_cfg_instance, attr))
            print("Loaded defaults from Config class instance.")
        except Exception as e:
            st.warning(f"Could not instantiate Config class from config.py: {e}. Will rely on direct attributes or secrets.")
    
    elif CONFIG_MODE == 'module_globals' and ImportedConfigHolder:
        expected_attrs = [
            'GEMINI_API_KEY', 'GCP_PROJECT_ID', 'GCS_BUCKET_NAME', 
            'GOOGLE_APPLICATION_CREDENTIALS', 'PROJECT_ROOT', 'SRC_DIR', 'LOG_LEVEL',
            'MASTER_PROFILE_FILE_PATH', 'TEMPLATES_DIR', # Added TEMPLATES_DIR
            'GEMINI_MODEL_FOR_TAILORING', 'SERVICE_ACCOUNT_JSON_CONTENT', # Added from your config
            'RESUME_TEMPLATE_PATH' # Ensure this is picked up
        ]
        for attr_name in dir(ImportedConfigHolder): # Iterate all attributes in module
            if not attr_name.startswith('__'):
                 setattr(cfg_obj, attr_name, getattr(ImportedConfigHolder, attr_name))
        print("Loaded attributes directly from config module (fallback mode).")

    if 'GEMINI_API_KEY' in st.secrets:
        cfg_obj.GEMINI_API_KEY = st.secrets['GEMINI_API_KEY']
    if 'GCP_PROJECT_ID' in st.secrets:
        cfg_obj.GCP_PROJECT_ID = st.secrets['GCP_PROJECT_ID']
    if 'GCS_BUCKET_NAME' in st.secrets:
        cfg_obj.GCS_BUCKET_NAME = st.secrets['GCS_BUCKET_NAME']
    
    gac_json_str = st.secrets.get('GOOGLE_CREDENTIALS_JSON_CONTENT') # Matches your config.py env var name
    gac_path_secret = st.secrets.get('GOOGLE_APPLICATION_CREDENTIALS') # For path based secret

    # Priority: Secrets JSON_STR > Secrets Path > Config object's SERVICE_ACCOUNT_JSON_CONTENT > Config object's GOOGLE_APPLICATION_CREDENTIALS path
    final_gac_source_for_env_var = None

    if gac_json_str:
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp_cred_file:
                tmp_cred_file.write(gac_json_str)
            final_gac_source_for_env_var = tmp_cred_file.name
            cfg_obj.GOOGLE_APPLICATION_CREDENTIALS = final_gac_source_for_env_var # Store path
            print(f"Using GOOGLE_CREDENTIALS_JSON_STR from Streamlit secrets (written to temp file: {final_gac_source_for_env_var}).")
        except Exception as e:
            st.warning(f"Failed to process GOOGLE_CREDENTIALS_JSON_STR from secrets: {e}")
    elif gac_path_secret:
        final_gac_source_for_env_var = gac_path_secret
        cfg_obj.GOOGLE_APPLICATION_CREDENTIALS = final_gac_source_for_env_var
        print(f"Using GOOGLE_APPLICATION_CREDENTIALS path from Streamlit secrets: {final_gac_source_for_env_var}.")
    elif hasattr(cfg_obj, 'SERVICE_ACCOUNT_JSON_CONTENT') and cfg_obj.SERVICE_ACCOUNT_JSON_CONTENT: # Check this attribute from your config
        try:
            # Ensure SERVICE_ACCOUNT_JSON_CONTENT is a string before writing
            sa_json_content_str = cfg_obj.SERVICE_ACCOUNT_JSON_CONTENT
            if not isinstance(sa_json_content_str, str):
                st.warning(f"SERVICE_ACCOUNT_JSON_CONTENT from config is not a string (type: {type(sa_json_content_str)}). Cannot write to temp file.")
                sa_json_content_str = None

            if sa_json_content_str:
                with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp_cred_file:
                    tmp_cred_file.write(sa_json_content_str)
                final_gac_source_for_env_var = tmp_cred_file.name
                cfg_obj.GOOGLE_APPLICATION_CREDENTIALS = final_gac_source_for_env_var # Store path
                print(f"Using SERVICE_ACCOUNT_JSON_CONTENT from config object (written to temp file: {final_gac_source_for_env_var}).")
        except Exception as e:
            st.warning(f"Failed to process SERVICE_ACCOUNT_JSON_CONTENT from config: {e}")
    elif hasattr(cfg_obj, 'GOOGLE_APPLICATION_CREDENTIALS') and cfg_obj.GOOGLE_APPLICATION_CREDENTIALS: # Check path if JSON content not used/failed
        # Ensure this is a path string
        gac_path_from_config = cfg_obj.GOOGLE_APPLICATION_CREDENTIALS
        if isinstance(gac_path_from_config, str):
            final_gac_source_for_env_var = gac_path_from_config
            print(f"Using GOOGLE_APPLICATION_CREDENTIALS path from config object: {final_gac_source_for_env_var}.")
        else:
            st.warning(f"GOOGLE_APPLICATION_CREDENTIALS from config is not a valid path string (type: {type(gac_path_from_config)}).")


    if final_gac_source_for_env_var:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = final_gac_source_for_env_var
        print(f"Set GOOGLE_APPLICATION_CREDENTIALS env var to: {final_gac_source_for_env_var}")
    else:
        print("GOOGLE_APPLICATION_CREDENTIALS environment variable not set (no source found in secrets or config). GCS/Vertex AI might fail if not set globally.")


    if not hasattr(cfg_obj, 'GEMINI_API_KEY') or not cfg_obj.GEMINI_API_KEY:
        st.error("GEMINI_API_KEY is MISSING. Please set it in Streamlit secrets (.streamlit/secrets.toml) or ensure your config.py / .env provides it.")
    
    return cfg_obj

CONFIG = load_final_config()

# --- Helper Functions ---
def load_master_profile():
    """Load default professional background file if it exists"""
    default_path = "master_profile.txt"
    file_path = getattr(CONFIG, 'DEFAULT_MASTER_PROFILE_PATH', None)
    if not file_path:
        file_path = getattr(CONFIG, 'MASTER_PROFILE_FILE_PATH', default_path)

    if not os.path.isabs(file_path):
        script_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
        project_root_path = None
        if hasattr(CONFIG, 'PROJECT_ROOT') and CONFIG.PROJECT_ROOT:
             project_root_path = os.path.join(CONFIG.PROJECT_ROOT, file_path)

        if os.path.exists(script_dir_path):
            file_path = script_dir_path
        elif project_root_path and os.path.exists(project_root_path):
            file_path = project_root_path
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        return None

def extract_job_keywords(job_description_text: str, max_words: int = 2) -> str:
    """Extract meaningful keywords from job description for naming"""
    if not job_description_text:
        return "UnknownPosition"
    
    # Common words to skip
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
        'we', 'you', 'they', 'our', 'your', 'their', 'job', 'position', 'role', 'opportunity', 'candidate',
        'experience', 'work', 'company', 'team', 'looking', 'seeking', 'hiring', 'join', 'responsibilities'
    }
    
    # Take first few lines which usually contain the job title
    first_lines = job_description_text.split('\n')[:3]
    text_to_analyze = ' '.join(first_lines)
    
    # Split into words and clean
    words = []
    for word in text_to_analyze.split():
        clean_word = ''.join(c for c in word if c.isalnum())
        if (len(clean_word) > 2 and 
            clean_word.lower() not in stop_words and
            not clean_word.isdigit()):
            words.append(clean_word.title())
        
        if len(words) >= max_words:
            break
    
    return ''.join(words) if words else "Position"

def generate_gcs_folder_name(job_description_text: str, uploaded_resume_name: str, candidate_name: str = None) -> str:
    """Generate a unique folder name for GCS storage using Option B (Resume-Based Naming)"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Use provided candidate name or extract from resume filename
    if candidate_name:
        folder_candidate_name = ''.join(c for c in candidate_name if c.isalnum() or c in '-_')
    else:
        # Extract from resume filename
        resume_base = Path(uploaded_resume_name).stem
        folder_candidate_name = ''.join(c for c in resume_base if c.isalnum() or c in '-_')[:20]
    
    return f"{timestamp}_{folder_candidate_name}"

def get_default_filename_base() -> str:
    """Get default filename base from config"""
    contact_info = getattr(CONFIG, 'PREDEFINED_CONTACT_INFO', {})
    candidate_name = contact_info.get('name', 'Shanmugam')
    
    # Extract last name for filename
    name_parts = candidate_name.split()
    if len(name_parts) > 1:
        last_name = name_parts[-1]
    else:
        last_name = candidate_name
    
    return f"{last_name}_AI_4_YOE"

def generate_cover_letter_pdf(text_content: str, output_path: str) -> str:
    # This function has been replaced by the sophisticated generate_styled_cover_letter_pdf
    # from src.docx_to_pdf_generator which provides professional formatting
    raise NotImplementedError("Use generate_styled_cover_letter_pdf instead")


# --- Main Application Logic ---
def run_tailoring_process(job_description_text: str, resume_input, professional_background_content: str = None, 
                         custom_resume_filename: str = None, custom_cl_filename: str = None):
    if not job_description_text or resume_input is None:
        st.error("Missing job description or resume.")
        return None, None, None, None

    # Professional background is optional
    if professional_background_content:
        st.info("✨ Using professional background for enhanced tailoring.")
    else:
        st.info("📝 Proceeding without professional background.")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Handle resume input: either uploaded file or default path
            temp_resume_path = None
            resume_file_name = ""
            
            if isinstance(resume_input, str): # It's a file path (likely the default file)
                if not os.path.exists(resume_input):
                    st.error(f"Default resume file not found at: {resume_input}")
                    return None, None, None, None
                temp_resume_path = resume_input # Use the provided path directly
                resume_file_name = os.path.basename(resume_input)
                st.info(f"Using default resume from: {temp_resume_path}")
                
            elif hasattr(resume_input, 'read'): # It's a file-like object (uploaded file)
                temp_resume_path = os.path.join(temp_dir, resume_input.name)
                with open(temp_resume_path, "wb") as f:
                    f.write(resume_input.getbuffer())
                resume_file_name = resume_input.name
                st.info(f"Uploaded resume saved temporarily to: {temp_resume_path}")
            else:
                st.error("Invalid resume input type.")
                return None, None, None, None

            # Save JD to temp file
            temp_jd_path = os.path.join(temp_dir, "job_description.txt")
            with open(temp_jd_path, "w", encoding="utf-8") as f_jd:
                f_jd.write(job_description_text)
            
            # Ensure CONFIG has GEMINI_API_KEY
            gemini_api_key = getattr(CONFIG, 'GEMINI_API_KEY', None)
            if not gemini_api_key:
                st.error("Cannot proceed: GEMINI_API_KEY is not configured.")
                return None, None, None, None

            # Instantiate GeminiClient
            llm_model_name = getattr(CONFIG, 'GEMINI_MODEL_FOR_TAILORING', "gemini-1.5-pro-001")
            
            try:
                llm_client = GeminiClient(api_key=gemini_api_key, model_name=llm_model_name) 
                st.info(f"GeminiClient initialized with model: {llm_model_name}.")
            except Exception as e:
                st.error(f"Failed to initialize GeminiClient: {e}")
                return None, None, None, None

            # --- Agent Processing ---
            st.info("Analyzing Job Description...")
            jd_analyzer = JDAnalysisAgent(llm_client)
            jd_analysis_result = jd_analyzer.run(jd_txt_path=temp_jd_path) 
            if not isinstance(jd_analysis_result, JobDescription) or not jd_analysis_result.job_title: 
                st.error(f"Failed to analyze job description or got unexpected result type: {type(jd_analysis_result)}")
                return None, None, None, None
            st.success("Job Description Analyzed.")

            st.info("Parsing Uploaded Resume...")
            resume_parser = ResumeParserAgent() 
            parsed_uploaded_resume_sections = resume_parser.run(resume_pdf_path=temp_resume_path) 
            if not isinstance(parsed_uploaded_resume_sections, ResumeSections) or not any(vars(parsed_uploaded_resume_sections).values()): 
                st.error(f"Failed to parse uploaded resume or got empty sections. Result type: {type(parsed_uploaded_resume_sections)}")
                return None, None, None, None
            st.success("Uploaded Resume Parsed.")

            st.info("Tailoring Resume...")
            tailoring_agent = TailoringAgent(llm_client=llm_client) 
            tailored_resume_sections, _ = tailoring_agent.run(
                job_desc=jd_analysis_result, 
                resume=parsed_uploaded_resume_sections,
                master_profile_text=professional_background_content  # Can be None
            )
            if not isinstance(tailored_resume_sections, ResumeSections):
                st.error("Failed to tailor resume or got unexpected result type.")
                return None, None, None, None
            st.success("Resume Tailored.")

            tailored_resume_json_data = tailored_resume_sections.dict() 

            temp_tailored_resume_json_path = os.path.join(temp_dir, "tailored_resume.json")
            with open(temp_tailored_resume_json_path, "w", encoding="utf-8") as f_json:
                json.dump(tailored_resume_json_data, f_json, indent=4)

            st.info("Generating Cover Letter...")
            cover_letter_agent = CoverLetterAgent(llm_client=llm_client)
            contact_info_for_cl = getattr(CONFIG, 'PREDEFINED_CONTACT_INFO', {})
            if not contact_info_for_cl:
                st.warning("PREDEFINED_CONTACT_INFO not found in config. Cover letter might be incomplete.")

            cover_letter_text = cover_letter_agent.run(
                job_desc=jd_analysis_result,
                tailored_resume=tailored_resume_sections, 
                contact_info=contact_info_for_cl,
                master_profile_text=professional_background_content  # Can be None
            )
            if not cover_letter_text:
                st.warning("Cover letter generation resulted in empty or no text. Skipping CL PDF.")
            else:
                st.success("Cover Letter Generated.")

            # --- Resume DOCX and PDF Generation via Google Drive ---
            st.info("Generating Resume PDF via Google Drive...")
            
            # Get required configuration
            contact_info_for_pdf = getattr(CONFIG, 'PREDEFINED_CONTACT_INFO', {})
            education_info_for_pdf = getattr(CONFIG, 'PREDEFINED_EDUCATION_INFO', [])
            
            if not contact_info_for_pdf:
                st.error("PREDEFINED_CONTACT_INFO not found in config. Cannot generate resume PDF.")
                return None, None, None, None
                
            if not education_info_for_pdf:
                st.error("PREDEFINED_EDUCATION_INFO not found in config. Cannot generate resume PDF.")
                return None, None, None, None

            try:
                # Use the actual function instead of class
                final_resume_pdf_path_temp = generate_styled_resume_pdf(
                    tailored_data=tailored_resume_json_data,
                    contact_info=contact_info_for_pdf,
                    education_info=education_info_for_pdf,
                    output_pdf_directory=temp_dir,
                    target_company_name=jd_analysis_result.company_name if hasattr(jd_analysis_result, 'company_name') else None,
                    years_of_experience=4,  # You can make this configurable
                    filename_keyword="TailoredResume"
                )
                
                if not final_resume_pdf_path_temp or not os.path.exists(final_resume_pdf_path_temp):
                    st.error(f"Failed to generate resume PDF via Google Drive.")
                    return None, None, None, None
                    
                st.success(f"Resume PDF generated via Google Drive: {os.path.basename(final_resume_pdf_path_temp)}")

            except Exception as e:
                st.error(f"Error during resume PDF generation: {e}")
                import traceback
                st.error(traceback.format_exc())
                return None, None, None, None

            # Generate Cover Letter PDF using sophisticated formatting
            generated_cl_pdf_actual_path = None
            if cover_letter_text: # Only generate if text exists
                st.info("Generating PDF for Cover Letter with professional formatting...")
                
                # Extract job title and company name from analysis
                job_title = getattr(jd_analysis_result, 'job_title', 'Position') or 'Position'
                company_name = getattr(jd_analysis_result, 'company_name', 'Company') or 'Company'
                
                try:
                    # Use the sophisticated cover letter PDF generator
                    generated_cl_pdf_actual_path = generate_styled_cover_letter_pdf(
                        cover_letter_body_text=cover_letter_text,
                        contact_info=contact_info_for_pdf,
                        job_title=job_title,
                        company_name=company_name,
                        output_pdf_directory=temp_dir,
                        filename_keyword="CoverLetter",
                        years_of_experience=4  # You can make this configurable
                    )
                    
                    if generated_cl_pdf_actual_path and os.path.exists(generated_cl_pdf_actual_path):
                        st.success(f"Cover Letter PDF generated with professional formatting: {os.path.basename(generated_cl_pdf_actual_path)}")
                    else:
                        st.warning("Cover Letter PDF generation failed - file not created")
                        generated_cl_pdf_actual_path = None
                        
                except Exception as e:
                    st.error(f"Error during cover letter PDF generation: {e}")
                    import traceback
                    st.error(traceback.format_exc())
                    generated_cl_pdf_actual_path = None
            else: 
                st.info("Skipping Cover Letter PDF generation as cover letter text was not generated or was empty.")


            # --- GCS Upload ---
            gcs_final_resume_path = None
            gcs_final_cl_path = None
            
            gcs_bucket_name_cfg = getattr(CONFIG, 'GCS_BUCKET_NAME', None)
            gac_env_var_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if gcs_bucket_name_cfg and gac_env_var_path:
                if not os.path.exists(gac_env_var_path):
                    st.warning(f"GCS Upload: GOOGLE_APPLICATION_CREDENTIALS file not found at '{gac_env_var_path}'. Skipping GCS upload.")
                else:
                    st.info("Attempting to upload documents to GCS...")
                    gcs_client_instance = get_gcs_client() 
                    if gcs_client_instance:
                        try:
                            # Generate unique folder name using Option B strategy
                            contact_name = contact_info_for_cl.get('name', 'User')
                            gcs_folder_name = generate_gcs_folder_name(job_description_text, resume_file_name, contact_name)
                            
                            # Use custom filenames if provided, otherwise use defaults
                            resume_gcs_filename = custom_resume_filename or "TailoredResume.pdf"
                            cl_gcs_filename = custom_cl_filename or "CoverLetter.pdf"
                            
                            if os.path.exists(final_resume_pdf_path_temp):
                                resume_blob_name = f"applications/{gcs_folder_name}/{resume_gcs_filename}"
                                upload_success_resume = upload_file_to_gcs( 
                                    gcs_client_instance, 
                                    final_resume_pdf_path_temp, 
                                    resume_blob_name, 
                                    bucket_name=gcs_bucket_name_cfg
                                )
                                if upload_success_resume:
                                    gcs_final_resume_path = f"gs://{gcs_bucket_name_cfg}/{resume_blob_name}"
                                    st.success(f"Tailored Resume uploaded to GCS: {gcs_final_resume_path}")
                                else:
                                    st.warning("Failed to upload Tailored Resume to GCS.")
                            else:
                                st.warning("Tailored Resume PDF does not exist. Skipping GCS upload for resume.")

                            if generated_cl_pdf_actual_path and os.path.exists(generated_cl_pdf_actual_path):
                                cl_blob_name = f"applications/{gcs_folder_name}/{cl_gcs_filename}"
                                upload_success_cl = upload_file_to_gcs( 
                                    gcs_client_instance, 
                                    generated_cl_pdf_actual_path, 
                                    cl_blob_name, 
                                    bucket_name=gcs_bucket_name_cfg
                                )
                                if upload_success_cl:
                                    gcs_final_cl_path = f"gs://{gcs_bucket_name_cfg}/{cl_blob_name}"
                                    st.success(f"Cover Letter uploaded to GCS: {gcs_final_cl_path}")
                                else:
                                    st.warning("Failed to upload Cover Letter to GCS.")
                                    
                            # Show folder organization info
                            if gcs_final_resume_path or gcs_final_cl_path:
                                st.info(f"📁 Documents organized in folder: `applications/{gcs_folder_name}/`")
                                st.info(f"📋 Folder naming: `Timestamp_CandidateName` (Option B)")
                                
                        except Exception as e:
                            st.warning(f"Failed to upload to GCS: {e}. Ensure GCS is configured correctly.")
                    else:
                        st.warning("Failed to get GCS client. Skipping GCS upload.")
            else:
                missing_gcs_configs = []
                if not gcs_bucket_name_cfg: missing_gcs_configs.append("GCS_BUCKET_NAME in config")
                if not gac_env_var_path: missing_gcs_configs.append("GOOGLE_APPLICATION_CREDENTIALS (env var not set)")
                elif not os.path.exists(gac_env_var_path):  missing_gcs_configs.append(f"GOOGLE_APPLICATION_CREDENTIALS file not found at '{gac_env_var_path}'")
                
                if missing_gcs_configs:
                    st.info(f"GCS settings not fully configured ({', '.join(missing_gcs_configs)}). Skipping GCS upload.")
                else:
                    st.info("GCS upload skipped due to missing configuration.")

            
            # Read PDF bytes for download
            resume_pdf_bytes = None
            if os.path.exists(final_resume_pdf_path_temp):
                with open(final_resume_pdf_path_temp, "rb") as f:
                    resume_pdf_bytes = f.read()
            
            cover_letter_pdf_bytes = None
            if generated_cl_pdf_actual_path and os.path.exists(generated_cl_pdf_actual_path):
                with open(generated_cl_pdf_actual_path, "rb") as f:
                    cover_letter_pdf_bytes = f.read()

            return resume_pdf_bytes, cover_letter_pdf_bytes, gcs_final_resume_path, gcs_final_cl_path

        except Exception as e:
            st.error(f"An error occurred during the tailoring process: {e}")
            import traceback # Should be at top of file ideally
            st.error(traceback.format_exc())
            return None, None, None, None


# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Resume Tailoring Agent")
st.title("📄 Resume Tailoring Agent")

if CONFIG_MODE == 'error':
    st.error("Application cannot start due to configuration import errors. Please check the messages above.")
else:
    # Load default professional background if available (non-blocking)
    default_professional_background = load_master_profile()

    st.header("1. Input Job Description")
    job_description = st.text_area("Paste the full job description here:", height=250, key="job_desc_input")

    st.header("2. Upload Your Current Resume")

    # Resume input options
    resume_input_method = st.radio(
        "Choose how to provide your resume:",
        ["Upload file", "Use default file"],
        key="resume_method"
    )

    uploaded_resume = None
    resume_path_to_use = None
    resume_source_name = ""

    default_resume_path = getattr(CONFIG, 'DEFAULT_BASE_RESUME_PDF_PATH', None)
    default_resume_exists = default_resume_path and os.path.exists(default_resume_path)

    if resume_input_method == "Upload file":
        uploaded_resume = st.file_uploader("Upload your resume (PDF or DOCX format recommended):", type=["pdf", "docx"], key="resume_upload")
        if uploaded_resume:
            resume_source_name = uploaded_resume.name
            # The path will be handled inside run_tailoring_process by saving the uploaded file
            # run_tailoring_process needs to accept the uploaded file object directly in this case

    elif resume_input_method == "Use default file":
        if default_resume_exists:
            resume_path_to_use = default_resume_path
            resume_source_name = os.path.basename(default_resume_path)
            st.info(f"✅ Using default resume file: {resume_source_name}")
        else:
            st.warning("Default resume file not found. Please upload a file.")
            # Automatically switch back to upload if default not found
            st.session_state.resume_method = "Upload file"
            st.experimental_rerun() # Rerun to update the UI

    st.header("3. Professional Background (Optional)")
    st.markdown("*This helps tailor your resume more effectively, but you can proceed without it.*")
    
    # Professional background input options
    bg_input_method = st.radio(
        "Choose how to provide your professional background:",
        ["None", "Enter as text", "Upload text file", "Use default file"],
        key="bg_method"
    )
    
    professional_background_content = None
    
    if bg_input_method == "Enter as text":
        professional_background_content = st.text_area(
            "Enter your professional background, key achievements, and career highlights:",
            height=200,
            placeholder="e.g., Software engineer with 5+ years in AI/ML, led team of 10 developers, expertise in Python, cloud platforms...",
            key="bg_text_input"
        )
        if professional_background_content.strip():
            st.success("✅ Professional background provided via text input.")
        
    elif bg_input_method == "Upload text file":
        uploaded_bg_file = st.file_uploader(
            "Upload a text file containing your professional background:",
            type=["txt"],
            key="bg_file_upload"
        )
        if uploaded_bg_file:
            try:
                professional_background_content = uploaded_bg_file.read().decode("utf-8")
                st.success(f"✅ Professional background loaded from: {uploaded_bg_file.name}")
                with st.expander("Preview uploaded content"):
                    st.text_area("Content:", professional_background_content, height=150, disabled=True)
            except Exception as e:
                st.error(f"Error reading file: {e}")
                
    elif bg_input_method == "Use default file" and default_professional_background:
        professional_background_content = default_professional_background
        st.success("✅ Using default professional background file.")
        with st.expander("Preview default content"):
            st.text_area("Content:", professional_background_content, height=150, disabled=True)
            
    elif bg_input_method == "Use default file" and not default_professional_background:
        st.warning("No default professional background file found. Please choose another option or proceed without it.")
        
    # Show status in sidebar
    with st.sidebar:
        st.subheader("📋 Application Status")
        st.write("**Job Description:**", "✅ Provided" if job_description else "❌ Missing")
        st.write("**Resume:**", "✅ Provided" if uploaded_resume or (resume_input_method == "Use default file" and default_resume_exists) else "❌ Missing")
        st.write("**Professional Background:**", 
                "✅ Provided" if professional_background_content else "⚪ Optional (proceeding without)")
        
        st.markdown("---")
        
        # File naming section
        st.subheader("📄 Output File Names")
        default_base = get_default_filename_base()
        
        resume_filename = st.text_input(
            "Resume PDF filename:",
            value=f"{default_base}_Resume.pdf",
            help="Name for the generated resume PDF file",
            key="resume_filename"
        )
        
        cover_letter_filename = st.text_input(
            "Cover Letter PDF filename:",
            value=f"{default_base}_CoverLetter.pdf", 
            help="Name for the generated cover letter PDF file",
            key="cover_letter_filename"
        )
        
        # Show preview of what will be used
        if resume_filename or cover_letter_filename:
            st.markdown("**Preview:**")
            if resume_filename:
                st.text(f"📄 {resume_filename}")
            if cover_letter_filename:
                st.text(f"📄 {cover_letter_filename}")

    # Initialize session state for generated files to prevent disappearing on download
    if 'generated_files' not in st.session_state:
        st.session_state.generated_files = {
            'resume_pdf_bytes': None,
            'cl_pdf_bytes': None,
            'gcs_resume_path': None,
            'gcs_cl_path': None,
            'resume_filename': None,
            'cl_filename': None
        }

    if st.button("✨ Generate Tailored Resume & Cover Letter", key="generate_button"):
        if not job_description:
            st.warning("Please paste the job description.")
        elif not uploaded_resume and resume_input_method == "Upload file": # Check if upload is selected but no file is uploaded
            st.warning("Please upload your resume.")
        elif resume_input_method == "Use default file" and not default_resume_exists:
             st.warning("Default resume file not found. Please upload a file instead.")
        elif not hasattr(CONFIG, 'GEMINI_API_KEY') or not CONFIG.GEMINI_API_KEY:
             st.error("Critical: GEMINI_API_KEY is missing. Cannot generate documents. Please check Streamlit secrets or config files.")
        else:
            # Determine which resume input to use
            resume_input_to_use = uploaded_resume if resume_input_method == "Upload file" else resume_path_to_use
            
            # Show what will be used
            if professional_background_content:
                st.info("🎯 Tailoring will use your professional background for enhanced customization.")
            else:
                st.info("📝 Proceeding without professional background - using only resume and job description.")
                
            with st.spinner("Processing... This may take a few minutes..."):
                result = run_tailoring_process(job_description, resume_input_to_use, professional_background_content, resume_filename, cover_letter_filename)
                # Initialize to ensure they exist even if result is None
                resume_pdf_bytes, cl_pdf_bytes, gcs_resume_path, gcs_cl_path = None, None, None, None

                if result is not None:
                    resume_pdf_bytes, cl_pdf_bytes, gcs_resume_path, gcs_cl_path = result
                    
                    # Store in session state to prevent disappearing on download
                    st.session_state.generated_files.update({
                        'resume_pdf_bytes': resume_pdf_bytes,
                        'cl_pdf_bytes': cl_pdf_bytes,
                        'gcs_resume_path': gcs_resume_path,
                        'gcs_cl_path': gcs_cl_path,
                        'resume_filename': resume_filename,
                        'cl_filename': cover_letter_filename
                    })

    # Use files from session state (either just generated or previously generated)
    resume_pdf_bytes = st.session_state.generated_files.get('resume_pdf_bytes')
    cl_pdf_bytes = st.session_state.generated_files.get('cl_pdf_bytes')
    gcs_resume_path = st.session_state.generated_files.get('gcs_resume_path')
    gcs_cl_path = st.session_state.generated_files.get('gcs_cl_path')
    stored_resume_filename = st.session_state.generated_files.get('resume_filename', 'Tailored_Resume.pdf')
    stored_cl_filename = st.session_state.generated_files.get('cl_filename', 'Generated_Cover_Letter.pdf')

    if resume_pdf_bytes: 
        st.success("🎉 Successfully generated tailored resume!")
        if cl_pdf_bytes:
            st.success("🎉 Cover letter also generated!")
        else:
             st.warning("Tailored resume generated, but cover letter PDF was not created (possibly due to CL text generation failure or empty text).")

        st.subheader("⬇️ Download Your Documents")
        col1, col2 = st.columns([2,2])

        with col1:
            st.download_button(
                label="Download Tailored Resume (PDF)",
                data=resume_pdf_bytes,
                file_name=stored_resume_filename,
                mime="application/pdf",
                key="download_resume_pdf"
            )
            if gcs_resume_path:
                st.info(f"Resume also uploaded to GCS: {gcs_resume_path}")
        
        if cl_pdf_bytes:
            with col2:
                st.download_button(
                    label="Download Cover Letter (PDF)",
                    data=cl_pdf_bytes,
                    file_name=stored_cl_filename,
                    mime="application/pdf",
                    key="download_cl_pdf"
                )
                if gcs_cl_path:
                    st.info(f"Cover Letter also uploaded to GCS: {gcs_cl_path}")
        else:
            with col2:
                 st.empty()
        
        # Add a clear button to reset generated files
        if st.button("🗑️ Clear Generated Files", key="clear_files"):
            st.session_state.generated_files = {
                'resume_pdf_bytes': None,
                'cl_pdf_bytes': None,
                'gcs_resume_path': None,
                'gcs_cl_path': None,
                'resume_filename': None,
                'cl_filename': None
            }
            st.rerun()

    elif 'generated_files' in st.session_state and st.session_state.generated_files.get('resume_pdf_bytes') is None:
        # Only show this message if we haven't generated anything yet
        pass

    st.markdown("---")
    # st.markdown("Developed with care.")