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
            search_query="Python",
            portals=["Duunitori (FI)", "Jobicy (EU)", "RemoteOK"],
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

    def test_nordic_country_filtering_and_multi_industry(self):
        """Infrastructure Layer: Verify live Sweden, Norway, and Denmark scraping returns direct job-ad permalinks"""
        se_jobs = self.scraper.fetch_jobs(country="Sweden", portals=["Platsbanken SE", "TheHub (SE)"], verify_links_live=False)
        self.assertTrue(len(se_jobs) > 0)
        self.assertTrue(all(j.country == "Sweden" for j in se_jobs))

        no_jobs = self.scraper.fetch_jobs(country="Norway", portals=["Arbeidsplassen (NO)", "TheHub (NO)"], verify_links_live=False)
        self.assertTrue(len(no_jobs) > 0)
        self.assertTrue(all(j.country == "Norway" for j in no_jobs))

        dk_jobs = self.scraper.fetch_jobs(country="Denmark", portals=["Jobindex (DK)", "TheHub (DK)"], verify_links_live=False)
        self.assertTrue(len(dk_jobs) > 0)
        self.assertTrue(all(j.country == "Denmark" for j in dk_jobs))
        # Ensure Denmark links point to actual job ads (/vis-job/ or /jobs/), NEVER homepage https://www.jobindex.dk
        self.assertTrue(all(j.url.rstrip("/") != "https://www.jobindex.dk" for j in dk_jobs))

    def test_link_validator_agent_filters_fake_links(self):
        """Infrastructure Layer: Verify LinkValidatorAgent rejects fake domains AND generic portal homepages"""
        from infrastructure.link_validator import LinkValidatorAgent
        agent = LinkValidatorAgent()
        fake_job = JobListing(
            id="fake-1", title="Fake Role", company="Ghost Co", location="Stockholm",
            is_remote=False, salary_range="N/A", source_portal="Test",
            url="https://example.invalid/fake-job", posted_date="Today", description="Fake"
        )
        homepage_job = JobListing(
            id="home-1", title="Trustpilot Dev", company="Trustpilot", location="Copenhagen",
            is_remote=False, salary_range="N/A", source_portal="Jobindex (DK)",
            url="https://www.jobindex.dk/", posted_date="Today", description="Homepage only"
        )
        valid_job = JobListing(
            id="real-1", title="Real Role", company="Danish Co", location="Copenhagen",
            is_remote=False, salary_range="Competitive", source_portal="Jobindex (DK)",
            url="https://www.jobindex.dk/vis-job/h1718155", posted_date="Today", description="Direct job ad"
        )
        validated = agent.validate_jobs([fake_job, homepage_job, valid_job], verify_http=False)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0].id, "real-1")

    def test_tailored_cover_letters_differ_by_job_description(self):
        """Application Layer: Ensure cover letters adapt uniquely to each job description & domain"""
        cand = CandidateProfile(
            id="c2", full_name="Alex Vance", headline="Senior Specialist",
            email="alex@nordic.example", summary="Led C# .NET cloud systems and hospital operations KPIs.",
            years_experience=8, seniority_level="Senior",
            skills=["C#", ".NET", "Azure", "Healthcare", "Clinical Leadership", "Operations"]
        )
        job_fintech = JobListing(
            id="se-1", title="Senior AI & C#/.NET Cloud Engineer", company="Klarna",
            location="Stockholm, Sweden", is_remote=False, salary_range="75k SEK",
            source_portal="Blocket SE", url="https://www.klarna.com/careers", posted_date="Today",
            description="Architect high-throughput financial transaction pipelines using C# .NET 8 and Azure.",
            requirements=["7+ years C#/.NET", "Azure Cloud architecture"], tags=["C#", ".NET", "Azure"]
        )
        job_health = JobListing(
            id="se-2", title="Healthcare Service Operations Director", company="Karolinska Hospital",
            location="Stockholm, Sweden", is_remote=False, salary_range="85k SEK",
            source_portal="Blocket SE", url="https://www.karolinska.se", posted_date="Today",
            description="Lead clinical service operations and patient care quality modernization across departments.",
            requirements=["5+ years clinical leadership", "Operational excellence"], tags=["Healthcare", "Operations"]
        )
        letter_1 = self.cover_letter_use_case.execute(cand, job_fintech, tone="persuasive")
        letter_2 = self.cover_letter_use_case.execute(cand, job_health, tone="executive")
        self.assertNotEqual(letter_1.content, letter_2.content)
        self.assertIn("Azure Cloud architecture", letter_1.content)
        self.assertIn("clinical leadership", letter_2.content)
        self.assertNotIn("RAG pipelines", letter_2.content)

    def test_cover_letter_excludes_pii_and_binary_xml(self):
        """Privacy & Security: Cover letters must NEVER include candidate name, email, phone, or raw DOCX binary XML"""
        cand = CandidateProfile(
            id="c-pii",
            full_name="Vicky Sharma",
            headline="Senior Engineer",
            email="vicky.private@gmail.com",
            summary="PK!$L})[Content_Types].xml garbage from raw docx",
            years_experience=10,
            seniority_level="Senior",
            skills=["Python", "Azure", "Microservices"],
        )
        job = JobListing(
            id="j-pii",
            title="Senior Cloud Architect",
            company="Spotify",
            location="Stockholm, Sweden",
            is_remote=True,
            salary_range="80k SEK",
            source_portal="Indeed SE",
            url="https://www.spotifyjobs.com",
            posted_date="Today",
            description="Architect scalable cloud APIs in Python and Azure.",
            requirements=["Python & Azure", "Distributed systems"],
            tags=["Python", "Azure"],
        )
        letter = self.cover_letter_use_case.execute(cand, job, tone="persuasive")
        self.assertNotIn("Vicky", letter.content)
        self.assertNotIn("vicky.private@gmail.com", letter.content)
        self.assertNotIn("PK!", letter.content)
        self.assertNotIn("[Content_Types].xml", letter.content)
        self.assertTrue(letter.content.strip().endswith("Sincerely,"))

    def test_cv_header_name_and_glued_text_never_leak_into_cover_letter(self):
        """Privacy & Formatting: Personal header lines (real name, citizenship, LinkedIn/Portfolio/GitHub) must not leak into cover letters"""
        raw_cv = (
            "Johnathan ExampleName AI / ML Engineer Helsinki, Finland (Finnish Citizen), , , "
            "Linkedin, Portfolio, GitHub\n"
            "SUMMARY\n"
            "SeniorSoftwareEngineerwithadecadeofexperiencearchitectingrobustC#/.NETenterpriseapplications\n"
            "Led production cloud migrations across Azure and Python microservices for international financial clients."
        )
        candidate, jobs, results = self.match_use_case.execute(
            cv_text=raw_cv,
            search_query="Developer",
            country="Sweden",
            portals=["Platsbanken SE"],
            privacy_mode=True,
        )
        self.assertTrue(len(jobs) > 0)
        letter = self.cover_letter_use_case.execute(candidate, jobs[0], match_result=results.get(jobs[0].id))
        self.assertNotIn("Johnathan", letter.content)
        self.assertNotIn("ExampleName", letter.content)
        self.assertNotIn("Finnish Citizen", letter.content)
        self.assertNotIn("LinkedIn", letter.content)
        self.assertNotIn("SeniorSoftwareEngineerwithadecadeofexperience", letter.content)
        self.assertNotIn("Grounded in my relevant experience (", letter.content)

    def test_deep_tailored_interview_questions_multi_industry(self):
        """Interview Prep: Verify 8+ insightful job-specific questions + reverse questions tailored to each company & domain"""
        cand = CandidateProfile(
            id="c-prep", full_name="Real Private Name", headline="Senior Specialist",
            email="private@example.com", summary="8 years leading backend systems and healthcare analytics.",
            years_experience=8, seniority_level="Senior",
            skills=["Python", "FastAPI", "Azure", "Clinical Operations", "KPIs"]
        )
        job_tech = JobListing(
            id="t1", title="Lead Platform Engineer", company="Klarna",
            location="Stockholm, Sweden", is_remote=False, salary_range="80k SEK",
            source_portal="Blocket SE", url="https://www.klarna.com/careers", posted_date="Today",
            description="Scale payment settlement APIs with strict p99 latency targets and automated observability.",
            requirements=["Distributed FastAPI systems", "Kubernetes SLOs"], tags=["Python", "FastAPI", "Kubernetes"]
        )
        job_health = JobListing(
            id="h1", title="Clinical Operations Manager", company="Karolinska Hospital",
            location="Stockholm, Sweden", is_remote=False, salary_range="85k SEK",
            source_portal="Blocket SE", url="https://www.karolinska.se", posted_date="Today",
            description="Modernize surgical ward triage workflows and cross-department patient care governance.",
            requirements=["Clinical leadership", "Regulatory quality auditing"], tags=["Healthcare", "Operations"]
        )
        prep_tech = self.llm.generate_interview_questions(cand, job_tech, matched_skills=["Python", "FastAPI"], missing_skills=["Kubernetes"], use_llm=False)
        prep_health = self.llm.generate_interview_questions(cand, job_health, matched_skills=["Clinical Operations"], missing_skills=["Regulatory auditing"], use_llm=False)

        self.assertGreaterEqual(len(prep_tech["questions"]), 8)
        self.assertGreaterEqual(len(prep_health["questions"]), 8)
        self.assertEqual(len(prep_tech["questions_to_ask"]), 3)
        self.assertNotEqual(prep_tech["questions"][0]["question"], prep_health["questions"][0]["question"])
        self.assertTrue(any("Klarna" in q["question"] for q in prep_tech["questions"]))
        self.assertTrue(any("Karolinska Hospital" in q["question"] for q in prep_health["questions"]))
        self.assertTrue(all("Real Private Name" not in q["question"] and "private@example.com" not in q["question"] for q in prep_tech["questions"]))

    def test_all_country_aggregation_completes_cleanly(self):
        """Performance & Coverage: Fetching across Country='All' aggregates live SE, NO, DK, FI jobs cleanly"""
        jobs = self.scraper.fetch_jobs(
            query="",
            country="All",
            portals=["Platsbanken SE", "Arbeidsplassen (NO)", "Jobindex (DK)", "Duunitori (FI)"],
            verify_links_live=False,
        )
        countries = {j.country for j in jobs}
        self.assertIn("Sweden", countries)
        self.assertIn("Norway", countries)
        self.assertIn("Denmark", countries)
        self.assertIn("Finland", countries)

    def test_cover_letter_includes_technical_skills_and_experience_bullets(self):
        """Quality: Cover letter must include candidate's real technical skills and bulleted experience without false substring matches"""
        raw_cv = (
            "Jane Developer\n"
            "SUMMARY\n"
            "Enterprise software engineer with 9 years building distributed backend systems.\n"
            "SKILLS: C#, .NET, Python, Azure, FastAPI, Docker, RAG\n"
            "EXPERIENCE\n"
            "• Architected high-throughput payment APIs using C# .NET and Azure Kubernetes Service reducing latency by 45%\n"
            "• Built production RAG pipelines with Python and FastAPI for internal knowledge retrieval"
        )
        candidate, jobs, results = self.match_use_case.execute(
            cv_text=raw_cv,
            search_query="Developer",
            country="Sweden",
            portals=["Platsbanken SE"],
            privacy_mode=True,
        )
        self.assertNotIn("ERP", candidate.skills)  # 'enterprise' must NOT trigger 'ERP'
        self.assertIn("C#", candidate.skills)
        self.assertIn(".NET", candidate.skills)
        self.assertIn("Python", candidate.skills)
        self.assertEqual(candidate.years_experience, 9)

        letter = self.cover_letter_use_case.execute(
            candidate, jobs[0], match_result=results.get(jobs[0].id), use_llm=False
        )
        self.assertIn("C#", letter.content)
        self.assertIn("Python", letter.content)
        self.assertIn("9+", letter.content)
        self.assertTrue(
            "Architected high-throughput payment APIs" in letter.content
            or "Built production RAG pipelines" in letter.content
        )


if __name__ == "__main__":
    unittest.main()
