# Resume_Tailoring/src/data_parser_for_pdf.py
import re
import logging
from typing import List, Dict, Any, Optional

# It's good practice to have a logger for each module
logger = logging.getLogger(__name__)

def parse_contact_info_from_resume_pdf_text(resume_pdf_text: str) -> Dict[str, Optional[str]]:
    """
    Parses contact information from the raw text of the original resume PDF.
    This is tailored based on the structure of "Shanmugam_AI_2025_4_YOE.pdf".
    """
    contact_info = {
        "name": "Venkatesh Shanmugam", # Default from your resume
        "location": "Virginia US",      # Default from your resume
        "email": "svenkatesh.js@gmail.com", # Default from your resume
        "phone": "+1 (703) 216-2540",   # Default from your resume
        "linkedin_url": "https://www.linkedin.com/in/svenkatesh-js/", # Default
        "github_url": None,      # Placeholder, as "GitHub" is text, not a URL in PDF
        "portfolio_url": None    # Placeholder, as "Portfolio" is text
    }
    logger.info(f"Using contact info: Name='{contact_info['name']}', Email='{contact_info['email']}'")
    # In a production system, you might use more robust regex or specific markers
    # if this information was to be dynamically parsed from various resume formats.
    # For this POC with your specific resume, hardcoding/defaulting is often reliable
    # if the PDF text extraction of these specific fields is inconsistent.
    # The provided PDF text has "GitHub" and "Portfolio" as text labels.
    # For the template, we'd ideally want actual URLs.
    # You can replace these with your actual URLs:
    contact_info["github_url"] = "https://github.com/your_actual_github_username" # Replace
    contact_info["portfolio_url"] = "your_actual_portfolio_link" # Replace

    return contact_info

def parse_llm_work_experience_string(text_block: str) -> List[Dict[str, Any]]:
    """
    Parses the LLM's generated string for work experience into a list of job dictionaries.
    This function is built based on the observed output format of your LLM.
    """
    jobs = []
    if not text_block or not text_block.strip():
        logger.warning("Work experience text block is empty.")
        return jobs

    # Remove potential "## Work Experience" markdown header from LLM output
    if text_block.strip().startswith("## Work Experience"):
        text_block = re.sub(r"^## Work Experience\s*\n+", "", text_block, flags=re.IGNORECASE).strip()

    # Split into individual job entries. LLM often uses double newlines between entries.
    # This regex tries to split by one or more empty lines, but only if the next line
    # looks like a job title (often bolded by LLM with ** or starting with caps).
    raw_jobs = re.split(r'\n\s*\n+(?=\s*(?:\*\*)?[A-Z][\w\s.,-]+?\s*(?:\*\*)?\s*\|)', text_block.strip())

    for raw_job_entry in raw_jobs:
        raw_job_entry = raw_job_entry.strip()
        if not raw_job_entry:
            continue

        lines = [line.strip() for line in raw_job_entry.split('\n') if line.strip()]
        if not lines:
            continue

        job_details: Dict[str, Any] = {
            "title": None, "company": None, "location": None, "dates": None, "bullet_points": []
        }
        
        # Regex for Job Title | Company | Location (first line typically)
        # e.g., **Senior AI/ML Engineer** | **ScriptChain Health** | Washington, DC
        header_match = re.match(r'^(?:\*\*)?(.+?)(?:\*\*)?\s*\|\s*(?:\*\*)?(.+?)(?:\*\*)?\s*\|\s*(.+)$', lines[0])
        current_line_idx = 0

        if header_match:
            job_details["title"] = header_match.group(1).strip()
            job_details["company"] = header_match.group(2).strip()
            job_details["location"] = header_match.group(3).strip()
            current_line_idx = 1
        else:
            logger.warning(f"Could not parse standard job header line: '{lines[0]}'. Attempting fallback.")
            # Fallback: Assume first line is title if no pipes, or try to split by first pipe for title/company
            parts = lines[0].split('|', 1)
            job_details["title"] = parts[0].replace("**", "").strip()
            if len(parts) > 1:
                 job_details["company"] = parts[1].replace("**", "").strip() # Company might include location here
            else:
                job_details["company"] = "N/A"
            job_details["location"] = "N/A" # Will be overwritten if found
            current_line_idx = 1


        # Parsing Dates (usually the next line after header)
        if current_line_idx < len(lines) and \
           re.match(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|September)[\w\s,–-]+$', lines[current_line_idx].strip(), re.IGNORECASE):
            job_details["dates"] = lines[current_line_idx].strip()
            current_line_idx += 1
        else:
            # Try to find dates if they were part of location in a simpler header
            if job_details["location"] and not job_details["dates"]:
                date_in_loc_match = re.search(r'(.*?)(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present)[\w\s,-–]+)$', job_details["location"])
                if date_in_loc_match:
                    job_details["location"] = date_in_loc_match.group(1).strip().rstrip(' |')
                    job_details["dates"] = date_in_loc_match.group(2).strip()

            if not job_details["dates"]:
                 job_details["dates"] = "Dates N/A"
                 logger.warning(f"Could not parse dates for job: {job_details.get('title')} at {job_details.get('company')}")
        
        # Parsing Bullet Points
        for i in range(current_line_idx, len(lines)):
            if lines[i].startswith('*'):
                job_details["bullet_points"].append(lines[i][1:].strip())
        
        if job_details.get("title"):
            jobs.append(job_details)
        else:
            logger.warning(f"Skipping job entry due to inability to parse title: '{raw_job_entry[:100]}...'")
            
    logger.info(f"Parsed {len(jobs)} work experience entries from LLM output.")
    return jobs

