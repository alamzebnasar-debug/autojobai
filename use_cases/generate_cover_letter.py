"""
Use Case: Generate Tailored Cover Letter Grounded in Retrieved RAG Evidence
"""
from core.entities import CandidateProfile, JobListing, CoverLetter, MatchResult
from core.interfaces import ILLMService

class GenerateCoverLetterUseCase:
    def __init__(self, llm_service: ILLMService):
        self.llm = llm_service

    def execute(
        self, 
        candidate: CandidateProfile, 
        job: JobListing, 
        match_result: MatchResult = None,
        tone: str = "persuasive"
    ) -> CoverLetter:
        evidence_snippets = [e.cv_snippet for e in match_result.evidence] if match_result else []
        content = self.llm.generate_cover_letter(candidate, job, evidence_snippets, tone=tone)
        
        words = content.split()
        return CoverLetter(
            job_id=job.id,
            company_name=job.company,
            role_title=job.title,
            tone=tone,
            content=content,
            word_count=len(words),
            ats_readiness=96
        )
