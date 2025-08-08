import os
import json
from utils.llm_gemini import LLMRouter
from agents.orchestrator import OrchestratorAgent
from src.docx_to_pdf_generator import (
    generate_styled_resume_pdf,
    generate_cover_letter_pdf,
    ensure_one_page_pdf,
)


def main():
    resume_pdf_candidates = [
        "Shanmugam_ML_2025_4_YOE_M.pdf",
        "Shanmugam_AI_2025_4_YOE.pdf",
    ]
    resume_pdf = next((p for p in resume_pdf_candidates if os.path.exists(p)), None)
    if not resume_pdf:
        raise SystemExit("No resume PDF found in project root.")

    jd_path = "jd.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    router = LLMRouter()
    contact_info = {
        "name": "Venkatesh Shanmugam",
        "email": "svenkatesh.js@gmail.com",
        "phone": "+1 (703) 216-2540",
        "linkedin_url": "https://www.linkedin.com/in/svenkatesh-js/",
        "linkedin_text": "LinkedIn Profile",
        "github_url": "https://github.com/Venkat-Git98",
        "github_text": "GitHub Portfolio",
        "portfolio_url": "https://venkatjs.netlify.app/",
        "portfolio_text": "Personal Portfolio",
        "line1_info": "Virginia US | svenkatesh.js@gmail.com | +1 (703) 216-2540",
    }

    print("Running orchestrator...")
    agent = OrchestratorAgent(llm_client=router)
    state = agent.run(
        resume_pdf_path=resume_pdf,
        contact_info_for_cl=contact_info,
        jd_text=jd_text,
        master_profile_text=None,
        company_name_for_cl=None,
    )

    # Extract tailored data for DOCX
    tailored = state.tailored_resume
    if not tailored:
        raise SystemExit("No tailored resume generated.")
    tailored_data = {
        "summary": tailored.summary or "",
        "work_experience": tailored.work_experience or "",
        "technical_skills": tailored.technical_skills or "",
        "projects": tailored.projects or "",
    }

    education_info = [
        {
            "degree_line": "Master of Science in Computer Science (3.81 / 4.0)",
            "university_line": "George Washington University",
            "dates_line": "August 2023 - May 2025",
        },
        {
            "degree_line": "Bachelor of Technology in Computer Science (3.5/4.0)",
            "university_line": "SRM University",
            "dates_line": "August 2016 - May 2020",
        },
    ]

    out_dir = os.path.join("data", "cli_outputs")
    os.makedirs(out_dir, exist_ok=True)

    print("Generating Resume PDF via Google Drive...")
    resume_pdf_out = generate_styled_resume_pdf(
        tailored_data=tailored_data,
        contact_info=contact_info,
        education_info=education_info,
        output_pdf_directory=out_dir,
        target_company_name=None,
        years_of_experience=4,
        filename_keyword="TailoredResume",
    )
    if not resume_pdf_out or not os.path.exists(resume_pdf_out):
        raise SystemExit("Failed to export Resume PDF via Drive.")
    if not ensure_one_page_pdf(resume_pdf_out):
        print("Resume exceeded one page. Regenerating compact...")
        resume_pdf_out = generate_styled_resume_pdf(
            tailored_data=tailored_data,
            contact_info=contact_info,
            education_info=education_info,
            output_pdf_directory=out_dir,
            target_company_name=None,
            years_of_experience=4,
            filename_keyword="TailoredResume",
            compact=True,
        )
        if not ensure_one_page_pdf(resume_pdf_out):
            print("Warning: Resume still exceeds one page.")
    print("Resume PDF:", resume_pdf_out)

    if state.generated_cover_letter_text:
        print("Generating Cover Letter PDF via Google Drive...")
        cl_pdf_out = generate_cover_letter_pdf(
            cover_letter_body_text=state.generated_cover_letter_text,
            contact_info=contact_info,
            job_title=state.job_description.job_title or "Position",
            company_name=getattr(state.job_description, 'company_name', 'Company') or 'Company',
            output_pdf_directory=out_dir,
            filename_keyword="CoverLetter",
            years_of_experience=4,
        )
        if cl_pdf_out and os.path.exists(cl_pdf_out):
            if not ensure_one_page_pdf(cl_pdf_out):
                print("Cover Letter exceeded one page. Regenerating compact...")
                cl_pdf_out = generate_cover_letter_pdf(
                    cover_letter_body_text=state.generated_cover_letter_text,
                    contact_info=contact_info,
                    job_title=state.job_description.job_title or "Position",
                    company_name=getattr(state.job_description, 'company_name', 'Company') or 'Company',
                    output_pdf_directory=out_dir,
                    filename_keyword="CoverLetter",
                    years_of_experience=4,
                    compact=True,
                )
                if not ensure_one_page_pdf(cl_pdf_out):
                    print("Warning: Cover Letter still exceeds one page.")
            print("Cover Letter PDF:", cl_pdf_out)
        else:
            print("Failed to export Cover Letter PDF via Drive.")
    else:
        print("No cover letter text; skipping CL PDF.")

    # Also output a DOCX for the resume (for user convenience)
    try:
        from docx import Document
        from src.docx_to_pdf_generator import (
            add_contact_info_docx,
            add_summary_docx,
            add_work_experience_docx,
            add_technical_skills_docx,
            add_projects_docx,
            add_education_docx,
        )
        docx_path = os.path.join(out_dir, "TailoredResume.docx")
        document = Document()
        add_contact_info_docx(document, contact_info)
        if tailored_data.get("summary"): add_summary_docx(document, tailored_data["summary"])
        if tailored_data.get("work_experience"): add_work_experience_docx(document, tailored_data["work_experience"])
        if tailored_data.get("technical_skills"): add_technical_skills_docx(document, tailored_data["technical_skills"])
        if tailored_data.get("projects"): add_projects_docx(document, tailored_data["projects"], contact_info)
        add_education_docx(document, education_info)
        document.save(docx_path)
        print("Resume DOCX:", docx_path)
    except Exception as e:
        print("Failed to generate DOCX:", e)


if __name__ == "__main__":
    main()