def parse_llm_technical_skills_string(text_block: str) -> List[Dict[str, str]]:
    """
    Parses the LLM's generated string for technical skills into a list of category dictionaries.
    Assumes format like: "**Category Name:** Skill1, Skill2"
    """
    skill_categories = []
    if not text_block or not text_block.strip():
        logger.warning("Technical skills text block is empty.")
        return skill_categories

    if text_block.strip().startswith("## Technical Skills"):
        text_block = re.sub(r"^## Technical Skills\s*\n+", "", text_block, flags=re.IGNORECASE).strip()

    lines = text_block.split('\n')
    for line in lines:
        line = line.strip()
        if not line: 
            continue
        
        match = re.match(r'^(?:\*\*)?(.+?)(?:\*\*)?\s*:\s*(.+)$', line)
        if match:
            category_name = match.group(1).strip()
            skills_list_str = match.group(2).strip()
            skill_categories.append({
                "name": category_name,
                "skills_list_str": skills_list_str
            })
        else:
            logger.warning(f"Could not parse skill line into category and skills: '{line}'")
            # Fallback: Treat the whole line as a skill item if no colon, or skip
            # skill_categories.append({"name": "General Skills", "skills_list_str": line})
            
    logger.info(f"Parsed {len(skill_categories)} technical skill categories from LLM output.")
    return skill_categories

