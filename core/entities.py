"""
Domain Layer: Pure Business Entities & Value Objects (Zero External Dependencies)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class CandidateProfile:
    id: str
    full_name: str
    headline: str
    email: str
    summary: str
    years_experience: int
    seniority_level: str
    skills: List[str] = field(default_factory=list)
    raw_text: str = ""
    is_anonymized: bool = False

@dataclass
class JobListing:
    id: str
    title: str
    company: str
    location: str
    is_remote: bool
    salary_range: str
    source_portal: str
    url: str
    posted_date: str
    description: str
    tags: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    match_score: Optional[int] = None
    company_url: Optional[str] = None
    category: str = "standard"  # "hidden_gem", "research_public", "startup_ats", "enterprise"
    is_hidden_gem: bool = False
    interview_tips: List[str] = field(default_factory=list)
    status: str = "discovered"

@dataclass
class RAGEvidenceChunk:
    cv_snippet: str
    job_requirement: str
    relevance_score: float

@dataclass
class MatchResult:
    job_id: str
    overall_score: int
    technical_fit: int
    experience_fit: int
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    evidence: List[RAGEvidenceChunk] = field(default_factory=list)

@dataclass
class CoverLetter:
    job_id: str
    company_name: str
    role_title: str
    tone: str
    content: str
    word_count: int = 0
    ats_readiness: int = 94

@dataclass
class NotificationAlert:
    recipient_email: str
    subject: str
    top_matches_count: int
    top_score: int
    is_dispatched: bool = True
