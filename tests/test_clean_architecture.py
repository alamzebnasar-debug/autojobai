"""
Clean Architecture Unit & Integration Tests
Tests Domain Entities, Use Cases, and Infrastructure Ports
Run with: python -m unittest discover tests
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.entities import CandidateProfile, JobListing
from infrastructure.rag_engine import RAGEngineImpl
from infrastructure.job_scrapers import JobScraperImpl
from infrastructure.llm_service import GeminiLLMService
from use_cases.match_cv_to_jobs import MatchCVToJobsUseCase
from use_cases.generate_cover_letter import GenerateCoverLetterUseCase

class TestCleanArchitecture(unittest.TestCase):
    def setUp(self):
        self.rag = RAGEngineImpl()
        self.scraper = JobScraperImpl()
        self.llm = GeminiLLMService()
        self.match_use_case = MatchCVToJobsUseCase(self.rag, self.scraper)
        self.cover_letter_use_case = GenerateCoverLetterUseCase(self.llm)

    def test_domain_entity_creation(self):
        """Domain Layer: Verify pure entities without external coupling"""
        job = JobListing(
            id="job-1",
            title="Senior AI Engineer",
            company="Tech Corp",
            location="Remote",
            is_remote=True,
            salary_range="$150k - $180k",
            source_portal="LinkedIn",
            url="https://linkedin.com",
            posted_date="Today",
            description="Build RAG pipelines with Python and FastAPI."
        )
        self.assertEqual(job.title, "Senior AI Engineer")
        self.assertTrue(job.is_remote)

    def test_pii_masking_infrastructure(self):
        """Infrastructure Layer: Verify zero-trust privacy sanitization"""
        raw = "Contact Jane Doe at jane.doe@example.com or call (555) 987-6543."
        sanitized = self.rag.mask_pii(raw)
        self.assertNotIn("jane.doe@example.com", sanitized)
        self.assertIn("[EMAIL_REDACTED]", sanitized)
        self.assertNotIn("(555) 987-6543", sanitized)
        self.assertIn("[PHONE_REDACTED]", sanitized)

    def test_match_cv_to_jobs_use_case(self):
        """Application Layer: Verify MatchCVToJobsUseCase orchestration"""
        cv_text = "Senior Software Engineer with 7 years experience in Python, FastAPI, React, and RAG systems."
        candidate, jobs, results = self.match_use_case.execute(
            cv_text=cv_text,
            search_query="Python AI Engineer",
            portals=["LinkedIn", "Indeed"],
            privacy_mode=True
        )
        self.assertTrue(len(jobs) > 0)
        self.assertTrue(candidate.is_anonymized)
        self.assertIn(jobs[0].id, results)
        self.assertGreaterEqual(results[jobs[0].id].overall_score, 65)

    def test_generate_cover_letter_use_case(self):
        """Application Layer: Verify GenerateCoverLetterUseCase RAG grounding"""
        candidate = CandidateProfile(
            id="c1", full_name="Alex Vance", headline="Senior AI Engineer",
            email="alex@example.com", summary="Expert in Python & RAG",
            years_experience=7, seniority_level="Senior", skills=["Python", "FastAPI"]
        )
        job = JobListing(
            id="j1", title="Lead Python Architect", company="Apex AI",
            location="Remote", is_remote=True, salary_range="$170k",
            source_portal="LinkedIn", url="https://example.com",
            posted_date="Today", description="Lead Python systems"
        )
        letter = self.cover_letter_use_case.execute(candidate, job, tone="persuasive")
        self.assertIn("Apex AI", letter.content)
        self.assertIn("Lead Python Architect", letter.content)
        self.assertGreater(letter.word_count, 100)

if __name__ == "__main__":
    unittest.main()
