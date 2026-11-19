"""
Infrastructure Layer: Concrete LLM & Grounded Cover Letter Synthesis Service
Implements ILLMService with Gemini SDK integration + Job-Description-Grounded Multi-Industry Synthesis.
Automatically loads GEMINI_API_KEY from environment or .env file.
Strictly excludes personal identifying information (name, email, phone, address, links, citizenship) from output.
"""
import hashlib
import os
import re
from typing import List, Optional

from core.entities import CandidateProfile, JobListing
from core.interfaces import ILLMService
from infrastructure.rag_engine import RAGEngineImpl


def _load_env_if_present():
    """Lightweight built-in .env parser (zero third-party dependency)"""
    search_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    ]
    for env_path in search_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


_load_env_if_present()


class GeminiLLMService(ILLMService):
    def __init__(self, api_key: str = None):
        _load_env_if_present()
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.last_generation_mode = "grounded_rag"

    def set_api_key(self, api_key: str):
        self.api_key = (api_key or "").strip()

    @property
    def is_active(self) -> bool:
        return bool(
            self.api_key
            and not self.api_key.startswith("MY_GEMINI")
            and not self.api_key.startswith("your-gemini")
        )

    @staticmethod
    def _detect_domain(job: JobListing) -> str:
        title_low = (job.title or "").lower()
        text = f"{job.title} {job.description} {' '.join(job.tags)} {' '.join(job.requirements)}".lower()
        # Check explicit role-title signals first so e.g. 'Cloud Engineer' at a bank stays tech/engineering
        if any(w in title_low for w in ["engineer", "developer", "architect", "devops", "llmops", "ml", "ai", "software", "cloud", "data"]):
            if not any(w in title_low for w in ["energy", "wind", "offshore"]):
                return "software architecture, cloud systems, and applied AI engineering"
        if any(w in text for w in ["nurse", "clinical", "patient", "hospital", "healthcare", "medical", "sairaanhoitaja"]):
            return "healthcare and clinical operations"
        if any(w in text for w in ["finance", "ifrs", "risk analysis", "accounting", "controller", "banking", "audit"]):
            return "finance, regulatory reporting, and risk analysis"
        if any(w in text for w in ["marketing", "brand", "campaign", "communications", "seo", "growth"]):
            return "brand strategy, communications, and multi-channel marketing"
        if any(w in text for w in ["hr", "talent", "recruiting", "recruitment", "people operations", "workforce"]):
            return "talent acquisition, organizational development, and HR leadership"
        if any(w in text for w in ["supply chain", "logistics", "freight", "warehouse", "erp", "procurement"]):
            return "supply chain optimization and international logistics operations"
        if any(w in text for w in ["energy", "renewable", "offshore", "wind", "grid"]):
            return "energy infrastructure and multidisciplinary project delivery"
        if any(w in text for w in ["python", ".net", "c#", "react", "rag", "llm", "ai", "software", "cloud", "fastapi", "kubernetes"]):
            return "software architecture, cloud systems, and applied AI engineering"
        return "operational strategy and specialized execution"

    @staticmethod
    def _extract_job_focus_points(job: JobListing) -> List[str]:
        desc = re.sub(r"\s+", " ", (job.description or "")).strip()
        # Split strictly on sentence-ending punctuation followed by whitespace (never '.NET' or 'Finn.no')
        sentences = [s.strip(" .") for s in re.split(r"(?:(?<!\s)[.!?]+(?=\s|$))", desc) if len(s.strip()) > 25]
        return sentences[:3]

    @staticmethod
    def _sanitize_evidence_snippet(text: str, candidate_name: str = "", candidate_email: str = "") -> str:
        """
        Extracts clean, grammatical experience prose from CV chunks:
        - Rejects binary/ZIP/XML corruption ('PK!', '[Content_Types].xml', etc.)
        - Strips CV headers (SUMMARY, citizenship, LinkedIn/GitHub/Portfolio, city/country, names, emails, phones)
        - Rejects glued-together PDF strings without proper word spacing (e.g. 'SeniorSoftwareEngineer...')
        """
        if not text:
            return ""

        binary_markers = ("PK!", "PK\x03", "[Content_Types].xml", "word/document.xml", "_rels/.rels", "%PDF-")
        if any(marker in text for marker in binary_markers):
            return ""

        # Skip raw SKILLS: / TECHNOLOGIES: label lines so comma lists don't pollute narrative experience prose
        if re.match(r"^\s*(skills|technical\s+skills|technologies|tools|languages|certifications)\s*[:\-]", text, flags=re.IGNORECASE):
            return ""

        cleaned = RAGEngineImpl.extract_clean_body(text) or text
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Remove any remaining PII / contact noise
        cleaned = re.sub(r"\[(EMAIL|PHONE|URL|ADDRESS|NAME|PII)_REDACTED\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\([^)]*citizen[^)]*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(LinkedIn|GitHub|Portfolio|SUMMARY|PROFILE|EXPERIENCE|SKILLS)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", cleaned)
        cleaned = re.sub(r"https?://\S+|www\.\S+", "", cleaned)
        cleaned = re.sub(r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}", "", cleaned)

        if candidate_name and candidate_name.lower() not in ("applicant", "candidate", "candidate (protected)", "candidate profile"):
            for part in [candidate_name] + candidate_name.split():
                if len(part) > 2:
                    cleaned = re.sub(rf"\b{re.escape(part)}\b", "", cleaned, flags=re.IGNORECASE)
        if candidate_email:
            cleaned = cleaned.replace(candidate_email, "")

        # Collapse stray punctuation like ", , ,"
        cleaned = re.sub(r"(?:[,\|•·]\s*){2,}", ", ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;|-:")

        # Split on newlines, bullets, OR sentence punctuation before collapsing spaces
        raw_clauses = re.split(r"(?:\r?\n|•|▪|◦|(?<=[.!?])\s+)", cleaned)
        good_clauses = []
        for raw_c in raw_clauses:
            clause = re.sub(r"^[\-\*\d\.\)\s]+", "", raw_c)
            clause = re.sub(r"\s+", " ", clause).strip(" ,.;|-:")
            if len(clause) < 28:
                continue
            words = clause.split()
            if len(words) < 5:
                continue
            # Reject glued tokens like "SeniorSoftwareEngineerwithadecade..." per clause only
            if any(len(w) > 28 and "/" not in w and "-" not in w for w in words):
                continue
            alpha_chars = sum(c.isalpha() for c in clause)
            if (alpha_chars / max(1, len(clause))) < 0.62:
                continue
            # Reject comma-separated tag lists with few connecting verbs
            if clause.count(",") >= 4 and len(words) <= 14:
                continue
            if not clause.endswith((".", "!", "?")):
                clause += "."
            good_clauses.append(clause)
            if len(" ".join(good_clauses)) >= 220:
                break

        result = " ".join(good_clauses).strip()
        if not result:
            return ""
        if len(result) > 260:
            result = result[:260].rsplit(" ", 1)[0].rstrip(" ,.;") + "."
        return result

    def _extract_experience_highlights(
        self,
        candidate: CandidateProfile,
        evidence: Optional[List[str]] = None,
        max_items: int = 2,
    ) -> List[str]:
        cand_name = getattr(candidate, "full_name", "")
        cand_email = getattr(candidate, "email", "")
        # Prefer raw CV lines first (preserving clean bullet boundaries), then RAG evidence chunks & summary
        sources = []
        if getattr(candidate, "raw_text", ""):
            sources.extend(re.split(r"(?:\r?\n|•|▪|◦)+", candidate.raw_text))
        for ev in (evidence or []):
            sources.extend(re.split(r"(?:\r?\n|•|▪|◦)+", ev))
        if getattr(candidate, "summary", ""):
            sources.extend(re.split(r"(?:\r?\n|•|▪|◦)+", candidate.summary))

        collected: List[str] = []
        seen_signatures = set()
        for line in sources:
            if not line or not line.strip():
                continue
            cleaned = self._sanitize_evidence_snippet(
                line,
                candidate_name=cand_name,
                candidate_email=cand_email,
            )
            if not cleaned:
                continue
            sig = cleaned.lower()[:45]
            if sig in seen_signatures or any(sig in prev.lower() or prev.lower()[:45] in cleaned.lower() for prev in collected):
                continue
            seen_signatures.add(sig)
            collected.append(cleaned)
            if len(collected) >= max_items:
                break
        return collected

    def _synthesize_grounded_letter(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        evidence: Optional[List[str]] = None,
        tone: str = "persuasive",
        matched_skills: Optional[List[str]] = None,
        custom_focus: str = "",
    ) -> str:
        domain = self._detect_domain(job)
        desc_points = self._extract_job_focus_points(job)
        primary_mission = desc_points[0] if desc_points else f"delivering high-impact results as {job.title}"
        secondary_focus = desc_points[1] if len(desc_points) > 1 else ""

        job_haystack = f"{job.title} {job.description} {' '.join(job.tags)} {' '.join(job.requirements)}".lower()
        cand_skills = [s for s in (candidate.skills or []) if s]

        overlapping = list(matched_skills or [])
        if not overlapping:
            overlapping = [s for s in cand_skills if s.lower() in job_haystack]

        # Build prioritized skill set: direct job overlap first, followed by candidate's core CV stack
        combined_skills: List[str] = []
        for s in overlapping + cand_skills:
            if s and s not in combined_skills:
                combined_skills.append(s)
        highlighted_skills = combined_skills[:4] if combined_skills else ["cross-functional execution"]
        secondary_stack = [s for s in combined_skills[4:8] if s not in highlighted_skills]

        req_items = [r.strip() for r in (job.requirements or []) if r and r.strip()]
        req_phrase = "; ".join(req_items[:3]) if req_items else ", ".join(job.tags[:3] or [domain])

        highlights = self._extract_experience_highlights(candidate, evidence=evidence, max_items=2)

        variant = int(hashlib.md5(f"{job.company}-{job.title}-{tone}".encode("utf-8")).hexdigest(), 16) % 3
        location_note = f" in {job.location}" if job.location else ""
        mission_phrase = primary_mission[0].lower() + primary_mission[1:] if len(primary_mission) > 1 else primary_mission

        if tone == "executive":
            openings = [
                f"With over {candidate.years_experience} years leading initiatives across {domain}, I was energized to see {job.company}'s opening for a {job.title}{location_note}.",
                f"Your mandate for the {job.title} role at {job.company}—specifically around {mission_phrase}—aligns squarely with my {candidate.years_experience}+ years of leadership track record.",
                f"At a pivotal stage for {job.company}'s initiatives in {job.location}, bringing strategic rigor to {domain} is critical—and that is precisely where my {candidate.years_experience}+ years of experience delivers immediate leverage.",
            ]
        elif tone == "conversational":
            openings = [
                f"As someone who has spent {candidate.years_experience}+ years immersed in {domain}, seeing {job.company} hiring for a {job.title}{location_note} immediately stood out.",
                f"I have been following {job.company}'s work closely, and the focus on {mission_phrase} in your {job.title} description aligns closely with the work I enjoy most.",
                f"Joining {job.company} as {job.title} is an exciting match: you are looking for someone skilled in {req_phrase}, which sits right at the heart of my background.",
            ]
        else:
            openings = [
                f"Your search for a {job.title} at {job.company}{location_note} stood out immediately because of the role's emphasis on {mission_phrase}.",
                f"With {candidate.years_experience}+ years of proven impact in {domain}, I am eager to bring directly relevant expertise to {job.company} as your next {job.title}.",
                f"{job.company}'s need for a {job.title} capable of tackling {req_phrase} aligns directly with the core strengths I have built across my {candidate.years_experience}-year career.",
            ]

        opening = openings[variant]

        bridge_para = (
            f"Specifically, your posting highlights key priorities including {req_phrase}. "
            f"My core technical and domain toolkit spans {', '.join(highlighted_skills)}"
            + (f", complemented by hands-on experience in {', '.join(secondary_stack)}" if secondary_stack else "")
            + f"—enabling me to step into {job.company}'s environment and contribute to {domain} from day one."
        )
        if secondary_focus:
            bridge_para += f' In particular, your goal around "{secondary_focus}" resonates strongly with how I structure high-impact deliverables.'

        if highlights:
            exp_text = " ".join(highlights)
            if len(exp_text) > 1 and not exp_text.startswith(("I ", "I'", ".NET")):
                exp_lead = exp_text[0].lower() + exp_text[1:]
            else:
                exp_lead = exp_text
            evidence_para = (
                f"\n\nIn my recent roles, I have {exp_lead} "
                f"Applying this hands-on delivery background to {job.company}'s priorities allows me to turn complex requirements into measurable, reliable outcomes."
            )
        else:
            evidence_para = (
                f"\n\nAcross {candidate.years_experience}+ years of hands-on delivery involving {', '.join(highlighted_skills[:4])}, "
                f"I have consistently translated ambiguous requirements into production-ready solutions with measurable business and operational impact. "
                f"Bringing this discipline to {job.company} positions me to accelerate key initiatives for the {job.title} team."
            )

        custom_para = ""
        if custom_focus and custom_focus.strip():
            custom_para = f"\n\nAdditionally, I want to emphasize: {custom_focus.strip()}"

        closings = [
            f"I welcome the opportunity to discuss how my expertise in {', '.join(highlighted_skills[:3])} can directly support {job.company}'s roadmap for the {job.title} position.",
            f"Thank you for considering my application. I look forward to speaking with the {job.company} hiring team about how my background in {', '.join(highlighted_skills[:2])} can add immediate value in this {job.title} role.",
            f"I would value a conversation to explore how my {candidate.years_experience}+ years of experience across {domain} and {', '.join(highlighted_skills[:2])} aligns with {job.company}'s goals.",
        ]
        closing = closings[(variant + 1) % 3]

        return (
            f"Dear {job.company} Hiring Team,\n\n"
            f"{opening}\n\n"
            f"{bridge_para}"
            f"{evidence_para}"
            f"{custom_para}\n\n"
            f"{closing}\n\n"
            f"Sincerely,"
        )

    def generate_cover_letter(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        evidence: list = None,
        tone: str = "persuasive",
        matched_skills: list = None,
        custom_focus: str = "",
        use_llm: bool = True,
    ) -> str:
        sanitized_summary = self._sanitize_evidence_snippet(
            candidate.summary or "",
            candidate_name=getattr(candidate, "full_name", ""),
            candidate_email=getattr(candidate, "email", ""),
        )
        sanitized_evidence = [
            self._sanitize_evidence_snippet(
                e,
                candidate_name=getattr(candidate, "full_name", ""),
                candidate_email=getattr(candidate, "email", ""),
            )
            for e in (evidence or [])
        ]
        sanitized_evidence = [e for e in sanitized_evidence if e]

        if use_llm and self.is_active:
            try:
                from google import genai

                client = genai.Client(api_key=self.api_key)
                prompt = f"""You are an Executive Career Strategist. Write a deeply personalized, company-specific cover letter for an applicant applying to "{job.title}" at {job.company} ({job.location}).

STRICT PRIVACY & ANTI-GENERIC RULES:
1. DO NOT include any personal identifying information (NO candidate name, NO email address, NO phone number, NO home address, NO citizenship, NO social links). End simply with "Sincerely,".
2. NEVER copy raw CV headers or paste parenthetical CV quotes. Paraphrase naturally.
3. NEVER open with clichés like "I am writing to express my interest". Open with a crisp hook specific to {job.company} and this role.
4. Explicitly address specific requirements from: {job.requirements} and description: "{job.description}".
5. Connect matched skills ({', '.join(matched_skills or candidate.skills[:5])}) and anonymized background ({' | '.join(sanitized_evidence)}) to {job.company}'s domain.
6. Keep the tone "{tone}", sharp, authentic, and 260–340 words.
{f'7. Emphasize this custom note: "{custom_focus}"' if custom_focus else ''}

Anonymized Applicant Profile:
- Years of Experience: {candidate.years_experience}
- Summary: {sanitized_summary}
- Skills: {', '.join(candidate.skills)}
"""
                for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                        )
                        if response.text and response.text.strip():
                            self.last_generation_mode = f"gemini:{model_name}"
                            return response.text.strip()
                    except Exception:
                        continue
            except Exception:
                pass

        self.last_generation_mode = "grounded_rag"
        return self._synthesize_grounded_letter(
            candidate=candidate,
            job=job,
            evidence=sanitized_evidence,
            tone=tone,
            matched_skills=matched_skills,
            custom_focus=custom_focus,
        )

    def _synthesize_grounded_interview_prep(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
    ) -> dict:
        domain = self._detect_domain(job)
        desc_points = self._extract_job_focus_points(job)
        primary_mandate = desc_points[0] if desc_points else f"driving measurable delivery for {job.title}"
        secondary_mandate = desc_points[1] if len(desc_points) > 1 else ""

        reqs = [r.strip() for r in (job.requirements or []) if r and r.strip()]
        req_1 = reqs[0] if reqs else (job.tags[0] if job.tags else job.title)
        req_2 = reqs[1] if len(reqs) > 1 else (job.tags[1] if len(job.tags) > 1 else domain)

        matched = list(matched_skills or [])
        if not matched:
            hay = f"{job.title} {job.description} {' '.join(job.tags)} {' '.join(reqs)}".lower()
            matched = [s for s in (candidate.skills or []) if s.lower() in hay]
        top_matched = matched[:3] if matched else (candidate.skills[:3] or ["domain leadership"])

        missing = [m.strip() for m in (missing_skills or []) if m and m.strip()]
        gap_focus = missing[0] if missing else req_2

        # Domain-specific deep governance/technical scenario probe
        if "healthcare" in domain:
            scale_q = (
                f"In {job.company}'s clinical environment in {job.location}, how do you balance patient safety, "
                f"regulatory compliance, and staff workload sustainability while executing '{primary_mandate}'?"
            )
            scale_rubric = "Patient-outcome metrics, regulatory awareness, clinician buy-in, and structured escalation protocols."
        elif "finance" in domain:
            scale_q = (
                f"How do you enforce auditability, IFRS/regulatory accuracy, and executive forecasting speed when "
                f"addressing {job.company}'s priorities around {req_1}?"
            )
            scale_rubric = "Control frameworks, variance diagnostics, automated reconciliation, and board-level risk clarity."
        elif "marketing" in domain:
            scale_q = (
                f"How would you structure multi-channel attribution and pipeline ROI experiments at {job.company} "
                f"to prove commercial lift across European markets for this {job.title} mandate?"
            )
            scale_rubric = "CAC/LTV discipline, regional localization across Nordics/EU, and experimentation rigor."
        elif "talent" in domain or "hr" in domain:
            scale_q = (
                f"At {job.company}, how have you partnered with functional leaders to scale hiring velocity "
                f"and workforce retention without compromising bar-raising assessment standards?"
            )
            scale_rubric = "Structured hiring rubrics, workforce analytics, change leadership, and retention metrics."
        elif "logistics" in domain or "supply chain" in domain:
            scale_q = (
                f"When cross-border disruptions hit freight or supplier SLAs, how do you redesign buffers, "
                f"carrier redundancies, and ERP visibility to protect {job.company}'s delivery commitments?"
            )
            scale_rubric = "SLA telemetry, cost-to-serve trade-offs, supplier governance, and contingency playbooks."
        elif "energy" in domain:
            scale_q = (
                f"How do you manage permitting bottlenecks, HSE compliance, and multi-contractor capex schedules "
                f"on large-scale initiatives similar to {job.company}'s {job.title} scope?"
            )
            scale_rubric = "Critical-path risk management, HSE non-negotiables, regulatory coordination, and budget control."
        else:
            scale_q = (
                f"In {job.company}'s context around '{primary_mandate}', what failure modes, latency/throughput bottlenecks, "
                f"or observability blind spots would you instrument first before scaling?"
            )
            scale_rubric = "Production telemetry, fault isolation, cost/latency trade-offs, and pragmatic system boundaries."

        questions = [
            {
                "category": "Core Role Mandate",
                "question": (
                    f"{job.company}'s posting specifically emphasizes '{primary_mandate}'. Walk through a comparable "
                    f"end-to-end initiative you led: what constraints did you inherit, what key decisions did you own, "
                    f"and what measurable result proved it worked?"
                ),
                "what_they_look_for": f"Direct ownership (not 'we did'), clear metrics tied to {job.company}'s real scope, and pragmatic trade-offs.",
                "answer_angle": f"Use STAR framing anchored on {', '.join(top_matched[:2])} and quantify outcome (cost, speed, quality, or reliability).",
            },
            {
                "category": "Requirement Deep Dive",
                "question": (
                    f"A core requirement for this {job.title} role is '{req_1}'. Describe a situation where applying "
                    f"'{req_1}' at scale broke down or revealed an unexpected edge case—and how you redesigned the approach."
                ),
                "what_they_look_for": f"Depth beyond buzzwords in {req_1}: diagnosing root causes rather than applying textbook fixes.",
                "answer_angle": f"Highlight a concrete technical or operational bottleneck you resolved using {top_matched[0]} and explain what changed permanently.",
            },
            {
                "category": "Domain Risk & Scale",
                "question": scale_q,
                "what_they_look_for": scale_rubric,
                "answer_angle": f"Connect your {candidate.years_experience}+ years in {domain} directly to risk prevention before problems reach end users or regulators.",
            },
            {
                "category": "Quantified Strength Proof",
                "question": (
                    f"Your profile aligns strongly on {', '.join(top_matched)}. Which specific deliverable in your "
                    f"recent work best predicts your day-one impact on {job.company}'s {job.title} team in {job.location}?"
                ),
                "what_they_look_for": "Transferability from past achievements directly into this team's immediate backlog.",
                "answer_angle": "Pick one flagship project with concrete before/after KPIs and explain why that pattern transfers cleanly to this company.",
            },
            {
                "category": "Skill-Gap & Ramp-Up Readiness",
                "question": (
                    f"For '{gap_focus}'—listed among {job.company}'s key expectations—how would you close any context "
                    f"gap in your first 30 days while still delivering early wins on {', '.join(top_matched[:2])}?"
                ),
                "what_they_look_for": "Intellectual honesty, fast self-directed ramp-up habits, and zero defensiveness around growth areas.",
                "answer_angle": f"Acknowledge adjacency between {top_matched[0]} and {gap_focus}, then outline a concrete 2-week learning & shadowing plan.",
            },
            {
                "category": "Architecture / Process Trade-Offs",
                "question": (
                    f"If leadership at {job.company} asked you to accelerate delivery on "
                    f"'{secondary_mandate or req_2}' by 40% without increasing headcount, what scope, process, or design trade-offs would you propose?"
                ),
                "what_they_look_for": "Prioritization judgment, eliminating low-ROI work, and protecting non-negotiable quality bars.",
                "answer_angle": "Separate must-have risk controls from deferrable polish and propose phased milestones with clear checkpoints.",
            },
            {
                "category": "Nordic Cross-Functional Alignment",
                "question": (
                    f"Nordic organizations like {job.company} rely heavily on flat hierarchy and consensus-driven "
                    f"collaboration. Tell us about a time key stakeholders strongly disagreed on direction around {req_2}—how did you align everyone and move forward?"
                ),
                "what_they_look_for": "Low-ego persuasion, data-backed alignment, active listening, and decisive follow-through.",
                "answer_angle": "Show how you surfaced shared business goals, tested assumptions objectively, and preserved team trust.",
            },
            {
                "category": "First 90 Days at " + job.company,
                "question": (
                    f"Imagine it is Day 90 in your role as {job.title} at {job.company}. What specific bottleneck "
                    f"have you unblocked, and what concrete metric would convince the hiring manager you were an exceptional hire?"
                ),
                "what_they_look_for": "Structured 30-60-90 thinking: listening first (Days 1-30), shipping a targeted win (Days 31-60), scaling impact (Days 61-90).",
                "answer_angle": f"Anchor your 30-60-90 hypothesis around '{primary_mandate}' and ask the panel to validate it.",
            },
        ]

        questions_to_ask = [
            f"Looking at the next 6 months for {job.company}'s {job.title} role, what is the single hardest bottleneck around '{req_1}' that the person stepping into this seat needs to solve first?",
            f"How does {job.company} define exceptional performance vs. solid performance at the 6-month mark for someone focusing on '{primary_mandate}'?",
            f"What cross-functional dependencies in {job.location} (product, operations, compliance, or leadership) most impact this team's velocity today?",
        ]

        return {
            "questions": questions,
            "questions_to_ask": questions_to_ask,
            "mode": "grounded_rag",
        }

    def generate_interview_questions(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
        use_llm: bool = False,
    ) -> dict:
        import json as json_lib

        if use_llm and self.is_active:
            try:
                from google import genai

                client = genai.Client(api_key=self.api_key)
                reqs_text = "; ".join(job.requirements or job.tags or [job.title])
                matched_text = ", ".join(matched_skills or candidate.skills[:5])
                missing_text = ", ".join(missing_skills or []) or "None identified"
                prompt = f"""You are a Principal Interview Coach. Generate 8 deeply insightful, role-specific interview questions AND 3 strategic reverse-interview questions for a candidate interviewing for "{job.title}" at {job.company} ({job.location}).

STRICT PRIVACY RULE: Never include any candidate name, email, phone, address, citizenship, or URLs.

Job Context:
- Company: {job.company}
- Role: {job.title}
- Location: {job.location}
- Description: {job.description}
- Requirements: {reqs_text}
- Candidate Matched Strengths: {matched_text}
- Candidate Potential Skill Gaps to Probe: {missing_text}
- Candidate Experience: {candidate.years_experience} years

Return ONLY valid JSON with this exact schema:
{{
  "questions": [
    {{
      "category": "Short category title (e.g. Core Mandate, Requirement Deep Dive, Gap Readiness, 90-Day Plan)",
      "question": "Deep, specific interview question referencing {job.company} and actual requirements/description details",
      "what_they_look_for": "Concise 1-sentence rubric of what separates a top 1% answer",
      "answer_angle": "Concise 1-sentence coaching tip grounded in matched strengths"
    }}
  ],
  "questions_to_ask": [
    "3 sharp reverse-interview questions the candidate should ask {job.company}"
  ]
}}"""
                for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
                    try:
                        response = client.models.generate_content(model=model_name, contents=prompt)
                        raw_txt = (response.text or "").strip()
                        m = re.search(r"\{.*\}", raw_txt, re.DOTALL)
                        if m:
                            parsed = json_lib.loads(m.group(0))
                            qs = parsed.get("questions", [])
                            ask = parsed.get("questions_to_ask", [])
                            if isinstance(qs, list) and len(qs) >= 6:
                                return {
                                    "questions": qs[:10],
                                    "questions_to_ask": ask[:4] if isinstance(ask, list) else [],
                                    "mode": f"gemini:{model_name}",
                                }
                    except Exception:
                        continue
            except Exception:
                pass

        return self._synthesize_grounded_interview_prep(
            candidate=candidate,
            job=job,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
        )
