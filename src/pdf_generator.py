# 

# Resume_Tailoring/src/pdf_generator.py
from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa
from io import BytesIO, StringIO # StringIO can also be useful

import json
import os
import logging
from .data_parser_for_pdf import preprocess_tailored_data_for_pdf

logger = logging.getLogger(__name__)

def generate_pdf_from_json_xhtml2pdf(
    tailored_json_path: str,
    original_resume_pdf_text: str,
    output_pdf_path: str,
    template_dir: str,
    template_name: str = "resume_template.html",
    css_name: str = "resume_style.css"
) -> bool:
    logger.info(f"Starting PDF generation with xhtml2pdf. Output: '{output_pdf_path}', Input JSON: '{tailored_json_path}'")

    try:
        with open(tailored_json_path, 'r', encoding='utf-8') as f:
            tailored_data_json = json.load(f)
        logger.info(f"Successfully loaded tailored JSON data from '{tailored_json_path}'.")
    except Exception as e:
        logger.error(f"Critical Error loading JSON '{tailored_json_path}': {e}", exc_info=True)
        return False

    try:
        logger.info("Preprocessing data for PDF template...")
        resume_data_for_template = preprocess_tailored_data_for_pdf(
            tailored_data_json,
            original_resume_pdf_text
        )
        logger.info("Data preprocessing for PDF template successful.")
    except Exception as e:
        logger.error(f"Critical Error during data preprocessing for PDF template: {e}", exc_info=True)
        return False

    html_output_string = ""
    try:
        if not os.path.isdir(template_dir):
            logger.error(f"Jinja2 template directory not found: '{template_dir}'.")
            return False
        
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template(template_name)
        logger.info(f"Jinja2 template '{template_name}' loaded successfully from '{template_dir}'.")
        html_output_string = template.render(resume_data=resume_data_for_template)
        logger.info("HTML template rendered successfully.")

        intermediate_html_path = os.path.splitext(output_pdf_path)[0] + "_debug.html"
        try:
            with open(intermediate_html_path, "w", encoding="utf-8") as f:
                f.write(html_output_string)
            logger.info(f"Intermediate HTML saved to: {intermediate_html_path}")
        except Exception as e_html_save:
            logger.warning(f"Could not save intermediate HTML debug file: {e_html_save}")

    except Exception as e:
        logger.error(f"Critical Error rendering HTML template: {e}", exc_info=True)
        return False

    # Read CSS content to pass it directly or ensure path is resolvable
    css_file_path = os.path.join(template_dir, css_name)
    css_string = None
    if os.path.exists(css_file_path):
        try:
            with open(css_file_path, 'r', encoding='utf-8') as cf:
                css_string = cf.read()
            logger.info(f"Successfully loaded CSS from '{css_file_path}'.")
        except Exception as e_css:
            logger.warning(f"Could not read CSS file '{css_file_path}': {e_css}. PDF might not be styled correctly.")
    else:
        logger.warning(f"CSS file '{css_file_path}' not found. PDF might not be styled correctly.")

    try:
        logger.info(f"Initiating PDF conversion with xhtml2pdf. Output to: '{output_pdf_path}'")
        with open(output_pdf_path, "w+b") as result_file:
            # Using StringIO for HTML source if pisa prefers it, BytesIO is also common.
            # The key is that html_output_string is a string.
            source_html = StringIO(html_output_string)
            
            # CreatePDF can take default_css argument with CSS string
            # The link_callback helps resolve relative paths for images if any are in your HTML/CSS later
            # and can also help find CSS if linked in HTML and paths are relative to template_dir
            pdf_status = pisa.CreatePDF(
                source_html,                # file-like object of HTML
                dest=result_file,           # file-like object of PDF
                default_css=css_string,     # Pass CSS content directly
                link_callback=lambda uri, rel: os.path.join(template_dir, uri.replace(os.path.basename(template_name), "" ).strip("/"), rel)
                                             # A more robust link_callback for finding relative resources
                                             # This specific callback might need tuning based on how CSS/images are linked.
                                             # A simpler one if CSS is directly provided via default_css:
                                             # link_callback=lambda uri, rel: os.path.join(template_dir, rel)
            )

        if pdf_status.err:
            logger.error(f"xhtml2pdf PDF generation error count: {pdf_status.err}. Errors: {pdf_status.log}")
            # Check pdf_status.log for more details on what went wrong (e.g., CSS errors, missing images)
            return False
        
        logger.info(f"PDF resume successfully generated and saved to: '{output_pdf_path}'")
        return True
    except Exception as e:
        logger.error(f"Critical Error generating PDF with xhtml2pdf: {e}", exc_info=True)
        return False