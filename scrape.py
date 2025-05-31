# Resume_Tailoring/Scrapping/scrape.py

import sys # Moved to top
import os  # Moved to top

project_root = os.path.abspath(os.path.dirname(__file__))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# At the top of scrape.py or within a relevant class
import datetime

CURRENT_DAY_TRACKER = datetime.date.today()
DAILY_RUN_COUNTER = 0 # Initialize to 0 as per your 12:05 comment

import requests
from bs4 import BeautifulSoup
import json
import time
import schedule # For running tasks periodically
import logging
import re

import random # Added for random delays
import datetime # For email subject line
from typing import Optional, Dict, Tuple, List # Added List here
from urllib.parse import urlparse # For checking domains

# Selenium specific imports (for Jobright)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, ElementClickInterceptedException
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.core.os_manager import ChromeType # For specifying chromium

# --- Logging Configuration (Setup early) ---
LOG_FILE_SCRAPER = "combined_job_scraper.log"
log_dir_path = os.path.join(project_root, "logs")
if os.path.exists(log_dir_path):
    LOG_FILE_SCRAPER = os.path.join(log_dir_path, "combined_job_scraper.log")
else:
    LOG_FILE_SCRAPER = os.path.join(os.path.dirname(__file__), "combined_job_scraper.log")


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_SCRAPER, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("webdriver_manager").setLevel(logging.WARNING)
logging.info(f"Scraper logging configured. Log file: {LOG_FILE_SCRAPER}")
logging.info(f"Project root for imports: {project_root}")
logging.info(f"Current sys.path: {sys.path}")

# SET WebDriver Manager logger to DEBUG specifically
wdm_logger = logging.getLogger("webdriver_manager")
wdm_logger.setLevel(logging.DEBUG)

# Set other verbose loggers to WARNING if you prefer
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

logging.info(f"Scraper logging configured. Log file: {LOG_FILE_SCRAPER}")
# --- Resume Tailoring Project Imports ---
app_config = None
try:
    import config as app_config # Changed from 'from .. import config'
    logging.info("Successfully imported app_config.")
except ImportError as e:
    logging.error(f"CRITICAL: Could not import app_config: {e}. sys.path: {sys.path}", exc_info=True)

TAILORING_MODULES_LOADED = False
OrchestratorAgent, GeminiClient, generate_styled_resume_pdf, generate_cover_letter_pdf, send_job_application_email, extract_tailored_data_for_resume_pdf = None, None, None, None, None, None
try:
    from agents.orchestrator import OrchestratorAgent
    from utils.llm_gemini import GeminiClient
    from src.docx_to_pdf_generator import generate_styled_resume_pdf, generate_cover_letter_pdf
    from utils.email_sender import send_job_application_email
    # THIS IMPORT:
    from src.data_parser_for_pdf import extract_tailored_data_for_resume_pdf # <--- Ensure this matches the function name
    TAILORING_MODULES_LOADED = True
    logging.info("Successfully imported all tailoring modules.")
except ImportError as e:
    logging.error(f"Failed to import one or more Resume_Tailoring modules: {e}. sys.path: {sys.path}", exc_info=True)
    # Reset all to None if any fails
    OrchestratorAgent, GeminiClient, generate_styled_resume_pdf, generate_cover_letter_pdf, send_job_application_email, extract_tailored_data_for_resume_pdf = None, None, None, None, None, None
try:
    from utils.gcs_utils import get_gcs_client, upload_file_to_gcs
    GCP_UTILS_LOADED = True
    logging.info("Successfully imported gcp_utils.")
except ImportError as e_gcp:
    GCP_UTILS_LOADED = False
    get_gcs_client, upload_file_to_gcs = None, None # Define them as None
    logging.error(f"Failed to import gcp_utils: {e_gcp}. GCS uploads will be skipped.", exc_info=True)
# --- Configuration Values (with fallbacks if app_config failed or is None) ---
USER_AGENT = getattr(app_config, "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
JOBRIGHT_URL = getattr(app_config, "JOBRIGHT_URL", "https://jobright.ai/")
JOBRIGHT_RECOMMEND_URL = getattr(app_config, "JOBRIGHT_RECOMMEND_URL", "https://jobright.ai/jobs/recommend")

JOBRIGHT_USERNAME_GLOBAL = os.getenv("JOBRIGHT_USERNAME") or getattr(app_config, "JOBRIGHT_USERNAME_FALLBACK", None)
JOBRIGHT_PASSWORD_GLOBAL = os.getenv("JOBRIGHT_PASSWORD") or getattr(app_config, "JOBRIGHT_PASSWORD_FALLBACK", None)

USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL = None
if app_config and hasattr(app_config, 'PROJECT_ROOT') and hasattr(app_config, 'JOBRIGHT_PROFILE_DIR_RELATIVE'):
    base_path_for_profile = app_config.PROJECT_ROOT
    relative_path_from_config = app_config.JOBRIGHT_PROFILE_DIR_RELATIVE
    if base_path_for_profile and relative_path_from_config:
        USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL = os.path.abspath(os.path.join(base_path_for_profile, relative_path_from_config))
        logging.info(f"Jobright profile path from app_config.PROJECT_ROOT: {USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL}")

if not USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL:
    USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL = os.path.abspath(os.path.join(project_root, "Scrapping", "chrome_jobright_profile"))
    logging.warning(f"Jobright profile path derived from app_config was not valid or app_config not loaded. Using fallback relative to project_root: {USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL}")

if USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL:
    try:
        os.makedirs(USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL, exist_ok=True)
        logging.info(f"Ensured Jobright profile directory exists: {USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL}")
    except OSError as e:
        logging.error(f"Could not create Jobright profile directory {USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL}: {e}. Jobright may fail if profile is needed.")
        USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL = None
else:
    logging.warning("Jobright profile directory is not set. Jobright will run with a temporary profile.")


SCRAPER_CONFIGS = getattr(app_config, "SCRAPER_CONFIGS", [
    {
        "platform": "linkedin",
        "url": "https://www.linkedin.com/jobs/search/?keywords=Machine%20Learning%20Engineer&location=United%20States&geoId=103644278&f_TPR=r3600&f_E=1%2C2%2C3&position=1&pageNum=0",
        "search_name": "Machine Learning Engineer (LinkedIn - USA, Last 1h)"
    },
    {
        "platform": "linkedin",
        "url": "https://www.linkedin.com/jobs/search/?keywords=Data%20Scientist&location=United%20States&geoId=103644278&f_TPR=r3600&f_E=1%2C2%2C3&position=1&pageNum=0",
        "search_name": "Data Scientist (LinkedIn - USA, Last 1h)"
    },
    {
        "platform": "jobright",
        "search_name": "Jobright Recommended Jobs",
        "target_job_count": 10,
    }
])
for cfg in SCRAPER_CONFIGS:
    if cfg.get("platform") == "jobright":
        cfg["profile_dir"] = USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL
        cfg["username"] = JOBRIGHT_USERNAME_GLOBAL
        cfg["password"] = JOBRIGHT_PASSWORD_GLOBAL


LI_JOB_LIST_SELECTOR = getattr(app_config, "LI_JOB_LIST_SELECTOR", "ul.jobs-search__results-list")
LI_JOB_CARD_SELECTOR = getattr(app_config, "LI_JOB_CARD_SELECTOR", "li")
LI_JOB_TITLE_SELECTOR = getattr(app_config, "LI_JOB_TITLE_SELECTOR", "h3.base-search-card__title")
LI_JOB_URL_SELECTOR = getattr(app_config, "LI_JOB_URL_SELECTOR", "a.base-card__full-link")
LI_JOB_ID_ELEMENT_SELECTOR = getattr(app_config, "LI_JOB_ID_ELEMENT_SELECTOR", "div.base-search-card")
LI_JOB_ID_ATTRIBUTE = getattr(app_config, "LI_JOB_ID_ATTRIBUTE", "data-entity-urn")

RELEVANT_JOB_KEYWORDS = getattr(app_config, "RELEVANT_JOB_KEYWORDS", ["data scientist", "machine learning", "ml engineer", "ai engineer"]) # Simplified for brevity
SOFTWARE_ENGINEER_TERMS = getattr(app_config, "SOFTWARE_ENGINEER_TERMS", ["software engineer", "sde"])
AI_ML_DATA_MODIFIERS_FOR_SE_TITLE = getattr(app_config, "AI_ML_DATA_MODIFIERS_FOR_SE_TITLE", ["ai", "ml", "machine learning", "data"])
EXCLUDE_JOB_TITLE_FIELDS = getattr(app_config, "EXCLUDE_JOB_TITLE_FIELDS", ["frontend", "ui developer", "web developer"]) # Simplified
EXCLUDE_JOB_TITLE_SENIORITY = getattr(app_config, "EXCLUDE_JOB_TITLE_SENIORITY", ["lead", "principal", "director", "manager"]) # Simplified
EXCLUDE_JOB_SOURCES_DOMAINS = getattr(app_config, "EXCLUDE_JOB_SOURCES_DOMAINS", ["lensa.com", "dice.com", "ziprecruiter.com"]) # Simplified

DATA_DIR_FALLBACK = os.path.join(project_root, 'data_scraper_fallback')
DATA_DIR = getattr(app_config, "DATA_DIR", DATA_DIR_FALLBACK)

SCRAPED_JOBS_DATA_DIR_FALLBACK = os.path.join(DATA_DIR, "scraped_jobs")
SCRAPED_JOBS_DATA_DIR = getattr(app_config, "SCRAPED_JOBS_DATA_DIR", SCRAPED_JOBS_DATA_DIR_FALLBACK)

if not os.path.exists(SCRAPED_JOBS_DATA_DIR):
    try:
        os.makedirs(SCRAPED_JOBS_DATA_DIR, exist_ok=True)
        logging.info(f"Ensured scraped_jobs directory exists: {SCRAPED_JOBS_DATA_DIR}")
    except OSError as e:
        logging.error(f"Could not create SCRAPED_JOBS_DATA_DIR {SCRAPED_JOBS_DATA_DIR}: {e}")


CONSOLIDATED_ALL_JOBS_FILE = getattr(app_config, "SCRAPER_CONSOLIDATED_ALL_JOBS_FILE", os.path.join(SCRAPED_JOBS_DATA_DIR, "consolidated_all_jobs.json"))
CONSOLIDATED_RELEVANT_NEW_JOBS_FILE = getattr(app_config, "SCRAPER_CONSOLIDATED_RELEVANT_NEW_JOBS_FILE", os.path.join(SCRAPED_JOBS_DATA_DIR, "consolidated_relevant_new_jobs.json"))
SCHEDULE_INTERVAL_MINUTES = getattr(app_config, "SCRAPER_SCHEDULE_INTERVAL_MINUTES", 60)

# Configs for tailoring, fetched from app_config with fallbacks
DEFAULT_BASE_RESUME_PDF_PATH = getattr(app_config, "DEFAULT_BASE_RESUME_PDF_PATH", None) # Path to your base PDF resume (e.g., for parsing initially)
DEFAULT_MASTER_PROFILE_PATH = getattr(app_config, "DEFAULT_MASTER_PROFILE_PATH", None) # Path to your master profile text file
PREDEFINED_CONTACT_INFO = getattr(app_config, "PREDEFINED_CONTACT_INFO", {}) # Dict of contact info
PREDEFINED_EDUCATION_INFO = getattr(app_config, "PREDEFINED_EDUCATION_INFO", []) # List of dicts for education
DEFAULT_YOE = getattr(app_config, "DEFAULT_YOE", 4) # Your default years of experience
DEFAULT_FILENAME_KEYWORD = getattr(app_config, "DEFAULT_FILENAME_KEYWORD", "AI_Resume") # Base keyword for resume filenames
DEFAULT_PDF_OUTPUT_DIR_TAILORING = getattr(app_config, "DEFAULT_PDF_OUTPUT_DIR", None) # Output dir for tailored PDFs
# Check if Google Drive PDF generation service account is configured
PDF_GENERATOR_SERVICE_ACCOUNT_CONFIGURED = bool(getattr(app_config, 'SERVICE_ACCOUNT_JSON_CONTENT', None) and \
                                isinstance(getattr(app_config, 'SERVICE_ACCOUNT_JSON_CONTENT', None), str) and \
                                len(getattr(app_config, 'SERVICE_ACCOUNT_JSON_CONTENT', '').strip()) > 0)


llm_client_global = None
orchestrator_agent_global = None
tailoring_output_dir_global = None
import subprocess
import logging # Ensure logging is imported if you use platform_logger

# At the very top of your script or before Selenium operations
try:
    # Check chromium-browser version
    cp_browser = subprocess.run(['/usr/bin/chromium', '--version'], capture_output=True, text=True, check=False)
    logging.info(f"DIAGNOSTIC: Chromium Browser Version: {cp_browser.stdout.strip() if cp_browser.stdout else 'Not found or error'} (stderr: {cp_browser.stderr.strip() if cp_browser.stderr else ''})")

    # Check chromedriver version
    cp_driver = subprocess.run(['/usr/bin/chromedriver', '--version'], capture_output=True, text=True, check=False)
    logging.info(f"DIAGNOSTIC: Chromedriver Version: {cp_driver.stdout.strip() if cp_driver.stdout else 'Not found or error'} (stderr: {cp_driver.stderr.strip() if cp_driver.stderr else ''})")
except Exception as e_diag_version:
    logging.error(f"DIAGNOSTIC: Error getting browser/driver versions: {e_diag_version}")

def load_jobs_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        logging.info(f"Successfully loaded {len(jobs)} jobs from {filepath}")
        return jobs
    except FileNotFoundError:
        logging.info(f"Job data file {filepath} not found. Initializing with an empty list.")
        return []
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {filepath}. Initializing with an empty list.")
        return []

def save_jobs_to_file(filepath, jobs):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=4, ensure_ascii=False)
        logging.info(f"Successfully saved {len(jobs)} jobs to {filepath}")
    except IOError as e:
        logging.error(f"Could not save jobs to {filepath}: {e}")

