from datetime import date, timedelta

import pandas as pd
import streamlit as st

import plan_generator
import risk
import store

st.set_page_config(page_title="JoinBridge", page_icon="🤝", layout="wide")

# status -> (text colour, background colour)
STATUS_COLORS = {
    "Offered": ("#44627F", "#E6EEF6"),
    "Confirmed": ("#0B7F7F", "#DDF3F2"),
    "Deferred": ("#A86400", "#FFF0D2"),
    "At Risk": ("#BE3A2B", "#FCE3E0"),
    "Joined": ("#2A7A4B", "#E0F2E7"),
    "Released": ("#5F6B7A", "#ECEFF3"),
}
RELEASE_REASONS = ["Accepted another offer", "Personal reasons", "Higher studies", "Joining date unsuitable", "Other"]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=Figtree:wght@400;500;600&display=swap');
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button {
    font-family: 'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.stApp h1, .stApp h2, .stApp h3 { font-family: 'Bricolage Grotesque', 'Figtree', sans-serif; color: #0E2A47; letter-spacing: -0.01em; }
.block-container { padding-top: 1.4rem; max-width: 1180px; }
footer { visibility: hidden; }
.jb-hero { background: #0E2A47; color: #fff; border-radius: 16px; padding: 22px 28px; display: flex; align-items: center; gap: 18px; }
.jb-hero svg { flex: none; }
.jb-title { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 34px; line-height: 1.1; }
.jb-sub { color: #B9CADB; font-size: 16px; margin-top: 4px; }
.jb-meta { color: #4A5A6A; font-size: 14px; margin: 18px 0 8px; }
.jb-pipe { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 18px; }
.jb-step { background: #fff; border: 1px solid #E1E7EE; border-top: 4px solid var(--c); border-radius: 12px; padding: 12px 14px; }
.jb-step b { display: block; font-family: 'Bricolage Grotesque', sans-serif; font-size: 32px; line-height: 1.1; color: var(--c); }
.jb-step span { font-size: 13px; color: #4A5A6A; }
@media (max-width: 800px) { .jb-pipe { grid-template-columns: repeat(3, 1fr); } }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { padding: 8px 16px; border-radius: 10px 10px 0 0; font-weight: 600; }
[data-testid="stForm"] { background: #fff; border: 1px solid #E1E7EE; border-radius: 14px; padding: 18px; }
.stButton > button, .stFormSubmitButton > button { background: #0E2A47; color: #fff; border: 0; border-radius: 10px; padding: 0.55rem 1.2rem; font-weight: 600; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background: #0FA3A3; color: #fff; }
.stButton > button:disabled { background: #AEB9C5; color: #fff; }
.st-key-release_btn button { background: #BE3A2B; }
.st-key-release_btn button:hover { background: #962D21; }
.jb-note { background: #fff; border: 1px solid #E1E7EE; border-left: 5px solid #0FA3A3; border-radius: 10px; padding: 12px 16px; color: #2B3A49; margin-bottom: 14px; }
.jb-note.warn { border-left-color: #F28C28; }
.jb-card { background: #fff; border: 1px solid #E1E7EE; border-radius: 14px; padding: 16px 18px; margin-bottom: 14px; }
.jb-status { font-family: 'Bricolage Grotesque', sans-serif; font-size: 26px; font-weight: 700; color: #0E2A47; }
.jb-big { font-family: 'Bricolage Grotesque', sans-serif; font-size: 52px; font-weight: 800; color: #0FA3A3; line-height: 1; }
.jb-bar { display: flex; align-items: center; gap: 10px; margin: 6px 0; font-size: 14px; }
.jb-bar .lab { width: 90px; }
.jb-bar .fill { height: 14px; border-radius: 4px; background: var(--c); min-width: 3px; }
</style>
"""

BRIDGE_SVG = """
<svg width="64" height="44" viewBox="0 0 64 44" fill="none" aria-hidden="true">
  <path d="M4 34 Q32 -6 60 34" stroke="#0FA3A3" stroke-width="3" fill="none"/>
  <path d="M2 34 H62" stroke="#F28C28" stroke-width="3"/>
  <path d="M16 34 V19 M28 34 V11 M36 34 V11 M48 34 V19" stroke="#B9CADB" stroke-width="2"/>
</svg>
"""


# ---------- helpers ----------
def flash(message):
    st.session_state["flash"] = message


def paint(value):
    colors = STATUS_COLORS.get(value)
    return f"color:{colors[0]};background-color:{colors[1]};font-weight:600" if colors else ""


def stretch(data, **kw):
    """Full-width table that works on old and new Streamlit versions."""
    try:
        st.dataframe(data, width="stretch", hide_index=True, **kw)
    except TypeError:
        st.dataframe(data, use_container_width=True, hide_index=True, **kw)


def label_of(o):
    return f'{o["student"]} - {o["company"]} (Offer ID: {o["id"]})'


def options_of(df):
    return {label_of(row): int(row["id"]) for _, row in df.iterrows()}


def date_text(o):
    if o["joining_date"]:
        return o["joining_date"]
    return "Not announced" + (f' (expected: {o["expected_window"]})' if o["expected_window"] else "")


def pipeline_html(df, flagged):
    counts = df["status"].value_counts().to_dict() if not df.empty else {}
    steps = "".join(
        f'<div class="jb-step" style="--c:{STATUS_COLORS[s][0]}"><b>{counts.get(s, 0)}</b><span>{s}</span></div>'
        for s in store.ALL_STATUSES
    )
    return f'<div class="jb-meta">{len(df)} offers tracked, {flagged} flagged for follow-up</div><div class="jb-pipe">{steps}</div>'


def offers_view(df):
    view = pd.DataFrame({
        "ID": df["id"], "Student": df["student"], "Company": df["company"], "Role": df["role"],
        "Status": df["status"], "Joining date": [date_text(r) for _, r in df.iterrows()],
    })
    stretch(view.style.map(paint, subset=["Status"]))


# ---------- page ----------
store.init_db()
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    f"""<div class="jb-hero">{BRIDGE_SVG}<div><div class="jb-title">JoinBridge</div>
    <div class="jb-sub">From offer to first day, students, employers and placement cells see the same status.</div></div></div>""",
    unsafe_allow_html=True,
)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

offers_df = store.get_offers()
risk_items = store.risk_list()
flagged = sum(1 for i in risk_items if i["a"]["at_risk"])
st.markdown(pipeline_html(offers_df, flagged), unsafe_allow_html=True)

if offers_df.empty:
    st.info("No offers yet. Add one in the Employer tab, or load a few fictional offers to try the app.")
    if st.button("Load sample data", key="load_sample"):
        store.load_sample()
        flash("Sample data loaded.")
        st.rerun()

tab_emp, tab_stu, tab_col = st.tabs(["Employer", "Student", "College"])

# =====================================================================
# EMPLOYER
# =====================================================================
with tab_emp:
    t_risk, t_offers, t_add, t_update, t_wait = st.tabs(["Risk list", "Offers", "Add offer", "Update", "Waitlist"])

    # ----- risk list -----
    with t_risk:
        st.header("Risk list")
        st.caption("Offers still waiting to join, riskiest first. Every flag lists the signals behind it.")
        for o, why in store.needs_employer_action():
            st.markdown(
                f'<div class="jb-note warn"><b>Your action:</b> {o["student"]} ({o["role"]}) is waiting for a joining date, {why}.</div>',
                unsafe_allow_html=True,
            )
        if not risk_items:
            st.info("No active offers to assess yet.")
        else:
            table = pd.DataFrame([{
                "Student": i["offer"]["student"], "Company": i["offer"]["company"], "Status": i["offer"]["status"],
                "Risk": i["a"]["risk"],
                "Why flagged": "; ".join(i["a"]["rules_triggered"] + i["a"]["reasons"][:2]) or "No flags",
            } for i in risk_items])
            stretch(table.style.map(paint, subset=["Status"]),
                    column_config={"Risk": st.column_config.ProgressColumn("Risk", min_value=0.0, max_value=1.0, format="%.2f")})
            st.caption("Scores come from a small model trained on synthetic data. Treat a flag as a reason to talk to the student, not as proof.")

            labels = {label_of(i["offer"]): i for i in risk_items}
            chosen = labels[st.selectbox("Open a candidate", list(labels), key="risk_pick")]
            o, a = chosen["offer"], chosen["a"]
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Why flagged")
                for r in a["rules_triggered"] + a["reasons"]:
                    st.markdown(f"- {r}")
                if not (a["rules_triggered"] or a["reasons"]):
                    st.write("No flags.")
            with c2:
                st.subheader("What would change this")
                for r in a["what_would_change"] or ["Nothing specific. Keep the student informed."]:
                    st.markdown(f"- {r}")
            st.progress(min(max(a["risk"], 0.0), 1.0), text=f'Risk {a["risk"]:.2f}')
            st.text_area("Suggested message (edit, then copy; nothing is sent from this app)",
                         store.suggested_message(o, a), height=130, key=f'msg_{o["id"]}')

    # ----- offers -----
    with t_offers:
        st.header("Offer status dashboard")
        if offers_df.empty:
            st.info("No offers yet.")
        else:
            c1, c2 = st.columns([2, 1])
            search = c1.text_input("Search student or company", key="search")
            status_filter = c2.selectbox("Filter by offer status", ["All"] + store.ALL_STATUSES, key="status_filter")
            shown = offers_df.copy()
            if search.strip():
                s = search.strip()
                shown = shown[shown["student"].str.contains(s, case=False, na=False)
                              | shown["company"].str.contains(s, case=False, na=False)]
            if status_filter != "All":
                shown = shown[shown["status"] == status_filter]
            offers_view(shown)
            st.caption(f"Showing {len(shown)} offer(s)")

    # ----- add offer -----
    with t_add:
        st.header("Add a new offer")
        st.markdown('<div class="jb-note">The employer (or the placement cell on the company\'s behalf) records the offer. '
                    "The student then accepts it in the Student tab.</div>", unsafe_allow_html=True)
        with st.form("offer_form"):
            student = st.text_input("Student name")
            company = st.text_input("Company name")
            role = st.selectbox("Role", list(plan_generator.ROLE_DESC))
            status = st.selectbox("Offer status", store.ALL_STATUSES)
            joining = st.date_input("Joining date", value=date.today() + timedelta(days=90))
            no_date = st.checkbox("Joining date not decided yet (ignore the date above)")
            window = st.text_input("Expected window, if no date yet (for example: July or August)")
            update_by = st.date_input("If no date yet, you will announce it by", value=date.today() + timedelta(days=14))
            if st.form_submit_button("Add offer"):
                if student.strip() and company.strip():
                    store.add_offer(student.strip(), company.strip(), role,
                                    None if no_date else joining, window.strip() if no_date else "",
                                    update_by if no_date else None, status)
                    flash("Offer saved.")
                    st.rerun()
                else:
                    st.error("Enter both the student name and the company name.")
        st.caption("Prototype notice: use fictional data for testing.")

    # ----- update -----
    with t_update:
        if offers_df.empty:
            st.info("Add an offer first.")
        else:
            opts = options_of(offers_df)
            oid = opts[st.selectbox("Select an offer", list(opts), key="upd_offer")]
            o = store.get_offer(oid)
            st.write(f'**{o["student"]}**, {o["role"]} at {o["company"]}. Status: **{o["status"]}**. Joining date: **{date_text(o)}**.')
            ca, cb, cc = st.columns(3)
            with ca:
                st.subheader("Status")
                new_status = st.selectbox("Choose new status", store.ALL_STATUSES, key="new_status")
                if st.button("Update status", key="btn_status"):
                    store.set_status(oid, new_status)
                    flash("Offer status updated.")
                    st.rerun()
            with cb:
                st.subheader("Joining date")
                new_date = st.date_input("New joining date", value=date.today() + timedelta(days=90), key="new_date")
                if st.button("Update joining date", key="btn_date"):
                    store.change_joining_date(oid, new_date)
                    flash("Joining date updated." + (" Counted as a deferral." if o["joining_date"] and o["joining_date"] != new_date.isoformat() else ""))
                    st.rerun()
            with cc:
                st.subheader("Stay in touch")
                if st.button("Send joining-date confirmation", key="btn_confirm", disabled=not o["joining_date"]):
                    store.send_confirmation(oid)
                    flash("Confirmation request recorded. The student will see it in their tab.")
                    st.rerun()
                if st.button("Post an update to the student", key="btn_post"):
                    store.post_update(oid)
                    flash("Update recorded. Employer silence is reset.")
                    st.rerun()

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Assign a pre-joining task")
                with st.form("task_form"):
                    title = st.text_input("Task title")
                    kind = st.selectbox("Type", store.TASK_KINDS)
                    if st.form_submit_button("Assign task"):
                        if title.strip():
                            store.add_task(oid, title.strip(), kind)
                            flash("Task assigned.")
                            st.rerun()
                        else:
                            st.error("Enter a task title.")
                st.caption("A finished task counts as activity, but it is only one signal. A student can do a task and still not join.")
            with c2:
                st.subheader("Edit the pre-joining plan")
                plan = plan_generator.get_plan(store.DB, oid, o["role"])
                st.caption(plan["source"])
                with st.form(f"plan_form_{oid}"):
                    titles = [st.text_input(f"Week {i + 1}", value=w["title"], key=f"wk_{oid}_{i}") for i, w in enumerate(plan["weeks"])]
                    if st.form_submit_button("Save plan"):
                        weeks = [{"week": i + 1, "title": t.strip(),
                                  "note": plan["weeks"][i]["note"] if t.strip() == plan["weeks"][i]["title"] else "Edited by employer"}
                                 for i, t in enumerate(titles) if t.strip()]
                        plan_generator.save_plan(store.DB, oid, weeks)
                        flash("Plan saved.")
                        st.rerun()

            st.divider()
            st.subheader("Record a release")
            st.caption("Use this when a student tells you directly that they will not join.")
            reason = st.selectbox("Reason for not joining", RELEASE_REASONS, key="emp_reason")
            if st.button("Record release", key="btn_emp_release", disabled=o["status"] not in store.ACTIVE):
                promoted = store.release(oid, reason)
                flash(f"Offer released. Reason: {reason}." + (f' {promoted["name"]} from the waitlist has been offered the seat.' if promoted else ""))
                st.rerun()

    # ----- waitlist -----
    with t_wait:
        st.header("Waitlist")
        st.caption("When an offer is released early, the next person here is offered the seat.")
        wl = store.get_waitlist()
        if wl:
            stretch(pd.DataFrame([{"Name": w["name"], "Role": w["role"], "Promoted": "Yes" if w["promoted"] else "No"} for w in wl]))
        else:
            st.info("The waitlist is empty. Add candidates below.")
        with st.form("wait_form"):
            wname = st.text_input("Candidate name")
            wrole = st.selectbox("Role", list(plan_generator.ROLE_DESC), key="wait_role")
            if st.form_submit_button("Add to waitlist"):
                if wname.strip():
                    store.add_waitlist(wname.strip(), wrole)
                    flash("Added to the waitlist.")
                    st.rerun()
                else:
                    st.error("Enter a name.")

# =====================================================================
# STUDENT
# =====================================================================
with tab_stu:
    if offers_df.empty:
        st.info("No offers yet.")
    else:
        opts = options_of(offers_df)
        sid = opts[st.selectbox("Demo: view as", list(opts), key="stu_pick")]
        o = store.get_offer(sid)
        active = o["status"] in store.ACTIVE
        plan = plan_generator.get_plan(store.DB, sid, o["role"])

        if active:
            line = f'Your offer still stands. Joining date: <b>{o["joining_date"]}</b>.' if o["joining_date"] else (
                "Your offer still stands. Your joining date is not fixed yet"
                + (f', expected {o["expected_window"]}' if o["expected_window"] else "")
                + (f'. The company has promised to tell you by <b>{o["update_by"]}</b>.' if o["update_by"] else "."))
        else:
            line = {"Released": "You told the employer early. Thank you for being honest.", "Joined": "You have joined. Welcome aboard!"}.get(o["status"], "")
        st.markdown(f'<div class="jb-card"><div class="jb-status">{o["status"]}</div><p>{line}</p>'
                    f'<p style="color:#5B6B7B;margin:0">{o["role"]} at {o["company"]}</p></div>', unsafe_allow_html=True)

        if o["status"] == "Offered":
            if st.button("Accept this offer", key="btn_accept"):
                store.student_accept(sid)
                flash("Offer accepted. The employer can see your answer.")
                st.rerun()

        pending = o["confirmations_sent"] - o["confirmations_replied"]
        if active and pending > 0 and o["joining_date"]:
            st.warning(f'The employer asked you to confirm your joining date ({pending} request(s) waiting).')
            if st.button("Confirm my joining date", key="btn_conf_date"):
                store.student_confirm_date(sid)
                flash("Thanks. Your confirmation was recorded.")
                st.rerun()

        if active:
            st.subheader("Are you still planning to join?")
            current = o["checkin"] if o["checkin"] in store.CHECKIN_OPTIONS else None
            answer = st.radio("Your answer", store.CHECKIN_OPTIONS, index=store.CHECKIN_OPTIONS.index(current) if current else None,
                              horizontal=True, key=f"checkin_{sid}", label_visibility="collapsed")
            st.caption("'Not sure' is a fine answer. It lets the employer talk to you early.")
            if st.button("Save my answer", key="btn_checkin", disabled=answer is None):
                store.set_checkin(sid, answer)
                flash("Answer saved." + (" You can release the offer below if you have decided." if answer == "No" else ""))
                st.rerun()

        st.subheader("Your pre-joining plan")
        st.caption(plan["source"])
        for i, w in enumerate(plan["weeks"]):
            mark = "✅" if i < o["modules_done"] else "⬜"
            st.markdown(f'{mark} **Week {w["week"]}: {w["title"]}**  \n<span style="color:#5B6B7B">{w["note"]}</span>', unsafe_allow_html=True)
        if active and st.button("Mark next module done", key="btn_module", disabled=o["modules_done"] >= len(plan["weeks"])):
            store.complete_module(sid, len(plan["weeks"]))
            flash("Module marked done.")
            st.rerun()

        tasks = store.get_tasks(sid)
        if tasks:
            st.subheader("Tasks from the employer")
            for t in tasks:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f'{"✅" if t["done"] else "⬜"} {t["title"]} ({t["kind"]})')
                if not t["done"] and c2.button("Mark done", key=f'task_{t["id"]}'):
                    store.complete_task(t["id"])
                    flash("Task marked done.")
                    st.rerun()

        if active:
            with st.expander("Other offers (optional)"):
                st.caption("Only share this if you want to. It is used as one signal, and you can see it in the list below.")
                n = st.number_input("Number of other offers you hold", min_value=0, max_value=20, value=int(o["other_offers"]), key=f"other_{sid}")
                if st.button("Save", key="btn_other"):
                    store.set_other_offers(sid, n)
                    flash("Saved.")
                    st.rerun()

        with st.expander("Signals used about you"):
            f = store.features(o)
            rows = [{"Signal": risk.SIGNALS[k], "Value": str(v)} for k, v in f.items()]
            rows.append({"Signal": "your answer to 'still planning to join?'", "Value": o["checkin"] or "not answered"})
            stretch(pd.DataFrame(rows))
            st.caption("Only activity inside this app is used. Nothing outside it is tracked.")

        if active:
            st.subheader("Not going to join?")
            st.caption("Tell the employer early. They can offer the seat to someone else.")
            reason = st.selectbox("Reason", RELEASE_REASONS, key="stu_reason")
            sure = st.checkbox("I understand the employer will be told today", key="stu_sure")
            if st.button("I will not be able to join", key="release_btn", disabled=not sure):
                promoted = store.release(sid, reason)
                flash("Released." + (f' {promoted["name"]} from the waitlist has been offered the seat.' if promoted else " No one was on the waitlist."))
                st.rerun()

# =====================================================================
# COLLEGE
# =====================================================================
with tab_col:
    st.header("College placement report")
    rep = store.college_report()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Offers", rep["offers"])
    c2.metric("Joined", rep["joined"])
    c3.metric("Released early", rep["released"])
    c4.metric("Still waiting", rep["waiting"])
    st.markdown(f'<div class="jb-card"><div style="color:#5B6B7B">True placement rate so far (joined / offers)</div>'
                f'<div class="jb-big">{round(rep["true_placement_rate"] * 100)}%</div>'
                f'<p style="color:#5B6B7B;margin:6px 0 0">An offer is not a placement. Only students who actually joined are counted, '
                f'and early releases give the company time to find a replacement.</p></div>', unsafe_allow_html=True)
    if rep["no_date"]:
        st.markdown(f'<div class="jb-note warn">{rep["no_date"]} active offer(s) still have no joining date.</div>', unsafe_allow_html=True)
    top = max(rep["by_status"].values(), default=1)
    bars = "".join(
        f'<div class="jb-bar" style="--c:{STATUS_COLORS[s][0]}"><span class="lab">{s}</span>'
        f'<div class="fill" style="width:{rep["by_status"].get(s, 0) / top * 60}%"></div><b>{rep["by_status"].get(s, 0)}</b></div>'
        for s in store.ALL_STATUSES)
    st.markdown(f'<div class="jb-card"><b>Offers by status</b>{bars}</div>', unsafe_allow_html=True)

st.caption("Prototype notice: use fictional data. Risk scores come from a model trained on synthetic data and are not predictions about real people.")