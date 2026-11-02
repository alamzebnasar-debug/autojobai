"""
Job Scrapers & Aggregators: Multi-portal connector for Global & Finnish Portals
Portals: RemoteOK, Arbeitnow, LinkedIn, Indeed, Duunitori (FI), Oikotie (FI), The Hub (Nordic FI), Työmarkkinatori (FI)
"""
from typing import List, Dict, Any
from infrastructure.job_scrapers import JobScraperImpl

class JobAggregator:
    def __init__(self):
        self.impl = JobScraperImpl()

    def aggregate_jobs(self, query: str = "", portals: List[str] = None) -> List[Dict[str, Any]]:
        listings = self.impl.fetch_jobs(query=query, portals=portals)
        return [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "isRemote": j.is_remote,
                "salaryRange": j.salary_range,
                "sourcePortal": j.source_portal,
                "url": j.url,
                "postedDate": j.posted_date,
                "description": j.description,
                "tags": j.tags,
                "requirements": j.requirements,
                "matchScore": j.match_score
            }
            for j in listings
        ]