def merge_and_deduplicate_jobs(old_jobs_list, new_jobs_list):
    merged_jobs_dict = {job['id']: job for job in old_jobs_list if job.get('id')}
    new_jobs_without_ids_or_duplicates = []
    for new_job in new_jobs_list:
        new_job_id = new_job.get('id')
        if new_job_id:
            merged_jobs_dict[new_job_id] = new_job
        else:
            logging.warning(f"New job encountered without an ID during merge: {new_job.get('detailed_title', 'Unknown Title')}")
            new_jobs_without_ids_or_duplicates.append(new_job)
    final_list = list(merged_jobs_dict.values()) + new_jobs_without_ids_or_duplicates
    return final_list

def parse_job_id_for_platform(raw_id_attribute_val, job_url, platform="unknown", title="", company=""):
    job_id = None
    id_source = "unknown_platform_id_logic"
    if platform == "linkedin":
        if raw_id_attribute_val and 'urn:li:jobPosting:' in raw_id_attribute_val:
            job_id = raw_id_attribute_val.split(':')[-1]
            id_source = 'linkedin_urn'
        elif raw_id_attribute_val and raw_id_attribute_val.isdigit() and len(raw_id_attribute_val) > 6:
            job_id = raw_id_attribute_val
            id_source = 'linkedin_attribute_direct_numeric'
        if not job_id and job_url and job_url != "N/A":
            match = re.search(r'currentJobId=(\d+)', job_url)
            if match: job_id = match.group(1); id_source = 'linkedin_url_currentJobId'
            if not match: match = re.search(r'view/(\d+)/', job_url)
            if match: job_id = match.group(1); id_source = 'linkedin_url_view_id'
            if not match:
                last_segment = job_url.split('?')[0].split('/')[-1]
                if last_segment.isdigit() and len(last_segment) > 8:
                     job_id = last_segment; id_source = 'linkedin_url_last_segment_numeric'
    elif platform == "jobright":
        if job_url and "jobright.ai/job/" in job_url:
            match = re.search(r'/job/([^/?#]+)', job_url)
            if match: job_id = f"jr_{match.group(1)}"; id_source = 'jobright_platform_url_id'
        if not job_id and raw_id_attribute_val:
            job_id = f"jr_dom_{str(raw_id_attribute_val)}"; id_source = 'jobright_dom_card_id'
    if not job_id and raw_id_attribute_val:
        if raw_id_attribute_val.isdigit() and len(raw_id_attribute_val) > 6:
            job_id = raw_id_attribute_val; id_source = 'generic_attribute_numeric'
        else: job_id = raw_id_attribute_val; id_source = 'generic_attribute_raw'
    if not job_id and job_url and job_url != "N/A":
        try:
            path_segments = job_url.split('?')[0].split('/')
            for segment in reversed(path_segments):
                if segment.isdigit() and len(segment) > 6: job_id = segment; id_source = 'generic_url_segment_numeric'; break
                if '-' in segment:
                    id_part = segment.split('-')[-1]
                    if id_part.isdigit() and len(id_part) > 6: job_id = id_part; id_source = 'generic_url_segment_slug'; break
        except Exception as e: logging.debug(f"Error in generic ID parsing from URL {job_url}: {e}")
    if not job_id:
        safe_title = re.sub(r'\W+', '_', title)[:30] if title and title != "N/A" else "notitle"
        safe_company = re.sub(r'\W+', '_', company)[:30] if company and company != "N/A" else "nocompany"
        url_hash = str(hash(job_url))[-6:] if job_url and job_url != "N/A" else "nourl"
        job_id = f"{platform[:3]}_{safe_company}_{safe_title}_{url_hash}"
        id_source = 'fallback_constructed_id'
        logging.warning(f"Could not parse a distinct job ID for platform '{platform}', URL '{job_url}', Title '{title}'. Using constructed fallback ID: {job_id}")
    return str(job_id), id_source

def parse_jobs_from_linkedin_search_page(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_jobs_list = []
    job_list_container = soup.select_one(LI_JOB_LIST_SELECTOR)
    if not job_list_container:
        job_list_container_check = soup.select_one('.jobs-search__results-list')
        if job_list_container_check: job_list_container = job_list_container_check
        else:
            logging.warning(f"No LinkedIn job list container found with selectors: '{LI_JOB_LIST_SELECTOR}' or '.jobs-search__results-list'. Page content might have changed or access is restricted.")
            if soup.title and "Sign In" in soup.title.string: logging.error("LinkedIn page requires Sign In.")
            return []
    job_cards = job_list_container.select(LI_JOB_CARD_SELECTOR) if job_list_container else []
    if not job_cards and job_list_container: job_cards = job_list_container.find_all('li', recursive=False)
    logging.info(f"Found {len(job_cards)} potential LinkedIn job cards.")
    for card_index, card in enumerate(job_cards):
        title_element = card.select_one(LI_JOB_TITLE_SELECTOR)
        url_element = card.select_one(LI_JOB_URL_SELECTOR)
        company_element_li = card.select_one('h4.base-search-card__subtitle a')
        if not company_element_li: company_element_li = card.select_one('h4.base-search-card__subtitle')
        title_from_search = title_element.get_text(strip=True) if title_element else "N/A"
        company_from_search = company_element_li.get_text(strip=True) if company_element_li else "N/A"
        job_page_url = url_element['href'] if url_element and url_element.has_attr('href') else "N/A"
        if job_page_url.startswith("/jobs/view/"):
            job_page_url = "https://www.linkedin.com" + job_page_url.split('?')[0]
        elif job_page_url.startswith("http") and "/jobs/view/" in job_page_url:
            job_page_url = job_page_url.split('?')[0]
        raw_id_attribute_val = None
        id_container_element = card.select_one(LI_JOB_ID_ELEMENT_SELECTOR) if LI_JOB_ID_ELEMENT_SELECTOR else card
        if id_container_element:
            if id_container_element.has_attr(LI_JOB_ID_ATTRIBUTE):
                raw_id_attribute_val = id_container_element.get(LI_JOB_ID_ATTRIBUTE)
            else:
                fallback_attrs = ['data-job-id', 'data-entity-urn', 'id']
                for attr in fallback_attrs:
                    if id_container_element.has_attr(attr):
                        raw_id_attribute_val = id_container_element.get(attr); break
                    elif card.has_attr(attr):
                        raw_id_attribute_val = card.get(attr); break
        job_id, id_source = parse_job_id_for_platform(raw_id_attribute_val, job_page_url, platform="linkedin", title=title_from_search, company=company_from_search)
        if title_from_search != "N/A" and job_page_url != "N/A" and job_page_url.startswith("http"):
            parsed_jobs_list.append({
                "id": job_id,
                "title_from_search": title_from_search,
                "company_from_search": company_from_search,
                "url": job_page_url,
                "id_source": id_source
            })
    logging.info(f"Parsed {len(parsed_jobs_list)} job summaries from LinkedIn search page.")
    return parsed_jobs_list

def extract_linkedin_job_page_details(job_url):
    logging.info(f"Fetching LinkedIn job page details: {job_url}")
    headers = {'User-Agent': USER_AGENT, 'Accept-Language': 'en-US,en;q=0.9'}
    details = {'detailed_title': 'N/A', 'company_name': 'N/A', 'description': 'N/A'}
    try:
        response = requests.get(job_url, headers=headers, timeout=25)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching LinkedIn job page {job_url}: {e}")
        details['description'] = f"Error fetching page: {e}"
        return details
    soup = BeautifulSoup(response.content, 'html.parser')
    title_selectors = [
        'h1.jobs-unified-top-card__job-title', 'h1.job-details-jobs-unified-top-card__job-title',
        '.top-card__title', 'h1'
    ]
    for selector in title_selectors:
        el = soup.select_one(selector)
        if el: details['detailed_title'] = el.get_text(strip=True); break
    company_selectors = [
        '.jobs-unified-top-card__company-name a', '.jobs-unified-top-card__company-name',
        '.job-details-jobs-unified-top-card__company-name a', '.job-details-jobs-unified-top-card__company-name',
        '.topcard__org-name-link', '.sub-nav-cta__meta-text'
    ]
    for selector in company_selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True): details['company_name'] = el.get_text(strip=True); break
    desc_selectors_options = [
        lambda s: s.select_one('div.jobs-description__content div.jobs-box__html-content'),
        lambda s: s.select_one('div.show-more-less-html__markup'),
        lambda s: s.select_one('article.jobs-description__container'),
        lambda s: s.select_one('#job-details'),
        lambda s: s.find('section', attrs={'aria-label': re.compile(r'Job description', re.I)})
    ]
    for func in desc_selectors_options:
        el = func(soup)
        if el:
            for btn_sel in ['button.show-more-less-html__button--more', 'button.show-more-less-html__button--less', '.jobs-description__footer button']:
                for btn in el.select(btn_sel): btn.decompose()
            details['description'] = el.get_text(separator='\n', strip=True)
            if len(details['description']) > 50: break
    if details['description'] == 'N/A' and soup.title and ("Sign In" in soup.title.string or "Authwall" in soup.title.string):
        details['description'] = "Access to LinkedIn job page possibly blocked/requires login."
        logging.warning(f"LinkedIn job page for {job_url} likely requires login or is behind an authwall.")
    return details


