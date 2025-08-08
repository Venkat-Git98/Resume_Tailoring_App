import os
from agents.orchestrator import OrchestratorAgent
from utils.llm_gemini import LLMRouter


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
        "line1_info": "Virginia US | svenkatesh.js@gmail.com | +1 (703) 216-2540"
    }

    agent = OrchestratorAgent(llm_client=router)
    state = agent.run(
        resume_pdf_path=resume_pdf,
        contact_info_for_cl=contact_info,
        jd_text=jd_text,
        master_profile_text=None,
        company_name_for_cl=None
    )

    print("Orchestrator finished.")
    print("Job title:", getattr(state.job_description, "job_title", None))
    print("ATS keywords:", getattr(state.job_description, "ats_keywords", [])[:25])
    print("Tailored summary len:", len((getattr(state.tailored_resume, 'summary', None) or "")))
    print("CL text len:", len(state.generated_cover_letter_text or ""))


if __name__ == "__main__":
    main()


