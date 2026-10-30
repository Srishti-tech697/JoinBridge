"""Data layer for JoinBridge.

Every risk signal comes from a recorded event (confirmation sent, student replied, module done,
joining date changed), not from numbers typed in by hand.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

import pandas as pd

import plan_generator
import risk

DB = os.environ.get("JOINBRIDGE_DB", "joinbridge_v2.db")
ACTIVE = ("Offered", "Confirmed", "Deferred", "At Risk")
ALL_STATUSES = ["Offered", "Confirmed", "Deferred", "At Risk", "Joined", "Released"]
CHECKIN_OPTIONS = ["Yes", "Not sure", "No"]
TASK_KINDS = ["Quiz", "Practical task", "Email reply"]
EDITABLE = {
    "status", "joining_date", "expected_window", "update_by", "other_offers", "deferrals",
    "confirmations_sent", "confirmations_replied", "modules_done", "created_at",
    "last_student_activity", "last_employer_update", "checkin", "release_reason",
}


def today():
    return date.today()


def iso(d):
    return d.isoformat() if isinstance(d, date) else d


@contextmanager
def _con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _con() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS offers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student TEXT NOT NULL, company TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
                joining_date TEXT, expected_window TEXT DEFAULT '', update_by TEXT,
                other_offers INTEGER DEFAULT 0, deferrals INTEGER DEFAULT 0,
                confirmations_sent INTEGER DEFAULT 0, confirmations_replied INTEGER DEFAULT 0,
                modules_done INTEGER DEFAULT 0,
                created_at TEXT, last_student_activity TEXT, last_employer_update TEXT,
                checkin TEXT, release_reason TEXT);
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT, offer_id INTEGER NOT NULL,
                title TEXT NOT NULL, kind TEXT NOT NULL, done INTEGER DEFAULT 0, created_at TEXT);
            CREATE TABLE IF NOT EXISTS waitlist(
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL,
                promoted INTEGER DEFAULT 0);
        """)
    plan_generator.ensure_table(DB)


# ---------- reading ----------
def get_offers():
    with _con() as con:
        return pd.read_sql_query("SELECT * FROM offers ORDER BY id DESC", con)


def get_offer(offer_id):
    with _con() as con:
        row = con.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    return dict(row) if row else None


def get_tasks(offer_id):
    with _con() as con:
        return [dict(r) for r in con.execute("SELECT * FROM tasks WHERE offer_id=? ORDER BY id", (offer_id,))]


def get_waitlist():
    with _con() as con:
        return [dict(r) for r in con.execute("SELECT * FROM waitlist ORDER BY id")]


# ---------- employer actions ----------
def add_offer(student, company, role, joining_date=None, expected_window="", update_by=None, status="Offered"):
    t = iso(today())
    with _con() as con:
        cur = con.execute(
            "INSERT INTO offers(student, company, role, status, joining_date, expected_window, update_by,"
            " created_at, last_student_activity, last_employer_update) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (student, company, role, status, iso(joining_date), expected_window, iso(update_by), t, t, t),
        )
        return cur.lastrowid


def update_fields(offer_id, **fields):
    bad = set(fields) - EDITABLE
    if bad:
        raise ValueError(f"cannot edit: {sorted(bad)}")
    sets = ", ".join(f"{k}=?" for k in fields)
    with _con() as con:
        con.execute(f"UPDATE offers SET {sets} WHERE id=?", (*[iso(v) for v in fields.values()], offer_id))


def set_status(offer_id, status):
    if status not in ALL_STATUSES:
        raise ValueError("unknown status")
    update_fields(offer_id, status=status)


def change_joining_date(offer_id, new_date):
    """First announcement is not a deferral; changing an announced date is."""
    o = get_offer(offer_id)
    deferred = 1 if o["joining_date"] and o["joining_date"] != iso(new_date) else 0
    status = "Deferred" if deferred and o["status"] in ("Offered", "Confirmed") else o["status"]
    with _con() as con:
        con.execute(
            "UPDATE offers SET joining_date=?, deferrals=deferrals+?, status=?, last_employer_update=? WHERE id=?",
            (iso(new_date), deferred, status, iso(today()), offer_id),
        )


def send_confirmation(offer_id):
    with _con() as con:
        con.execute("UPDATE offers SET confirmations_sent=confirmations_sent+1, last_employer_update=? WHERE id=?",
                    (iso(today()), offer_id))


def post_update(offer_id):
    update_fields(offer_id, last_employer_update=today())


