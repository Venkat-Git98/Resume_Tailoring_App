# Resume_Tailoring/utils/llm_gemini.py
import os
import requests
from typing import List, Optional,Dict 
import logging
from models import ResumeSections, JobDescription, ResumeCritique # Corrected
import config # Corrected
# GeminiClient class remains the same as your provided version
class GeminiClient:
    """Client for generating text using the Gemini Pro LLM via REST API with API key."""
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-pro-001"):
        self.api_key =  api_key or os.getenv("GOOGLE_API_KEY") # Your hardcoded key
        if api_key: 
            self.api_key = api_key
        
        if not self.api_key:
            raise EnvironmentError("Missing Google API key. Set GOOGLE_API_KEY environment variable or pass api_key.")

        self.model = model_name
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_text(self, prompt: str, temperature: float = 0.2, max_tokens: int = 1024, top_p: Optional[float] = None) -> str:
        headers = {"Content-Type": "application/json"}
        
        generation_config = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
        if top_p is not None:
            generation_config["topP"] = top_p

        body = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": generation_config
        }
        logging.debug(f"Sending prompt to Gemini ({self.model}) (first 200 chars): {prompt[:200]}...")
        response = requests.post(self.endpoint, headers=headers, json=body)
        
        if response.status_code != 200:
            logging.error(f"Gemini API call failed: {response.status_code} {response.text}")
            raise RuntimeError(f"Gemini API call failed: {response.status_code} {response.text}")

        try:
            response_json = response.json()
            if not response_json.get("candidates"):
                if response_json.get("error"):
                    error_details = response_json.get("error")
                    logging.error(f"Gemini API returned an error: {error_details.get('message', 'Unknown error')}")
                    raise RuntimeError(f"Gemini API error: {error_details.get('message', 'No candidates and error details missing.')}")
                logging.error(f"No candidates found in Gemini API response: {response_json}")
                raise RuntimeError("No response candidates from Gemini API.")

            candidates = response_json.get("candidates", [])
            if not candidates: 
                raise RuntimeError("No candidates in response after initial check.")

            content_parts = candidates[0].get("content", {}).get("parts", [])
            if not content_parts or "text" not in content_parts[0]:
                finish_reason = candidates[0].get("finishReason")
                if finish_reason not in [None, "STOP", "MAX_TOKENS"]: 
                    safety_ratings = candidates[0].get("safetyRatings", [])
                    logging.error(f"Gemini content generation stopped for reason: {finish_reason}. Safety Ratings: {safety_ratings}. Response: {response_json}")
                    raise RuntimeError(f"Gemini content generation failed. Reason: {finish_reason}. Check logs for details.")
                
                logging.error(f"Unexpected response structure from Gemini API (missing text part): {response_json}")
                raise RuntimeError("Malformed response from Gemini API: Missing text part.")

            generated_text = content_parts[0]["text"]
            logging.debug(f"Received text from Gemini (first 200 chars): {generated_text[:200]}...")
            return generated_text
        except (ValueError, KeyError, IndexError) as e: 
            logging.error(f"Error parsing Gemini API response: {e}. Response text: {response.text}")
            raise RuntimeError(f"Error parsing Gemini API response: {e}")

import logging
from typing import List, Optional