# In Resume_Tailoring/Scrapping/scrape.py




# THIS IS THE NEW FUNCTION TO REPLACE THE OLD scrape_jobright_platform

def scrape_jobright_platform(scraper_cfg, platform_logger, seen_job_ids_globally):
    platform_logger.info(f"Jobright: Starting scraping for: {scraper_cfg.get('search_name')}")

    jr_username = scraper_cfg.get("username") # This is how you get it from config
    jr_password = scraper_cfg.get("password")
    jr_profile_dir = scraper_cfg.get("profile_dir") # This is USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL from your config
    target_job_count = scraper_cfg.get("target_job_count", 10)
    newly_detailed_jobs_for_jobright = []

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument("--window-size=1920,1080")

    # --- TEMPORARY DIAGNOSTIC STEP: Run WITHOUT the persistent user profile ---
    # This helps rule out profile corruption or permission issues with the profile directory.
    platform_logger.warning("Jobright: DIAGNOSTIC - Running WITHOUT user-data-dir for this attempt.")
    if jr_profile_dir and os.path.isabs(jr_profile_dir):
        options.add_argument(f"user-data-dir={jr_profile_dir}")
        platform_logger.info(f"Jobright: Using Chrome profile directory: {jr_profile_dir}")
    else:
        platform_logger.warning(f"Jobright: Profile directory '{jr_profile_dir}' is not configured or not absolute. Using temporary profile.")
    # --- END TEMPORARY DIAGNOSTIC STEP ---

    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")  # Highly recommended for headless and stability
    options.add_argument('--no-sandbox')   # Essential for server/container environments
    options.add_argument('--disable-dev-shm-usage') # Crucial for resource-constrained environments
    
    # Enable verbose logging for Chromium browser itself.
    # These logs usually go to stderr or a standard log location like /tmp/chrome_debug.log
    options.add_argument('--enable-logging')
    options.add_argument('--v=1') # For verbosity level 1

    # Ensure Selenium knows where the browser executable is (installed by apt)
    options.binary_location = "/usr/bin/chromium"

    driver = None
    # Define a path for chromedriver service log for easier retrieval
    chromedriver_log_path = "/tmp/chromedriver_service.log" # Using /tmp which is usually writable

    try:
        # --- CRITICAL for Docker ---
        # The driver installed by 'apt install chromium-driver' is usually at /usr/bin/chromedriver
        chromedriver_path = "/usr/bin/chromedriver"
        # --- END CRITICAL ---
        
        platform_logger.info(f"Jobright: Using system-installed chromedriver from apt, expected at {chromedriver_path}")
        #service = ChromeService(executable_path=chromedriver_path)
        service_args = ['--verbose'] # This will send chromedriver logs to stderr
        service = ChromeService(
            executable_path=chromedriver_path,
            service_args=service_args
        )
        driver = webdriver.Chrome(service=service, options=options)
        # Wait times from user's working standalone script
        wait = WebDriverWait(driver, 15)
        short_wait = WebDriverWait(driver, 7) 
        very_short_wait = WebDriverWait(driver, 3)

        platform_logger.info(f"Jobright: Navigating to {JOBRIGHT_URL} to check login status...") # JOBRIGHT_URL from scrape.py globals
        driver.get(JOBRIGHT_URL)
        time.sleep(3) 
        main_signin_modal_trigger_button_selector = (By.XPATH, "//span[normalize-space()='SIGN IN' and contains(@class, 'index_text__wh4pg') and contains(@class, 'css-w9mjmz')]")
        #main_signin_modal_trigger_button_selector = (By.XPATH, "//span[normalize-space()='SIGN IN' and contains(@class, 'index_text__wh4pg') and contains(@class, 'css-3l591y')]")
        needs_login = False

        try:
            platform_logger.debug("Jobright: Checking for main 'SIGN IN' modal trigger button...")
            very_short_wait.until(EC.visibility_of_element_located(main_signin_modal_trigger_button_selector))
            platform_logger.info("Jobright: 'SIGN IN' modal trigger button found. Login required.")
            needs_login = True
        except TimeoutException:
            platform_logger.info("Jobright: 'SIGN IN' modal trigger button NOT found. Attempting to load recommendations.")
            driver.get(JOBRIGHT_RECOMMEND_URL) # JOBRIGHT_RECOMMEND_URL from scrape.py globals
            time.sleep(2) 
            if "/login" in driver.current_url.lower() or "/auth" in driver.current_url.lower():
                platform_logger.info(f"Jobright: Redirected to login page ({driver.current_url}). Login required.")
                needs_login = True
                driver.get(JOBRIGHT_URL) 
                time.sleep(1)
            else:
                try:
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "index_job-card__AsPKC")))
                    platform_logger.info("Jobright: Successfully on recommendations page with job cards. Already logged in.")
                except TimeoutException:
                    platform_logger.warning("Jobright: Could not confirm job cards on recommendations page. Assuming login required.")
                    needs_login = True
                    driver.get(JOBRIGHT_URL) 
                    time.sleep(1)
        
        if needs_login:
            if not jr_username or not jr_password:
                platform_logger.critical("Jobright: Username or Password not available in config. Login cannot proceed.")
                return [] # Critical failure
            platform_logger.info("Jobright: Performing login...")
            try:
                # Ensure on main page if login modal is triggered from there
                if JOBRIGHT_URL not in driver.current_url:
                    driver.get(JOBRIGHT_URL)
                    short_wait.until(EC.url_to_be(JOBRIGHT_URL)) # Wait for navigation
                
                main_signin_button = wait.until(EC.element_to_be_clickable(main_signin_modal_trigger_button_selector))
                main_signin_button.click()
                modal_email_field_selector = (By.ID, "basic_email")
                email_input = wait.until(EC.visibility_of_element_located(modal_email_field_selector))
                password_input = driver.find_element(By.ID, "basic_password")
                # Using the specific modal sign-in button from user's script
                modal_signin_button = driver.find_element(By.XPATH, "//button[contains(@class, 'index_sign-in-button__jjge4')]")
                
                email_input.send_keys(jr_username)
                password_input.send_keys(jr_password)
                time.sleep(0.3) # Small pause before click
                modal_signin_button.click()
                platform_logger.info("Jobright: Login attempt submitted.")
                wait.until(EC.url_contains("/jobs/recommend")) 
                platform_logger.info("Jobright: Login successful, navigated to recommendations page.")
            except Exception as e_login:
                platform_logger.error(f"Jobright: Error during login process: {e_login}", exc_info=True)
                if driver: driver.save_screenshot(os.path.join(project_root, "screenshots_scraper", f"{scraper_cfg.get('search_name', 'jobright_login_error').replace(' ', '_')}_login_failure.png"))
                return [] # Stop if login fails
        
        if "/jobs/recommend" not in driver.current_url.lower(): # Ensure .lower() for case-insensitivity
            platform_logger.info(f"Jobright: Not on recommendations page. Current URL: {driver.current_url}. Navigating...")
            driver.get(JOBRIGHT_RECOMMEND_URL)
            # Wait for URL to actually be the recommendations page
            try:
                wait.until(EC.url_contains("/jobs/recommend"))
            except TimeoutException:
                platform_logger.error(f"Jobright: Failed to navigate to recommendations page. Current URL: {driver.current_url}")
                return []
            time.sleep(2.5) # User script's sleep

        initial_modal_close_button_selector = (By.CSS_SELECTOR, "button.ant-modal-close[aria-label='Close']")
        try:
            platform_logger.debug("Jobright: Checking for an initial general modal to close...")
            initial_close_button = WebDriverWait(driver, 5).until( # Using 5s wait from user script
                EC.element_to_be_clickable(initial_modal_close_button_selector)
            )
            platform_logger.info("Jobright: Initial modal close button found. Attempting to click via JS...")
            driver.execute_script("arguments[0].click();", initial_close_button)
            WebDriverWait(driver, 5).until( # Using 5s wait
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.ant-modal-wrap")) # User script's selector
            )
            platform_logger.info("Jobright: Initial modal likely closed.")
            time.sleep(1) 
        except TimeoutException:
            platform_logger.info("Jobright: No initial modal found or it did not close as expected. Continuing...")
        except Exception as e_initial_modal:
            platform_logger.error(f"Jobright: Error trying to close initial modal: {e_initial_modal}", exc_info=True)

        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "index_job-card__AsPKC")))
            platform_logger.info("Jobright: Job cards are confirmed present on the recommendations page.")
        except TimeoutException:
            platform_logger.critical("Jobright: Job cards NOT found on recommendations page. Check page state.")
            if driver: driver.save_screenshot(os.path.join(project_root, "screenshots_scraper",f"{scraper_cfg.get('search_name', 'jobright_no_cards').replace(' ', '_')}_no_cards.png"))
            return []

        platform_logger.info(f"Jobright: Attempting to load up to {target_job_count} job cards...")
        job_card_locator = (By.CLASS_NAME, "index_job-card__AsPKC")
        
        # Scrolling logic from user's script (max 3 scrolls after initial load)
        for scroll_attempt_user in range(4): # initial load + 3 scrolls = 4 checks
            current_card_elements = driver.find_elements(*job_card_locator)
            if len(current_card_elements) >= target_job_count:
                platform_logger.info(f"Jobright: Found {len(current_card_elements)} cards. Target met.")
                break
            if scroll_attempt_user < 3: # Only scroll 3 times
                platform_logger.debug(f"Jobright: Scrolling attempt {scroll_attempt_user + 1}/3 to load more cards...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3) # User script's sleep
                # Check if new cards were loaded
                if len(driver.find_elements(*job_card_locator)) == len(current_card_elements) and len(current_card_elements) > 0 :
                    platform_logger.info("Jobright: No new cards loaded by scroll. Stopping scroll.")
                    break
            else:
                platform_logger.info(f"Jobright: Max scroll attempts reached. Proceeding with {len(current_card_elements)} cards.")

        all_job_card_elements_on_page = driver.find_elements(*job_card_locator)
        if not all_job_card_elements_on_page:
            platform_logger.warning("Jobright: No job cards found after scrolling. Returning empty list.")
            return []
            
        job_card_elements_to_process_count = min(len(all_job_card_elements_on_page), target_job_count)
        platform_logger.info(f"Jobright: Processing details for {job_card_elements_to_process_count} job cards...")
        
        # Selectors for detail pane from user script
        job_detail_specific_close_button_selector = (By.XPATH, "//img[@alt='close detail']") 
        job_detail_pane_selector = (By.CLASS_NAME, "index_jobIntroduction__iafCp")
        
        # Helper for detail extraction (nested to use local 'short_wait' and 'platform_logger')
        def extract_section_details_nested(section_name_for_xpath, current_job_id):
            items = []
            # Scoped XPath from user script
            header_xpath = f"//div[contains(@class,'index_jobIntroduction__iafCp')]//h2[normalize-space()='{section_name_for_xpath}']"
            try:
                # Using short_wait as in user script's helper
                header = short_wait.until(EC.presence_of_element_located((By.XPATH, header_xpath)))
                section_container = header.find_element(By.XPATH, "./ancestor::section[contains(@class, 'index_sectionContent__zTR73')] | ./ancestor::div[contains(@class, 'index_sectionContent__zTR73')][1]")
                item_elements = section_container.find_elements(By.XPATH, ".//div[contains(@class, 'index_text-row__L_prl')]/span[contains(@class, 'index_listText__ENCyh')] | .//li")
                for elem in item_elements: items.append(elem.text.strip())
            except TimeoutException:
                platform_logger.debug(f"Jobright:    '{section_name_for_xpath}' section header not found for {current_job_id}.")
            except Exception as e_section_extract:
                platform_logger.warning(f"Jobright:    Error extracting '{section_name_for_xpath}' for {current_job_id}: {e_section_extract}")
            return items

        for i in range(job_card_elements_to_process_count):
            platform_logger.info(f"Jobright: ---- Card Loop Iteration {i+1}/{job_card_elements_to_process_count} ----")
            job_id_from_card_attr = "N/A" # From card's 'id' attribute
            
            # Re-fetch card list for freshness, as in user script
            current_cards_in_dom_loop = driver.find_elements(*job_card_locator) 
            if i >= len(current_cards_in_dom_loop):
                platform_logger.warning(f"Jobright: Card index {i} out of bounds after re-fetch. Stopping.")
                break
            card_to_click = current_cards_in_dom_loop[i]
            
            try:
                job_id_from_card_attr = card_to_click.get_attribute('id') or f"no_id_card_idx_{i}"
                # Your original scrape.py used a processed_card_dom_ids set. If you re-introduce that,
                # check here: if job_id_from_card_attr in processed_card_dom_ids: continue
                platform_logger.info(f"Jobright: Attempting to click job card (DOM ID: {job_id_from_card_attr})...")
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", card_to_click)
                time.sleep(0.5) # User script's sleep
                
                clickable_card_element = wait.until(EC.element_to_be_clickable(card_to_click))
                clickable_card_element.click()
                platform_logger.info(f"Jobright: Card clicked. Waiting for detail pane to update...")

                try:
                    short_wait.until(EC.visibility_of_element_located(job_detail_pane_selector))
                    platform_logger.info("Jobright: Detail pane appears to be loaded.")
                    time.sleep(2) # User script's sleep
                except TimeoutException:
                    platform_logger.warning(f"Jobright: Detail pane indicator did not appear for card {job_id_from_card_attr}. Skipping job.")
                    try: ActionChains(driver).send_keys(Keys.ESCAPE).perform(); time.sleep(0.5)
                    except: pass
                    continue 
                
                # --- Detail Extraction (Exact logic from user script) ---
                job_title_detail, company_name_detail, full_description = "Not found", "Not found", "Detailed description could not be extracted."
                try:
                    title_el_detail = short_wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.index_jobIntroduction__iafCp h1.index_job-title__sStdA")))
                    job_title_detail = title_el_detail.text.strip()
                except: platform_logger.warning(f"Jobright:    Title not found in detail pane for {job_id_from_card_attr}.")
                try:
                    company_el_detail = short_wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.index_jobIntroduction__iafCp h2.index_company-row__vOzgg strong")))
                    company_name_detail = company_el_detail.text.strip()
                except: platform_logger.warning(f"Jobright:    Company name not found in detail pane for {job_id_from_card_attr}.")
                
                overview_description = ""
                try:
                    overview_el_candidates = driver.find_elements(By.CSS_SELECTOR, "div.index_jobContentBrief__dWTPw p.index_company-summary__8nWbU")
                    if overview_el_candidates and overview_el_candidates[0].is_displayed():
                        overview_description = overview_el_candidates[0].text.strip()
                    # No else, as user script didn't log if not found here explicitly
                except Exception as e_overview:
                     platform_logger.warning(f"Jobright:    Error extracting overview for {job_id_from_card_attr}: {e_overview}")

                responsibilities_texts = extract_section_details_nested("Responsibilities", job_id_from_card_attr)
                qualifications_texts = extract_section_details_nested("Qualification", job_id_from_card_attr)
                benefits_texts = extract_section_details_nested("Benefits", job_id_from_card_attr)
                
                full_description_parts = []
                # Using formatting from user's script
                if overview_description and overview_description not in ["Not found", ""]:
                     full_description_parts.append(overview_description)
                if responsibilities_texts: full_description_parts.append("\nResponsibilities:\n" + "\n".join(responsibilities_texts))
                if qualifications_texts: full_description_parts.append("\nQualifications:\n" + "\n".join(qualifications_texts))
                if benefits_texts: full_description_parts.append("\nBenefits:\n" + "\n".join(benefits_texts))
                
                full_description = "\n\n".join(filter(None, full_description_parts)).strip()
                if not full_description: # Fallback from user script
                    full_description = "Detailed description could not be extracted."
                # --- End of Detail Extraction ---

                # Construct job URL for ID parsing and output (can be refined)
                # The user script didn't extract a specific apply URL from the pane.
                # This constructed URL is for internal tracking and ID generation.
                constructed_job_url = f"{JOBRIGHT_RECOMMEND_URL}#card_id_{job_id_from_card_attr}"

                stable_job_id, id_source_val = parse_job_id_for_platform(
                    raw_id_attribute_val=job_id_from_card_attr, # Using the card's DOM ID as raw
                    job_url=constructed_job_url, 
                    platform="jobright",
                    title=job_title_detail if job_title_detail != "Not found" else "Unknown Title", 
                    company=company_name_detail if company_name_detail != "Not found" else "Unknown Company"
                )

                if stable_job_id in seen_job_ids_globally:
                    platform_logger.info(f"Jobright: Job ID {stable_job_id} (Title: {job_title_detail}) already seen globally. Skipping.")
                    # Still need to close the pane
                else:
                    # Prepare job_data for the main application
                    job_data = {
                        'id': stable_job_id,
                        'title_from_search': job_title_detail, # Jobright doesn't have separate search title here
                        'detailed_title': job_title_detail,
                        'company_name': company_name_detail,
                        'location': "N/A", # Not extracted by user's script
                        'description': full_description,
                        'url': constructed_job_url, # Primary URL
                        'external_apply_url': "N/A", # Not extracted by user's script, original scrape.py might expect it
                        'jobright_internal_url': constructed_job_url,
                        'id_source': id_source_val,
                        'source_platform': "jobright",
                        'search_source_name': scraper_cfg.get("search_name", "Jobright Recommended Jobs"),
                        'scraped_timestamp': datetime.datetime.utcnow().isoformat()
                    }
                    
                    if len(job_data['description']) > 50 and job_data['description'] != "Detailed description could not be extracted.":
                        newly_detailed_jobs_for_jobright.append(job_data)
                        platform_logger.info(f"Jobright: **** NEW Job Processed & Added **** '{job_title_detail}' at '{company_name_detail}', ID: {stable_job_id}")
                        # seen_job_ids_globally.add(stable_job_id) # This is done in the calling function run_all_scrapers_and_process
                    else:
                        platform_logger.warning(f"Jobright: Job '{job_title_detail}' (ID: {stable_job_id}) processed but description too short or default. Not added. Desc: '{job_data['description'][:100]}...'")


                # --- Close the JOB SPECIFIC detail pane (Exact logic from user script) ---
                closed_job_detail_successfully = False
                try:
                    platform_logger.debug(f"Jobright: Attempting to close job detail pane (JS click) for card ID: {job_id_from_card_attr}...")
                    job_close_button = wait.until(EC.element_to_be_clickable(job_detail_specific_close_button_selector))
                    driver.execute_script("arguments[0].click();", job_close_button)
                    platform_logger.debug(f"Jobright: Job detail pane 'X' button JS click attempted.")
                    wait.until(EC.invisibility_of_element_located(job_detail_pane_selector))
                    platform_logger.info(f"Jobright: Job detail pane confirmed closed for card ID: {job_id_from_card_attr}.")
                    closed_job_detail_successfully = True
                except TimeoutException:
                    platform_logger.warning(f"Jobright: Job detail pane did not become invisible or 'X' not clickable for {job_id_from_card_attr}.")
                except Exception as e_job_close:
                     platform_logger.error(f"Jobright: Error during JS click on job detail 'X' button for {job_id_from_card_attr}: {e_job_close}", exc_info=True)

                if not closed_job_detail_successfully:
                    try:
                        platform_logger.info(f"Jobright: Job detail 'X' close failed for {job_id_from_card_attr}. Trying ESCAPE key...")
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        wait.until(EC.invisibility_of_element_located(job_detail_pane_selector))
                        platform_logger.info(f"Jobright: Job detail pane confirmed closed via ESCAPE for card ID: {job_id_from_card_attr}.")
                    except: # Generic except as in user script
                        platform_logger.warning(f"Jobright: WARNING: Could not confirm closure of job detail pane for card {job_id_from_card_attr} after ESCAPE.")
                
                time.sleep(0.5) # Pause after closing as in user script

            except StaleElementReferenceException:
                platform_logger.warning(f"Jobright: StaleElementReferenceException for card at index {i}. Re-evaluating.")
                time.sleep(1); continue
            except ElementClickInterceptedException as e_intercept_card:
                 platform_logger.warning(f"Jobright: ElementClickInterceptedException clicking card {job_id_from_card_attr}: {str(e_intercept_card).splitlines()[0]}.")
                 try: ActionChains(driver).send_keys(Keys.ESCAPE).perform(); time.sleep(0.5) 
                 except: pass
                 continue 
            except Exception as e_card_processing:
                platform_logger.error(f"Jobright: Error processing card at index {i} (ID: {job_id_from_card_attr}): {e_card_processing}", exc_info=True)
                if driver: driver.save_screenshot(os.path.join(project_root, "screenshots_scraper", f"{scraper_cfg.get('search_name', 'jobright_card_error').replace(' ', '_')}_{job_id_from_card_attr}.png"))

        platform_logger.info(f"Jobright: Finished card processing loop. Found {len(newly_detailed_jobs_for_jobright)} new jobs this run.")
        return newly_detailed_jobs_for_jobright

    except Exception as e_main_jr:
        platform_logger.critical(f"Jobright: Major error in Jobright scraping function: {e_main_jr}", exc_info=True)
        
        # Attempt to read and print the chromedriver service log file
        platform_logger.info(f"Jobright: Attempting to read chromedriver service log from {chromedriver_log_path}")
        if os.path.exists(chromedriver_log_path):
            try:
                with open(chromedriver_log_path, "r") as log_f:
                    platform_logger.info(f"--- Chromedriver Service Log ({chromedriver_log_path}) ---")
                    # Read and log line by line to avoid one giant log message
                    for line in log_f:
                        platform_logger.info(line.strip())
                    platform_logger.info(f"--- End Chromedriver Service Log ---")
            except Exception as e_log:
                platform_logger.error(f"Jobright: Failed to read {chromedriver_log_path}: {e_log}")
        else:
            platform_logger.warning(f"Jobright: Chromedriver service log not found at {chromedriver_log_path}")
        
        # Your existing screenshot logic (might not work if driver didn't initialize)
        if driver: # Check if driver object was successfully created
            try:
                # project_root needs to be defined in this scope or passed, assuming it's global in your scrape.py
                screenshots_dir = os.path.join(project_root, "screenshots_scraper") 
                os.makedirs(screenshots_dir, exist_ok=True)
                screenshot_path_fname = f'{scraper_cfg.get("search_name", "jobright_error").replace(" ", "_")}_WebDriverError.png'
                full_screenshot_path = os.path.join(screenshots_dir, screenshot_path_fname)
                driver.save_screenshot(full_screenshot_path)
                platform_logger.info(f"Jobright: Screenshot of error state saved to {full_screenshot_path}")
            except Exception as e_screenshot:
                platform_logger.error(f"Jobright: Failed to save error screenshot (driver might not be fully working): {e_screenshot}")
        return [] # Return empty list or handle error as appropriate
    finally:
        if driver:
            platform_logger.info("Jobright: Closing browser.")
            driver.quit()
            platform_logger.info("Jobright: Browser closed.")
    
def process_linkedin_job_search(scraper_cfg, seen_job_ids_globally):
    search_url = scraper_cfg.get("url")
    search_name = scraper_cfg.get("search_name", "Unknown LinkedIn Search")
    if not search_url:
        logging.error(f"LINKEDIN: URL missing for search: {search_name}. Skipping.")
        return []
    logging.info(f"LINKEDIN: Starting search: {search_name} (URL: {search_url})")
    newly_detailed_jobs_for_linkedin = []
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"LINKEDIN: Failed to fetch search page for {search_name}: {e}")
        return []
    jobs_from_search_page = parse_jobs_from_linkedin_search_page(response.text)
    if not jobs_from_search_page:
        logging.warning(f"LINKEDIN: No job summaries parsed from {search_name}. Check selectors or page content.")
        return []
    logging.info(f"LINKEDIN: {search_name} - Found {len(jobs_from_search_page)} summaries. Checking against {len(seen_job_ids_globally)} globally seen jobs.")
    for job_summary in jobs_from_search_page:
        job_id = job_summary.get("id")
        job_page_url = job_summary.get("url")
        if job_id in seen_job_ids_globally:
            logging.debug(f"LINKEDIN: Job ID {job_id} (Title: {job_summary.get('title_from_search')}) already seen globally. Skipping.")
            continue
        job_data = {
            "id": job_id,
            "title_from_search": job_summary.get("title_from_search", "N/A"),
            "company_name": job_summary.get("company_from_search", "N/A"),
            "url": job_page_url,
            "id_source": job_summary.get("id_source", "N/A"),
            "source_platform": "linkedin",
            "search_source_name": search_name,
            "detailed_title": job_summary.get("title_from_search", "N/A"), # Will be updated
            "description": "N/A", # Will be updated
            'scraped_timestamp': datetime.datetime.utcnow().isoformat()
        }
        if job_page_url != "N/A" and job_page_url.startswith("http"):
            try:
                delay_seconds = random.uniform(3, 7)
                logging.debug(f"LINKEDIN: Waiting {delay_seconds:.2f}s for: {job_page_url}")
                time.sleep(delay_seconds)
                page_details = extract_linkedin_job_page_details(job_page_url)
                job_data.update(page_details) # This updates detailed_title, company_name (if better), and description
                # Ensure detailed_title and company_name fall back to search results if detail extraction fails for them
                if not job_data.get("detailed_title") or job_data.get("detailed_title") == "N/A":
                    job_data["detailed_title"] = job_summary.get("title_from_search", "N/A")
                if not job_data.get("company_name") or job_data.get("company_name") == "N/A":
                    job_data["company_name"] = job_summary.get("company_from_search", "N/A")

                newly_detailed_jobs_for_linkedin.append(job_data)
                logging.info(f"LINKEDIN: NEWLY PROCESSED: {job_data.get('detailed_title')} at {job_data.get('company_name')} (ID: {job_id}), URL: {job_page_url}")
            except Exception as e:
                logging.error(f"LINKEDIN: Error processing page {job_page_url} for job ID {job_id}: {e}", exc_info=True)
                job_data["description"] = f"Error processing page details: {e}" # Keep the error in desc
                newly_detailed_jobs_for_linkedin.append(job_data) # Still add the summary job with error
        else:
            logging.warning(f"LINKEDIN: Invalid URL for detail extraction: {job_page_url} for job ID {job_id}. Adding summary job.")
            newly_detailed_jobs_for_linkedin.append(job_data) # Add summary if URL is bad
    logging.info(f"LINKEDIN: Search {search_name} done. Found {len(newly_detailed_jobs_for_linkedin)} new detailed jobs this run.")
    return newly_detailed_jobs_for_linkedin
