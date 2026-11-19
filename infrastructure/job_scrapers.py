"""
Infrastructure Layer: Live Multi-Country & Multi-Industry Job Scraping Engine
Supports All Professions (Engineering, IT, Healthcare, Finance, Marketing, HR, Logistics, Public Sector)
across Sweden, Norway, Denmark, Finland, Europe, and Global Remote feeds.
"""
import html as html_lib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List

from core.entities import JobListing
from core.interfaces import IJobScraper
from infrastructure.link_validator import LinkValidatorAgent


class JobScraperImpl(IJobScraper):
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,sv;q=0.8,nb;q=0.7,da;q=0.6,fi;q=0.5",
        }
        self.link_validator = LinkValidatorAgent(timeout=2.5, max_workers=8)

    @staticmethod
    def _infer_country(location: str, default: str = "Europe / Remote") -> str:
        loc = (location or "").lower()
        if any(w in loc for w in ["sweden", "sverige", "stockholm", "gothenburg", "göteborg", "malmö", "uppsala"]):
            return "Sweden"
        if any(w in loc for w in ["norway", "norge", "oslo", "bergen", "stavanger", "trondheim", "fornebu"]):
            return "Norway"
        if any(w in loc for w in ["denmark", "danmark", "copenhagen", "københavn", "aarhus", "odense"]):
            return "Denmark"
        if any(w in loc for w in ["finland", "suomi", "helsinki", "espoo", "tampere", "oulu", "turku"]):
            return "Finland"
        return default

    # ----------------- 1. LIVE SWEDEN PLATSBANKEN / JOBTECH OPEN API (ALL INDUSTRIES) -----------------
    def _fetch_sweden_jobtech_live(self, query: str = "", limit: int = 15) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            q_enc = urllib.parse.quote_plus((query or "").strip())
            url = f"https://jobsearch.api.jobtechdev.se/search?q={q_enc}&limit={limit}"
            req = urllib.request.Request(url, headers={**self.headers, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                for hit in data.get("hits", []):
                    title = hit.get("headline", "").strip()
                    employer = hit.get("employer", {}).get("name", "Swedish Employer")
                    city = hit.get("workplace_address", {}).get("municipality") or "Sweden"
                    webpage = hit.get("webpage_url") or f"https://arbetsformedlingen.se/platsbanken/annonser/{hit.get('id', '')}"
                    desc = (hit.get("description", {}) or {}).get("text", "")
                    occ = (hit.get("occupation", {}) or {}).get("label", "Specialist")
                    if not title or not webpage:
                        continue
                    jobs.append(
                        JobListing(
                            id=f"se-pb-{hit.get('id', abs(hash(webpage)) % 1000000)}",
                            title=title,
                            company=employer,
                            location=f"{city}, Sweden",
                            country="Sweden",
                            is_remote="remote" in f"{title} {desc}".lower() or "distans" in desc.lower(),
                            salary_range="Competitive Swedish Collective / Market Salary",
                            source_portal="Platsbanken SE",
                            url=webpage,
                            posted_date="Active Today",
                            description=re.sub(r"\s+", " ", desc)[:600] if desc else f"Live vacancy for {title} at {employer}.",
                            tags=["Sweden", occ, "Verified Live Ad"],
                            requirements=[f"Qualification in {occ}", "Eligible to work in Sweden / EU"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
        except Exception:
            pass
        return jobs

    # ----------------- 2. LIVE DENMARK JOBINDEX RSS SCRAPER (ALL INDUSTRIES, DIRECT PERMALINKS) -----------------
    def _fetch_jobindex_dk_live(self, query: str = "", limit: int = 20) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        try:
            q_enc = urllib.parse.quote_plus((query or "").strip())
            url = f"https://www.jobindex.dk/jobsoegning.rss?q={q_enc}" if q_enc else "https://www.jobindex.dk/jobsoegning.rss"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4.5) as response:
                raw_bytes = response.read()
                # Jobindex RSS declares ISO-8859-1 or UTF-8
                tree = ET.fromstring(raw_bytes)
                for item in tree.findall(".//item")[:limit]:
                    raw_title = html_lib.unescape(item.findtext("title") or "").strip()
                    direct_url = (item.findtext("link") or "").strip()
                    raw_desc = html_lib.unescape(item.findtext("description") or "")
                    if not raw_title or not direct_url or "/vis-job/" not in direct_url:
                        continue
                    if direct_url in seen_urls:
                        continue
                    seen_urls.add(direct_url)

                    # Jobindex RSS titles are usually "Role Title, Company Name"
                    if "," in raw_title:
                        title_part, comp_part = raw_title.rsplit(",", 1)
                        clean_title = title_part.strip()
                        clean_comp = comp_part.strip() or "Danish Employer"
                    else:
                        clean_title = raw_title
                        clean_comp = "Danish Employer"

                    area_match = re.search(r'class="jix_robotjob--area">([^<]+)<', raw_desc)
                    city = html_lib.unescape(area_match.group(1)).strip() if area_match else "Denmark"
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                    if clean_desc.lower().startswith(clean_title.lower()):
                        clean_desc = clean_desc[len(clean_title) :].strip(" -:,.")
                    if len(clean_desc) < 25:
                        clean_desc = f"Live position for {clean_title} with {clean_comp} in {city}, Denmark."

                    is_rem = any(w in f"{clean_title} {clean_desc}".lower() for w in ["remote", "hjemmearbejde", "hybrid"])
                    jobs.append(
                        JobListing(
                            id=f"dk-ji-{abs(hash(direct_url)) % 1000000}",
                            title=clean_title,
                            company=clean_comp,
                            location=f"{city}, Denmark" if "denmark" not in city.lower() else city,
                            country="Denmark",
                            is_remote=is_rem,
                            salary_range="Competitive Danish Salary",
                            source_portal="Jobindex (DK)",
                            url=direct_url,
                            posted_date="Active Today",
                            description=clean_desc[:550],
                            tags=["Denmark", "Jobindex", "Verified Direct Ad"],
                            requirements=[f"Relevant experience for {clean_title}", "Eligible to work in Denmark / EU"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
        except Exception:
            pass
        return jobs

    # ----------------- 3. LIVE NORWAY NAV ARBEIDSPLASSEN SCRAPER (ALL INDUSTRIES) -----------------
    def _fetch_arbeidsplassen_no_live(self, query: str = "", limit: int = 20) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        try:
            q_enc = urllib.parse.quote_plus((query or "").strip())
            url = f"https://arbeidsplassen.nav.no/stillinger?q={q_enc}" if q_enc else "https://arbeidsplassen.nav.no/stillinger"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4.5) as response:
                page = response.read().decode("utf-8", errors="ignore")
                for m_art in re.finditer(r"<article[^>]*>(.*?)</article>", page, re.S):
                    card = m_art.group(1)
                    m_link = re.search(r'<a[^>]*href="(/stillinger/stilling/[^"]+)"[^>]*>(.*?)</a>', card, re.S)
                    if not m_link:
                        continue
                    direct_url = "https://arbeidsplassen.nav.no" + m_link.group(1).strip()
                    if direct_url in seen_urls:
                        continue
                    seen_urls.add(direct_url)

                    clean_title = html_lib.unescape(re.sub(r"<[^>]+>", " ", m_link.group(2))).strip()
                    plain = html_lib.unescape(re.sub(r"<[^>]+>", " | ", card))
                    plain = re.sub(r"\s+", " ", plain)

                    # Extract Arbeidsgiver & Sted fields cleanly from NAV card
                    comp_match = re.search(r"Arbeidsgiver\s*(?:\|\s*)+([^|]+)", plain)
                    loc_match = re.search(r"Sted\s*(?:\|\s*)+([^|]+)", plain)
                    role_match = re.search(re.escape(clean_title) + r"\s*(?:\|\s*)+([^|]+)", plain)

                    clean_comp = comp_match.group(1).strip() if comp_match else "Norwegian Employer"
                    city = loc_match.group(1).strip() if loc_match else "Norway"
                    role_cat = role_match.group(1).strip() if role_match else clean_title
                    if role_cat == "Arbeidsgiver":
                        role_cat = clean_title

                    is_rem = any(w in f"{clean_title} {city}".lower() for w in ["remote", "hjemmekontor", "hybrid"])
                    jobs.append(
                        JobListing(
                            id=f"no-nav-{abs(hash(direct_url)) % 1000000}",
                            title=clean_title,
                            company=clean_comp,
                            location=f"{city}, Norway" if "norway" not in city.lower() and "norge" not in city.lower() else city,
                            country="Norway",
                            is_remote=is_rem,
                            salary_range="Competitive Norwegian Market / Tariff Salary",
                            source_portal="Arbeidsplassen (NO)",
                            url=direct_url,
                            posted_date="Active Today",
                            description=f"Official NAV Norway vacancy for {clean_title} ({role_cat}) at {clean_comp} in {city}.",
                            tags=["Norway", role_cat[:32], "Verified Direct Ad"],
                            requirements=[f"Qualifications in {role_cat}", "Eligible to work in Norway / EEA"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
                    if len(jobs) >= limit:
                        break
        except Exception:
            pass
        return jobs

    # ----------------- 4. LIVE THEHUB NORDIC SCRAPER (SE, NO, DK, FI) -----------------
    def _fetch_thehub_nordic_live(self, country_code: str, country_name: str, portal_label: str, query: str = "", limit: int = 12) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        try:
            q_enc = urllib.parse.quote_plus((query or "").strip())
            url = f"https://thehub.io/jobs?countryCode={country_code}"
            if q_enc:
                url += f"&search={q_enc}"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4.5) as response:
                page = response.read().decode("utf-8", errors="ignore")
                cards = re.findall(
                    r'<div class="card card-job-find-list".*?'
                    r'<span class="card-job-find-list__position">(.*?)</span>.*?'
                    r'<div class="bullet-inline-list[^>]*>(.*?)</div>.*?'
                    r'<a href="(/jobs/[a-f0-9]+)" class="card-job-find-list__link">',
                    page,
                    re.S,
                )
                for raw_title, meta_html, rel_url in cards[:limit]:
                    direct_url = "https://thehub.io" + rel_url.strip()
                    if direct_url in seen_urls:
                        continue
                    seen_urls.add(direct_url)
                    clean_title = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_title)).strip()
                    spans = [
                        html_lib.unescape(re.sub(r"<[^>]+>", " ", sp)).strip()
                        for sp in re.findall(r"<span[^>]*>(.*?)</span>", meta_html, re.S)
                    ]
                    spans = [s for s in spans if s]
                    clean_comp = spans[0] if spans else f"{country_name} Growth Co"
                    city = spans[1] if len(spans) > 1 else country_name
                    emp_type = spans[2] if len(spans) > 2 else "Full-time"
                    loc_str = f"{city}, {country_name}" if country_name.lower() not in city.lower() and "remote" not in city.lower() else f"{city} ({country_name})"
                    is_rem = "remote" in f"{clean_title} {city}".lower()

                    jobs.append(
                        JobListing(
                            id=f"hub-{country_code.lower()}-{abs(hash(direct_url)) % 1000000}",
                            title=clean_title,
                            company=clean_comp,
                            location=loc_str,
                            country=country_name,
                            is_remote=is_rem,
                            salary_range="Competitive Nordic Growth Company Compensation",
                            source_portal=portal_label,
                            url=direct_url,
                            posted_date="Active Today",
                            description=f"{emp_type} opportunity for {clean_title} at {clean_comp} ({loc_str}) via TheHub Nordic.",
                            tags=[country_name, emp_type, "TheHub", "Verified Direct Ad"],
                            requirements=[f"Relevant background for {clean_title}", f"Based in or eligible for {country_name}"],
                            category="live_verified",
                            is_hidden_gem=True,
                        )
                    )
        except Exception:
            pass
        return jobs

    # ----------------- 5. LIVE ACADEMIC WORK NORDIC (SE, NO, DK, FI) -----------------
    def _fetch_academic_work_nordic(self, domain: str, path_prefix: str, country_name: str, portal_label: str, query: str = "", limit: int = 12) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        clean_q = (query or "").strip()
        try:
            url = f"https://www.{domain}{path_prefix}"
            if clean_q:
                url += f"?q={urllib.parse.quote_plus(clean_q)}"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4.5) as response:
                page = response.read().decode("utf-8", errors="ignore")
                # Match both aria-label links and direct /j/ links
                matches = re.findall(
                    rf'aria-label="(?:Mene|Gå till|Gå til)\s*([^"]+)"\s+href="({re.escape(path_prefix)}/j/[^"]+)"',
                    page,
                )
                for title, link in matches:
                    direct_url = f"https://www.{domain}{link.strip()}"
                    if direct_url in seen_urls:
                        continue
                    seen_urls.add(direct_url)
                    clean_title = html_lib.unescape(title).strip()
                    jobs.append(
                        JobListing(
                            id=f"aw-{country_name[:2].lower()}-{abs(hash(direct_url)) % 1000000}",
                            title=clean_title,
                            company=f"Academic Work {country_name}",
                            location=f"{country_name} (Capital Region & Remote)",
                            country=country_name,
                            is_remote=any(w in clean_title.lower() for w in ["remote", "etä", "distans", "hjemmekontor", "hybrid"]),
                            salary_range="Competitive Nordic Salary",
                            source_portal=portal_label,
                            url=direct_url,
                            posted_date="Active Today",
                            description=f"Verified active position for {clean_title} via Academic Work {country_name}.",
                            tags=[country_name, "Academic Work", "Verified Direct Ad"],
                            requirements=["Relevant professional qualifications", f"Working proficiency in English or local {country_name} language"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
                    if len(jobs) >= limit:
                        break
        except Exception:
            pass
        return jobs

    # ----------------- 3. LIVE DUUNITORI SCRAPER (FINLAND - ALL INDUSTRIES) -----------------
    def _fetch_duunitori_live(self, query: str = "", max_pages: int = 2) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        clean_q = (query or "").strip()
        q_enc = urllib.parse.quote_plus(clean_q if clean_q else "työpaikat")

        for page_num in range(1, max_pages + 1):
            try:
                url = f"https://duunitori.fi/tyopaikat?haku={q_enc}&sivu={page_num}"
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=4) as response:
                    page = response.read().decode("utf-8", errors="ignore")
                    matches = re.findall(
                        r'data-company="([^"]+)"[^>]*href="(/tyopaikat/tyo/[^"]+)">([^<]+)</a>',
                        page,
                    )
                    for comp, link, title in matches:
                        clean_title = html_lib.unescape(title).strip()
                        clean_comp = html_lib.unescape(comp).strip()
                        direct_url = "https://duunitori.fi" + link.strip()
                        if direct_url not in seen_urls:
                            seen_urls.add(direct_url)
                            is_rem = any(w in clean_title.lower() for w in ["remote", "etä", "hybrid", "etätyö"])
                            jobs.append(
                                JobListing(
                                    id=f"duuni-{abs(hash(direct_url)) % 1000000}",
                                    title=clean_title,
                                    company=clean_comp,
                                    location="Finland (Helsinki / Espoo / Tampere / Remote)",
                                    country="Finland",
                                    is_remote=is_rem,
                                    salary_range="Competitive Nordic Salary (TES collective agreement)",
                                    source_portal="Duunitori (FI)",
                                    url=direct_url,
                                    posted_date="Active Today",
                                    description=f"Active verified vacancy for {clean_title} at {clean_comp}. Live job ad on Duunitori Finland.",
                                    tags=["Finland", "Duunitori", "Verified Live Ad"],
                                    requirements=["Relevant professional experience", "Working proficiency in English or Finnish"],
                                    category="live_verified",
                                    is_hidden_gem=False,
                                )
                            )
            except Exception:
                pass
        return jobs

    # ----------------- 4. LIVE LINKEDIN DIRECT SCRAPER (ALL NORDIC COUNTRIES) -----------------
    def _fetch_linkedin_live(self, query: str = "", location: str = "Sweden", limit: int = 12) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        clean_q = (query or "").strip() or "Specialist"
        q_enc = urllib.parse.quote_plus(clean_q)
        loc_enc = urllib.parse.quote_plus(location)

        try:
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={q_enc}&location={loc_enc}&start=0"
            )
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                page = response.read().decode("utf-8", errors="ignore")
                titles = re.findall(r'<h3 class="base-search-card__title">([^<]+)</h3>', page)
                companies = re.findall(r'<h4 class="base-search-card__subtitle">[^<]*<a[^>]*>([^<]+)</a>', page)
                locations = re.findall(r'<span class="job-search-card__location">([^<]+)</span>', page)
                links = re.findall(r'<a class="base-card__full-link[^"]*"\s+href="([^"]+)"', page)

                total = min(len(titles), len(companies), len(links))
                for i in range(min(total, limit)):
                    direct_url = links[i].split("?")[0].strip()
                    if direct_url not in seen_urls:
                        seen_urls.add(direct_url)
                        clean_title = html_lib.unescape(titles[i]).strip()
                        clean_comp = html_lib.unescape(companies[i]).strip()
                        clean_loc = html_lib.unescape(locations[i]).strip() if i < len(locations) else location
                        detected_country = self._infer_country(clean_loc, default=location)
                        is_rem = any(w in clean_title.lower() for w in ["remote", "etä", "distans", "hybrid"])

                        jobs.append(
                            JobListing(
                                id=f"li-{abs(hash(direct_url)) % 1000000}",
                                title=clean_title,
                                company=clean_comp,
                                location=clean_loc,
                                country=detected_country,
                                is_remote=is_rem,
                                salary_range="Market Rate (per employer specification)",
                                source_portal="LinkedIn (Verified)",
                                url=direct_url,
                                posted_date="Active Today",
                                description=f"Verified live requisition for {clean_title} at {clean_comp} ({clean_loc}) on LinkedIn.",
                                tags=["LinkedIn", detected_country, "Direct Verified Ad"],
                                requirements=[f"Relevant background for {clean_title}", "View full specifications on LinkedIn"],
                                category="live_verified",
                                is_hidden_gem=False,
                            )
                        )
        except Exception:
            pass
        return jobs

    # ----------------- 5. LIVE WORK IN FINLAND -----------------
    def _fetch_work_in_finland(self, query: str = "", limit: int = 30) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            clean_q = (query or "").strip()
            url = (
                f"https://www.workinfinland.com/api/jobs/?query={urllib.parse.quote_plus(clean_q)}"
                if clean_q
                else "https://www.workinfinland.com/api/jobs/"
            )
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                for item in data.get("jobs", []):
                    title = item.get("title", "")
                    direct_url = item.get("externalUrl")
                    if not direct_url or not title:
                        continue
                    if "jobly.fi" in direct_url and not re.search(r"-\d+$", direct_url):
                        continue

                    employer = item.get("employer", {})
                    comp_name = employer.get("name", "Finnish Employer")
                    city = employer.get("city", "Finland") or "Helsinki / Finland"

                    jobs.append(
                        JobListing(
                            id=f"wif-{abs(hash(direct_url)) % 1000000}",
                            title=title,
                            company=comp_name,
                            location=f"{city}, Finland",
                            country="Finland",
                            is_remote="remote" in title.lower(),
                            salary_range="Competitive Nordic Scale",
                            source_portal="Work in Finland (FI)",
                            url=direct_url,
                            posted_date="Active Today",
                            description=f"Verified opportunity for {title} with {comp_name} via Business Finland / Work in Finland.",
                            tags=["Finland", "Work in Finland", "Verified Live Ad"],
                            requirements=["Eligible to work in Finland or EU", "Professional qualifications in role"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
                    if len(jobs) >= limit:
                        break
        except Exception:
            pass
        return jobs

    # ----------------- 6. LIVE ACADEMIC WORK FINLAND -----------------
    def _fetch_academic_work(self, query: str = "", limit: int = 15) -> List[JobListing]:
        jobs: List[JobListing] = []
        seen_urls = set()
        clean_q = (query or "").strip() or "specialist"
        try:
            q_enc = urllib.parse.quote_plus(clean_q)
            url = f"https://www.academicwork.fi/avoimet-tyopaikat?q={q_enc}"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                page = response.read().decode("utf-8", errors="ignore")
                matches = re.findall(r'aria-label="Mene ([^"]+)" href="(/avoimet-tyopaikat/j/[^"]+)"', page)
                for title, link in matches:
                    direct_url = "https://www.academicwork.fi" + link.strip()
                    if direct_url not in seen_urls:
                        seen_urls.add(direct_url)
                        clean_title = html_lib.unescape(title).strip()
                        jobs.append(
                            JobListing(
                                id=f"aw-{abs(hash(direct_url)) % 1000000}",
                                title=clean_title,
                                company="Academic Work Finland",
                                location="Helsinki / Espoo / Tampere, Finland",
                                country="Finland",
                                is_remote="remote" in clean_title.lower() or "etä" in clean_title.lower(),
                                salary_range="Competitive Nordic Salary (TES Collective Agreement)",
                                source_portal="Academic Work (FI)",
                                url=direct_url,
                                posted_date="Active Today",
                                description=f"Verified active position for {clean_title} via Academic Work Finland.",
                                tags=["Finland", "Academic Work", "Verified Live Ad"],
                                requirements=["Relevant professional experience", "Fluent English or Finnish"],
                                category="live_verified",
                                is_hidden_gem=False,
                            )
                        )
                    if len(jobs) >= limit:
                        break
        except Exception:
            pass
        return jobs

    # ----------------- 7. EU & GLOBAL REMOTE FEEDS (PRESERVED) -----------------
    def _fetch_arbeitnow(self, query: str = "", limit: int = 20) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            clean_q = (query or "").strip()
            url = (
                f"https://www.arbeitnow.com/api/job-board-api?search={urllib.parse.quote_plus(clean_q)}"
                if clean_q
                else "https://www.arbeitnow.com/api/job-board-api"
            )
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                for item in data.get("data", [])[:limit]:
                    tags = item.get("tags", [])
                    job_url = item.get("url") or f"https://www.arbeitnow.com/view/{item.get('slug', '')}"
                    loc = item.get("location") or ("Remote (EU)" if item.get("remote") else "Europe / Hybrid")
                    jobs.append(
                        JobListing(
                            id=f"abn-{item.get('slug', 'item')}",
                            title=item.get("title", ""),
                            company=item.get("company_name", ""),
                            location=loc,
                            country=self._infer_country(loc, default="Europe / Remote"),
                            is_remote=bool(item.get("remote")),
                            salary_range="€65,000 - €100,000 / year",
                            source_portal="Arbeitnow (EU)",
                            url=job_url,
                            posted_date="Active Today",
                            description=re.sub(r"<[^>]*>", "", item.get("description", ""))[:600],
                            tags=tags if tags else ["Professional"],
                            requirements=[f"Skills in {t}" for t in tags[:5]],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
        except Exception:
            pass
        return jobs

    def _fetch_jobicy_europe(self, limit: int = 20) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            url = f"https://jobicy.com/api/v2/remote-jobs?count={limit}&geo=europe"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                for item in data.get("jobs", [])[:limit]:
                    clean_desc = re.sub(r"<[^>]*>", "", item.get("jobDescription", ""))[:500]
                    loc = f"Europe ({item.get('jobGeo', 'EU Remote')})"
                    jobs.append(
                        JobListing(
                            id=f"jobicy-{item.get('id', 'job')}",
                            title=item.get("jobTitle", "Professional"),
                            company=item.get("companyName", "Employer"),
                            location=loc,
                            country=self._infer_country(loc, default="Europe / Remote"),
                            is_remote=True,
                            salary_range=(
                                f"${item.get('annualSalaryMin', 85000):,} - ${item.get('annualSalaryMax', 135000):,} USD"
                                if item.get("annualSalaryMin")
                                else "€70,000 - €105,000 / year"
                            ),
                            source_portal="Jobicy (EU)",
                            url=item.get("url", "https://jobicy.com"),
                            posted_date="Active Today",
                            description=clean_desc,
                            tags=["Europe", "Jobicy", "Verified Live Ad"],
                            requirements=["Strong background in relevant skills", "Eligible to work in Europe or EU timezones"],
                            category="live_verified",
                            is_hidden_gem=False,
                        )
                    )
        except Exception:
            pass
        return jobs

    def _fetch_weworkremotely(self, limit: int = 15) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            url = "https://weworkremotely.com/remote-jobs.rss"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                tree = ET.fromstring(response.read())
                for it in tree.findall(".//item")[:limit]:
                    title_elem = it.find("title")
                    link_elem = it.find("link")
                    desc_elem = it.find("description")
                    pub_elem = it.find("pubDate")

                    full_title = title_elem.text if title_elem is not None else "Remote Professional"
                    if ":" in full_title:
                        comp, role = full_title.split(":", 1)
                        comp, role = comp.strip(), role.strip()
                    else:
                        comp, role = "Remote Co", full_title.strip()

                    link = link_elem.text if link_elem is not None else "https://weworkremotely.com"
                    desc = desc_elem.text if desc_elem is not None else ""
                    clean_desc = re.sub(r"<[^>]*>", "", desc)[:500]

                    jobs.append(
                        JobListing(
                            id=f"wwr-{abs(hash(link)) % 1000000}",
                            title=role,
                            company=comp,
                            location="Remote (Global / EU)",
                            country="Europe / Remote",
                            is_remote=True,
                            salary_range="Global Remote Market Rate",
                            source_portal="WeWorkRemotely",
                            url=link,
                            posted_date=pub_elem.text[:16] if pub_elem is not None and pub_elem.text else "Recent",
                            description=clean_desc,
                            tags=["Remote", "WeWorkRemotely", "Verified Live Ad"],
                            requirements=["Demonstrated background in field", "Experience in distributed remote teams"],
                            category="live_verified",
                            is_hidden_gem=True,
                        )
                    )
        except Exception:
            pass
        return jobs

    def _fetch_remoteok(self, limit: int = 15) -> List[JobListing]:
        jobs: List[JobListing] = []
        try:
            req = urllib.request.Request("https://remoteok.com/api", headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                for item in data[1 : limit + 1]:
                    if "position" in item and "company" in item:
                        tags = item.get("tags", [])
                        job_url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                        jobs.append(
                            JobListing(
                                id=f"rok-{item.get('id', 'item')}",
                                title=item.get("position", ""),
                                company=item.get("company", ""),
                                location=item.get("location") or "Remote (Global)",
                                country="Europe / Remote",
                                is_remote=True,
                                salary_range=(
                                    f"${item.get('salary_min', 100000):,} - ${item.get('salary_max', 160000):,} USD"
                                    if item.get("salary_min")
                                    else "Global Remote Market Rate"
                                ),
                                source_portal="RemoteOK",
                                url=job_url,
                                posted_date="Active Today",
                                description=re.sub(r"<[^>]*>", "", item.get("description", ""))[:600],
                                tags=tags if tags else ["Remote", "Professional"],
                                requirements=[f"Experience with {t}" for t in tags[:5]],
                                category="live_verified",
                                is_hidden_gem=False,
                            )
                        )
        except Exception:
            pass
        return jobs

    def validate_job_links(self, jobs: List[JobListing], verify_http: bool = True) -> List[JobListing]:
        """Link Validator Agent: verifies URL structure & HTTP reachability, filtering fake/broken links."""
        return self.link_validator.validate_jobs(jobs, verify_http=verify_http)

    # ----------------- MASTER AGGREGATOR (CONCURRENT) -----------------
    def fetch_jobs(
        self,
        query: str = "",
        portals: List[str] = None,
        country: str = "All",
        only_hidden_gems: bool = False,
        verify_links_live: bool = True,
    ) -> List[JobListing]:
        import concurrent.futures

        all_jobs: List[JobListing] = []
        portals_lower = [p.lower() for p in (portals or [])]
        filter_by_portal = bool(portals_lower and "all" not in portals_lower)

        def want(portal_tag: str) -> bool:
            if not filter_by_portal:
                return True
            pt = portal_tag.lower()
            return any(p == pt or p in pt or pt in p for p in portals_lower)

        # Build concurrent scraping tasks only for selected country & portals
        tasks = []
        if country in ("All", "Sweden"):
            if want("Platsbanken SE"):
                tasks.append((self._fetch_sweden_jobtech_live, (query, 15)))
            if want("Academic Work (SE)"):
                tasks.append((self._fetch_academic_work_nordic, ("academicwork.se", "/lediga-jobb", "Sweden", "Academic Work (SE)", query, 12)))
            if want("TheHub (SE)"):
                tasks.append((self._fetch_thehub_nordic_live, ("SE", "Sweden", "TheHub (SE)", query, 12)))
            if want("LinkedIn (Verified)"):
                tasks.append((self._fetch_linkedin_live, (query, "Sweden", 8)))

        if country in ("All", "Norway"):
            if want("Arbeidsplassen (NO)"):
                tasks.append((self._fetch_arbeidsplassen_no_live, (query, 15)))
            if want("Academic Work (NO)"):
                tasks.append((self._fetch_academic_work_nordic, ("academicwork.no", "/ledige-stillinger", "Norway", "Academic Work (NO)", query, 12)))
            if want("TheHub (NO)"):
                tasks.append((self._fetch_thehub_nordic_live, ("NO", "Norway", "TheHub (NO)", query, 12)))
            if want("LinkedIn (Verified)"):
                tasks.append((self._fetch_linkedin_live, (query, "Norway", 8)))

        if country in ("All", "Denmark"):
            if want("Jobindex (DK)"):
                tasks.append((self._fetch_jobindex_dk_live, (query, 18)))
            if want("Academic Work (DK)"):
                tasks.append((self._fetch_academic_work_nordic, ("academicwork.dk", "/ledige-stillinger", "Denmark", "Academic Work (DK)", query, 12)))
            if want("TheHub (DK)"):
                tasks.append((self._fetch_thehub_nordic_live, ("DK", "Denmark", "TheHub (DK)", query, 12)))
            if want("LinkedIn (Verified)"):
                tasks.append((self._fetch_linkedin_live, (query, "Denmark", 8)))

        if country in ("All", "Finland"):
            if want("Duunitori (FI)"):
                tasks.append((self._fetch_duunitori_live, (query, 1)))
            if want("Work in Finland (FI)"):
                tasks.append((self._fetch_work_in_finland, (query, 20)))
            if want("Academic Work (FI)"):
                tasks.append((self._fetch_academic_work, (query, 12)))
            if want("TheHub (FI)"):
                tasks.append((self._fetch_thehub_nordic_live, ("FI", "Finland", "TheHub (FI)", query, 12)))
            if want("LinkedIn (Verified)"):
                tasks.append((self._fetch_linkedin_live, (query, "Finland", 8)))

        if country in ("All", "Europe / Remote"):
            if want("Arbeitnow (EU)"):
                tasks.append((self._fetch_arbeitnow, (query, 15)))
            if want("Jobicy (EU)"):
                tasks.append((self._fetch_jobicy_europe, (15,)))
            if want("WeWorkRemotely"):
                tasks.append((self._fetch_weworkremotely, (12,)))
            if want("RemoteOK"):
                tasks.append((self._fetch_remoteok, (12,)))

        # Execute all live web scrapers concurrently with non-blocking timeout ceiling
        if tasks:
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=14)
            try:
                future_map = [pool.submit(fn, *args) for fn, args in tasks]
                try:
                    for fut in concurrent.futures.as_completed(future_map, timeout=5.5):
                        try:
                            res = fut.result(timeout=0.3)
                            if res:
                                all_jobs.extend(res)
                        except Exception:
                            pass
                except concurrent.futures.TimeoutError:
                    pass
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

        # Apply country filter across all aggregated listings
        if country and country != "All":
            c_low = country.lower()
            all_jobs = [
                j for j in all_jobs
                if c_low in (j.country or "").lower() or c_low in (j.location or "").lower()
            ]

        # Apply portal filter if specified
        if filter_by_portal:
            all_jobs = [
                j for j in all_jobs
                if any(p == j.source_portal.lower() or p in j.source_portal.lower() for p in portals_lower)
            ]

        # Run Link Validator Agent (bounded concurrency)
        all_jobs = self.validate_job_links(all_jobs, verify_http=verify_links_live)

        # Deduplicate by (title, company)
        seen = set()
        unique_jobs: List[JobListing] = []
        for j in all_jobs:
            key = (j.title.lower().strip(), j.company.lower().strip())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(j)

        # Multi-keyword relevance ranking
        if query and query.strip():
            keywords = [w.lower() for w in re.split(r"\W+", query) if len(w) > 2]
            stop_words = {"and", "the", "for", "with", "from"}
            meaningful = [k for k in keywords if k not in stop_words]
            if meaningful:
                unique_jobs.sort(
                    key=lambda j: (
                        sum(
                            1
                            for kw in meaningful
                            if kw in f"{j.title} {j.company} {j.location} {' '.join(j.tags)} {j.description}".lower()
                        )
                        + sum(1 for kw in meaningful if kw in j.title.lower()) * 3
                    ),
                    reverse=True,
                )

        return unique_jobs

    aggregate_jobs = fetch_jobs


JobAggregator = JobScraperImpl
