import re
from typing import Dict
def split_resume_sections(pdf_text: str) -> Dict[str, str]:
    headers = [
        ('summary', r'SUMMARY'),
        ('work_experience', r'WORK EXPERIENCE'), # Current section being processed
        ('technical_skills', r'TECHNICAL SKILLS'), # Expected next by this list
        ('projects', r'PROJECTS'),
    ]
    pattern = r'(?i)(' + '|'.join(h[1] for h in headers) + r')'
    matches = list(re.finditer(pattern, pdf_text)) # These are in order of appearance in PDF
    section_texts = {}
    for idx, (section_key, header_regex_pattern_from_list) in enumerate(headers): # Iterating in order of `headers` list
        # Find this header_regex_pattern_from_list in matches
        current_header_match = next((m for m in matches if m.group(0).strip().upper() == header_regex_pattern_from_list.upper()), None) # Corrected to use .upper() on the pattern for comparison consistency
        
        if not current_header_match:
            section_texts[section_key] = ''
            continue
        
        start_of_content = current_header_match.end()
        end_of_content = len(pdf_text) # Default end

        # Try to find the *actual next occurring header in the PDF* from the `matches` list
        # to define the end of the current section's content.
        current_header_start_in_pdf = current_header_match.start()
        next_actual_header_in_pdf_match = None
        
        for m_obj in matches: # Iterate through all headers found in PDF order
            if m_obj.start() > current_header_start_in_pdf: # Found a header that appears after the current one
                next_actual_header_in_pdf_match = m_obj
                break # Take the very first one

        if next_actual_header_in_pdf_match:
            end_of_content = next_actual_header_in_pdf_match.start()
            
        section_texts[section_key] = pdf_text[start_of_content:end_of_content].strip()
    return section_texts

def parse_job_description(jd_text: str) -> Dict:
    """Parse job description text into job_title and requirements."""
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    job_title = lines[0] if lines else None
    # Requirements: all non-empty lines after the first (or all lines if only one line)
    requirements = lines[1:] if len(lines) > 1 else lines
    return {
        'job_title': job_title,
        'requirements': requirements
    } 