gcs_client_global = None

def initialize_tailoring_system():
    global llm_client_global, orchestrator_agent_global, tailoring_output_dir_global
    if not TAILORING_MODULES_LOADED:
        logging.error("Resume Tailoring modules are not loaded. Cannot initialize tailoring system.")
        return False
    if not app_config:
        logging.warning("app_config not loaded. Tailoring system paths will use fallbacks.")

    try:
        logging.info("Initializing Gemini LLM client for tailoring...")
        llm_client_global = GeminiClient() # Assumes GeminiClient() handles its own config (API key etc.)
        logging.info("Initializing OrchestratorAgent...")
        # Ensure OrchestratorAgent class is available (it's checked by TAILORING_MODULES_LOADED at top)
        orchestrator_agent_global = OrchestratorAgent(llm_client=llm_client_global)

        tailoring_output_dir_global = DEFAULT_PDF_OUTPUT_DIR_TAILORING # From app_config or None
        if not tailoring_output_dir_global:
            fallback_dir = os.path.join(project_root, "data_scraper_fallback", "tailored_outputs_scraper")
            tailoring_output_dir_global = fallback_dir
            logging.warning(f"DEFAULT_PDF_OUTPUT_DIR from app_config not found or empty, using fallback: {tailoring_output_dir_global}")

        os.makedirs(tailoring_output_dir_global, exist_ok=True)
        logging.info(f"Tailoring system initialized. PDFs will be saved to: {tailoring_output_dir_global}")
        # Check for PDF generator service account configuration for Google Drive
        if not PDF_GENERATOR_SERVICE_ACCOUNT_CONFIGURED:
            logging.warning("Google Drive SERVICE_ACCOUNT_FILE_PATH is NOT configured in app_config. PDF generation via Google Drive will fail or be skipped.")
        else:
            logging.info("Google Drive SERVICE_ACCOUNT_FILE_PATH is configured. PDF generation can proceed.")
        return True
    except Exception as e:
        logging.critical(f"Failed to initialize tailoring system: {e}", exc_info=True)
        return False