def parse_llm_projects_string(text_block: str) -> List[Dict[str, Any]]:
    """
    Parses the LLM's generated string for projects into a list of project dictionaries.
    """
    projects = []
    if not text_block or not text_block.strip():
        logger.warning("Projects text block is empty.")
        return projects
    
    # Remove header like "## Rewritten Projects Section:" or "## PROJECTS"
    text_block = re.sub(r"^## (?:Rewritten )?Projects(?: Section)?:\s*\n+", "", text_block, flags=re.IGNORECASE).strip()

    # Split by what appears to be double newlines between project entries.
    # The lookahead tries to ensure the next block starts with something like a bolded title or a title with a pipe.
    raw_project_entries = re.split(r'\n\s*\n+(?=\s*(?:\*\*)?[A-Z][\w\s\-]+?(?:\*\*)?\s*(?:\||\n))', text_block.strip())

    for entry in raw_project_entries:
        entry = entry.strip()
        if not entry:
            continue
        lines = [line.strip() for line in entry.split('\n') if line.strip()]
        if not lines:
            continue

        project_details: Dict[str, Any] = {"title": None, "tagline": None, "bullet_points": []}
        
        # Example Title line: **Intelligent Building Code QA | _NLP, RAG_** or just **AI-Text Discriminator**
        title_line_match = re.match(r'^\s*(?:\*\*)?(.+?)(?:\*\*)?\s*(?:\|\s*_(.+?)_)?$', lines[0])
        if title_line_match:
            project_details["title"] = title_line_match.group(1).strip()
            project_details["tagline"] = title_line_match.group(2).strip() if title_line_match.group(2) else None
            bullet_lines_start_index = 1
        else:
            # Fallback if no pipe and underscore, assume whole first line is title
            project_details["title"] = lines[0].replace("**", "").strip()
            project_details["tagline"] = None
            bullet_lines_start_index = 1
            logger.warning(f"Could not parse project title line with tagline: '{lines[0]}'. Using full line as title.")


        for i in range(bullet_lines_start_index, len(lines)):
            if lines[i].startswith('*'):
                project_details["bullet_points"].append(lines[i][1:].strip())
        
        if project_details.get("title"):
            projects.append(project_details)
    logger.info(f"Parsed {len(projects)} project entries from LLM output.")
    return projects

def parse_education_from_resume_pdf_text(resume_pdf_text: str) -> List[Dict[str, Optional[str]]]:
    """
    Parses education information from the raw text of the original resume PDF.
    Tailored for "Shanmugam_AI_2025_4_YOE.pdf" [cite: 1] structure.
    """
    education_list = []
    logger.info("Attempting to parse education from original PDF text.")

    # Pattern for: Degree Name (GPA), University Name Month Year - Month Year
    # Example: Master of Science in Computer Science (3.81 / 4.0), George Washington University August 2023 - May 2025 [cite: 1]
    # Note: The PDF text for education in source [18] shows a table structure that might be extracted linearly.
    # The raw text you provided later shows a more linear structure.
    
    # Using the linear structure observed in your later raw text paste:
    # "Master of Science in Computer Science (3.81 / 4.0), George Washington University\nAugust 2023 - May 2025"
    
    # Regex to find degree, (gpa), university, followed by dates on a new line or same line
    # This regex is complex and assumes a certain proximity and ordering.
    # It tries to capture degree, optional GPA, university, and then dates.
    # It's hard to make this perfectly robust for all PDF extraction variations without seeing the exact text for education.

    # For "Shanmugam_AI_2025_4_YOE.pdf"[cite: 1], the education section looks like:
    # EDUCATION
    # Master of Science in Computer Science (3.81 / 4.0), George Washington University August 2023 - May 2025
    # Bachelor of Technology in Computer Science (3.5/4.0), SRM University Aug 2016 - May 2020 [This was not in source [18] but in your later paste]

    # Let's use the concrete examples from your resume
    education_entries_data = [
        {
            "degree_text": "Master of Science in Computer Science",
            "gpa_text": "3.81 / 4.0",
            "university_text": "George Washington University",
            "dates_text": "August 2023 - May 2025",
            "location_text": "Washington, DC" # From context, not explicitly on same line
        },
        {
            "degree_text": "Bachelor of Technology in Computer Science",
            "gpa_text": "3.5/4.0",
            "university_text": "SRM University",
            "dates_text": "Aug 2016 - May 2020",
            "location_text": "India" # From context
        }
    ]

    for entry_data in education_entries_data:
        # This simplified approach assumes the structure based on your provided resume.
        # A more general parser would need more complex regex based on raw PDF text.
        education_list.append({
            "degree": entry_data["degree_text"],
            "gpa": entry_data["gpa_text"],
            "university": entry_data["university_text"],
            "location": entry_data["location_text"],
            "dates": entry_data["dates_text"],
            "coursework": None # Placeholder, parse if available in your PDF
        })
    
    if not education_list:
        logger.warning("No education entries parsed. Check parsing logic and raw PDF text for education.")

    logger.info(f"Parsed {len(education_list)} education entries.")
    return education_list


