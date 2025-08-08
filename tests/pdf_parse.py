import os
from utils.file_utils import read_pdf_text
from utils.nlp_utils import split_resume_sections
from src.docx_to_pdf_generator import ensure_one_page_pdf


def main():
    # Prefer user-provided resume; fallback to default sample
    preferred_pdf = "Shanmugam_ML_2025_4_YOE_M.pdf"
    fallback_pdf = "Shanmugam_AI_2025_4_YOE.pdf"
    pdf_path = preferred_pdf if os.path.exists(preferred_pdf) else fallback_pdf
    print("Using PDF:", pdf_path)
    if not os.path.exists(pdf_path):
        raise SystemExit(f"Resume PDF not found: {pdf_path}")

    text = read_pdf_text(pdf_path)
    print("PDF text length:", len(text))
    print("First 600 chars:\n", text[:600])

    sections = split_resume_sections(text)
    print("\nDetected sections and lengths:")
    for k, v in sections.items():
        print(f"- {k}: {len(v)} chars")
        snippet = v[:400]
        print(snippet, "\n---")

    print("Original resume one page:", ensure_one_page_pdf(pdf_path))


if __name__ == "__main__":
    main()


