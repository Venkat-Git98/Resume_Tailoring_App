from agents.jd_analysis import JDAnalysisAgent


def main():
    jd_path = "jd.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    agent = JDAnalysisAgent(None)
    res = agent.run(jd_text=jd_text)

    print("Job Title:", res.job_title)
    print("Requirements lines:", len(res.requirements))
    print("ATS keywords (top 25):", res.ats_keywords[:25])


if __name__ == "__main__":
    main()