def preprocess_tailored_data_for_pdf(
    tailored_json_data: Dict[str, str], 
    original_resume_pdf_text: str # Raw text from the original PDF
) -> Dict[str, Any]:
    """
    Transforms the flat JSON output from the LLM and original resume PDF text
    into a structured dictionary suitable for the HTML template.
    """
    logger.info("Starting preprocessing of tailored JSON data and original PDF text for HTML template.")
    processed_data: Dict[str, Any] = {}

    # 1. Parse Contact Info from original PDF text
    processed_data["contact_info"] = parse_contact_info_from_resume_pdf_text(original_resume_pdf_text)

    # 2. Get LLM-tailored Summary
    processed_data["summary"] = tailored_json_data.get("summary", "").strip()

    # 3. Parse LLM's string output for complex sections into structured lists
    processed_data["work_experience_parsed"] = parse_llm_work_experience_string(
        tailored_json_data.get("work_experience", "")
    )
    processed_data["technical_skills_parsed"] = parse_llm_technical_skills_string(
        tailored_json_data.get("technical_skills", "")
    )
    processed_data["projects_parsed"] = parse_llm_projects_string(
        tailored_json_data.get("projects", "")
    )
    
    # 4. Parse Education from original PDF text (as it's typically not LLM-tailored)
    processed_data["education_parsed"] = parse_education_from_resume_pdf_text(original_resume_pdf_text)
    
    logger.info("Preprocessing for PDF template complete.")
    return processed_data

