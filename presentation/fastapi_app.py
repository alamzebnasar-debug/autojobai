"""
Presentation Layer: FastAPI REST Controller
Exposes Clean Use Cases via HTTP Endpoints with Dependency Injection
"""
from fastapi import FastAPI, Depends, Query
from typing import List, Optional
from pydantic import BaseModel

from infrastructure.rag_engine import RAGEngineImpl
from infrastructure.job_scrapers import JobScraperImpl
from infrastructure.llm_service import GeminiLLMService
from use_cases.match_cv_to_jobs import MatchCVToJobsUseCase
from use_cases.generate_cover_letter import GenerateCoverLetterUseCase

app = FastAPI(
    title="AutoJobAI Clean Architecture API",
    description="Clean Architecture implementation of Autonomous CV Matcher & Job Hunter",
    version="2.0.0"
)

# Dependency Injection Container
def get_match_use_case():
    rag = RAGEngineImpl()
    scraper = JobScraperImpl()
    return MatchCVToJobsUseCase(rag, scraper)

def get_cover_letter_use_case():
    llm = GeminiLLMService()
    return GenerateCoverLetterUseCase(llm)

class CVMatchRequest(BaseModel):
    cv_text: str
    search_query: str = "Senior AI Engineer"
    portals: Optional[List[str]] = ["LinkedIn", "RemoteOK", "Indeed"]
    privacy_mode: bool = True

@app.get("/")
def health():
    return {"status": "healthy", "architecture": "Clean / Hexagonal Architecture", "version": "2.0.0"}

@app.post("/api/jobs/match")
def match_jobs(req: CVMatchRequest, use_case: MatchCVToJobsUseCase = Depends(get_match_use_case)):
    candidate, jobs, results = use_case.execute(
        cv_text=req.cv_text,
        search_query=req.search_query,
        portals=req.portals,
        privacy_mode=req.privacy_mode
    )
    return {
        "candidate": candidate,
        "total_jobs_found": len(jobs),
        "jobs": jobs,
        "match_results": results
    }