# In Resume_Tailoring/Scrapping/scrape.py

def run_tailoring_pipeline_for_job(job_details: Dict[str, any]) -> Optional[Dict[str, any]]:
    if not TAILORING_MODULES_LOADED or not orchestrator_agent_global or not OrchestratorAgent or not extract_tailored_data_for_resume_pdf:
        logging.error("Tailoring system not properly initialized or essential functions missing. Skipping tailoring.")
        return None

    logging.info(f"Running tailoring for job: '{job_details.get('detailed_title', 'N/A')}' at '{job_details.get('company_name', 'N/A')}' (ID: {job_details.get('id')})")
    jd_text = job_details.get("description")

    if not jd_text or not jd_text.strip() or len(jd_text.strip()) < 50:
        logging.warning(f"Job description is empty or too short for job ID {job_details.get('id')}. Skipping tailoring.")
        return None

    final_state = None  # Initialize final_state to None
    try:
        master_profile_content = None
        if DEFAULT_MASTER_PROFILE_PATH and os.path.exists(DEFAULT_MASTER_PROFILE_PATH):
            with open(DEFAULT_MASTER_PROFILE_PATH, 'r', encoding='utf-8') as f_mp:
                master_profile_content = f_mp.read()
            logging.info(f"Loaded master profile from: {DEFAULT_MASTER_PROFILE_PATH}")
        elif DEFAULT_MASTER_PROFILE_PATH:
             logging.warning(f"Master profile path configured ('{DEFAULT_MASTER_PROFILE_PATH}') but file not found.")
        else:
            logging.info(f"Master profile path not configured.")

        if not DEFAULT_BASE_RESUME_PDF_PATH or not os.path.exists(DEFAULT_BASE_RESUME_PDF_PATH):
            logging.error(f"Base resume PDF path for parsing not found or not configured: {DEFAULT_BASE_RESUME_PDF_PATH}. Cannot run tailoring for job ID {job_details.get('id')}.")
            return None
        else:
            current_resume_path_for_parsing = DEFAULT_BASE_RESUME_PDF_PATH

        logging.info(f"Calling OrchestratorAgent for job ID {job_details.get('id')}")
        final_state = orchestrator_agent_global.run( # This is your OrchestratorAgent class
            resume_pdf_path=current_resume_path_for_parsing,
            jd_txt_path=None, # jd_text is prioritized
            jd_text=jd_text,
            contact_info_for_cl=PREDEFINED_CONTACT_INFO, 
            master_profile_text=master_profile_content,
            company_name_for_cl=job_details.get("company_name")
        )
        logging.info(f"OrchestratorAgent returned for job ID {job_details.get('id')}. Final state object: {'Exists' if final_state else 'None'}")

        # More robust check for final_state and its tailored_resume attribute
        if not final_state:
            logging.error(f"OrchestratorAgent returned None (failed) for job ID {job_details.get('id')}.")
            return None
        
        if not hasattr(final_state, 'tailored_resume') or not final_state.tailored_resume:
            logging.error(f"OrchestratorAgent's final_state is missing 'tailored_resume' attribute or it's empty for job ID {job_details.get('id')}.")
            try:
                # Attempt to log the structure of final_state if it's not as expected
                logging.info(f"Debug: Content of final_state for job {job_details.get('id')}: {vars(final_state)}")
            except TypeError:
                logging.info(f"Debug: Content of final_state (could not get vars) for job {job_details.get('id')}: {final_state}")
            return None

        # Now it's safer to access final_state.tailored_resume
        tailored_resume_pydantic_model = final_state.tailored_resume
        
        # Ensure the model dump is happening correctly
        try:
            tailored_resume_dict_for_extraction = tailored_resume_pydantic_model.model_dump(exclude_none=True)
        except AttributeError: # Fallback for older Pydantic
            tailored_resume_dict_for_extraction = tailored_resume_pydantic_model.dict(exclude_none=True)
        except Exception as e_dump:
            logging.error(f"Could not dump tailored_resume_pydantic_model to dict for job ID {job_details.get('id')}: {e_dump}")
            return None
            
        if not tailored_resume_dict_for_extraction:
            logging.error(f"Pydantic model dump of tailored_resume resulted in None or empty for job ID {job_details.get('id')}")
            return None

        resume_data_for_pdf = extract_tailored_data_for_resume_pdf(tailored_resume_dict_for_extraction)
        
        if not resume_data_for_pdf:
             logging.error(f"Extracted resume data for PDF is None for job ID {job_details.get('id')}. Check extract_tailored_data_for_resume_pdf function.")
             return None

        company_safe = re.sub(r'\W+', '_', str(job_details.get("company_name", "UnknownCompany")))[:25].strip('_')
        title_safe = re.sub(r'\W+', '_', str(job_details.get("detailed_title", "UnknownTitle")))[:30].strip('_')
        company_safe = company_safe if company_safe else "UnknownCompany"
        title_safe = title_safe if title_safe else "UnknownTitle"

        filename_keyword_from_config = DEFAULT_FILENAME_KEYWORD
        # Construct a base for the filename, specific parts will be added by PDF generator
        base_filename_resume = f"Resume_{company_safe}_{title_safe}_{filename_keyword_from_config}"
        base_filename_cl = f"CoverLetter_{company_safe}_{title_safe}"


        if not tailoring_output_dir_global: # Should be set by initialize_tailoring_system
            logging.error("Tailoring output directory (tailoring_output_dir_global) not set. Cannot generate PDFs.")
            return None # Cannot proceed without output directory

        if not generate_styled_resume_pdf or not generate_cover_letter_pdf : # Check if functions were imported
            logging.error("PDF generation functions (generate_styled_resume_pdf or generate_cover_letter_pdf) are not available. Skipping PDF generation.")
            return None # Cannot proceed if PDF generation modules themselves are missing
        
        resume_pdf_path = None
        cover_letter_pdf_path = None

        if not PDF_GENERATOR_SERVICE_ACCOUNT_CONFIGURED: # Global flag based on app_config
            logging.warning(f"Google Drive PDF Generator not configured (SERVICE_ACCOUNT_JSON_CONTENT missing or invalid in config). PDFs will NOT be generated for job ID {job_details.get('id')}.")
        else:
            logging.info(f"Attempting to generate RESUME PDF for job ID {job_details.get('id')}")
            resume_pdf_path = generate_styled_resume_pdf(
                tailored_data=resume_data_for_pdf, 
                contact_info=PREDEFINED_CONTACT_INFO, 
                education_info=PREDEFINED_EDUCATION_INFO, 
                output_pdf_directory=tailoring_output_dir_global, 
                target_company_name=job_details.get("company_name", "TargetCo"), # For potential use in PDF content/naming
                years_of_experience=DEFAULT_YOE, # For potential use in PDF content/naming
                filename_keyword=base_filename_resume # Pass the constructed base filename
            )
            if resume_pdf_path:
                logging.info(f"Tailored Resume PDF generated: {resume_pdf_path}")
            else:
                logging.error(f"Failed to generate resume PDF via Google Drive for job ID {job_details.get('id')}")

            if final_state.generated_cover_letter_text:
                logging.info(f"Attempting to generate COVER LETTER PDF for job ID {job_details.get('id')}")
                cover_letter_pdf_path = generate_cover_letter_pdf(
                    cover_letter_body_text=final_state.generated_cover_letter_text,
                    contact_info=PREDEFINED_CONTACT_INFO,
                    job_title=job_details.get("detailed_title", "Position"),
                    company_name=job_details.get("company_name", "Company"),
                    output_pdf_directory=tailoring_output_dir_global,
                    filename_keyword=base_filename_cl, # Pass the constructed base filename
                    years_of_experience=DEFAULT_YOE
                )
                if cover_letter_pdf_path:
                    logging.info(f"Tailored Cover Letter PDF generated: {cover_letter_pdf_path}")
                else:
                    logging.error(f"Failed to generate cover letter PDF via Google Drive for job ID {job_details.get('id')}")
            else:
                logging.info(f"No cover letter text generated by orchestrator for job ID {job_details.get('id')}. Skipping CL PDF.")

        # Construct critique text
        critique_parts = []
        critique_header_job_title = job_details.get('detailed_title', 'N/A')
        critique_header_company_name = job_details.get('company_name', 'N/A')
        critique_parts.append(f"Critique for: {critique_header_job_title} at {critique_header_company_name}")
        if hasattr(final_state, 'resume_critique') and final_state.resume_critique: 
            critique = final_state.resume_critique
            # Ensure critique object has these attributes before accessing
            ats_score = getattr(critique, 'ats_score', 'N/A')
            ats_pass = getattr(critique, 'ats_pass_assessment', 'N/A')
            rec_impression = getattr(critique, 'recruiter_impression_assessment', 'N/A')
            critique_parts.append(f"  ATS Score: {ats_score if ats_score is not None else 'N/A'}%")
            critique_parts.append(f"  ATS Pass Assessment: {ats_pass or 'N/A'}")
            critique_parts.append(f"  Recruiter Impression: {rec_impression or 'N/A'}")
        elif hasattr(final_state, 'raw_critique_text') and final_state.raw_critique_text and final_state.raw_critique_text.strip():
            critique_parts.append(f"  Raw Critique (Parsing Failed/Incomplete):\n{final_state.raw_critique_text}")
        else:
            critique_parts.append("  No structured resume critique was generated or available in final_state.")
        final_critique_text = "\n".join(critique_parts)

        artifacts_to_return = {
            "job_id": job_details.get("id"),
            "job_title": job_details.get("detailed_title"),
            "company_name": job_details.get("company_name"),
            "job_url": job_details.get("url"),
            "source_platform": job_details.get("source_platform"),
            "search_source_name": job_details.get("search_source_name"),
            "resume_pdf": resume_pdf_path, 
            "cover_letter_pdf": cover_letter_pdf_path, 
            "critique_text": final_critique_text
        }
        return artifacts_to_return

    except Exception as e:
        logging.error(f"CRITICAL ERROR in tailoring pipeline for job ID {job_details.get('id')}: {e}", exc_info=True)
        # Log final_state if it was assigned before the error
        if 'final_state' in locals() and final_state is not None:
             try: logging.info(f"Debug: Content of final_state at time of CRITICAL error: {vars(final_state)}")
             except: logging.info(f"Debug: Content of final_state (could not get vars) at time of CRITICAL error: {final_state}")
        else:
             logging.info(f"Debug: final_state was not assigned or was None at time of CRITICAL error for job ID {job_details.get('id')}")
        return None