def add_task(offer_id, title, kind):
    with _con() as con:
        con.execute("INSERT INTO tasks(offer_id, title, kind, created_at) VALUES (?,?,?,?)",
                    (offer_id, title, kind, iso(today())))


def add_waitlist(name, role):
    with _con() as con:
        con.execute("INSERT INTO waitlist(name, role) VALUES (?,?)", (name, role))


# ---------- student actions ----------
def _activity(offer_id):
    update_fields(offer_id, last_student_activity=today())


def student_accept(offer_id):
    o = get_offer(offer_id)
    if o["status"] == "Offered":
        update_fields(offer_id, status="Confirmed")
    _activity(offer_id)


def student_confirm_date(offer_id):
    with _con() as con:
        con.execute(
            "UPDATE offers SET confirmations_replied=MIN(confirmations_sent, confirmations_replied+1),"
            " last_student_activity=? WHERE id=?", (iso(today()), offer_id))


def complete_module(offer_id, total_modules):
    with _con() as con:
        con.execute("UPDATE offers SET modules_done=MIN(?, modules_done+1), last_student_activity=? WHERE id=?",
                    (total_modules, iso(today()), offer_id))


def complete_task(task_id):
    with _con() as con:
        row = con.execute("SELECT offer_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        con.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))
    _activity(row["offer_id"])


def set_checkin(offer_id, answer):
    if answer not in CHECKIN_OPTIONS:
        raise ValueError("unknown answer")
    update_fields(offer_id, checkin=answer)
    _activity(offer_id)


def set_other_offers(offer_id, n):
    update_fields(offer_id, other_offers=int(n))
    _activity(offer_id)


def release(offer_id, reason):
    """Graceful Release: the offer is released early and the next waitlisted candidate is promoted."""
    o = get_offer(offer_id)
    if not o or o["status"] not in ACTIVE:
        raise ValueError("Only an active offer can be released")
    promoted = None
    with _con() as con:
        con.execute("UPDATE offers SET status='Released', release_reason=? WHERE id=?", (reason, offer_id))
        w = (con.execute("SELECT * FROM waitlist WHERE promoted=0 AND role=? ORDER BY id LIMIT 1", (o["role"],)).fetchone()
             or con.execute("SELECT * FROM waitlist WHERE promoted=0 ORDER BY id LIMIT 1").fetchone())
        if w:
            con.execute("UPDATE waitlist SET promoted=1 WHERE id=?", (w["id"],))
            t = iso(today())
            cur = con.execute(
                "INSERT INTO offers(student, company, role, status, joining_date, expected_window, update_by,"
                " created_at, last_student_activity, last_employer_update) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (w["name"], o["company"], o["role"], "Offered", o["joining_date"], o["expected_window"],
                 o["update_by"], t, t, t),
            )
            promoted = {"id": cur.lastrowid, "name": w["name"], "role": o["role"]}
    return promoted


# ---------- risk ----------
def _days_since(s):
    return max((today() - date.fromisoformat(s)).days, 0) if s else 0


def features(o):
    """Signals for the risk model, all derived from recorded events."""
    return {
        "weeks_inactive": _days_since(o["last_student_activity"]) // 7,
        "unanswered": o["confirmations_sent"] - o["confirmations_replied"],
        "deferrals": o["deferrals"],
        "employer_silence_days": _days_since(o["last_employer_update"]),
        "other_offers": o["other_offers"],
        "modules_completed": o["modules_done"],
    }


def assess(o):
    """Model score + PS rules + direct signals (check-in, missing date). None if the offer is no longer active."""
    if o["status"] not in ACTIVE:
        return None
    f = features(o)
    res = risk.score(f)
    rules = list(res["rules_triggered"])
    if o["checkin"] == "Not sure":
        rules.append("Student said they are not sure about joining")
    if o["checkin"] == "No":
        rules.append("Student said they will not join")
    if not o["joining_date"]:
        waiting = _days_since(o["created_at"])
        if waiting >= 14:
            rules.append(f"Joining date not announced for {waiting} days")
        if o["update_by"] and date.fromisoformat(o["update_by"]) < today():
            rules.append(f"Employer promised a date by {o['update_by']}, now overdue")
    change = list(res["what_would_change"])
    if not o["joining_date"]:
        change.append("Employer announces the joining date")
    if o["checkin"] in ("Not sure", "No"):
        change.append("Recruiter talks to the student about their concerns")
    return {**res, "rules_triggered": rules, "what_would_change": change, "features": f,
            "at_risk": res["risk"] >= 0.5 or bool(rules), "priority": res["risk"] + 0.2 * len(rules)}