def get_section_prompt(
    section: str,
    original: str,
    job_title: str,
    requirements: List[str],
    ats_keywords: List[str],
    company_name_from_jd: Optional[str] = None,
    job_location_type: Optional[str] = None,
    master_profile_text: Optional[str] = None,
    previously_tailored_sections_text: Optional[str] = None
) -> str:
    reqs_str = '\n'.join(f"- {r}" for r in requirements) if requirements else "No specific requirements provided."
    ats_keywords_str = ', '.join(ats_keywords) if ats_keywords else "No specific ATS keywords identified."

    one_page_constraint_reminder = "CRITICAL OVERALL REMINDER: The entire resume (all sections combined) MUST ideally fit on a single page. Therefore, ensure this current section's content is extremely concise and adheres strictly to all specified length and bullet point limits."

    bolding_instruction = "INSTRUCTION FOR KEYWORD EMPHASIS: Within your rewritten text for THIS section, identify 2-4 of the most impactful keywords or phrases (especially those aligning with the provided ATS KEYWORDS or the KEY REQUIREMENTS from the job description for the target role) and enclose them in double asterisks. For example: 'developed a **machine learning** model for **predictive analytics**.' Do NOT bold section titles or sub-headers themselves using this markdown (e.g., do not output '**Programming Languages:**')."

    master_profile_context_str = ""
    if master_profile_text and master_profile_text.strip():
        master_profile_context_str = f"---\nCANDIDATE'S MASTER PROFILE (Primary source for candidate's detailed skills, experiences, and achievements):\n{master_profile_text}\n---"

    previous_context_block = ""
    if previously_tailored_sections_text and previously_tailored_sections_text.strip():
        previous_context_block = f"---\nPREVIOUSLY TAILORED RESUME SECTIONS (For your context and keyword consistency. Do NOT repeat content from these unless a specific instruction for the current section asks to synthesize or draw from them):\n{previously_tailored_sections_text}\n---"

    # --- MODIFIED how_to_use_context_instruction with new general instructions ---
    how_to_use_context_instruction = f"""
GENERAL INSTRUCTIONS (APPLY TO ALL GENERATED RESUME SECTIONS):
1.  **Primary Goal:** Based on the CANDIDATE'S MASTER PROFILE (if provided), their ORIGINAL CONTENT for the current section, the TARGET JOB TITLE, KEY REQUIREMENTS, and specific ATS KEYWORDS, rewrite and tailor the '{section.upper()}' section. Your main goal for all sections is to impress a recruiter by highlighting the candidate's suitability for the target role with impactful language and quantifiable achievements where possible.
2.  **ATS Optimization (CRITICAL):** Across ALL sections, strategically and naturally integrate relevant ATS keywords from the job description as well as core skills for the target role type. Aim for a high degree of relevance and keyword density to help achieve a strong ATS score (ideally above 80%), without making the text sound unnatural, forced, or repetitive.
3.  **Instruction Adherence:** Follow ALL specific instructions given for the current section regarding length, format, content, and tone METICULOUSLY.
4.  **Avoid Orphan Words (Readability):** Strive for natural sentence flow in all generated text (summaries, bullet points, descriptions). Where possible through minor rephrasing (without sacrificing clarity, conciseness, or impact), try to avoid leaving single or very few words (e.g., 1 or 2 words) on the last line of a paragraph or bullet point. This enhances readability.
5.  **Keyword Integration for Current Section:** Strategically incorporate the provided ATS KEYWORDS into THIS '{section.upper()}' section, ensuring they are used naturally and effectively, especially if they haven't been strongly emphasized in the master profile or original content. Avoid excessive keyword stuffing.
"""
    # --- END MODIFIED ---

    base_prompt_intro = f"""
You are an expert technical resume writer and career coach. Your task is to rewrite a specific section of a candidate's resume to be perfectly tailored for a job application, focusing on showcasing the candidate's qualifications for the role, not the company.
{master_profile_context_str}
{previous_context_block}
{how_to_use_context_instruction}

**Objective:** Rewrite the candidate's '{section.upper()}' section.

**Details for Current Section ('{section.upper()}'):**
* **Candidate's Original Content for '{section.upper()}':**
    ```
    {original.strip() if original and original.strip() else f"No original content was provided by the candidate for the '{section}' section. Rely primarily on the Master Profile if available."}
    ```
* **Target Job Title for this Resume:** "{job_title}" (The resume is being tailored FOR this type of role).
* **Key Requirements/Responsibilities from the Job Description (for overall guidance on relevant skills):**
    {reqs_str}
* **Specific ATS KEYWORDS to prioritize and strategically incorporate into THIS '{section.upper()}' section:**
    `{ats_keywords_str}`
* **Company Name from Job Description (FOR CONTEXT ONLY, DO NOT MENTION IN SUMMARY):** {company_name_from_jd if company_name_from_jd else "Not specified"}
* **Job Location Type from Job Description (FOR CONTEXT ONLY, DO NOT MENTION IN SUMMARY):** {job_location_type if job_location_type else "Not specified"}
"""
    # --- SUMMARY SECTION (UPDATED AS PER YOUR REQUEST) ---
    if section == 'summary':
        candidate_education_level_fact = "The candidate is pursuing a Master's degree (M.S.) in Computer Science."
        return f"""
{base_prompt_intro}

**MANDATORY INSTRUCTIONS & CONSTRAINTS for the SUMMARY section (Follow all very strictly):**
1.  **Focus on Candidate & Role Type, NOT Specific Company/Opportunity:**
    * The summary MUST be about the **candidate's general qualifications, skills, and experience relevant to the *type* of role indicated by the TARGET JOB TITLE ('{job_title}')**.
    * **ABSOLUTELY DO NOT** mention the specific company name ('{company_name_from_jd if company_name_from_jd else "the company"}'), its products, its mission, its values, or any company-specific information.
    * **DO NOT** tailor the summary to the specific company. It should be a general, strong summary for the *type* of role.
    * **DO NOT** mention work arrangement preferences (e.g., remote, hybrid, onsite) or the specific location mentioned in the job description.
2.  **Accurate Educational Qualification (CRITICAL):**
    * **{candidate_education_level_fact}**
    * **YOU MUST ACCURATELY REFLECT THIS EDUCATION LEVEL.** Do NOT state or imply the candidate is a PhD candidate or pursuing a PhD. Refer to the candidate's current Master's degree program as needed, based on the provided Master Profile or Original Content. Ensure factual accuracy regarding their educational qualifications.
3.  **Length & Structure (ABSOLUTELY CRITICAL):**
    * The rewritten summary **MUST be 3 to 4 complete lines long.**
    * The total character count for the entire summary (including spaces) **MUST be strictly between 350 and 450 characters.**
    * **DO NOT produce a summary shorter than 3 complete lines or less than 350 characters.** Be impactful yet concise within these strict limits.
4.  **Content - Core Message (Candidate-Centric):**
    * The summary should clearly articulate the candidate's professional identity (e.g., 'Machine Learning Engineer,' 'Data Scientist') and highlight their core skills and experience that align with the *nature* of the TARGET JOB TITLE ('{job_title}'). **However, DO NOT explicitly state or repeat the TARGET JOB TITLE (e.g., '{job_title}') itself within the summary text.** Focus on the candidate's expertise relevant to this *type* of role.
    * Highlight 2-3 of the candidate's most crucial skills, core competencies, and significant experiences (drawn from their "Original Content of 'SUMMARY'" or "CANDIDATE'S MASTER PROFILE") that directly align with the "Key Requirements" and "ATS KEYWORDS" for the *target role type*.
    * Briefly state total years of relevant experience if clearly available and impactful for the role type.
    * **IMPORTANT FORMATTING NOTE:** The summary text **MUST start directly** with the descriptive text about the candidate. **DO NOT** begin with labels like "Summary:", "Professional Summary:", "Objective:", "Responsibilities:", or any similar prefixes.
5.  **Tone:** Confident, professional, results-oriented, and engaging. Use strong action verbs where appropriate. Avoid clichés and passive voice.
6.  **Accuracy (General):** ONLY use information verifiably present in the "Original Content of 'SUMMARY'" or the "CANDIDATE'S MASTER PROFILE." DO NOT invent new skills, experiences, or qualifications beyond the educational clarification provided above.
7.  {bolding_instruction}
8.  **Output Format:** Provide ONLY the rewritten summary text. Absolutely DO NOT include any introductory phrases like "Rewritten Professional Summary:", section labels (like "SUMMARY:"), or any other headers or conversational text in your output. Start directly with the first sentence of the summary.
9.  {one_page_constraint_reminder}

**Rewritten Professional Summary (Your output should be ONLY the summary text itself, precisely adhering to all instructions above, especially regarding educational accuracy, company non-mention, non-mention of the specific target job title, and length constraints):**
"""

    # --- WORK EXPERIENCE SECTION (UPDATED AS PER YOUR REQUEST) ---
    elif section == 'work_experience':
        role_specific_constraints_guidance = """
    * For each role, aim to make bullet points as impactful and detailed as possible within the specified upper character limit. Avoid overly brief points if more detail can be provided effectively.
    * If a role is titled "AI/ML Engineer" (or very similar, like "Machine Learning Engineer"):
        * Generate EXACTLY 4 bullet points. Each bullet point should aim for **approximately 140-160 characters**, and ideally closer to 160 characters. Each bullet point **MUST be AT LEAST 120 characters** and **MUST NOT EXCEED 160 characters.**
        * Within these character limits, ensure each bullet point provides specific details about the *action taken*, the *technologies used*, the *scale or context*, and the *quantifiable result or impact*. Each point should represent a significant achievement or responsibility.
    * If a role is titled "Data Consultant":
        * Generate EXACTLY 2 bullet points. Each bullet point should aim for **approximately 80-100 characters** and **MUST NOT EXCEED 100 characters.**
    * If a role is titled "Digital Transformation Developer":
        * Generate EXACTLY 2 bullet points. Each bullet point should aim for **approximately 100-120 characters** and **MUST NOT EXCEED 120 characters.**
    * For any other roles identified:
        * Generate 2-3 concise bullet points. Each bullet point should aim for **approximately 130-150 characters** and **MUST NOT EXCEED 150 characters.**
    * Ensure all character limits are for the bullet point text itself (excluding the leading asterisk/bullet symbol or any markdown for bolding).
"""
        return f"""
{base_prompt_intro}

**CRITICAL INSTRUCTIONS - READ AND FOLLOW METICULOUSLY for WORK EXPERIENCE section:**
1.  **Identify ALL Individual Roles:** Carefully parse the "Original Content of 'WORK EXPERIENCE'" (or "CANDIDATE'S MASTER PROFILE") to identify EVERY distinct job role, including Job Title, Company, Employment Dates, and associated responsibilities/achievements.
2.  **PRESERVE AND INCLUDE ALL ROLES:** You **MUST** include and rewrite EVERY distinct job role found in the source text. **DO NOT OMIT ANY ROLES.** If a role seems less relevant, be more concise but DO NOT remove it.
3.  **ACCURACY MANDATE (NO MISATTRIBUTION):** When rewriting each role, you **MUST** only use information, responsibilities, and achievements that are DIRECTLY AND EXCLUSIVELY associated with *that specific role* in the source text. **DO NOT transfer or mix achievements or context from one job role to another.**
4.  **APPLY ROLE-SPECIFIC CONSTRAINTS (MANDATORY FOR BULLETS & LENGTH):**
    {role_specific_constraints_guidance}
5.  **Content & Style for Each Bullet Point (within constraints):**
    * Start with a strong, impactful action verb.
    * Focus on quantifiable achievements or clear, measurable impact related to "ATS KEYWORDS" and "Key Requirements/Keywords from Job Description".
    * Naturally integrate relevant keywords.
    * Each bullet point should ideally be one line, maximum two lines, strictly adhering to its character limit. Strive for natural sentence flow to avoid awkward line breaks (as per general instructions).
6.  {bolding_instruction} (Apply this within each bullet point's text for emphasis on keywords).
7.  **Formatting for Each Role (NO SEPARATE TECH STACK LISTING):**
    **Job Title** | **Company Name** | City, State
    *Dates of Employment (e.g., Month foundry-YYYY – Month foundry-YYYY or Month foundry-YYYY - Present)*
    * Rewritten bullet point 1 (adhering to limits, with **keyword** markdown)
    * Rewritten bullet point 2 (adhering to limits, with **keyword** markdown)
    * ... (and so on, for the specified number of bullets for that role)
    (Ensure any relevant technologies are naturally woven into the bullet points themselves if appropriate and space permits, rather than listed separately.)
8.  **Order:** List roles in reverse chronological order (most recent first).
9.  **No Fabrication:** Base rewrites strictly on the source text. DO NOT INVENT details or achievements.
10. **Tone:** Professional, results-oriented, and human-like.
11. {one_page_constraint_reminder}
12. **Output Format:** Provide ONLY the rewritten work experience text, starting directly with the first job title. Absolutely DO NOT include any introductory phrases like "Rewritten Work Experience Section:" or any other headers in your output.

**Rewritten Work Experience Section (Your output should be only the work experience text itself, formatted as per instruction 7):**
"""

    # --- TECHNICAL SKILLS SECTION (Preserved from your input) ---
    elif section == 'technical_skills':
        return f"""
{base_prompt_intro}

**THE STRATEGIC IMPORTANCE OF THE TECHNICAL SKILLS SECTION:**
The 'Technical Skills' section is critically important as it's often the first area a recruiter or hiring manager scans to quickly assess core technical competencies and alignment with job requirements. It is also heavily weighted by Applicant Tracking Systems (ATS). Therefore, this section must be comprehensive enough to showcase the candidate's relevant abilities for a **Machine Learning role** (or the TARGET JOB TITLE: "{job_title}"), rich in keywords for ATS, yet concise and easy to scan for human readers.

**Mandatory Instructions & Constraints for TECHNICAL SKILLS section (Follow all very strictly):**
1.  **Content Strategy - Blend of Specific and General Core Skills:**
    * **Job-Specific Keywords:** Ensure that technical skills explicitly mentioned in the provided "ATS KEYWORDS" list and the "Key Requirements/Keywords from Job Description" are PROMINENTLY FEATURED if they are part of the candidate's skillset (as indicated by "Original Content" or "CANDIDATE'S MASTER PROFILE"). Use exact phrasing and acronyms from the job description where appropriate for optimal ATS matching.
    * **Core Role-Relevant Skills:** Beyond the immediate job description, this section MUST ALSO showcase a robust set of technical skills generally expected and essential for a **Machine Learning role** (or the TARGET JOB TITLE: "{job_title}"). This demonstrates broader expertise and fundamental preparedness. Refer to the "CANDIDATE'S MASTER PROFILE" and "Original Content of 'TECHNICAL SKILLS'" to identify these core foundational skills (e.g., key programming languages, common ML libraries, fundamental concepts).
    * **Achieve a Balance:** Do not *only* list skills from the current job description. The goal is to present a well-rounded technical profile that is both tailored to the specific job and reflective of the candidate's overall competence in the Machine Learning domain.
2.  **Content Source Hierarchy:**
    * Primarily use skills from the "CANDIDATE'S MASTER PROFILE" if available, as this is the most comprehensive source.
    * Supplement and cross-reference with skills from the "Original Content of 'TECHNICAL SKILLS'".
    * Integrate relevant "ATS KEYWORDS" and "Key Requirements" from the job description if these skills are plausibly possessed by the candidate and align with their broader skill set.
3.  **Categorization & Formatting (STRICT ADHERENCE):**
    * Group related skills under logical, concise subheadings (e.g., Programming Languages, ML Frameworks & Libraries, MLOps & Cloud, Databases & Data Engineering, Key ML Concepts). Use standard industry terms for categories.
    * **Example of desired output format for a category:** `Programming Languages: **Python**, SQL, **Java**`
        (Note: Category names like "Programming Languages:" should NOT be bolded by you with **markdown**; only mark individual skills like **Python** for bolding if they meet the {bolding_instruction} criteria).
4.  **Overall Length, Consistency, and Conciseness (CRITICAL):**
    * Aim for approximately **4 to 5 main categorized skill lines/groups in total** for the entire skills section. This ensures the section is substantial but not overwhelming.
    * Each categorized skill line (meaning the subheading/category label AND all the skills listed for it) **MUST BE STRICTLY UNDER 110 characters.** This is a hard limit per line to maintain scannability and fit.
    * To meet this, be extremely concise in both category names and the skills listed. For any given category, select only the most impactful and relevant skills. For instance, for a 'Machine Learning' category, choose a maximum of 4-5 of the MOST CRITICAL and distinct areas/concepts to ensure the entire line remains under 110 characters.
5.  {bolding_instruction} (Apply this to individual skills within the comma-separated lists, e.g., `**Python**, SQL, **Java**`). Do NOT apply it to the category names.
6.  **Accuracy:** DO NOT list skills the candidate does not demonstrably possess based on the provided source materials.
7.  **Output Format:** Provide ONLY the complete, formatted Skills section text with subheadings and skills, as per the example format. Absolutely DO NOT include any introductory phrases (like "Rewritten Technical Skills Section:"), do NOT use markdown backticks (```) to wrap your entire response, and do NOT include any "##" headers or other section labels in your output. Start directly with the first skill category.
8.  {one_page_constraint_reminder}

**Rewritten Technical Skills Section (Your output should be only the skills text itself, precisely adhering to all instructions, especially length per line, number of categories, and the blend of JD-specific and core role skills for a Machine Learning professional):**
"""
    # --- PROJECTS SECTION (UPDATED AS PER YOUR REQUEST) ---
    elif section == 'projects':
        return f"""
{base_prompt_intro}

**Mandatory Instructions & Constraints for Each Identified Project in the PROJECTS section:**
1.  **Identify Distinct Projects:** Parse from "Original Content of 'PROJECTS'" or "CANDIDATE'S MASTER PROFILE".
2.  **Structure & Content for Each Project (NO SEPARATE TECH STACK LISTING):**
    * **Title:** Clearly state the project title. **Do NOT use markdown like '##' for project titles.** Optionally, you can add a brief, relevant tagline if it fits well (e.g., "| _NLP, RAG_").
    * **Bullet Points:** Provide **EXACTLY 2 bullet points** describing the project.
    * **Character Limit per Bullet:** Each of these 2 bullet points **MUST BE STRICTLY UNDER 170 characters** (aim for 140-160 characters).
    * **Line Flow & Orphans:** Strive for each bullet point to be a single impactful line or, at most, two concise lines to enhance readability and avoid orphan words. Rephrase slightly if needed to ensure lines break cleanly, particularly if a bullet point extends to two lines, while adhering to the character limit.
    * Relevant technologies (especially from "ATS KEYWORDS" or "Key Requirements/Keywords from Job Description") should be naturally woven into the bullet point descriptions if they are key to the achievement and space permits. Do not list a separate "Tech Stack:" line.
3.  **Bullet Point Content (Problem, Action, Result - within constraints):**
    * Focus on problem solved, key actions taken, specific technologies used, and quantifiable results or significant outcomes.
    * Start bullets with strong action verbs.
    * **Terminology and Special Characters:** Use standard technical terminology and acronyms precisely (e.g., "Q&A", "C++", "Node.js"). **Specifically, for "Question and Answer", the preferred term is "Q&A" or "Question-and-Answer". Avoid variations like "Q/A".** Ensure correct usage of other special characters only when part of a standard term.
4.  {bolding_instruction} (Apply this within each bullet point's text for emphasis on keywords).
5.  **Relevance:** Emphasize aspects of the project most relevant to the target job "{job_title}" and its associated "ATS KEYWORDS".
6.  **No Fabrication:** DO NOT invent details, technologies, or outcomes not supported by the original project descriptions.
7.  **Output Format:** Provide ONLY the rewritten project descriptions, starting directly with the first project title. Absolutely DO NOT include any introductory phrases like "Rewritten Projects Section:" or any other "##" headers or markdown for individual project titles in your output.
8.  {one_page_constraint_reminder}

**Rewritten Projects Section (Your output should be only the projects text itself, with each project formatted as per instruction 2):**
"""
    # --- FALLBACK (Preserved from your input) ---
    else:
        logging.warning(f"Received unhandled section type: '{section}' in get_section_prompt. Using a generic refinement prompt.")
        return f"""
You are an expert resume writer. Review the following resume section based on the target job description.
{master_profile_context_str}
{previous_context_block}
The job title is "{job_title}".
Key Requirements from Job Description: {reqs_str}
Specific ATS KEYWORDS to prioritize: {ats_keywords_str}

Original Section Content ('{section}'):
    ```
    {original}
    ```

Please refine this '{section}' section to be concise, impactful, and aligned with the job requirements and ATS keywords.
{bolding_instruction}
Keep the one-page resume constraint in mind.
If this section is not typically valuable or seems irrelevant after considering the job details, you may state: "This section can be omitted to save space."
Output ONLY the refined section text itself or the omission recommendation. Do not include any other "##" headers, markdown backticks (```), or conversational text.
"""



