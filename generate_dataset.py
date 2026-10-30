import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

ROLES = ["Software Engineer", "Data Analyst", "QA Engineer", "Support Engineer", "DevOps Trainee"]
TIERS = ["Tier 1", "Tier 2", "Tier 3"]
COHORTS = {"2023": (400, 0.0), "2024": (450, 0.3), "2025": (500, -0.2)}


def make_cohort(name, n, shift):
    df = pd.DataFrame({
        "student_id": [f"{name}-{i:04d}" for i in range(n)],
        "cohort": name,
        "college_tier": rng.choice(TIERS, n, p=[0.25, 0.45, 0.30]),
        "role": rng.choice(ROLES, n),
        "other_offers": rng.poisson(0.9, n),
        "deferrals": rng.choice([0, 1, 2, 3], n, p=[0.45, 0.30, 0.17, 0.08]),
        "confirmations_sent": rng.integers(2, 6, n),
        "employer_silence_days": rng.integers(0, 120, n),
        "weeks_inactive_on_plan": rng.integers(0, 12, n),
    })
    df["confirmations_replied"] = [rng.integers(0, s + 1) for s in df["confirmations_sent"]]
    df["modules_completed"] = np.clip(
        rng.poisson(6, n) - df["weeks_inactive_on_plan"] // 2, 0, None
    )
    unanswered = df["confirmations_sent"] - df["confirmations_replied"]
    z = (
        -3.0 + shift
        + 0.35 * df["other_offers"]
        + 0.40 * df["deferrals"]
        + 0.30 * unanswered
        + 0.012 * df["employer_silence_days"]
        + 0.15 * df["weeks_inactive_on_plan"]
        - 0.08 * df["modules_completed"]
        + rng.normal(0, 0.8, n)
    )
    df["joined"] = (rng.random(n) > 1 / (1 + np.exp(-z))).astype(int)
    return df


data = pd.concat([make_cohort(k, n, s) for k, (n, s) in COHORTS.items()], ignore_index=True)
data.to_csv("offer_to_joining_synthetic.csv", index=False)
print(data.groupby("cohort")["joined"].agg(["count", "mean"]))
