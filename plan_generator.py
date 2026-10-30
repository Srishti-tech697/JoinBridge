"""Pre-joining plan: role description -> matched catalogue courses -> weekly plan (employer can edit).

NOTE: CATALOGUE below is a SAMPLE. Replace it with the real pre-joining course catalogue
from the organisers (keep the same fields: title + keywords).
"""
import json
import sqlite3

CATALOGUE = [
    {"title": "Python Fundamentals", "keywords": ["python", "programming", "scripting"]},
    {"title": "Git and Version Control", "keywords": ["git", "github", "version control"]},
    {"title": "Data Structures Basics", "keywords": ["data structures", "algorithms", "clean code"]},
    {"title": "REST APIs with FastAPI", "keywords": ["api", "rest", "backend"]},
    {"title": "SQL for Beginners", "keywords": ["sql", "database", "queries"]},
    {"title": "Excel for Analysis", "keywords": ["excel", "spreadsheet"]},
    {"title": "Statistics Essentials", "keywords": ["statistics", "analyse", "analysis"]},
    {"title": "Data Visualization", "keywords": ["charts", "dashboards", "visualization"]},
    {"title": "Software Testing Basics", "keywords": ["test cases", "testing", "manual"]},
    {"title": "Test Automation", "keywords": ["automated", "automation", "selenium"]},
    {"title": "Linux Command Line", "keywords": ["linux", "shell", "command line"]},
    {"title": "Networking Basics", "keywords": ["networking", "troubleshoot", "tcp"]},
    {"title": "Customer Communication", "keywords": ["communication", "customers", "support"]},
    {"title": "Docker Essentials", "keywords": ["docker", "containers"]},
    {"title": "Cloud Basics", "keywords": ["cloud", "deployment", "aws"]},
    {"title": "CI/CD Basics", "keywords": ["ci/cd", "pipeline"]},
]

ROLE_DESC = {
    "Software Engineer": "Build backend services in Python, design REST APIs, work with git and SQL databases, and write clean code using data structures.",
    "Data Analyst": "Analyse data using SQL and Excel, apply statistics, and build charts and dashboards for business teams.",
    "QA Engineer": "Write test cases, run manual and automated testing with selenium, and query databases with SQL to verify results.",
    "Support Engineer": "Troubleshoot customer issues using the linux command line and networking knowledge, with strong communication with customers.",
    "DevOps Trainee": "Work with linux, git, docker containers and cloud deployment, and help maintain a CI/CD pipeline.",
}


def generate(role, weeks=4):
    """Keyword-match the role description against the catalogue; explain every pick."""
    desc = ROLE_DESC.get(role, role).lower()
    scored = []
    for course in CATALOGUE:
        hits = [k for k in course["keywords"] if k in desc]
        if hits:
            scored.append((len(hits), course, hits))
    scored.sort(key=lambda t: -t[0])  # stable: ties keep catalogue order
    return [{"week": i + 1, "title": c["title"], "note": "Matches role: " + ", ".join(h)}
            for i, (_, c, h) in enumerate(scored[:weeks])]


def ensure_table(db):
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS plans(candidate_id INTEGER PRIMARY KEY, weeks TEXT)")
    con.commit()
    con.close()


def get_plan(db, cid, role):
    con = sqlite3.connect(db)
    row = con.execute("SELECT weeks FROM plans WHERE candidate_id=?", (cid,)).fetchone()
    con.close()
    if row:
        return {"source": "edited by employer", "weeks": json.loads(row[0])}
    return {"source": "generated from role description", "weeks": generate(role)}


def save_plan(db, cid, weeks):
    con = sqlite3.connect(db)
    con.execute("INSERT OR REPLACE INTO plans VALUES (?,?)", (cid, json.dumps(weeks)))
    con.commit()
    con.close()