import logging
from typing import Dict, List, Optional

# Ensure logging is configured (e.g., in your main script or at the top of llm_gemini.py)
# logging.basicConfig(level=logging.INFO) # Or your preferred level

def get_cover_letter_prompt(
    candidate_name: str,
    candidate_contact_info: Dict[str, str],
    job_title: str,
    company_name: str,
    job_requirements_summary: str,
    ats_keywords_str: str,
    tailored_resume_summary_text: Optional[str],
    tailored_work_experience_text: Optional[str],
    tailored_projects_text: Optional[str],
    master_profile_text: Optional[str] = None,
    hiring_manager_name: Optional[str] = None,
    project_details_for_cl: Optional[List[Dict[str,str]]] = None
) -> str:
    logging.info("Generating detailed prompt for cover letter generation.")

    contact_info_str = f"Candidate Email: {candidate_contact_info.get('email', 'N/A')}\n"
    if candidate_contact_info.get('phone'):
        contact_info_str += f"Candidate Phone: {candidate_contact_info.get('phone')}\n"
    if candidate_contact_info.get('linkedin_url'):
        contact_info_str += f"Candidate LinkedIn: {candidate_contact_info.get('linkedin_url')}\n"

    profile_source_text = ""
    if master_profile_text and master_profile_text.strip():
        profile_source_text += f"\n\n--- CANDIDATE'S MASTER PROFILE (Use as primary source of truth and detailed context) ---\n{master_profile_text}\n--- END MASTER PROFILE ---"

    if tailored_resume_summary_text and tailored_resume_summary_text.strip():
        profile_source_text += f"\n\n--- CANDIDATE'S TAILORED RESUME SUMMARY ---\n{tailored_resume_summary_text}\n--- END SUMMARY ---"

    if tailored_work_experience_text and tailored_work_experience_text.strip():
        profile_source_text += f"\n\n--- CANDIDATE'S TAILORED WORK EXPERIENCE (Key achievements and roles) ---\n{tailored_work_experience_text}\n--- END WORK EXPERIENCE ---"

    if tailored_projects_text and tailored_projects_text.strip():
        profile_source_text += f"\n\n--- CANDIDATE'S TAILORED PROJECTS (Key projects and contributions) ---\n{tailored_projects_text}\n--- END PROJECTS ---"

    if not profile_source_text:
        profile_source_text = "\nCandidate information (Master Profile, Tailored Resume sections) seems to be missing or incomplete. Base your writing on any available details."

    salutation_address = hiring_manager_name if hiring_manager_name else f"Hiring Team at {company_name}"

    project_context_for_cl = ""
    if project_details_for_cl:
        project_lines = [
            f"- Project: {proj.get('title', 'N/A')}" + (f" (Context: Has Demo URL - {proj.get('url')})" if proj.get('url') else " (Context: No Demo URL provided for this project)")
            for proj in project_details_for_cl
        ]
        if project_lines:
            project_context_for_cl = "\n\n--- KEY PROJECT DETAILS (For your reference if mentioning projects. DO NOT insert any project URLs from here into the cover letter body itself.) ---\n" + "\n".join(project_lines) + "\n--- END KEY PROJECT DETAILS ---"

    # Keyword Bolding Instruction for Cover Letter
    cover_letter_bolding_instruction = """
**Keyword Bolding Guidance:** Throughout the body paragraphs of the cover letter, identify and emphasize 2-4 of the most impactful and relevant keywords, technical skills, or specific experiences that directly align with the 'Key Job Requirements Summary' or 'Key ATS Keywords' for the target role. Enclose these selected terms in double asterisks (e.g., 'My experience with **machine learning algorithms** and **cloud platforms like AWS** makes me a strong candidate.'). Use bolding sparingly and strategically to draw attention to the most critical qualifications. Avoid bolding generic phrases, full sentences, or parts of the salutation/closing.
"""

    prompt = f"""
You are an expert career strategist and an exceptionally skilled cover letter writer, renowned for crafting compelling narratives that captivate recruiters in seconds.
Your task is to write a highly personalized, impactful, and human-written one-page cover letter for '{candidate_name}'.

**CRITICAL GOAL:** The first paragraph MUST be a powerful "10-Second Hook" that makes the recruiter stop and read the entire letter. It should immediately convey strong, specific interest, a unique value proposition, and a direct link to the role or company.

**CONTEXT FOR COVER LETTER GENERATION (Use this information to write the letter):**
{contact_info_str.strip()}
{profile_source_text}
{project_context_for_cl}
{cover_letter_bolding_instruction}

1.  **CANDIDATE INFORMATION (Source Material):**
    * Name: {candidate_name}
    * Contact (for your reference, do not necessarily replicate this verbatim in the letter header unless appropriate for standard letter format):
        {contact_info_str.strip()}
    * Detailed Profile & Experience (draw from these sources, prioritizing the Master Profile if available, then tailored resume sections):
        {profile_source_text}

2.  **TARGET ROLE & COMPANY (Source Material):**
    * Job Title: {job_title}
    * Company Name: {company_name}
    * Key Job Requirements Summary (from Job Description): {job_requirements_summary if job_requirements_summary else 'Not explicitly provided; infer from ATS Keywords and Job Title.'}
    * Key ATS Keywords to Address: {ats_keywords_str if ats_keywords_str else 'Focus on general alignment with the job title and requirements.'}

**INSTRUCTIONS FOR WRITING THE COVER LETTER (Follow Meticulously):**

1.  **Overall Tone & Style:**
    * **Human-Written & Engaging:** Avoid robotic, generic, or overly formal language. Write with authentic enthusiasm and a confident, professional voice.
    * **Well-Crafted:** Ensure impeccable grammar, clear sentence structure, and a smooth, logical flow between paragraphs.
    * **Concise & Impactful:** The entire cover letter MUST NOT exceed one page. Be impactful with fewer words. Every sentence should add clear value.
    * **Keyword Emphasis:** Follow the 'Keyword Bolding Guidance' provided above to highlight key terms effectively.

2.  **Structure & Content Details:**
    * **Salutation:** Address it to "{salutation_address}".
    * **Opening Paragraph (The 10-Second Hook - CRITICAL):**
        * Clearly state the specific position ({job_title}) you are applying for.
        * Immediately articulate your core value proposition or a compelling reason for your interest that directly relates to the company or role. Make this opening uniquely tailored and impactful.
    * **Body Paragraphs (2-3 maximum, each substantial):**
        * **Depth and Elaboration:** Each body paragraph should be well-developed, consisting of at least 3-5 substantial sentences. This is crucial for conveying adequate detail and avoiding a cover letter that feels too short.
        * **Focus on Impact:** For each paragraph, select 1-2 distinct and significant achievements, projects, or skill sets from the "CANDIDATE INFORMATION". Elaborate on the situation, your specific actions/contributions, the skills/technologies utilized (especially those from ATS Keywords), and the **quantifiable results or impact**.
        * **Targeted Relevance:** Clearly demonstrate how each example aligns with the most critical "Key Job Requirements Summary" or "Key ATS Keywords". Show, don't just tell.
        * **Online Presence & Project Mentions:**
            * You can subtly weave in general references to professional online presence if it flows naturally (e.g., "My broader project portfolio, available on my GitHub, showcases...").
            * **Mentioning Specific Projects (CRITICAL - NO URLS IN BODY):** You can and should discuss relevant projects, drawing details from the 'KEY PROJECT DETAILS' or other candidate information. However, **DO NOT include any URLs (like 'http://...' or 'www...') for these specific projects directly in the body of the cover letter.** You can state that project details are available (e.g., 'details of which can be found in my portfolio' or 'as demonstrated in my work on the XYZ project'), but do not attempt to insert HTTP links or placeholders like '[Project URL]' for specific projects within your generated text. The 'KEY PROJECT DETAILS' section in the context (if provided) is for your informational background only regarding which projects might have demos.
        * **Company Focus (CRITICALLY IMPORTANT - AVOID PLACEHOLDERS):**
            * **If '{company_name}' is a specific, real company name (e.g., "NVIDIA", "Google", "Aidaptive", not generic like "Hiring Team" or "A Startup"):**
                * You MUST research (or infer based on common knowledge if specific research isn't possible from the context provided) and weave in 1-2 brief, genuine, and *specific* points about your interest in *that particular company*. This could be related to its known mission, widely recognized values, a significant recent project or product, its industry leadership, or how its specific work aligns with the candidate's career goals or values from the Master Profile.
                * **Your output for this part MUST be the actual personalized sentence(s). DO NOT output instructional text or placeholders like "[mention a specific detail...]" or "[company-specific point]" or similar.**
            * **If, after attempting to personalize, you cannot find truly specific information about '{company_name}' OR if '{company_name}' seems like a generic placeholder:**
                * In this case, instead of specific company details, you should write a sentence or two expressing enthusiasm for the *type of work done in the industry of the '{job_title}'*, or how the *challenges typical for such a role* are what motivate the candidate. Focus on the candidate's passion for the field and the general opportunity the role represents.
                * **Again, DO NOT output any instructional text or placeholders. Generate actual, natural-sounding prose that fits the context.**
    * **Closing Paragraph:**
        * Briefly reiterate your strong interest and confidence in your ability to contribute.
        * You can include a phrase like: "My full professional profile, showcasing my projects and contributions, is detailed on my LinkedIn and GitHub, referenced in my resume."
        * Include a clear call to action, expressing your eagerness to discuss your qualifications further in an interview.
    * **Professional Closing (Formatting CRITICAL):**
        * Use a standard closing like 'Sincerely,'.
        * Then, ensure there is **one clear blank line** (equivalent to two newline characters in raw text: '\\n\\n') before writing the candidate's name: '{candidate_name}'.
        * **Example of desired raw text output for closing:**
            Sincerely,\\n
            \\n
            {candidate_name}
        * The generated text for the cover letter MUST END after the candidate's name. Any additional contact information or profile links (like GitHub/Portfolio as separate lines below the name) will be handled by downstream DOCX formatting processes and should NOT be part of your generated text here.

3.  **What to AVOID (Strict Adherence Required):**
    * **Do NOT include a date** anywhere in the cover letter.
    * Do NOT simply rehash the resume. Synthesize and connect the dots to the target role.
    * Avoid clichés (e.g., "I am a hardworking team player"). Show your qualities through examples.
    * Do NOT make up information or skills not present in the provided "CANDIDATE INFORMATION".
    * Do NOT include your own headers like "Cover Letter:" or "Dear {salutation_address}," if the salutation is already handled by the structure above. Start directly with the salutation.
    * **CRITICALLY AVOID (PLACEHOLDERS):** Do not output any instructional text or placeholders from this prompt (e.g., "[mention a specific detail...]", "[company-specific point]", "[Project URL]"). Your response must be the cover letter itself, ready for use.
    * **CRITICALLY AVOID (PROJECT URLS IN BODY):** Do not insert any URLs for specific projects (e.g., 'http://...', 'www...') within the body paragraphs when discussing projects.

**OUTPUT FORMAT:**
Provide ONLY the text of the cover letter, formatted as a standard business letter. This includes the salutation, the body paragraphs (with keyword bolding applied as per 'Keyword Bolding Guidance'), and the closing (formatted as specified above). Do not add any other explanations, titles, or text before or after the cover letter itself.

--- BEGIN COVER LETTER ---
"""
    return prompt


