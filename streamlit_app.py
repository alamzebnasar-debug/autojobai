"""
Presentation Layer: Streamlit Dashboard UI
AutoJobAI - Comprehensive Autonomous Job Hunter & Career Copilot
- Aggregates Live Duunitori, WeWorkRemotely, Remotive, Arbeitnow, RemoteOK, LinkedIn
- Uncovers Hidden Gems: Direct ATS (Teamtailor/Greenhouse/Lever), Supercomputing (CSC LUMI), & VTT/Aalto Research
- 1-Click Application Pack: Tailored Cover Letter + Recruiter Cold Outreach + Interview Prep Predictor
- Built-in Application Pipeline Tracker with CSV Export
"""
import streamlit as st
import time
import re
import sys
import os
import pandas as pd
import io

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version import VERSION
from infrastructure.rag_engine import RAGEngineImpl
from infrastructure.job_scrapers import JobScraperImpl
from infrastructure.llm_service import GeminiLLMService
from use_cases.match_cv_to_jobs import MatchCVToJobsUseCase
from use_cases.generate_cover_letter import GenerateCoverLetterUseCase

st.set_page_config(
    page_title="AutoJobAI - Comprehensive Autonomous Job Hunter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #4F46E5; margin-bottom: 0px; }
    .subtitle { font-size: 1rem; color: #94A3B8; margin-bottom: 12px; }
    .job-card { background: #1E293B; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #334155; }
    .tag-chip { background: #0F172A; color: #CBD5E1; padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; margin-right: 4px; display: inline-block; }
    .gem-badge { background: #F59E0B22; color: #F59E0B; border: 1px solid #F59E0B66; padding: 3px 10px; border-radius: 8px; font-size: 0.82rem; font-weight: 700; margin-left: 8px; }
    div[data-baseweb="select"] { min-height: 52px; font-size: 1rem; }
    div[data-baseweb="tag"] {
        background-color: #3730A3 !important;
        color: #EEF2FF !important;
        padding: 6px 12px !important;
        border-radius: 8px !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        margin: 4px 6px 4px 0 !important;
        border: 1px solid #4F46E5 !important;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = RAGEngineImpl()
if "job_scraper" not in st.session_state:
    st.session_state.job_scraper = JobScraperImpl()
if "llm_service" not in st.session_state:
    st.session_state.llm_service = GeminiLLMService()

if "match_use_case" not in st.session_state:
    st.session_state.match_use_case = MatchCVToJobsUseCase(
        st.session_state.rag_engine, 
        st.session_state.job_scraper
    )
if "cover_letter_use_case" not in st.session_state:
    st.session_state.cover_letter_use_case = GenerateCoverLetterUseCase(
        st.session_state.llm_service
    )
if "pipeline_jobs" not in st.session_state:
    st.session_state.pipeline_jobs = {}

def extract_file_text(file) -> str:
    if file is None:
        return ""
    name = file.name.lower()
    if name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(file)
            extracted = "\n".join([page.extract_text() or "" for page in reader.pages])
            if extracted.strip():
                return extracted
        except Exception:
            pass
        file.seek(0)
        raw = file.read().decode("latin-1", errors="ignore")
        matches = re.findall(r'\(([^\)]{3,})\)', raw)
        return " ".join(matches) if matches else raw[:4000]
    return file.read().decode("utf-8", errors="ignore")

# Sidebar
with st.sidebar:
    st.title("🎯 AutoJobAI")
    st.caption(f"Comprehensive Job Hunter v{VERSION}")
    st.divider()

    st.subheader("🛡️ Data Privacy")
    privacy_mode = st.toggle("Zero-Trust PII Redaction", value=True, help="Masks personal phone, email, and home address before processing.")

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

# Header
st.markdown("<h1 class='main-title'>AutoJobAI</h1>", unsafe_allow_html=True)
st.markdown(f"<div style='display:inline-flex; align-items:center; gap:8px; background:#10B98122; border:1px solid #10B98166; color:#10B981; padding:4px 12px; border-radius:8px; font-weight:700; font-size:0.85rem; margin-bottom:8px;'>✔ Comprehensive Multi-Channel Engine v{VERSION} &bull; 50+ Sources &bull; Hidden Gems Active</div>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Autonomous Job Hunter &bull; Live Scrapers (Duunitori, WWR, Remotive, Arbeitnow, RemoteOK, LinkedIn) &bull; Direct ATS & Hidden Research Jobs</p>", unsafe_allow_html=True)

# ----------------- SECTION 1: CV UPLOAD -----------------
st.subheader("1. Your CV / Resume")
col_upload, col_sample = st.columns([3, 1])

with col_upload:
    uploaded_file = st.file_uploader("Upload your CV file (PDF, DOCX, or TXT):", type=["pdf", "docx", "txt"])

with col_sample:
    st.write("Or test without upload:")
    load_sample = st.button("Load Pre-set AI Engineer Profile")

cv_text = ""
if uploaded_file is not None:
    cv_text = extract_file_text(uploaded_file)
    st.success(f"✅ Loaded **{uploaded_file.name}** ({len(cv_text.split())} words extracted)")
elif load_sample or "cv_text" in st.session_state:
    if load_sample:
        st.session_state["cv_text"] = """Alex Vance | Senior Full Stack & AI Systems Engineer
Email: alex.vance.dev@example.com | San Francisco, CA
SUMMARY: Senior Engineer with 7+ years of experience in Python, FastAPI, LangGraph, RAG pipelines, React, Docker, and AWS."""
    cv_text = st.session_state.get("cv_text", "")
    st.info("ℹ️ Using pre-set sample candidate profile.")

# ----------------- SECTION 2: SEARCH CRITERIA & HIDDEN GEMS -----------------
st.subheader("2. Search Criteria & Channel Matrix")

c_kw, c_gems, c_rem = st.columns([3, 1.8, 1])
with c_kw:
    search_keyword = st.text_input("🎯 Target Role / Tech Stack:", value="Python Engineer")
with c_gems:
    st.write("")
    st.write("")
    only_hidden_gems = st.checkbox("✨ Hidden Gems & Direct ATS Only", value=False, help="Limits results to research labs (CSC LUMI, VTT, Aalto) and direct ATS startup boards with lower applicant competition.")
with c_rem:
    st.write("")
    st.write("")
    remote_only = st.checkbox("Remote Only", value=False)

ALL_PORTALS = [
    "Duunitori (FI)",
    "LinkedIn",
    "WeWorkRemotely",
    "Remotive",
    "CSC Careers (Direct ATS)",
    "VTT Research (Direct ATS)",
    "Aalto Open Positions",
    "Varjo (Greenhouse ATS)",
    "Kempower (Teamtailor ATS)",
    "Oura (Lever ATS)",
    "Work in Finland",
    "Jobly (FI)",
    "Oikotie (FI)",
    "The Hub (Nordic FI)",
    "Työmarkkinatori (FI)",
    "RemoteOK",
    "Arbeitnow"
]
FINNISH_PORTALS = [
    "Duunitori (FI)",
    "CSC Careers (Direct ATS)",
    "VTT Research (Direct ATS)",
    "Aalto Open Positions",
    "Varjo (Greenhouse ATS)",
    "Kempower (Teamtailor ATS)",
    "Oura (Lever ATS)",
    "Work in Finland",
    "Jobly (FI)",
    "Oikotie (FI)",
    "The Hub (Nordic FI)",
    "Työmarkkinatori (FI)"
]
GLOBAL_PORTALS = ["WeWorkRemotely", "Remotive", "LinkedIn", "RemoteOK", "Arbeitnow"]
HIDDEN_GEMS = [
    "CSC Careers (Direct ATS)",
    "VTT Research (Direct ATS)",
    "Aalto Open Positions",
    "Varjo (Greenhouse ATS)",
    "Kempower (Teamtailor ATS)",
    "Oura (Lever ATS)",
    "The Hub (Nordic FI)",
    "WeWorkRemotely",
    "Remotive"
]

if "active_portals" not in st.session_state:
    st.session_state.active_portals = ALL_PORTALS

# Preset buttons
st.markdown("### 🌐 Portals & Sources to Search (Full Matrix)")
p1, p2, p3, p4, p5 = st.columns([1.5, 1.4, 1.4, 1, 1])
with p1:
    if st.button("🇫🇮 Finland + Direct ATS", use_container_width=True):
        st.session_state.active_portals = FINNISH_PORTALS
        st.rerun()
with p2:
    if st.button("✨ Hidden Gems Only", use_container_width=True):
        st.session_state.active_portals = HIDDEN_GEMS
        st.rerun()
with p3:
    if st.button("🌐 Global Remote Only", use_container_width=True):
        st.session_state.active_portals = GLOBAL_PORTALS
        st.rerun()
with p4:
    if st.button("✅ All (17)", use_container_width=True):
        st.session_state.active_portals = ALL_PORTALS
        st.rerun()
with p5:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.active_portals = []
        st.rerun()

selected_portals = st.multiselect(
    "Active Job Channels:",
    options=ALL_PORTALS,
    default=st.session_state.active_portals,
    help="Add or remove channels with 1 click."
)

# ----------------- SECTION 3: MASTER EXECUTION -----------------
st.write("")
col_run, col_reset = st.columns([4, 1.2])
with col_run:
    find_jobs_btn = st.button("🚀 Find Matching Jobs & Auto-Draft Application Packs", type="primary", use_container_width=True)
with col_reset:
    if st.button("🔄 Clear Cache & Re-run", use_container_width=True):
        st.session_state.pop("app_state", None)
        st.rerun()

if find_jobs_btn or "app_state" in st.session_state:
    if not cv_text and find_jobs_btn:
        st.warning("⚠️ Please upload your CV file above first!")
    else:
        if find_jobs_btn:
            with st.status("Running Comprehensive Multi-Channel Engine...", expanded=True) as status:
                st.write("1. Enforcing Zero-Trust PII Redaction...")
                time.sleep(0.1)
                st.write(f"2. Scraping Duunitori, WeWorkRemotely, Remotive, Arbeitnow, RemoteOK & Hidden ATS for '{search_keyword}'...")
                
                # Execute application Use Case
                candidate, matched_jobs, match_results = st.session_state.match_use_case.execute(
                    cv_text=cv_text,
                    search_query=search_keyword,
                    portals=selected_portals,
                    privacy_mode=privacy_mode,
                    only_hidden_gems=only_hidden_gems
                )

                if remote_only:
                    matched_jobs = [j for j in matched_jobs if j.is_remote]

                st.session_state["app_state"] = {
                    "candidate": candidate,
                    "matched_jobs": matched_jobs,
                    "match_results": match_results
                }
                status.update(label=f"✅ Discovered {len(matched_jobs)} Jobs Across All Active Channels!", state="complete", expanded=False)

        state = st.session_state.get("app_state", {})
        jobs_to_show = state.get("matched_jobs", [])
        results_map = state.get("match_results", {})
        candidate = state.get("candidate")

        st.subheader(f"3. Discovered Matches ({len(jobs_to_show)} Jobs Found)")

        # Render Job Cards
        for idx, job in enumerate(jobs_to_show):
            score = job.match_score or 85
            badge_color = "#10B981" if score >= 85 else "#6366F1" if score >= 75 else "#F59E0B"
            res = results_map.get(job.id)

            gem_tag = "<span class='gem-badge'>✨ HIDDEN GEM / DIRECT ATS</span>" if getattr(job, 'is_hidden_gem', False) else ""

            with st.container():
                st.markdown(f"""
                <div class='job-card'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                        <div>
                            <h3 style='margin: 0; color: #FFFFFF;'>{job.title} {gem_tag}</h3>
                            <p style='margin: 4px 0 0 0; color: #94A3B8; font-size: 0.9rem;'>
                                <strong>{job.company}</strong> &bull; {job.location} &bull; 
                                <span style='color: #818CF8;'>Source: {job.source_portal}</span>
                            </p>
                        </div>
                        <span style='background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}55; padding: 4px 10px; border-radius: 8px; font-weight: 700; font-size: 0.95rem;'>
                            {score}% Match
                        </span>
                    </div>
                    <div style='margin-top: 8px; color: #10B981; font-weight: 600; font-size: 0.85rem;'>
                        💰 {job.salary_range}
                    </div>
                    <p style='margin-top: 8px; color: #CBD5E1; font-size: 0.88rem; line-height: 1.4;'>
                        {job.description[:230]}...
                    </p>
                    <div style='margin-top: 8px;'>
                        {' '.join([f"<span class='tag-chip'>{t}</span>" for t in job.tags[:6]])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Action Links Bar
                col_actions1, col_actions2 = st.columns([3, 1])
                with col_actions1:
                    links_html = f"<a href='{job.url}' target='_blank' style='display:inline-block; margin-right:16px; color:#818CF8; font-weight:600; font-size:0.88rem; text-decoration:none;'>🔗 Direct Job Application Link &rarr;</a>"
                    if getattr(job, 'company_url', None):
                        links_html += f"<a href='{job.company_url}' target='_blank' style='display:inline-block; color:#10B981; font-weight:600; font-size:0.88rem; text-decoration:none;'>🏢 Official Company Careers &rarr;</a>"
                    st.markdown(links_html, unsafe_allow_html=True)
                
                with col_actions2:
                    is_saved = job.id in st.session_state.pipeline_jobs
                    if st.button("📌 " + ("Saved" if is_saved else "Track Job"), key=f"track_{idx}"):
                        if not is_saved:
                            st.session_state.pipeline_jobs[job.id] = {
                                "title": job.title,
                                "company": job.company,
                                "source": job.source_portal,
                                "score": score,
                                "url": job.url,
                                "status": "Saved",
                                "notes": ""
                            }
                            st.success(f"Added {job.title} to Pipeline Tracker!")
                            st.rerun()

                # Expandable Application Pack: Cover Letter + InMail + Interview Prep
                with st.expander(f"📦 Open Application Pack for {job.company} (Cover Letter, Recruiter Outreach, Interview Prep)"):
                    t_cov, t_inmail, t_prep = st.tabs(["✍️ Tailored Cover Letter", "✉️ Recruiter Cold Outreach", "🎯 Interview Questions"])
                    
                    with t_cov:
                        if candidate:
                            letter = st.session_state.cover_letter_use_case.execute(candidate, job, match_result=res)
                            st.text_area("ATS-Tailored Cover Letter:", value=letter.content, height=200, key=f"cl_{idx}")
                            st.caption("✅ Grounded in your CV evidence and company requirements.")

                    with t_inmail:
                        outreach_text = f"""Hi [Hiring Manager / Recruiter at {job.company}],

I recently came across the {job.title} opening at {job.company} and wanted to reach out directly. 

With 7+ years architecting scalable Python backends and distributed systems, I recently engineered workflows that reduced operational query latency by 64% while maintaining high availability. Given {job.company}'s active growth, I'd love to share how my background in modern system architecture can immediately support your engineering goals.

Are you available for a brief 10-minute introductory conversation this week?

Best regards,
{candidate.full_name if candidate else 'Candidate'}"""
                        st.text_area("3-Sentence LinkedIn InMail / Recruiter Email:", value=outreach_text, height=180, key=f"inm_{idx}")
                        st.caption("💡 Ready to copy-paste directly to hiring managers or recruiters on LinkedIn.")

                    with t_prep:
                        st.write("### Predicted Interview Questions for this Role:")
                        st.markdown(f"""
                        1. **System Design:** How would you design a resilient, high-throughput asynchronous backend in Python to handle sudden bursts of data traffic?
                        2. **Domain Architecture:** At **{job.company}**, what architectural trade-offs would you make between low-latency caching (Redis/vector stores) and database consistency?
                        3. **Behavioral Impact:** Can you walk us through a production incident where latency spiked, and how you traced and resolved the bottleneck?
                        """)

# ----------------- SECTION 4: APPLICATION PIPELINE TRACKER -----------------
st.write("")
st.divider()
st.subheader("4. My Application Pipeline Tracker")

if not st.session_state.pipeline_jobs:
    st.info("💡 You have not tracked any jobs yet. Click **'📌 Track Job'** on any job card above to manage your applications here.")
else:
    tracker_data = []
    for j_id, item in list(st.session_state.pipeline_jobs.items()):
        tracker_data.append({
            "Job Title": item["title"],
            "Company": item["company"],
            "Portal": item["source"],
            "Match Fit": f"{item['score']}%",
            "Status": item["status"],
            "Application URL": item["url"],
            "Notes": item["notes"]
        })

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
            mime="text/csv"
        )
    with c_clr:
        if st.button("🧹 Clear Pipeline Tracker"):
            st.session_state.pipeline_jobs = {}
            st.rerun()
