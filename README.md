# 🌉 JoinBridge: AI-Assisted Placement Retention & Risk Management Platform

> **Problem Statement / Context:** Campus placement "ghosting" aur offer reneging (students ka offer accept karke baad mein drop out ho jana) ko solve karne ke liye ek smart platform. Yeh colleges aur employers ko real-time risk tracking, transparent student consent, aur automated waitlist promotion provide karta hai.

---

## 🚀 Key Features

* **🔍 Behavioral Risk Prediction Engine (`risk.py`):** Analyzes student activity patterns (inactivity periods, response delays, joining date deferrals) to flag drop-out risks early with transparent reasons.
* **⚡ Graceful Release & Auto-Waitlist Promotion:** Allows students to cleanly release an offer if they choose otherwise, instantly notifying the employer and auto-promoting the top candidate from the waitlist.
* **🔒 Student Consent Toggles:** Empowers students to control which personal data signals (assessment scores, response latency, CGPA) are utilized by the risk engine.
* **📊 Multi-Role Dashboard (`app.py`):** Tailored views for Students, Employers, and College Placement Officers with secure, professional UI styling.
* **📈 Honest Model Validation:** Evaluates historical placement cycles with clear performance comparisons against baseline rules.

---

## 🛠️ Technology Stack

* **Frontend & UI:** Streamlit (Python) with custom clean styling
* **Backend Logic & Risk Engine:** Python (`scikit-learn`, custom threshold rules)
* **Database & Persistence:** SQLite (`store.py`) using secure parameterized queries
* **Testing & Automation:** Pytest for validation workflows

---

## 📂 Project Structure

```text
JoinBridge/
│
├── app.py                 # Main Streamlit application (Multi-role views)
├── store.py               # SQLite database manager & parameterized queries
├── risk.py                # Machine learning and rule-based risk evaluation
├── plan_generator.py      # Dynamic onboarding action plan generator
├── ui.py                  # Custom UI styling and theme helpers
├── test_joinbridge.py     # Automated test suite (pytest)
├── .streamlit/
│   └── config.toml        # Streamlit theme configuration
└── requirements.txt       # Project dependencies