def get_resume_critique_prompt(
    job_title: str,
    job_description_text: str, 
    ats_keywords: List[str],   
    tailored_resume_text: str, # Full text of the tailored resume
    candidate_name: Optional[str] = "the candidate"

) -> str:
    logging.info("Generating enhanced prompt for comprehensive resume critique.")
    ats_keywords_str = ", ".join(ats_keywords) if ats_keywords else "Not specifically provided."
    
   
    prompt = f"""
You are an expert AI resume reviewer combining the precision of an ATS with the critical eye of an experienced senior recruiter and a meticulous proofreader.
Your task is to provide a comprehensive evaluation of the TAILORED RESUME for '{candidate_name}' against the JOB DESCRIPTION for the role of '{job_title}'.

**Inputs for Your Analysis:**
1.  **Job Title:** {job_title}
2.  **Full Job Description:**
    ```
    {job_description_text}
    ```
3.  **Key ATS Keywords derived from Job Description:** {ats_keywords_str}
4.  **Candidate's Tailored Resume (TEXT ONLY):** ```
    {tailored_resume_text}
    ```
    (Note: You are analyzing the text content. You cannot see the final PDF formatting or actual page breaks.)

**Evaluation Output Required (Strict Format - Each item on a new line):**
ATS_SCORE: [Provide a numerical percentage score from 0 to 100, e.g., 85.5, based on keyword alignment and content relevance.]
ATS_PASS: [Brief assessment - e.g., Likely to pass, Borderline, Needs significant keyword improvement.]
RECRUITER_IMPRESSION: [Brief assessment of overall impact on a recruiter - e.g., Highly impressive and engaging, Good fit needs minor polish, Lacks impact needs substantial revision.]
POTENTIAL_LENGTH_CONCERN: [Based on the *amount of text*, assess if it's concise for a target of one page. Examples: 'Concise, likely fits one page.', 'Moderate length, should fit one page.', 'Extensive text, may risk exceeding one page; review section lengths carefully.', 'Very brief, might appear underdeveloped.']
CONTENT_STRUCTURE_AND_CLARITY: [Assess if the content is well-organized (based on typical resume sections like Summary, Experience, Skills, Projects), if the language is clear, and if there are any sentences or phrases that seem out of place, awkward, or grammatically incorrect. Highlight any specific phrases needing immediate attention. Example: 'Well-structured. One phrase in projects, "...XYZ...", seems awkward and needs rephrasing.']
FORMATTING_CONSISTENCY_FROM_TEXT: [Based *only* on the provided text, identify any textual inconsistencies that might *imply* formatting issues (e.g., mixed date formats if visible in text, inconsistent use of terminology for similar items, bullet points not starting with action verbs if that was an instruction). You cannot see visual formatting. Example: 'Bullet points in work experience consistently start with action verbs. Date formats appear consistent.' or 'Inconsistent phrasing for similar project metrics noted.']

**Detailed Instructions for Each Output Point:**
* **ATS_SCORE:** Focus on keyword density/relevance (ATS Keywords & JD terms), alignment of experience with job requirements, and overall structure readable by an ATS. Provide only the number.
* **ATS_PASS:** Your qualitative judgment on ATS pass likelihood based on the score and analysis.
* **RECRUITER_IMPRESSION:** Beyond keywords, assess if the achievements, clarity, and impact of language would quickly impress a human recruiter.
* **POTENTIAL_LENGTH_CONCERN:** As you cannot see the PDF, make an educated guess based on the volume of text provided. Is it lean and impactful, or does it seem overly verbose suggesting it might struggle to fit a single page attractively?
* **CONTENT_STRUCTURE_AND_CLARITY:** Look for logical flow between sections (if discernible from headers in the text), clarity of sentences, and any awkward phrasing or grammatical errors that need immediate attention before applying. Point out specific examples of problematic text if found.
* **FORMATTING_CONSISTENCY_FROM_TEXT:** Comment on patterns in the text that suggest good or poor formatting discipline (e.g., are all job titles bolded if that's a text convention used? Are bullet points consistently structured in the text?). Avoid commenting on visual layout you cannot see.

Keep each assessment concise and actionable.

*   **Output Format:** `RECRUITER_IMPRESSION: [Your assessment, e.g., Strengths: Clear summary and impactful project descriptions. Weaknesses: Work experience could be more quantified.]`

**Example of the EXACT expected output format (Your response MUST look like this):**
```
ATS_SCORE: 88%
ATS_PASS: Likely to pass. The resume shows good alignment with several key skills like Python, machine learning, and data analysis, which are prominent in the job description.
RECRUITER_IMPRESSION: The resume is well-structured and easy to read. The summary effectively highlights relevant experience. To further strengthen, quantify achievements in the project section more consistently.
```

**Your entire output MUST strictly follow this three-part structure with the specified labels (ATS_SCORE:, ATS_PASS:, RECRUITER_IMPRESSION:). Do not add any other text, headers, or explanations.**
"""
    return prompt