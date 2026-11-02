"""
Comprehensive Test Suite for AutoJobAI Pipeline
Run directly with: python -m unittest test_ai_pipeline.py
"""
import unittest
import sys
import os

# Add current directory and backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, '..', 'backend'))

from rag_engine import RAGEngine
from job_scrapers import JobAggregator
from langgraph_pipeline import LangGraphJobPipeline

class TestAutoJobAIPipeline(unittest.TestCase):
    def setUp(self):
        self.rag = RAGEngine(chunk_size=50, chunk_overlap=10)
        self.aggregator = JobAggregator()
        self.pipeline = LangGraphJobPipeline(self.rag, self.aggregator)

    def test_pii_masking_privacy(self):
        """Test zero-trust PII redaction of email, phone, and addresses"""
        raw_text = "John Doe, email john.doe@techcorp.com, phone (555) 123-4567, address 123 Main Street, Suite 400."
        masked = self.rag.mask_pii(raw_text)
        self.assertNotIn("john.doe@techcorp.com", masked)
        self.assertIn("[EMAIL_REDACTED]", masked)
        self.assertNotIn("(555) 123-4567", masked)
        self.assertIn("[PHONE_REDACTED]", masked)
        self.assertNotIn("123 Main Street", masked)
        self.assertIn("[ADDRESS_REDACTED]", masked)

    def test_rag_chunking(self):
        """Test document chunking with overlapping windows"""
        text = "word " * 150
        chunks = self.rag.chunk_document(text)
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(all(len(c.split()) <= 50 for c in chunks))

    def test_vector_similarity_computation(self):
        """Test cosine token similarity between requirements and CV"""
        query = "Python FastAPI LangGraph backend engineer"
        good_doc = "Experienced with Python, FastAPI, and LangGraph multi-agent systems."
        bad_doc = "Pastry chef specializing in sourdough bread and dessert catering."

        score_good = self.rag.compute_similarity(query, good_doc)
        score_bad = self.rag.compute_similarity(query, bad_doc)

        self.assertGreater(score_good, score_bad)
        self.assertGreater(score_good, 0.4)
        self.assertEqual(score_bad, 0.0)

    def test_job_aggregator_search_and_filter(self):
        """Test job aggregator query filtering and portal scoping"""
        jobs = self.aggregator.aggregate_jobs(query="Python", portals=["LinkedIn", "Indeed"])
        self.assertTrue(len(jobs) > 0)
        for j in jobs:
            self.assertIn(j["sourcePortal"], ["LinkedIn", "Indeed"])
            has_python = "python" in j["title"].lower() or any("python" in t.lower() for t in j["tags"])
            self.assertTrue(has_python)

    def test_langgraph_pipeline_state_execution(self):
        """Test complete StateGraph flow from ingestion to alert trigger"""
        input_data = {
            "raw_cv_text": "Alex Vance. Senior Python Developer with FastAPI, React, and LangGraph experience.",
            "privacy_mode": True,
            "search_query": "Python",
            "target_portals": ["LinkedIn", "RemoteOK"],
            "user_email": "vickycricketer@gmail.com",
            "min_match_threshold": 70
        }
        result = self.pipeline.run_pipeline(input_data)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(len(result["execution_trace"]) >= 5)
        self.assertTrue(len(result["matched_jobs"]) > 0)
        self.assertTrue(len(result["alerts_dispatched"]) > 0)

        top_job = result["matched_jobs"][0]
        self.assertIn("matchScore", top_job)
        self.assertGreaterEqual(top_job["matchScore"], 60)

if __name__ == '__main__':
    unittest.main()
