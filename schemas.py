"""
Pydantic Schemas for AutoJobAI Python Backend
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

class UserAuthSchema(BaseModel):
    email: EmailStr
    password: Optional[str] = "secret"
    name: Optional[str] = "Job Seeker"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str

class SkillsBreakdown(BaseModel):
    coreTechnical: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    cloudAndDevOps: List[str] = Field(default_factory=list)
    aiAndData: List[str] = Field(default_factory=list)
    softSkills: List[str] = Field(default_factory=list)

class ExperienceItem(BaseModel):
    company: str
    role: str
    duration: str
    highlights: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

class EducationItem(BaseModel):
    institution: str
    degree: str
    field: str
    year: Optional[str] = None

class ParsedCVSchema(BaseModel):
    id: str
    fullName: str
    headline: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: str
    yearsOfExperience: int
    seniorityLevel: str
    skills: SkillsBreakdown
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    targetRoles: List[str] = Field(default_factory=list)
    rawText: str = ""
    isAnonymized: bool = False

class JobListingSchema(BaseModel):
    id: str
    title: str
    company: str
    location: str
    isRemote: bool
    employmentType: str = "Full-time"
    salaryRange: Optional[str] = None
    sourcePortal: str
    url: str
    postedDate: str
    description: str
    requirements: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    matchScore: Optional[int] = None
    status: str = "discovered"

class RAGEvidence(BaseModel):
    cvSnippet: str
    jobRequirement: str
    relevance: str

class FitAnalysisSchema(BaseModel):
    overallScore: int
    technicalFit: int
    experienceFit: int
    domainFit: int
    educationFit: int
    matchedSkills: List[str]
    missingSkills: List[str]
    strengths: List[str]
    concernsOrGaps: List[str]
    recommendations: List[str]
    interviewTalkingPoints: List[str]
    ragEvidence: List[RAGEvidence] = Field(default_factory=list)

class CoverLetterRequest(BaseModel):
    jobId: str
    tone: str = "persuasive"
    specificFocus: Optional[str] = None

class CoverLetterResponse(BaseModel):
    id: str
    jobId: str
    jobTitle: str
    companyName: str
    tone: str
    content: str
    atsReadinessScore: int
    wordCount: int

class NotificationSettingsSchema(BaseModel):
    email: EmailStr
    enabled: bool = True
    frequency: str = "daily"
    preferredTime: str = "08:00 AM"
    minMatchScore: int = 75
    portalSources: List[str] = Field(default_factory=lambda: ["LinkedIn", "RemoteOK", "Indeed", "Arbeitnow"])