def delete_state_files_task():
    logging.info("Midnight task: Deleting consolidated job state JSON files...")
    all_jobs_file_path = CONSOLIDATED_ALL_JOBS_FILE
    relevant_new_jobs_file_path = CONSOLIDATED_RELEVANT_NEW_JOBS_FILE

    files_to_delete = [all_jobs_file_path, relevant_new_jobs_file_path]
    for filepath in files_to_delete:
        if filepath and os.path.exists(filepath):
            try: os.remove(filepath); logging.info(f"Deleted: {filepath}")
            except Exception as e: logging.error(f"Error deleting {filepath}: {e}")
        elif filepath: logging.info(f"File not found, skipping deletion: {filepath}")
        else: logging.info("File path for deletion is None, skipping.")
    logging.info("Midnight file deletion task completed.")

def run_all_scrapers_and_process():
    global CURRENT_DAY_TRACKER, DAILY_RUN_COUNTER, gcs_client_global # Ensure gcs_client_global is global if initialized elsewhere

    # --- Daily Counter Logic & GCS Client Init ---
    today = datetime.date.today()
    if today != CURRENT_DAY_TRACKER:
        logging.info(f"Date changed from {CURRENT_DAY_TRACKER} to {today}. Resetting daily run counter.")
        CURRENT_DAY_TRACKER = today
        DAILY_RUN_COUNTER = 0  # Reset for the new day, first run will be 0
    
    current_run_number_for_logging = DAILY_RUN_COUNTER # Capture current run number for logging this cycle

    logging.info(f"===== CYCLE START (Date: {CURRENT_DAY_TRACKER}, Run: {current_run_number_for_logging}) =====")

    # Initialize GCS client if not already done and utils are loaded
    if GCP_UTILS_LOADED and not gcs_client_global:
        gcs_client_global = get_gcs_client()
        if not gcs_client_global:
            logging.error("Failed to initialize GCS client for this cycle. GCS uploads will be skipped.")
    # --- End Daily Counter Logic & GCS Client Init ---

    if not TAILORING_MODULES_LOADED:
        logging.error("Tailoring modules not loaded. Full processing (tailoring, emailing, GCS upload) will be skipped.")
    elif not llm_client_global or not orchestrator_agent_global: # Check if tailoring system components are ready
        if not initialize_tailoring_system(): # This function should also handle gcs_client_global if you move init there
            logging.error("Failed to initialize tailoring system. Full processing will be skipped.")

    all_previously_scraped_jobs = load_jobs_from_file(CONSOLIDATED_ALL_JOBS_FILE)
    seen_job_ids_globally = {job['id'] for job in all_previously_scraped_jobs if job.get('id')}
    logging.info(f"Loaded {len(all_previously_scraped_jobs)} jobs ({len(seen_job_ids_globally)} unique IDs) from {CONSOLIDATED_ALL_JOBS_FILE}")

    newly_detailed_jobs_this_cycle = []
    for i, current_scraper_config in enumerate(SCRAPER_CONFIGS):
        platform = current_scraper_config.get("platform")
        search_name = current_scraper_config.get("search_name", "Unknown Search")
        processed_jobs_for_this_config = []
        logging.info(f"--- Processing scraper_cfg #{i+1}: {search_name} (Platform: {platform}) ---")
        if platform == "linkedin":
            processed_jobs_for_this_config = process_linkedin_job_search(current_scraper_config, seen_job_ids_globally)
        elif platform == "jobright":
            current_scraper_config["profile_dir"] = USER_DATA_PROFILE_DIR_JOBRIGHT_GLOBAL
            current_scraper_config["username"] = JOBRIGHT_USERNAME_GLOBAL
            current_scraper_config["password"] = JOBRIGHT_PASSWORD_GLOBAL
            if not current_scraper_config.get("username") or not current_scraper_config.get("password"):
                logging.warning(f"Jobright credentials for '{search_name}' are missing. Skipping Jobright scraping for this config.")
            else:
                processed_jobs_for_this_config = scrape_jobright_platform(current_scraper_config, logging, seen_job_ids_globally)
        else:
            logging.error(f"Unknown platform type '{platform}' in config for '{search_name}'. Skipping.")
            continue
        
        if processed_jobs_for_this_config:
            newly_detailed_jobs_this_cycle.extend(processed_jobs_for_this_config)
            for job in processed_jobs_for_this_config: # Update globally seen IDs
                if job.get('id'): seen_job_ids_globally.add(job['id'])
        
        if i < len(SCRAPER_CONFIGS) - 1: # Delay between different scraper configs
            delay = random.uniform(5, 15)
            logging.info(f"Delaying {delay:.1f}s before next scraper config.")
            time.sleep(delay)

    logging.info(f"All scraping configurations processed. Total newly detailed jobs this cycle: {len(newly_detailed_jobs_this_cycle)}")
    if newly_detailed_jobs_this_cycle:
        final_list_to_save = merge_and_deduplicate_jobs(all_previously_scraped_jobs, newly_detailed_jobs_this_cycle)
        save_jobs_to_file(CONSOLIDATED_ALL_JOBS_FILE, final_list_to_save)
    else: # No new jobs, but check if existing file needs deduplication
        if all_previously_scraped_jobs:
            deduplicated_old_jobs = merge_and_deduplicate_jobs(all_previously_scraped_jobs, [])
            if len(deduplicated_old_jobs) != len(all_previously_scraped_jobs):
                logging.info("Deduplicating and re-saving the existing consolidated job file.")
                save_jobs_to_file(CONSOLIDATED_ALL_JOBS_FILE, deduplicated_old_jobs)
        else:
            logging.info(f"No new jobs detailed this cycle. {CONSOLIDATED_ALL_JOBS_FILE} remains unchanged or empty.")

    # --- Job Filtering Logic ---
    relevant_new_jobs = []
    processed_job_cores_this_cycle = set() # For de-duping based on company|title within this run

    if newly_detailed_jobs_this_cycle:
        for job in newly_detailed_jobs_this_cycle:
            title_to_check = job.get('detailed_title', job.get('title_from_search', '')).lower()
            job_url = job.get('url', '').lower()
            job_id = job.get('id', 'N/A')

            # Domain exclusion filter
            is_excluded_source = False
            if job_url:
                try:
                    parsed_url = urlparse(job_url)
                    domain = parsed_url.netloc.replace("www.", "")
                    for excluded_domain in EXCLUDE_JOB_SOURCES_DOMAINS:
                        if excluded_domain.lower() in domain.lower():
                            is_excluded_source = True
                            logging.debug(f"FILTERED (Source Domain): Job '{title_to_check}' (ID: {job_id}) from domain '{domain}'. URL: {job_url}")
                            break
                except Exception as e_url_parse:
                    logging.warning(f"Could not parse URL '{job_url}' for domain check (ID: {job_id}). Error: {e_url_parse}")
            if is_excluded_source: continue

            # Seniority filter
            is_too_senior = False
            for senior_kw in EXCLUDE_JOB_TITLE_SENIORITY:
                if re.search(r'\b' + re.escape(senior_kw) + r'\b', title_to_check):
                    is_too_senior = True; logging.debug(f"FILTERED (Seniority): Job '{title_to_check}' (ID: {job_id})..."); break
            if is_too_senior: continue

            # Software Engineer specific logic filter
            is_se_title = any(se_term in title_to_check for se_term in SOFTWARE_ENGINEER_TERMS)
            if is_se_title:
                has_ai_ml_modifier = any(modifier in title_to_check for modifier in AI_ML_DATA_MODIFIERS_FOR_SE_TITLE)
                if not has_ai_ml_modifier:
                    logging.debug(f"FILTERED (Generic SE): Job '{title_to_check}' (ID: {job_id})..."); continue
            else: # Not SE title, check general excluded fields
                is_undesired_field = False
                for undesired_kw in EXCLUDE_JOB_TITLE_FIELDS:
                    if re.search(r'\b' + re.escape(undesired_kw) + r'\b', title_to_check):
                        is_undesired_field = True; logging.debug(f"FILTERED (Other Field): Job '{title_to_check}' (ID: {job_id})..."); break
                if is_undesired_field: continue

            # Relevance keyword matching
            desc_to_check = job.get('description', '').lower()
            combined_text_to_check = title_to_check + " " + desc_to_check
            is_relevant_keyword_match = not RELEVANT_JOB_KEYWORDS # True if no keywords specified
            if RELEVANT_JOB_KEYWORDS:
                for kw in RELEVANT_JOB_KEYWORDS:
                    if kw.strip() and re.search(r'\b' + re.escape(kw.strip()) + r'\b', combined_text_to_check, re.IGNORECASE):
                        is_relevant_keyword_match = True; break
            
            if is_relevant_keyword_match:
                company_name_for_dedupe = job.get('company_name', 'N/A').lower().strip()
                normalized_title_for_dedupe = job.get('detailed_title', title_to_check).lower().strip()
                job_core_key = f"{company_name_for_dedupe}|{normalized_title_for_dedupe}"

                if job_core_key in processed_job_cores_this_cycle:
                    logging.info(f"FILTERED (Duplicate Core Job this cycle): '{title_to_check}' at '{company_name_for_dedupe}' (ID: {job_id}).")
                    continue

                if job.get("description") and job.get("description").strip() != "N/A" and len(job.get("description").strip()) > 50 :
                    relevant_new_jobs.append(job)
                    processed_job_cores_this_cycle.add(job_core_key)
                    logging.info(f"RELEVANT JOB ADDED for processing: '{title_to_check}' at '{company_name_for_dedupe}' (ID: {job_id}).")
                else:
                    logging.warning(f"Job '{title_to_check}' (ID: {job_id}) matched keywords but has insufficient/missing description.")
            else:
                logging.debug(f"FILTERED (No Relevant Keywords): Job '{title_to_check}' (ID: {job_id}).")
        
        if relevant_new_jobs:
            logging.info(f"Found {len(relevant_new_jobs)} relevant new jobs with descriptions for tailoring after all filters.")
            save_jobs_to_file(CONSOLIDATED_RELEVANT_NEW_JOBS_FILE, relevant_new_jobs)
        else:
            logging.info("No new jobs this cycle matched all filtering criteria or had descriptions.")
            save_jobs_to_file(CONSOLIDATED_RELEVANT_NEW_JOBS_FILE, []) # Save empty list
    else:
        logging.info("No new jobs were detailed this cycle to check for relevance.")
        save_jobs_to_file(CONSOLIDATED_RELEVANT_NEW_JOBS_FILE, [])


    # --- Tailoring, GCS Upload, and Emailing Part ---
    any_processing_attempted_this_run = False # To track if we should increment the run counter

    if relevant_new_jobs and TAILORING_MODULES_LOADED and orchestrator_agent_global and llm_client_global and send_job_application_email:
        logging.info(f"Starting tailoring process for {len(relevant_new_jobs)} relevant jobs...")
        successful_tailoring_and_emailing_count = 0
        any_processing_attempted_this_run = True # We are attempting to process relevant jobs

        for job_detail in relevant_new_jobs:
            logging.info(f"--- Processing job ID: {job_detail.get('id')} for tailoring, GCS upload, and emailing ---")
            tailored_artifacts = run_tailoring_pipeline_for_job(job_detail)
            
            if tailored_artifacts:
                logging.info(f"Successfully generated artifacts for job: {tailored_artifacts.get('job_title')} (ID: {job_detail.get('id')})")
                
                # --- GCS Upload Logic ---
                gcs_upload_completed_for_resume = False
                gcs_upload_completed_for_cl = False

                if GCP_UTILS_LOADED and gcs_client_global and getattr(app_config, 'GCS_BUCKET_NAME', None):
                    company_safe_gcs = re.sub(r'[^\w\-_.]', '_', tailored_artifacts.get('company_name', 'UnknownCompany'))
                    now_gcs = datetime.datetime.now() # Use datetime.datetime.now()
                    date_folder_gcs = now_gcs.strftime("%Y-%m-%d")
                    time_prefix_gcs = now_gcs.strftime("%H%M%S%f") # Added microseconds for more uniqueness

                    if tailored_artifacts.get("resume_pdf") and os.path.exists(tailored_artifacts["resume_pdf"]):
                        resume_filename_gcs = os.path.basename(tailored_artifacts["resume_pdf"])
                        gcs_resume_path = f"tailored_applications/{company_safe_gcs}/{date_folder_gcs}/{time_prefix_gcs}_{resume_filename_gcs}"
                        logging.info(f"Attempting to upload resume to GCS: gs://{app_config.GCS_BUCKET_NAME}/{gcs_resume_path}")
                        if upload_file_to_gcs(gcs_client_global, tailored_artifacts["resume_pdf"], gcs_resume_path):
                            gcs_upload_completed_for_resume = True
                            logging.info(f"Successfully uploaded resume to GCS: {gcs_resume_path}")
                        else:
                            logging.error(f"Failed to upload resume to GCS: {gcs_resume_path}")

                    if tailored_artifacts.get("cover_letter_pdf") and os.path.exists(tailored_artifacts["cover_letter_pdf"]):
                        cl_filename_gcs = os.path.basename(tailored_artifacts["cover_letter_pdf"])
                        gcs_cl_path = f"tailored_applications/{company_safe_gcs}/{date_folder_gcs}/{time_prefix_gcs}_{cl_filename_gcs}"
                        logging.info(f"Attempting to upload cover letter to GCS: gs://{app_config.GCS_BUCKET_NAME}/{gcs_cl_path}")
                        if upload_file_to_gcs(gcs_client_global, tailored_artifacts["cover_letter_pdf"], gcs_cl_path):
                            gcs_upload_completed_for_cl = True
                            logging.info(f"Successfully uploaded cover letter to GCS: {gcs_cl_path}")
                        else:
                            logging.error(f"Failed to upload cover letter to GCS: {gcs_cl_path}")
                else: # Log reasons for skipping GCS
                    if not GCP_UTILS_LOADED: logging.warning("gcp_utils not loaded, skipping GCS upload.")
                    elif not gcs_client_global: logging.warning("GCS client not initialized, skipping GCS upload.")
                    elif not getattr(app_config, 'GCS_BUCKET_NAME', None): logging.warning("GCS_BUCKET_NAME not configured, skipping GCS upload.")
                # --- End GCS Upload Logic ---

                try:
                    date_str_subject = CURRENT_DAY_TRACKER.strftime("%Y-%m-%d")
                    # Using current_run_number_for_logging for the subject of emails sent in *this* cycle
                    email_subject = f"Job Apps {date_str_subject} - Run {current_run_number_for_logging}"

                    email_body_parts = [
                        f"Tailored application documents for: {tailored_artifacts.get('job_title', 'N/A')} at {tailored_artifacts.get('company_name', 'N/A')}",
                        f"Job URL: {tailored_artifacts.get('job_url', 'N/A')}",
                        f"Platform: {tailored_artifacts.get('source_platform', 'N/A')} ({tailored_artifacts.get('search_source_name', 'N/A')})",
                        f"Run ID: {date_str_subject} / Run No: {current_run_number_for_logging}",
                        f"Resume GCS: {'Uploaded' if gcs_upload_completed_for_resume else 'Upload Failed/Skipped'}",
                        f"Cover Letter GCS: {'Uploaded' if gcs_upload_completed_for_cl else 'Upload Failed/Skipped'}",
                        "\nCritique:",
                        tailored_artifacts.get('critique_text', "Critique not available."),
                        "--------------------"
                    ]
                    email_body = "\n".join(email_body_parts)
                    attachments_for_this_job = []
                    if tailored_artifacts.get("resume_pdf") and os.path.exists(tailored_artifacts["resume_pdf"]):
                        attachments_for_this_job.append(tailored_artifacts["resume_pdf"])
                    if tailored_artifacts.get("cover_letter_pdf") and os.path.exists(tailored_artifacts["cover_letter_pdf"]):
                        attachments_for_this_job.append(tailored_artifacts["cover_letter_pdf"])

                    email_recipient_address = getattr(app_config, "APP_EMAIL_RECIPIENT", None)
                    if not email_recipient_address:
                        logging.error(f"Email recipient (APP_EMAIL_RECIPIENT) not configured. Email not sent for job ID {job_detail.get('id')}.")
                        continue # Skip to next job

                    # Check Brevo config (already in your provided code)
                    brevo_smtp_key_env_name = getattr(app_config, "BREVO_SMTP_KEY_ENV_VAR_NAME", "BREVO_SMTP_KEY")
                    brevo_smtp_key_fallback = getattr(app_config, "BREVO_SMTP_KEY_FALLBACK_FOR_TESTING", None)
                    can_resolve_key = os.getenv(brevo_smtp_key_env_name) or brevo_smtp_key_fallback
                    can_resolve_login = getattr(app_config, "BREVO_SMTP_LOGIN", None)
                    can_resolve_sender_display = getattr(app_config, "BREVO_SENDER_DISPLAY_EMAIL", None)

                    if not (can_resolve_key and can_resolve_login and can_resolve_sender_display):
                        logging.error(f"Brevo SMTP Key, Login, or Sender Display Email not available. Email not sent for job ID {job_detail.get('id')}.")
                        continue

                    logging.info(f"Preparing to send email with subject: {email_subject}")
                    email_sent_successfully = send_job_application_email(
                        subject=email_subject,
                        body=email_body,
                        recipient_email=email_recipient_address,
                        attachments=attachments_for_this_job
                    )
                    if email_sent_successfully:
                        successful_tailoring_and_emailing_count += 1
                        logging.info(f"Email for job '{tailored_artifacts.get('job_title')}' sent successfully to {email_recipient_address}.")
                        # Local PDF Deletion (Decision Point: Keep if GCS is primary, or remove this block)
                        if tailored_artifacts.get("resume_pdf") and os.path.exists(tailored_artifacts["resume_pdf"]):
                            try: os.remove(tailored_artifacts["resume_pdf"]); logging.info(f"Deleted local resume PDF: {tailored_artifacts['resume_pdf']}")
                            except OSError as e_del: logging.warning(f"Could not delete local resume PDF {tailored_artifacts['resume_pdf']}: {e_del}")
                        if tailored_artifacts.get("cover_letter_pdf") and os.path.exists(tailored_artifacts["cover_letter_pdf"]):
                            try: os.remove(tailored_artifacts["cover_letter_pdf"]); logging.info(f"Deleted local CL PDF: {tailored_artifacts['cover_letter_pdf']}")
                            except OSError as e_del: logging.warning(f"Could not delete local CL PDF {tailored_artifacts['cover_letter_pdf']}: {e_del}")
                    else:
                        logging.error(f"Failed to send email for job '{tailored_artifacts.get('job_title')}' (ID: {job_detail.get('id')}).")
                except Exception as e_email_block:
                    logging.error(f"Error during GCS upload or email processing for job ID {job_detail.get('id')}: {e_email_block}", exc_info=True)
            else:
                logging.warning(f"Tailoring pipeline failed or returned no artifacts for job: {job_detail.get('detailed_title')} (ID: {job_detail.get('id')})")
        
        if successful_tailoring_and_emailing_count > 0:
            logging.info(f"Successfully processed, uploaded to GCS (if configured), and emailed for {successful_tailoring_and_emailing_count} jobs.")
        else:
            logging.info("No job artifacts were successfully generated and emailed in this cycle.")

    elif not relevant_new_jobs:
        logging.info("No relevant new jobs to process for tailoring in this cycle.")
    else: # Catchall if tailoring modules not loaded etc.
        logging.warning("Tailoring modules not loaded, system not initialized, or email sender not available. Skipping tailoring, GCS upload, and emailing steps.")

    # --- Increment Daily Run Counter AFTER all jobs in this run are processed ---
    if any_processing_attempted_this_run : # Increment if we attempted to process relevant jobs
        DAILY_RUN_COUNTER += 1
        logging.info(f"Daily run counter for {CURRENT_DAY_TRACKER} incremented to: {DAILY_RUN_COUNTER} for the next scheduled run.")
    # --- End Counter Increment ---
    
    logging.info(f"===== CYCLE END (Date: {CURRENT_DAY_TRACKER}, Processed Run: {current_run_number_for_logging}) =====")

