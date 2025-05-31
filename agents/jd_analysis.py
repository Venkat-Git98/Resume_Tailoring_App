# Resume_Tailoring/agents/jd_analysis.py
import logging
from typing import List, Optional

# Assuming your project structure allows these imports
# If these are in Resume_Tailoring/utils, the path might need adjustment
# depending on how you run the script (e.g., from project root).
# For this example, assuming direct importability if Resume_Tailoring is in PYTHONPATH
from utils.file_utils import read_text_file # Assuming read_text_file is what you use
from models import JobDescription
from utils.llm_gemini import GeminiClient

class JDAnalysisAgent:
    """Agent to analyze the job description text and extract key information, including ATS keywords."""

    def __init__(self, llm_client: GeminiClient):
        if not llm_client:
            logging.warning("JDAnalysisAgent initialized without an LLM client. ATS keyword extraction via LLM will fail.")
            # Consider: raise ValueError("JDAnalysisAgent requires an llm_client instance.")
        self.llm_client = llm_client

    def _extract_ats_keywords_with_llm(self, jd_text: str, job_title: Optional[str]) -> List[str]:
        if not self.llm_client:
            logging.warning("LLM client not available in JDAnalysisAgent; cannot extract ATS keywords via LLM.")
            return []

        prompt = f"""
You are an expert ATS keyword identification system, specifically programmed to analyze job descriptions for roles in Machine Learning, Data Science, Artificial Intelligence, and related fields.

Your task is to meticulously analyze the following job description for the role of "{job_title or 'the position'}".
From this analysis, identify and extract a list of the top 15-20 most critical and specific keywords that an Applicant Tracking System (ATS) would likely be programmed to screen for.

Please prioritize keywords that fall into these categories relevant to Machine Learning and Data Science:

1.  **Programming Languages & Core Data Science Libraries:**
    * Examples: Python, R, SQL, Scala, Java, C++
    * Libraries: Pandas, NumPy, SciPy, Matplotlib, Seaborn, Plotly

2.  **Machine Learning Frameworks & Specialized Libraries:**
    * Examples: Scikit-learn, TensorFlow, PyTorch, Keras, Hugging Face Transformers, spaCy, NLTK, OpenCV
    * Specific ML Libraries: XGBoost, LightGBM, CatBoost, Statsmodels

3.  **Core ML/DS Concepts & Advanced Techniques:**
    * General: Supervised Learning, Unsupervised Learning, Reinforcement Learning, Semi-Supervised Learning
    * Specific Areas: Deep Learning (DL), Natural Language Processing (NLP), Computer Vision (CV), Recommender Systems, Time Series Analysis, Anomaly Detection, Predictive Modeling, Statistical Modeling, Causal Inference, A/B Testing, Experimentation
    * Model Lifecycle: Feature Engineering, Feature Selection, Model Validation (e.g., Cross-Validation), Hyperparameter Tuning, Model Interpretability (e.g., SHAP, LIME), Model Deployment, Model Monitoring

4.  **Specific Algorithms & Model Architectures (if mentioned prominently):**
    * Examples: Linear Regression, Logistic Regression, SVM, Decision Trees, Random Forest, Gradient Boosting Machines (GBM), K-Means, DBSCAN, PCA, Neural Networks (NN), Convolutional Neural Networks (CNN), Recurrent Neural Networks (RNN), LSTMs, Transformers (e.g., BERT, GPT variants)

5.  **MLOps, Data Engineering & Big Data Technologies:**
    * MLOps Concepts: CI/CD for ML, Version Control (Git), Reproducibility
    * MLOps Tools: MLflow, Kubeflow, DVC, Weights & Biases
    * Data Platforms: Apache Spark, Hadoop, Kafka, Flink
    * Databases: SQL (PostgreSQL, MySQL), NoSQL (MongoDB, Cassandra), Data Warehouses (Snowflake, BigQuery, Redshift)
    * Containerization & Orchestration: Docker, Kubernetes

6.  **Cloud Platforms & Services (specifically their AI/ML offerings):**
    * Examples: AWS (SageMaker, S3, EC2, Lambda, EMR), Azure (Azure ML, Blob Storage, Azure Functions), GCP (Vertex AI, Google Cloud Storage, Cloud Functions, BigQuery)

7.  **Key Qualifications & Domain Expertise (if explicitly listed as hard requirements):**
    * Examples: PhD, MSc, "experience in finance", "healthcare analytics" (Extract these only if the JD strongly emphasizes them as essential keywords rather than general descriptive text).

**Instructions for Output:**
* Extract the **exact phrases or acronyms** as they appear in the job description whenever possible.
* Focus on **hard skills and technologies**. Avoid very generic soft skills (e.g., "teamwork", "communication skills") unless they are uniquely phrased as a specific requirement.
* Provide a list of **15-20 keywords**. If more are highly relevant, you can include up to 25.
* **Return ONLY a comma-separated list of these keywords.** Do not include any numbering, bullet points, category names, or any other explanatory text or introductory phrases in your output.

Job Description:
---
{jd_text}
---

Comma-separated ATS keywords:
"""
        try:
            response = self.llm_client.generate_text(prompt, temperature=0.1, max_tokens=200)
            keywords = [kw.strip() for kw in response.split(',') if kw.strip()]
            logging.info(f"Extracted {len(keywords)} ATS keywords via LLM: {keywords}")
            return keywords
        except Exception as e:
            logging.error(f"Failed to extract ATS keywords via LLM: {e}", exc_info=True)
            return []

    # *** MODIFIED run method signature and logic ***
    def run(self, jd_txt_path: Optional[str] = None, jd_text: Optional[str] = None) -> JobDescription:
        """
        Analyzes job description from provided text string or a file path.
        jd_text takes precedence if provided.
        """
        final_jd_text_content = ""
        source_description = ""

        if jd_text and jd_text.strip():
            final_jd_text_content = jd_text
            source_description = "from provided text string"
            logging.info(f"JDAnalysisAgent: Analyzing job description {source_description}.")
            # DEBUG: Log raw content details
            logging.info(f"JDAnalysisAgent DEBUG: Raw jd_text length: {len(jd_text)}")
            logging.info(f"JDAnalysisAgent DEBUG: First 200 chars: {repr(jd_text[:200])}")
        elif jd_txt_path:
            try:
                final_jd_text_content = read_text_file(jd_txt_path)
                source_description = f"from file '{jd_txt_path}'"
                logging.info(f"JDAnalysisAgent: Reading and analyzing job description {source_description}.")
            except RuntimeError as e:
                logging.error(f"JDAnalysisAgent: Failed to read job description file {jd_txt_path}: {e}")
                return JobDescription(job_title="Error: JD File Read Failed", requirements=[str(e)], ats_keywords=[])
        else:
            logging.error("JDAnalysisAgent: Neither jd_text nor jd_txt_path provided. Cannot analyze job description.")
            return JobDescription(job_title="Error: No JD Input", requirements=["No job description input was provided to the agent."], ats_keywords=[])

        if not final_jd_text_content.strip():
            logging.warning(f"JDAnalysisAgent: Job description content is empty {source_description}.")
            return JobDescription(job_title="Empty JD Input", requirements=["Job description content was empty."], ats_keywords=[])

        # DEBUG: Log final content details
        logging.info(f"JDAnalysisAgent DEBUG: Final content length: {len(final_jd_text_content)}")
        logging.info(f"JDAnalysisAgent DEBUG: Final content first 200 chars: {repr(final_jd_text_content[:200])}")

        # Parse job title and requirements from the final_jd_text_content
        lines = [line.strip() for line in final_jd_text_content.splitlines() if line.strip()]
        job_title_extracted = lines[0] if lines else "Unknown Position"
        # For requirements, you can pass the full text or split lines.
        # Passing list of lines is consistent with current JobDescription model.
        requirements_extracted_as_list = lines[1:] if len(lines) > 1 else lines

        # DEBUG: Log parsed values
        logging.info(f"JDAnalysisAgent DEBUG: Total lines: {len(lines)}")
        logging.info(f"JDAnalysisAgent DEBUG: Extracted job_title: {repr(job_title_extracted)}")
        logging.info(f"JDAnalysisAgent DEBUG: Requirements count: {len(requirements_extracted_as_list)}")

        ats_keywords_extracted = []
        if self.llm_client:
            ats_keywords_extracted = self._extract_ats_keywords_with_llm(final_jd_text_content, job_title_extracted)
        else:
            logging.warning("JDAnalysisAgent: LLM client not available. Cannot extract ATS keywords.")

        job_desc_data = {
            "job_title": job_title_extracted,
            "requirements": requirements_extracted_as_list,
            "ats_keywords": ats_keywords_extracted
        }
        
        job_desc = JobDescription(**job_desc_data)
        
        if not job_desc.requirements:
            logging.warning(f"No requirements extracted from JD {source_description}. The JD might be unstructured or empty.")
        if not job_desc.ats_keywords and self.llm_client: # Only warn if LLM was supposed to run
            logging.warning(f"No ATS keywords were extracted by the LLM from the JD {source_description}.")
            
        logging.info(f"JDAnalysisAgent: Completed analysis {source_description}. Title: '{job_desc.job_title}', "
                     f"Req lines: {len(job_desc.requirements)}, ATS keywords: {len(job_desc.ats_keywords)}.")
        return job_desc