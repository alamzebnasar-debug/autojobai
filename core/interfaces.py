"""
Domain Interfaces (Ports): Clean Abstract Contracts for Infrastructure to Implement
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from core.entities import CandidateProfile, JobListing, MatchResult, CoverLetter

class IRAGEngine(ABC):
    @abstractmethod
    def mask_pii(self, text: str) -> str:
        """Sanitizes sensitive Personally Identifiable Information"""
        pass

    @abstractmethod
    def chunk_document(self, text: str) -> List[str]:
        """Splits document into overlapping semantic passages"""
        pass

    @abstractmethod
    def compute_similarity(self, query: str, document: str) -> float:
        """Computes semantic cosine similarity between vectors"""
        pass

    @abstractmethod
    def retrieve_relevant_chunks(self, query: str, chunks: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        """Retrieves top-k matching evidence chunks for a requirement"""
        pass

class IJobScraper(ABC):
    @abstractmethod
    def fetch_jobs(self, query: str = "", portals: List[str] = None) -> List[JobListing]:
        """Scrapes and aggregates job listings from external portals"""
        pass

class ILLMService(ABC):
    @abstractmethod
    def generate_cover_letter(self, candidate: CandidateProfile, job: JobListing, evidence: List[str], tone: str = "persuasive") -> str:
        """Generates tailored cover letter grounded in retrieved RAG evidence"""
        pass

class INotificationService(ABC):
    @abstractmethod
    def send_alert(self, email: str, top_jobs: List[JobListing]) -> bool:
        """Dispatches automated match notifications to candidate"""
        pass
