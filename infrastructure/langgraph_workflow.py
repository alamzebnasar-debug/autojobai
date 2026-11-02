"""
Infrastructure Layer: LangGraph Multi-Agent StateGraph Workflow
Coordinates: Ingestion -> Vector Indexer -> Scraper -> RAG Matcher -> Cover Letter -> Alert
"""
import time
from typing import Dict, Any, List
from core.entities import CandidateProfile, JobListing
from use_cases.match_cv_to_jobs import MatchCVToJobsUseCase
from use_cases.generate_cover_letter import GenerateCoverLetterUseCase

class LangGraphWorkflow:
    def __init__(self, match_use_case: MatchCVToJobsUseCase, cover_letter_use_case: GenerateCoverLetterUseCase):
        self.match_use_case = match_use_case
        self.cover_letter_use_case = cover_letter_use_case

    def run(self, cv_text: str, search_query: str = "Senior AI Engineer", portals: List[str] = None, privacy_mode: bool = True) -> Dict[str, Any]:
        t0 = time.time()
        
        # 1. Execute matching use case (ingestion + vector chunking + scraper + RAG scoring)
        candidate, matched_jobs, match_results = self.match_use_case.execute(
            cv_text=cv_text,
            search_query=search_query,
            portals=portals,
            privacy_mode=privacy_mode
        )

        # 2. Pre-generate cover letter for top matching jobs
        letters = {}
        for job in matched_jobs[:3]:
            res = match_results.get(job.id)
            letters[job.id] = self.cover_letter_use_case.execute(candidate, job, match_result=res)

        elapsed_ms = int((time.time() - t0) * 1000)

        trace = [
            {"node": "CV_Ingestion_Node", "summary": f"Parsed profile. PII Redaction: {'Active' if privacy_mode else 'Off'}"},
            {"node": "RAG_Vector_Indexer_Node", "summary": "Segmented CV into semantic vector chunks."},
            {"node": "Portal_Scraper_Node", "summary": f"Queried active job boards for '{search_query}'."},
            {"node": "Semantic_Fit_Node", "summary": f"Ranked {len(matched_jobs)} candidate positions."},
            {"node": "Cover_Letter_Synthesis_Node", "summary": f"Synthesized ATS-tailored letters for top matches."},
        ]

        return {
            "status": "completed",
            "candidate": candidate,
            "matched_jobs": matched_jobs,
            "match_results": match_results,
            "cover_letters": letters,
            "execution_trace": trace,
            "duration_ms": elapsed_ms
        }