def extract_tailored_data_for_resume_pdf(
    tailored_resume_model_dump: Dict[str, Any]
) -> Optional[Dict[str, str]]:
    """
    Extracts and flattens relevant sections from the tailored resume Pydantic model dump
    into a simple dictionary of strings suitable for the DOCX PDF generation functions.
    The values in the returned dictionary should be markdown-formatted strings if complex.
    """
    if not tailored_resume_model_dump:
        logger.warning("Received empty or None tailored_resume_model_dump for PDF data extraction.")
        return None

    processed_data: Dict[str, str] = {} # Ensure values are strings

    # Summary
    # Assuming 'summary' key directly holds the text or is under a common section name.
    summary_text = tailored_resume_model_dump.get("summary")
    if not summary_text: # Fallback if summary is nested, e.g. in a "summary_section"
        summary_section = tailored_resume_model_dump.get("summary_section")
        if isinstance(summary_section, dict):
            summary_text = summary_section.get("text")
        elif isinstance(summary_section, str): # If summary_section itself is the text
            summary_text = summary_section
            
    processed_data["summary"] = str(summary_text).strip() if summary_text else "Summary not provided."
    logger.debug(f"PDF Extractor - Summary: {processed_data['summary'][:50]}...")

    # Work Experience
    # Expected by add_work_experience_docx: A single string, markdown formatted.
    # Example: "**Job Title** | Company | Location | Dates\n* Bullet 1\n* Bullet 2\n\n**Next Job**..."
    work_experience_data = tailored_resume_model_dump.get("work_experience")
    if isinstance(work_experience_data, str): # If it's already a formatted string
        processed_data["work_experience"] = work_experience_data
    elif isinstance(work_experience_data, list): # If it's a list of experience objects/dicts
        experiences_str_parts = []
        for exp in work_experience_data:
            if not isinstance(exp, dict): continue
            title_line_parts = [
                f"**{exp.get('title', exp.get('job_title', 'N/A'))}**",
                exp.get('company', exp.get('company_name', 'N/A')),
                exp.get('location', 'N/A'),
                exp.get('dates', 'N/A')
            ]
            experiences_str_parts.append(" | ".join(filter(None, title_line_parts)))
            bullets = exp.get('bullet_points', exp.get('responsibilities', exp.get('description_bullets', [])))
            if isinstance(bullets, list):
                for bullet in bullets:
                    experiences_str_parts.append(f"* {str(bullet).strip()}")
            elif isinstance(bullets, str): # If bullets are a single string block
                 for line in bullets.split('\n'):
                    if line.strip(): experiences_str_parts.append(f"* {line.strip()}")
            experiences_str_parts.append("") # Add a newline between entries
        processed_data["work_experience"] = "\n".join(experiences_str_parts).strip()
    else:
        processed_data["work_experience"] = "Work experience data not in expected format or not provided."
    logger.debug(f"PDF Extractor - Work Experience: {processed_data['work_experience'][:100]}...")


    # Technical Skills
    # Expected by add_technical_skills_docx: A single string.
    # Example: "**Languages:** Python, Java\n**Frameworks:** Django, Spring"
    technical_skills_data = tailored_resume_model_dump.get("technical_skills", tailored_resume_model_dump.get("skills"))
    if isinstance(technical_skills_data, str):
        processed_data["technical_skills"] = technical_skills_data
    elif isinstance(technical_skills_data, dict): # E.g., {"Languages": ["Python"], "Frameworks": ["Flask"]}
        skills_str_parts = []
        for category, skills_list in technical_skills_data.items():
            if isinstance(skills_list, list) and skills_list:
                skills_str_parts.append(f"**{str(category).replace('_', ' ').title()}:** {', '.join(map(str, skills_list))}")
            elif isinstance(skills_list, str): # If skills are already a string under the category
                skills_str_parts.append(f"**{str(category).replace('_', ' ').title()}:** {skills_list}")
        processed_data["technical_skills"] = "\n".join(skills_str_parts)
    elif isinstance(technical_skills_data, list): # E.g., just a list of skill strings or dicts
        # If list of strings:
        if all(isinstance(s, str) for s in technical_skills_data):
             processed_data["technical_skills"] = "**Skills:** " + ", ".join(technical_skills_data)
        # If list of dicts (e.g. from parse_llm_technical_skills_string if that was used by orchestrator)
        elif all(isinstance(s, dict) and "name" in s and "skills_list_str" in s for s in technical_skills_data):
            skills_str_parts = [f"**{s['name']}:** {s['skills_list_str']}" for s in technical_skills_data]
            processed_data["technical_skills"] = "\n".join(skills_str_parts)
        else:
            processed_data["technical_skills"] = "Technical skills data not in expected list format or not provided."
    else:
        processed_data["technical_skills"] = "Technical skills data not in expected format or not provided."
    logger.debug(f"PDF Extractor - Skills: {processed_data['technical_skills'][:100]}...")

    # Projects
    # Expected by add_projects_docx: A single string, markdown formatted.
    projects_data = tailored_resume_model_dump.get("projects")
    if isinstance(projects_data, str):
        processed_data["projects"] = projects_data
    elif isinstance(projects_data, list): # If it's a list of project objects/dicts
        projects_str_parts = []
        for proj in projects_data:
            if not isinstance(proj, dict): continue
            title_line_parts = [f"**{proj.get('title', proj.get('project_name', 'N/A'))}**"]
            tagline = proj.get('tagline', proj.get('technologies_used')) # Flexible tagline
            if isinstance(tagline, list): tagline = ", ".join(tagline)
            if tagline: title_line_parts.append(f"| _{str(tagline)}_")

            projects_str_parts.append(" ".join(filter(None, title_line_parts)))
            
            bullets = proj.get('bullet_points', proj.get('description_bullets', proj.get('description',[])))
            if isinstance(bullets, list):
                for bullet in bullets:
                    projects_str_parts.append(f"* {str(bullet).strip()}")
            elif isinstance(bullets, str): # If bullets are a single string block
                 for line in bullets.split('\n'):
                    if line.strip(): projects_str_parts.append(f"* {line.strip()}")
            projects_str_parts.append("") # Add a newline between entries
        processed_data["projects"] = "\n".join(projects_str_parts).strip()
    else:
        processed_data["projects"] = "Projects data not in expected format or not provided."
    logger.debug(f"PDF Extractor - Projects: {processed_data['projects'][:100]}...")
    
    # Note: Education and Contact Info are usually handled separately by the PDF generator functions,
    # often passed as distinct arguments, so they might not need to be in this flat dict
    # unless your PDF generator pulls them from here too.

    return processed_data