if __name__ == "__main__":
    if app_config is None:
        logging.warning("__main__: app_config is None. Many configurations will use hardcoded fallbacks. This might lead to unexpected behavior or errors if critical paths are not set.")
    else:
        logging.info("__main__: app_config loaded. Configurations will be used.")

    logging.info(f"Job Scraper & Tailor starting. Log file: {LOG_FILE_SCRAPER}")

    if not SCRAPER_CONFIGS:
        logging.critical("CRITICAL: SCRAPER_CONFIGS is empty. Exiting.")
        sys.exit(1)

    for i, cfg_item in enumerate(SCRAPER_CONFIGS): # Validate essential parts of scraper configs
        if not cfg_item.get("platform"):
            logging.critical(f"CRITICAL: Config #{i+1} ('{cfg_item.get('search_name')}') missing 'platform' key. Exiting.")
            sys.exit(1)
        if cfg_item.get("platform") == "linkedin" and (not cfg_item.get("url") or "YOUR_LINKEDIN_JOB_SEARCH_URL" in cfg_item.get("url", "")): # Check for placeholder URL
            logging.critical(f"CRITICAL: LinkedIn URL for config #{i+1} ('{cfg_item.get('search_name')}') not set properly. Exiting.")
            sys.exit(1)
        if not cfg_item.get("search_name"):
             logging.critical(f"CRITICAL: 'search_name' missing for config #{i+1}. Exiting.")
             sys.exit(1)

    if TAILORING_MODULES_LOADED and OrchestratorAgent and GeminiClient and generate_styled_resume_pdf and send_job_application_email and extract_tailored_data_for_resume_pdf:
        if not initialize_tailoring_system():
            logging.warning("Failed to initialize tailoring system on startup. Tailoring will be skipped unless re-initialized successfully in a cycle.")
    else:
        logging.warning("One or more Tailoring modules or their dependencies (OrchestratorAgent, GeminiClient, PDF generators, email_sender, extract_tailored_data_for_resume_pdf) not loaded. Only scraping will occur if tailoring is attempted.")

    logging.info(f"Job processing scheduled every {SCHEDULE_INTERVAL_MINUTES} minutes.")
    logging.info(f"Positive Relevant Job Keywords: {RELEVANT_JOB_KEYWORDS}")
    logging.info(f"Excluding Field Keywords in Title: {EXCLUDE_JOB_TITLE_FIELDS}")
    logging.info(f"Excluding Seniority Keywords in Title: {EXCLUDE_JOB_TITLE_SENIORITY}")
    logging.info(f"Excluding Source Domains: {EXCLUDE_JOB_SOURCES_DOMAINS}")
    logging.info(f"Software Engineer Terms for specific logic: {SOFTWARE_ENGINEER_TERMS}")
    logging.info(f"AI/ML/Data Modifiers for SE Titles: {AI_ML_DATA_MODIFIERS_FOR_SE_TITLE}")
    if not PDF_GENERATOR_SERVICE_ACCOUNT_CONFIGURED and TAILORING_MODULES_LOADED :
        logging.warning("REMINDER: Google Drive SERVICE_ACCOUNT_JSON_CONTENT is not configured or is invalid. Tailoring will attempt to run, but PDF generation will be skipped/fail.")


    try:
        run_all_scrapers_and_process() # Initial run
    except Exception as e_initial:
        logging.critical(f"Unhandled exception during initial run_all_scrapers_and_process: {e_initial}", exc_info=True)

    schedule.every(SCHEDULE_INTERVAL_MINUTES).minutes.do(run_all_scrapers_and_process)
    try:
        schedule.every().day.at("00:05").do(delete_state_files_task) # Daily at 00:05 server time
        logging.info(f"Daily state file deletion scheduled at 00:05 for {CONSOLIDATED_ALL_JOBS_FILE} and {CONSOLIDATED_RELEVANT_NEW_JOBS_FILE}.")
    except Exception as e_sched_del: logging.error(f"Could not schedule daily file deletion: {e_sched_del}")

    logging.info("Scheduler started. Waiting for next run...")
    while True:
        try:
            schedule.run_pending()
        except Exception as e_sched_loop: # Catch errors from within scheduled jobs too
            logging.critical(f"Unhandled exception in scheduler loop or during scheduled job execution: {e_sched_loop}", exc_info=True)
        time.sleep(1)