def risk_list():
    items = []
    for _, row in get_offers().iterrows():
        o = row.to_dict()
        a = assess(o)
        if a:
            items.append({"offer": o, "a": a})
    return sorted(items, key=lambda i: i["a"]["priority"], reverse=True)


def needs_employer_action():
    """Offers where the employer owes the student a joining date."""
    out = []
    for _, row in get_offers().iterrows():
        o = row.to_dict()
        if o["status"] in ACTIVE and not o["joining_date"]:
            waiting = _days_since(o["created_at"])
            overdue = o["update_by"] and date.fromisoformat(o["update_by"]) < today()
            if waiting >= 14 or overdue:
                out.append((o, "promised date is overdue" if overdue else f"no joining date for {waiting} days"))
    return out


def suggested_message(o, a):
    m = f"Hi {o['student'].split()[0]}, hope you are well. We wanted to check in about your {o['role']} role at {o['company']}. "
    if o["joining_date"]:
        m += f"Your joining date is {o['joining_date']}. "
    else:
        m += "We have not fixed your joining date yet" + (f" and will share it by {o['update_by']}. " if o["update_by"] else ". ")
    f = a["features"]
    if f["unanswered"] > 0 and o["joining_date"]:
        m += "Could you please confirm your joining date in the app? "
    if f["weeks_inactive"] >= 3:
        m += "Your pre-joining plan is waiting for you, and even one module helps. "
    m += "If your plans have changed, please tell us early in the app. We would rather know than be surprised."
    return m


def college_report():
    df = get_offers()
    counts = df["status"].value_counts().to_dict()
    offers, joined = len(df), counts.get("Joined", 0)
    no_date = int((df["joining_date"].isna() & df["status"].isin(ACTIVE)).sum())
    return {
        "offers": offers, "joined": joined, "released": counts.get("Released", 0),
        "waiting": int(df["status"].isin(ACTIVE).sum()), "no_date": no_date,
        "true_placement_rate": round(joined / offers, 2) if offers else 0.0, "by_status": counts,
    }


def load_sample():
    """Fictional demo data with realistic ages, so the risk list has something to explain."""
    t = today()
    d = lambda n: t - timedelta(days=n)  # noqa: E731
    f = lambda n: t + timedelta(days=n)  # noqa: E731
    rows = [
        ("Riya Sharma", "Brightwave Systems", "Software Engineer", f(120), "", None, "Confirmed",
         dict(modules_done=3, confirmations_sent=2, confirmations_replied=2, last_student_activity=d(2), last_employer_update=d(6), checkin="Yes")),
        ("Aman Verma", "Kiteloop", "Data Analyst", f(120), "", None, "Offered",
         dict(confirmations_sent=3, confirmations_replied=0, other_offers=2, deferrals=1, last_student_activity=d(32), last_employer_update=d(45))),
        ("Priya Nair", "Orbit Analytics", "QA Engineer", None, "July or August", d(5), "Offered",
         dict(created_at=d(40), last_student_activity=d(12), last_employer_update=d(40))),
        ("Rahul Mehta", "Brightwave Systems", "Support Engineer", f(120), "", None, "Confirmed",
         dict(checkin="Not sure", modules_done=1, last_student_activity=d(9), last_employer_update=d(20))),
        ("Sneha Iyer", "Kiteloop", "Data Analyst", d(10), "", None, "Joined", dict(modules_done=4)),
        ("Karan Singh", "Orbit Analytics", "DevOps Trainee", f(120), "", None, "Confirmed",
         dict(modules_done=4, confirmations_sent=1, confirmations_replied=1, last_student_activity=d(1), last_employer_update=d(3))),
        ("Ananya Rao", "Brightwave Systems", "Software Engineer", f(120), "", None, "Released", dict(release_reason="Accepted another offer")),
        ("Vikram Joshi", "Kiteloop", "QA Engineer", f(150), "", None, "Deferred",
         dict(deferrals=3, confirmations_sent=2, confirmations_replied=0, other_offers=1, last_student_activity=d(28), last_employer_update=d(35))),
    ]
    for student, company, role, jd, window, upd, status, extra in rows:
        oid = add_offer(student, company, role, jd, window, upd, status)
        if extra:
            update_fields(oid, **extra)
    first = get_offers().sort_values("id").iloc[0]["id"]
    add_task(int(first), "Short quiz on Python basics", "Quiz")
    for name, role in [("Sahil Kapoor", "Software Engineer"), ("Mitali Desai", "Data Analyst"), ("Ishaan Bose", "QA Engineer")]:
        add_waitlist(name, role)