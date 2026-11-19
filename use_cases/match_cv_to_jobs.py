"""
Use Case: Match CV against Portal Job Postings using Clean Architecture & Multi-Factor Fit Scoring
Supports all professions (Engineering, IT, Healthcare, Finance, Marketing, HR, Logistics, Public Sector).
"""
import re
from typing import Dict, List, Tuple

from core.entities import CandidateProfile, JobListing, MatchResult, RAGEvidenceChunk
from core.interfaces import IJobScraper, IRAGEngine


class MatchCVToJobsUseCase:
    def __init__(self, rag_engine: IRAGEngine, job_scraper: IJobScraper):
        self.rag = rag_engine
        self.scraper = job_scraper

    def _extract_skills(self, text: str) -> List[str]:
        # Ordered tuples: (display_label, regex_pattern) so short tokens use strict boundaries
        skill_patterns = [
            # Tech, Cloud & Backend
            (".NET", r"(?<!\w)\.net(?:\s*(?:core|\d+))?(?!\w)"),
            ("C#", r"(?<!\w)c#"),
            ("C++", r"(?<!\w)c\+\+"),
            ("Python", r"\bpython\b"),
            ("FastAPI", r"\bfastapi\b"),
            ("Django", r"\bdjango\b"),
            ("TypeScript", r"\btypescript\b"),
            ("JavaScript", r"\bjavascript\b"),
            ("React", r"\breact(?:\.js|js)?\b"),
            ("Angular", r"\bangular\b"),
            ("Vue", r"\bvue(?:\.js)?\b"),
            ("Node.js", r"\bnode(?:\.js|js)?\b"),
            ("Java", r"\bjava\b"),
            ("Azure", r"\bazure\b"),
            ("AWS", r"\baws\b"),
            ("GCP", r"\bgcp\b"),
            ("Docker", r"\bdocker\b"),
            ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
            ("Microservices", r"\bmicroservices?\b"),
            ("REST APIs", r"\brest(?:ful)?(?:\s*apis?)?\b"),
            ("GraphQL", r"\bgraphql\b"),
            ("SQL", r"\b(?:t-?sql|sql(?:\s*server)?)\b"),
            ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
            ("DevOps", r"\bdevops\b"),
            ("CI/CD", r"\bci/cd\b"),
            ("Git", r"\bgit\b"),
            ("Kafka", r"\bkafka\b"),
            ("Terraform", r"\bterraform\b"),
            ("Cloud Architecture", r"\bcloud\b"),
            ("Embedded Systems", r"\bembedded\b"),
            # Data & Applied AI
            ("RAG", r"\brag\b|retrieval[- ]augmented"),
            ("LLMs", r"\bllms?\b"),
            ("AI Agents", r"\bai\s*agents?\b|\bagentic\b"),
            ("LangChain", r"\blangchain\b"),
            ("LangGraph", r"\blanggraph\b"),
            ("PyTorch", r"\bpytorch\b"),
            ("TensorFlow", r"\btensorflow\b"),
            ("Vector Search", r"\bvector\s*(?:search|databases?|db|store)\b"),
            ("LLMOps", r"\bllmops\b|\bmlops\b"),
            ("Machine Learning", r"\bmachine\s+learning\b"),
            ("Deep Learning", r"\bdeep\s+learning\b"),
            ("Data Engineering", r"\bdata\s+engineering\b"),
            ("Applied AI", r"\b(?:generative\s+ai|applied\s+ai|ai\s*/?\s*ml)\b"),
            ("NLP", r"\bnlp\b"),
            # Healthcare & Clinical
            ("Healthcare Operations", r"\bhealthcare\b"),
            ("Clinical Leadership", r"\bclinical\b"),
            ("Patient Care", r"\bpatient\s+care\b"),
            ("Nursing", r"\bnursing\b|\bsairaanhoitaja\b|\blähihoitaja\b"),
            ("Hospital Management", r"\bhospital\b"),
            # Finance & Banking
            ("Finance", r"\bfinance\b|\bfinancial\b"),
            ("IFRS", r"\bifrs\b"),
            ("Accounting", r"\baccounting\b"),
            ("Risk Analysis", r"\brisk\s+(?:analysis|management|modeling)\b"),
            ("Banking", r"\bbanking\b"),
            ("Audit", r"\baudit(?:ing)?\b"),
            ("Financial Controlling", r"\bcontroller\b"),
            # Business, Marketing, HR, Logistics & Energy
            ("Marketing", r"\bmarketing\b"),
            ("Brand Strategy", r"\bbrand\s+strategy\b"),
            ("Communications", r"\bcommunications\b"),
            ("Project Management", r"\bproject\s+management\b|\bpmp\b"),
            ("HR & Talent Acquisition", r"\btalent\s+acquisition\b|\brecruitment\b|\bpeople\s+operations\b|\bhr\b"),
            ("Change Management", r"\bchange\s+management\b"),
            ("Supply Chain", r"\bsupply\s+chain\b"),
            ("Logistics", r"\blogistics\b"),
            ("Operations", r"\boperations\b"),
            ("ERP", r"\berp\b"),
            ("Procurement", r"\bprocurement\b"),
            ("Renewable Energy", r"\brenewable\s+energy\b"),
            ("SEO", r"\bseo\b"),
            ("CRM", r"\bcrm\b"),
            ("Analytics", r"\banalytics\b"),
            ("Leadership", r"\bleadership\b"),
            ("Strategy", r"\bstrategy\b"),
        ]
        found: List[str] = []
        for label, pattern in skill_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                found.append(label)
        return found if found else ["Domain Expertise", "Problem Solving", "Communication", "Leadership"]

    @staticmethod
    def _extract_years_experience(text: str) -> int:
        matches = re.findall(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", text, flags=re.IGNORECASE)
        nums = [int(m) for m in matches if 1 <= int(m) <= 40]
        if nums:
            return max(nums)
        if re.search(r"\bdecade\b", text, flags=re.IGNORECASE):
            return 10
        if any(k in text.lower() for k in ("senior", "principal", "director", "architect", "lead")):
            return 7
        return 4

    def execute(
        self,
        cv_text: str,
        search_query: str = "",
        portals: List[str] = None,
        country: str = "All",
        privacy_mode: bool = True,
        only_hidden_gems: bool = False,
    ) -> Tuple[CandidateProfile, List[JobListing], Dict[str, MatchResult]]:
        # 1. Enforce Zero-Trust PII Redaction & strip top personal header (name, contact, links)
        sanitized_text = self.rag.mask_pii(cv_text) if privacy_mode else cv_text
        clean_body = (
            self.rag.extract_clean_body(sanitized_text)
            if hasattr(self.rag, "extract_clean_body")
            else sanitized_text
        )

        # 2. Extract Candidate Skills, Experience Years & Profile (never store personal name/email into cover letters)
        cand_skills = self._extract_skills(clean_body or sanitized_text)
        years_exp = self._extract_years_experience(clean_body or sanitized_text)

        candidate = CandidateProfile(
            id="cand-01",
            full_name="Applicant",
            headline="Cross-Domain Specialist & Professional",
            email="",
            summary=(clean_body or sanitized_text)[:600],
            years_experience=years_exp,
            seniority_level="Senior" if years_exp >= 6 or any(k in sanitized_text.lower() for k in ("senior", "director", "lead", "architect", "decade")) else "Mid-Level",
            skills=cand_skills,
            raw_text=clean_body or sanitized_text,
            is_anonymized=True,
        )

        # 3. Build RAG Semantic Vector Chunks from anonymized body
        cv_chunks = self.rag.chunk_document(clean_body or sanitized_text)

        # 4. Scrape & Aggregate Jobs from Portals (handles scrapers with or without `country` param)
        try:
            raw_jobs = self.scraper.fetch_jobs(
                query=search_query,
                portals=portals,
                country=country,
                only_hidden_gems=only_hidden_gems,
            )
        except TypeError:
            raw_jobs = self.scraper.fetch_jobs(query=search_query, portals=portals)

        # 5. Differentiated Multi-Factor Fit Evaluation
        match_results: Dict[str, MatchResult] = {}
        cand_lower = sanitized_text.lower()

        for job in raw_jobs:
            req_haystack = f"{job.title} {job.description} {' '.join(job.tags)} {' '.join(job.requirements)}".lower()

            # Factor 1: Technical & Domain Skill Overlap (40% weight)
            matched_skills = [s for s in cand_skills if s.lower() in req_haystack]
            skill_ratio = len(matched_skills) / max(1, min(3, len(cand_skills)))
            skill_score = min(40, int(skill_ratio * 40))

            # Factor 2: Role Title & Search Query Alignment (35% weight)
            q_words = [w.lower() for w in re.split(r"\W+", search_query or "") if len(w) > 1]
            q_match = sum(1 for w in q_words if w in job.title.lower() or w in req_haystack)
            query_ratio = q_match / max(1, len(q_words)) if q_words else 0.65
            title_score = min(35, int(query_ratio * 35))

            # Factor 3: Seniority & Experience Match (15% weight)
            is_cand_senior = any(k in cand_lower for k in ("senior", "lead", "director", "manager", "architect"))
            is_job_senior = any(k in job.title.lower() for k in ("senior", "lead", "director", "manager", "architect"))
            seniority_score = 15 if is_cand_senior and is_job_senior else 10

            # Factor 4: Baseline Alignment (10%)
            base_score = 10

            overall_score = min(98, max(45, skill_score + title_score + seniority_score + base_score))
            job.match_score = overall_score

            missing_skills = [t for t in job.tags if t.title() not in matched_skills and t.lower() not in (country or "").lower()]

            evidence_pairs = self.rag.retrieve_relevant_chunks(req_haystack, cv_chunks, top_k=2)
            evidence_chunks = [
                RAGEvidenceChunk(cv_snippet=chunk, job_requirement=job.title, relevance_score=score)
                for chunk, score in evidence_pairs
            ]

            match_results[job.id] = MatchResult(
                job_id=job.id,
                overall_score=overall_score,
                technical_fit=min(98, overall_score + 3),
                experience_fit=min(95, overall_score - 2),
                matched_skills=matched_skills if matched_skills else cand_skills[:3],
                missing_skills=missing_skills[:3],
                strengths=[
                    f"Strong alignment with {', '.join(matched_skills[:3])}"
                    if matched_skills
                    else f"Transferable alignment with {job.title}"
                ],
                evidence=evidence_chunks,
            )

        raw_jobs.sort(key=lambda j: j.match_score or 0, reverse=True)
        return candidate, raw_jobs, match_results
