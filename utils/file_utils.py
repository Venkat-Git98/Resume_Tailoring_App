import fitz  # PyMuPDF
import logging


def read_pdf_text(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    logging.info(f"Attempting to open PDF: {pdf_path}") # Added for more verbose logging
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logging.error(f"Failed to open PDF file: {pdf_path}. Error: {e}") # Log error with path
        raise RuntimeError(f"Failed to open PDF file: {e}")
    text = ""
    for page_num, page in enumerate(doc): # Added page_num for context
        logging.info(f"Reading text from page {page_num + 1}")
        text += page.get_text()
    doc.close()
    logging.info(f"Successfully read PDF {pdf_path}, total characters extracted: {len(text)}")


    # ---- END TEMPORARY DEBUG BLOCK ----
    return text


def read_text_file(txt_path: str) -> str:
    """Read all text from a plain text file."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to open text file: {e}")
    logging.info(f"Read text file {txt_path}, characters: {len(text)}")
    return text 