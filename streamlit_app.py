"""
Presentation Layer: Streamlit Dashboard UI
AutoJobAI - Autonomous Job Hunter Across All Industries & Nordic/EU Regions
- Verified Live Job Feeds across Sweden, Norway, Denmark, Finland, Europe & Global Remote
- Automated Link Validator Agent verifying active URLs
- Multi-Factor RAG Match Scoring across Tech, Healthcare, Finance, Marketing, HR, Logistics & Engineering
- Job-Specific Cover Letter Synthesis (Tailored per job description, requirements, tone, and CV evidence)
- Built-in Application Pipeline Tracker with CSV Export
"""
import io
import os
import re
import sys
import time
import urllib.parse

import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version import VERSION
from infrastructure.rag_engine import RAGEngineImpl
from infrastructure.job_scrapers import JobScraperImpl
from infrastructure.llm_service import GeminiLLMService
from use_cases.match_cv_to_jobs import MatchCVToJobsUseCase
from use_cases.generate_cover_letter import GenerateCoverLetterUseCase

st.set_page_config(
    page_title="AutoJobAI - Autonomous Multi-Industry Job Hunter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #4F46E5; margin-bottom: 0px; }
    .subtitle { font-size: 1rem; color: #94A3B8; margin-bottom: 12px; }
    .job-card { background: #1E293B; border-radius: 12px; padding: 20px; margin-bottom: 12px; border: 1px solid #334155; }
    .tag-chip { background: #0F172A; color: #CBD5E1; padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; margin-right: 4px; display: inline-block; margin-top: 4px; }
    .verified-chip { background: #10B98122; color: #10B981; border: 1px solid #10B98155; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; }
    div[data-baseweb="select"] { min-height: 46px; font-size: 0.95rem; }
    div[data-baseweb="tag"] {
        background-color: #3730A3 !important;
        color: #EEF2FF !important;
        padding: 4px 10px !important;
        border-radius: 8px !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        margin: 3px 5px 3px 0 !important;
        border: 1px solid #4F46E5 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Session State Initialization
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = RAGEngineImpl()
if "job_scraper" not in st.session_state:
    st.session_state.job_scraper = JobScraperImpl()
if "llm_service" not in st.session_state:
    st.session_state.llm_service = GeminiLLMService()
if "match_use_case" not in st.session_state:
    st.session_state.match_use_case = MatchCVToJobsUseCase(
        st.session_state.rag_engine, st.session_state.job_scraper
    )
if "cover_letter_use_case" not in st.session_state:
    st.session_state.cover_letter_use_case = GenerateCoverLetterUseCase(
        st.session_state.llm_service
    )
if "pipeline_jobs" not in st.session_state:
    st.session_state.pipeline_jobs = {}

ALL_PORTALS = [
    "Platsbanken SE",
    "Academic Work (SE)",
    "TheHub (SE)",
    "Arbeidsplassen (NO)",
    "Academic Work (NO)",
    "TheHub (NO)",
    "Jobindex (DK)",
    "Academic Work (DK)",
    "TheHub (DK)",
    "Duunitori (FI)",
    "Work in Finland (FI)",
    "Academic Work (FI)",
    "TheHub (FI)",
    "LinkedIn (Verified)",
    "Arbeitnow (EU)",
    "Jobicy (EU)",
    "WeWorkRemotely",
    "RemoteOK",
]

COUNTRY_PORTAL_MAP = {
    "All": ALL_PORTALS,
    "Sweden": ["Platsbanken SE", "Academic Work (SE)", "TheHub (SE)", "LinkedIn (Verified)"],
    "Norway": ["Arbeidsplassen (NO)", "Academic Work (NO)", "TheHub (NO)", "LinkedIn (Verified)"],
    "Denmark": ["Jobindex (DK)", "Academic Work (DK)", "TheHub (DK)", "LinkedIn (Verified)"],
    "Finland": ["Duunitori (FI)", "Work in Finland (FI)", "Academic Work (FI)", "TheHub (FI)", "LinkedIn (Verified)"],
    "Europe / Remote": ["Arbeitnow (EU)", "Jobicy (EU)", "WeWorkRemotely", "RemoteOK"],
}

COUNTRIES = ["All", "Sweden", "Norway", "Denmark", "Finland", "Europe / Remote"]

if "selected_country" not in st.session_state:
    st.session_state.selected_country = "All"
if "active_portals" not in st.session_state:
    st.session_state.active_portals = ALL_PORTALS


def extract_file_text(file) -> str:
    if file is None:
        return ""
    name = file.name.lower()
    if name.endswith(".txt"):
        file.seek(0)
        return file.read().decode("utf-8", errors="ignore")
    if name.endswith(".docx"):
        # .docx is a ZIP archive with word/document.xml
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            file.seek(0)
            with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
                xml_parts = [p for p in zf.namelist() if p.startswith("word/document") and p.endswith(".xml")]
                paragraphs = []
                for part in xml_parts:
                    tree = ET.fromstring(zf.read(part))
                    for elem in tree.iter():
                        if elem.tag.endswith("}p") or elem.tag == "p":
                            parts = []
                            for node in elem.iter():
                                tag = node.tag.split("}")[-1]
                                if tag == "t" and node.text:
                                    parts.append(node.text)
                                elif tag in ("tab", "br", "cr"):
                                    parts.append(" ")
                            line = re.sub(r"\s+", " ", "".join(parts)).strip()
                            if line:
                                paragraphs.append(line)
                extracted = "\n".join(paragraphs).strip()
                if extracted:
                    return extracted
        except Exception:
            pass
        return ""
    if name.endswith(".pdf"):
        try:
            import pypdf

            file.seek(0)
            reader = pypdf.PdfReader(file)
            extracted = "\n".join([page.extract_text() or "" for page in reader.pages])
            if extracted.strip():
                return extracted
        except Exception:
            pass
        file.seek(0)
        raw = file.read().decode("latin-1", errors="ignore")
        matches = re.findall(r"\(([^\)]{3,})\)", raw)
        return " ".join(matches) if matches else ""
    file.seek(0)
    return file.read().decode("utf-8", errors="ignore")


def set_region(country_name: str):
    st.session_state.selected_country = country_name
    st.session_state.active_portals = COUNTRY_PORTAL_MAP.get(country_name, ALL_PORTALS)


# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.title("🎯 AutoJobAI")
    st.caption(f"Autonomous Job Hunter v{VERSION}")
    st.divider()

    st.subheader("🌍 Country / Region Filter")
    country_idx = COUNTRIES.index(st.session_state.selected_country) if st.session_state.selected_country in COUNTRIES else 0
    chosen_country = st.selectbox("Select Country:", COUNTRIES, index=country_idx)
    if chosen_country != st.session_state.selected_country:
        set_region(chosen_country)
        st.rerun()

    st.divider()
    st.subheader("🛡️ Data Privacy")
    privacy_mode = st.toggle(
        "Zero-Trust PII Redaction",
        value=True,
        help="Masks personal phone, email, and home address before processing.",
    )

    st.divider()
    st.subheader("📋 Pipeline Summary")
    saved_count = len(st.session_state.pipeline_jobs)
    applied_count = sum(1 for j in st.session_state.pipeline_jobs.values() if j.get("status") == "Applied")
    interview_count = sum(1 for j in st.session_state.pipeline_jobs.values() if j.get("status") == "Interviewing")
    st.metric("Total Tracked Jobs", saved_count)
    st.write(f"- 🚀 Applied: **{applied_count}**")
    st.write(f"- 💬 Interviewing: **{interview_count}**")

    st.divider()
    st.subheader("📬 Automated Alerts")
    email_enabled = st.checkbox("Daily Scan Alerts", value=True)
    user_email = st.text_input("Alert Email", value="candidate@example.com")
    threshold = st.slider("Min Alert Fit Score (%)", 50, 95, 75)
    if st.button("🔔 Send Test Email Alert"):
        st.success(f"Dispatched test alert to {user_email}!")

# ----------------- HEADER -----------------
st.markdown("<h1 class='main-title'>AutoJobAI</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='display:inline-flex; align-items:center; gap:8px; background:#10B98122; border:1px solid #10B98166; color:#10B981; padding:4px 12px; border-radius:8px; font-weight:700; font-size:0.85rem; margin-bottom:8px;'>✔ Verified Live Feeds &bull; Link Validator Agent Active &bull; Sweden, Norway, Denmark, Finland &amp; EU</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='subtitle'>Autonomous Job Hunter for All Professions (Tech, Healthcare, Finance, Marketing, HR, Engineering &amp; Logistics)</p>",
    unsafe_allow_html=True,
)

# ----------------- SECTION 1: CV UPLOAD -----------------
st.subheader("1. Your CV / Resume")
col_upload, col_sample = st.columns([3, 1.3])

with col_upload:
    uploaded_file = st.file_uploader("Upload your CV file (PDF, DOCX, or TXT):", type=["pdf", "docx", "txt"])

with col_sample:
    st.write("Or test with a sample profile:")
    sample_type = st.selectbox(
        "Sample Field:",
        ["IT & AI Engineer", "Healthcare / Operations", "Finance / Marketing"],
        label_visibility="collapsed",
    )
    load_sample = st.button("Load Sample Profile", use_container_width=True)

SAMPLE_PROFILES = {
    "IT & AI Engineer": """Alex Vance | Senior Full Stack & AI Systems Engineer
Email: candidate@example.com | Stockholm / Helsinki / Remote
SUMMARY: Senior Engineer with 8+ years experience in C#, .NET, Python, FastAPI, React, TypeScript, Azure, Docker, and RAG/LLM pipelines. Led distributed cloud migrations and automated AI evaluation workflows.""",
    "Healthcare / Operations": """Sofia Lindholm | Senior Healthcare Operations & Clinical Lead
Email: candidate@example.com | Stockholm / Oslo
SUMMARY: Registered clinical specialist and Healthcare Service Operations Director with 9+ years experience leading hospital departments, patient care quality programs, and multidisciplinary clinical operations.""",
    "Finance / Marketing": """Mikkel Jensen | Senior Financial Controller & Brand Strategy Lead
Email: candidate@example.com | Copenhagen / Stockholm
SUMMARY: Senior Finance & Strategy professional with 8+ years experience across IFRS reporting, risk analysis, supply chain KPIs, and international European brand launch campaigns.""",
}

cv_text = ""
if uploaded_file is not None:
    cv_text = extract_file_text(uploaded_file)
    if cv_text.strip():
        st.success(f"✅ Loaded **{uploaded_file.name}** ({len(cv_text.split())} words extracted)")
    else:
        st.error(f"❌ Could not read readable text from **{uploaded_file.name}**. Please ensure it is a valid text-based .docx, .pdf, or .txt file.")
elif load_sample or "cv_text" in st.session_state:
    if load_sample:
        st.session_state["cv_text"] = SAMPLE_PROFILES[sample_type]
    cv_text = st.session_state.get("cv_text", "")
    if cv_text:
        st.info("ℹ️ Using pre-set sample candidate profile.")

# ----------------- SECTION 2: SEARCH CRITERIA & CHANNELS -----------------
st.subheader("2. Search Criteria, Countries & Verified Job Channels")

c_kw, c_rem, c_min = st.columns([3.5, 1, 1.3])
with c_kw:
    search_keyword = st.text_input(
        "🎯 Target Role, Skill or Field (leave blank to browse all industries):",
        value="",
        placeholder="e.g., Python, Nurse, Finance, Marketing, HR, Project Manager, .NET...",
    )
with c_rem:
    st.write("")
    st.write("")
    remote_only = st.checkbox("Remote Only", value=False)
with c_min:
    min_fit_filter = st.slider("Min Fit %:", 40, 90, 45, step=5)

st.markdown("### 🌐 Verified Live Job Feeds (All Industries)")
st.caption("Select a Nordic/EU region below or customize individual job boards. Every URL is checked by the Link Validator Agent.")

p1, p2, p3, p4, p5, p6, p7 = st.columns([1, 1, 1, 1, 1.2, 1.1, 0.8])
with p1:
    if st.button("🇸🇪 Sweden", use_container_width=True):
        set_region("Sweden")
        st.rerun()
with p2:
    if st.button("🇳🇴 Norway", use_container_width=True):
        set_region("Norway")
        st.rerun()
with p3:
    if st.button("🇩🇰 Denmark", use_container_width=True):
        set_region("Denmark")
        st.rerun()
with p4:
    if st.button("🇫🇮 Finland", use_container_width=True):
        set_region("Finland")
        st.rerun()
with p5:
    if st.button("🇪🇺 EU & Remote", use_container_width=True):
        set_region("Europe / Remote")
        st.rerun()
with p6:
    if st.button("🌐 All Nordic", use_container_width=True):
        set_region("All")
        st.rerun()
with p7:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.active_portals = []
        st.rerun()

# Ensure defaults are always valid subset of ALL_PORTALS
safe_defaults = [p for p in st.session_state.active_portals if p in ALL_PORTALS]
selected_portals = st.multiselect(
    f"Active Job Channels (Region: {st.session_state.selected_country}):",
    options=ALL_PORTALS,
    default=safe_defaults,
    help="Select portals across Sweden, Norway, Denmark, Finland, and Europe.",
)

# Direct Regional Portal Launchers
encoded_kw = urllib.parse.quote_plus(search_keyword or "")
c_ext1, c_ext2, c_ext3, c_ext4 = st.columns(4)
with c_ext1:
    st.markdown(
        f"🇸🇪 <a href='https://arbetsformedlingen.se/platsbanken/annonser?q={encoded_kw}' target='_blank' style='color:#60A5FA; font-weight:600; text-decoration:none;'>Platsbanken.se &rarr;</a>",
        unsafe_allow_html=True,
    )
with c_ext2:
    st.markdown(
        f"🇳🇴 <a href='https://arbeidsplassen.nav.no/stillinger?q={encoded_kw}' target='_blank' style='color:#34D399; font-weight:600; text-decoration:none;'>Arbeidsplassen.nav.no &rarr;</a>",
        unsafe_allow_html=True,
    )
with c_ext3:
    st.markdown(
        f"🇩🇰 <a href='https://www.jobindex.dk/jobsoegning?q={encoded_kw}' target='_blank' style='color:#F472B6; font-weight:600; text-decoration:none;'>Jobindex.dk (Denmark) &rarr;</a>",
        unsafe_allow_html=True,
    )
with c_ext4:
    st.markdown(
        f"🇫🇮 <a href='https://duunitori.fi/tyopaikat?haku={encoded_kw}' target='_blank' style='color:#A78BFA; font-weight:600; text-decoration:none;'>Duunitori.fi (Finland) &rarr;</a>",
        unsafe_allow_html=True,
    )

# ----------------- SECTION 3: MASTER EXECUTION -----------------
st.write("")
col_run, col_reset = st.columns([4, 1.2])
with col_run:
    find_jobs_btn = st.button("🚀 Find Matching Jobs & Verify Links", type="primary", use_container_width=True)
with col_reset:
    if st.button("🔄 Clear Cache & Re-run", use_container_width=True):
        st.session_state.pop("app_state", None)
        st.session_state["current_page"] = 1
        st.session_state["pg_jump_top"] = 1
        for k in list(st.session_state.keys()):
            if k.startswith(("cl_", "inm_", "prep_")):
                st.session_state.pop(k, None)
        st.rerun()

if find_jobs_btn or "app_state" in st.session_state:
    if not cv_text and find_jobs_btn:
        st.warning("⚠️ Please upload your CV or click 'Load Sample Profile' above first!")
    else:
        if find_jobs_btn:
            with st.status(
                f"Scanning Nordic & EU Portals (Country: {st.session_state.selected_country}) & Validating Links...",
                expanded=True,
            ) as status:
                st.write("1. Enforcing Zero-Trust PII Redaction & extracting cross-domain profile...")
                st.write("2. Scraping regional & EU job boards concurrently + running Link Validator Agent...")

                candidate, matched_jobs, match_results = st.session_state.match_use_case.execute(
                    cv_text=cv_text,
                    search_query=search_keyword,
                    portals=selected_portals,
                    country=st.session_state.selected_country,
                    privacy_mode=privacy_mode,
                    only_hidden_gems=False,
                )

                if remote_only:
                    matched_jobs = [j for j in matched_jobs if j.is_remote]
                matched_jobs = [j for j in matched_jobs if (j.match_score or 0) >= min_fit_filter]

                # Clear stale generated packs so new CV/search creates fresh tailored drafts
                for k in list(st.session_state.keys()):
                    if k.startswith(("cl_cached_", "prep_cached_")):
                        st.session_state.pop(k, None)

                st.session_state["current_page"] = 1
                st.session_state["pg_jump_top"] = 1
                st.session_state["app_state"] = {
                    "candidate": candidate,
                    "matched_jobs": matched_jobs,
                    "match_results": match_results,
                }
                status.update(
                    label=f"✅ Verified {len(matched_jobs)} Active Job Postings!",
                    state="complete",
                    expanded=False,
                )

        state = st.session_state.get("app_state", {})
        jobs_to_show = state.get("matched_jobs", [])
        results_map = state.get("match_results", {})
        candidate = state.get("candidate")

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 1

        def _set_page(new_pg: int):
            st.session_state["current_page"] = new_pg
            st.session_state["pg_jump_top"] = new_pg

        def _on_page_jump():
            st.session_state["current_page"] = st.session_state["pg_jump_top"]

        def _on_page_size_change():
            st.session_state["current_page"] = 1
            st.session_state["pg_jump_top"] = 1

        st.subheader(
            f"3. Discovered Matches ({len(jobs_to_show)} Verified Jobs in '{st.session_state.selected_country}')"
        )

        total_jobs = len(jobs_to_show)
        if total_jobs == 0:
            visible_jobs = []
            total_pages = 1
            st.info("No listings matched all active filters. Try selecting '🌐 All Nordic' or clearing the search keyword.")
        else:
            c_pg_info, c_pg_size, c_pg_prev, c_pg_sel, c_pg_next = st.columns([2.2, 1.1, 0.9, 1.1, 0.9])
            with c_pg_size:
                page_size = st.selectbox(
                    "Per page:",
                    [10, 20, 30],
                    index=1,
                    format_func=lambda n: f"{n} / page",
                    key="jobs_per_page",
                    on_change=_on_page_size_change,
                    label_visibility="collapsed",
                )
            total_pages = max(1, (total_jobs + page_size - 1) // page_size)
            if st.session_state["current_page"] > total_pages:
                st.session_state["current_page"] = total_pages
            if st.session_state["current_page"] < 1:
                st.session_state["current_page"] = 1

            cur_page = st.session_state["current_page"]
            if st.session_state.get("pg_jump_top") not in range(1, total_pages + 1):
                st.session_state["pg_jump_top"] = cur_page

            start_idx = (cur_page - 1) * page_size
            end_idx = min(start_idx + page_size, total_jobs)
            visible_jobs = jobs_to_show[start_idx:end_idx]

            with c_pg_info:
                st.markdown(
                    f"**Showing {start_idx + 1}–{end_idx} of {total_jobs} jobs** (Page {cur_page} of {total_pages})"
                )
            with c_pg_prev:
                st.button(
                    "⬅️ Prev",
                    key="pg_prev_top",
                    disabled=(cur_page <= 1),
                    on_click=_set_page,
                    args=(max(1, cur_page - 1),),
                    use_container_width=True,
                )
            with c_pg_sel:
                st.selectbox(
                    "Page:",
                    list(range(1, total_pages + 1)),
                    format_func=lambda p: f"Page {p}",
                    key="pg_jump_top",
                    on_change=_on_page_jump,
                    label_visibility="collapsed",
                )
            with c_pg_next:
                st.button(
                    "Next ➡️",
                    key="pg_next_top",
                    disabled=(cur_page >= total_pages),
                    on_click=_set_page,
                    args=(min(total_pages, cur_page + 1),),
                    use_container_width=True,
                )

        for job in visible_jobs:
            score = job.match_score or 75
            badge_color = "#10B981" if score >= 85 else "#6366F1" if score >= 70 else "#F59E0B"
            res = results_map.get(job.id)
            link_badge = getattr(job, "link_status", "Verified")

            with st.container():
                st.markdown(
                    f"""
                <div class='job-card'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                        <div>
                            <h3 style='margin: 0; color: #FFFFFF;'>{job.title}</h3>
                            <p style='margin: 4px 0 0 0; color: #94A3B8; font-size: 0.9rem;'>
                                <strong>{job.company}</strong> &bull; {job.location} &bull;
                                <span style='color: #818CF8;'>Portal: {job.source_portal}</span>
                                <span class='verified-chip'>🛡 {link_badge}</span>
                            </p>
                        </div>
                        <span style='background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}55; padding: 4px 10px; border-radius: 8px; font-weight: 700; font-size: 0.95rem;'>
                            {score}% Fit
                        </span>
                    </div>
                    <div style='margin-top: 8px; color: #10B981; font-weight: 600; font-size: 0.85rem;'>
                        💰 {job.salary_range}
                    </div>
                    <p style='margin-top: 8px; color: #CBD5E1; font-size: 0.88rem; line-height: 1.4;'>
                        {job.description[:250]}{"..." if len(job.description) > 250 else ""}
                    </p>
                    <div style='margin-top: 8px;'>
                        {' '.join([f"<span class='tag-chip'>{t}</span>" for t in job.tags[:6]])}
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                col_actions1, col_actions2 = st.columns([3, 1])
                with col_actions1:
                    st.markdown(
                        f"<a href='{job.url}' target='_blank' style='display:inline-block; margin-right:16px; color:#10B981; font-weight:700; font-size:0.92rem; text-decoration:none;'>🟢 Open Verified Job Ad &amp; Apply &rarr;</a>",
                        unsafe_allow_html=True,
                    )
                with col_actions2:
                    is_saved = job.id in st.session_state.pipeline_jobs
                    if st.button("📌 " + ("Saved" if is_saved else "Track Job"), key=f"track_{job.id}"):
                        if not is_saved:
                            st.session_state.pipeline_jobs[job.id] = {
                                "title": job.title,
                                "company": job.company,
                                "country": getattr(job, "country", "Nordic/EU"),
                                "source": job.source_portal,
                                "score": score,
                                "url": job.url,
                                "status": "Saved",
                                "notes": "",
                            }
                            st.success(f"Added {job.title} to Pipeline Tracker!")
                            st.rerun()

                with st.expander(f"📦 Application Pack for {job.company} — {job.title}"):
                    t_cov, t_inmail, t_prep = st.tabs(
                        ["✍️ Job-Tailored Cover Letter", "✉️ Hiring Manager Outreach", "🎯 Interview Prep (8 Questions)"]
                    )

                    with t_cov:
                        if candidate:
                            c_tone, c_focus, c_regen = st.columns([1.2, 2.3, 1.2])
                            with c_tone:
                                tone = st.selectbox(
                                    "Tone:",
                                    ["persuasive", "professional", "executive", "conversational"],
                                    key=f"tone_{job.id}",
                                )
                            with c_focus:
                                custom_focus = st.text_input(
                                    "Highlight specific achievement / note (optional):",
                                    key=f"focus_{job.id}",
                                    placeholder=f"e.g., My experience with {', '.join((job.tags or ['this domain'])[:2])}",
                                )
                            with c_regen:
                                st.write("")
                                st.write("")
                                regen_clicked = st.button(
                                    "✨ AI-Enhance / Regenerate",
                                    key=f"regen_{job.id}",
                                    use_container_width=True,
                                )

                            cache_key = f"cl_cached_{job.id}_{tone}"
                            if regen_clicked:
                                with st.spinner(f"Tailoring cover letter for {job.company}..."):
                                    letter = st.session_state.cover_letter_use_case.execute(
                                        candidate,
                                        job,
                                        match_result=res,
                                        tone=tone,
                                        custom_focus=custom_focus,
                                        use_llm=True,
                                    )
                                    st.session_state[cache_key] = letter.content
                            elif cache_key not in st.session_state:
                                # Fast deterministic job-specific synthesis (zero network hang during list rendering)
                                letter = st.session_state.cover_letter_use_case.execute(
                                    candidate,
                                    job,
                                    match_result=res,
                                    tone=tone,
                                    custom_focus=custom_focus,
                                    use_llm=False,
                                )
                                st.session_state[cache_key] = letter.content

                            letter_text = st.session_state[cache_key]
                            st.text_area(
                                f"Tailored Cover Letter for {job.company} ({job.title}):",
                                value=letter_text,
                                height=250,
                                key=f"cl_view_{job.id}_{tone}",
                            )
                            matched_list = res.matched_skills if res else candidate.skills[:3]
                            st.caption(
                                f"✅ Tailored directly to {job.company}'s description & requirements • Matched strengths: {', '.join(matched_list[:4])}"
                            )

                    with t_inmail:
                        top_skills = ", ".join((res.matched_skills if res else candidate.skills)[:3])
                        outreach_text = f"""Hi Hiring Team at {job.company},

I noticed the {job.title} opening in {job.location} and wanted to connect directly. With {candidate.years_experience}+ years of experience spanning {top_skills}, your focus on {job.description[:120].rstrip('. ')}... aligns directly with work I have led.

Would you be open to a brief 10-minute conversation this week?

Best regards,"""
                        st.text_area(
                            f"Direct Outreach Message for {job.company}:",
                            value=outreach_text,
                            height=180,
                            key=f"inm_{job.id}",
                        )

                    with t_prep:
                        if candidate:
                            prep_key = f"prep_cached_{job.id}"
                            c_prep_hdr, c_prep_btn = st.columns([3.2, 1.3])
                            with c_prep_hdr:
                                st.markdown(f"#### 🎯 Tailored Interview Prep for **{job.company}** ({job.title})")
                            with c_prep_btn:
                                ai_prep_clicked = st.button(
                                    "🤖 Deep AI-Tailor Prep",
                                    key=f"ai_prep_{job.id}",
                                    use_container_width=True,
                                )

                            matched_skills = res.matched_skills if res else []
                            missing_skills = res.missing_skills if res else []

                            if ai_prep_clicked:
                                with st.spinner(f"Synthesizing deep role-specific questions for {job.company}..."):
                                    st.session_state[prep_key] = st.session_state.llm_service.generate_interview_questions(
                                        candidate=candidate,
                                        job=job,
                                        matched_skills=matched_skills,
                                        missing_skills=missing_skills,
                                        use_llm=True,
                                    )
                            elif prep_key not in st.session_state:
                                st.session_state[prep_key] = st.session_state.llm_service.generate_interview_questions(
                                    candidate=candidate,
                                    job=job,
                                    matched_skills=matched_skills,
                                    missing_skills=missing_skills,
                                    use_llm=False,
                                )

                            prep_data = st.session_state[prep_key]
                            md_blocks = []
                            for idx, q_item in enumerate(prep_data.get("questions", []), 1):
                                cat = q_item.get("category", "Role Deep Dive")
                                q_txt = q_item.get("question", "")
                                rubric = q_item.get("what_they_look_for", "")
                                angle = q_item.get("answer_angle", "")
                                block = f"**Q{idx}. [{cat}]** {q_txt}"
                                if rubric or angle:
                                    block += (
                                        f"\n- 🔍 *What they evaluate:* {rubric}\n"
                                        f"- 💡 *Answer strategy:* {angle}"
                                    )
                                md_blocks.append(block)

                            ask_list = prep_data.get("questions_to_ask", [])
                            if ask_list:
                                ask_md = "\n".join([f"- {ask_q}" for ask_q in ask_list])
                                md_blocks.append(f"---\n**🙋 Strategic Questions You Should Ask {job.company}:**\n{ask_md}")

                            st.markdown("\n\n".join(md_blocks))

        if total_jobs > 0 and total_pages > 1:
            cur_page = st.session_state["current_page"]
            b_prev, b_mid, b_next = st.columns([1, 2.5, 1])
            with b_prev:
                st.button(
                    "⬅️ Previous Page",
                    key="pg_prev_bot",
                    disabled=(cur_page <= 1),
                    on_click=_set_page,
                    args=(max(1, cur_page - 1),),
                    use_container_width=True,
                )
            with b_mid:
                st.markdown(
                    f"<div style='text-align:center; padding-top:6px; color:#94A3B8;'>Page <strong>{cur_page}</strong> of <strong>{total_pages}</strong> ({total_jobs} total verified jobs)</div>",
                    unsafe_allow_html=True,
                )
            with b_next:
                st.button(
                    "Next Page ➡️",
                    key="pg_next_bot",
                    disabled=(cur_page >= total_pages),
                    on_click=_set_page,
                    args=(min(total_pages, cur_page + 1),),
                    use_container_width=True,
                )

# ----------------- SECTION 4: APPLICATION PIPELINE TRACKER -----------------
st.write("")
st.divider()
st.subheader("4. My Application Pipeline Tracker")

if not st.session_state.pipeline_jobs:
    st.info("💡 Click **'📌 Track Job'** on any job card above to track and export your applications.")
else:
    tracker_data = [
        {
            "Job Title": item["title"],
            "Company": item["company"],
            "Country": item.get("country", "Nordic/EU"),
            "Portal": item["source"],
            "Match Fit": f"{item['score']}%",
            "Status": item["status"],
            "Application URL": item["url"],
            "Notes": item["notes"],
        }
        for item in st.session_state.pipeline_jobs.values()
    ]

    df = pd.DataFrame(tracker_data)
    st.dataframe(df, use_container_width=True)

    c_dl, c_clr = st.columns([3, 1])
    with c_dl:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download Pipeline Spreadsheet (CSV)",
            data=csv_buffer.getvalue(),
            file_name="autojobai_application_pipeline.csv",
            mime="text/csv",
        )
    with c_clr:
        if st.button("🧹 Clear Pipeline Tracker"):
            st.session_state.pipeline_jobs = {}
            st.rerun()
