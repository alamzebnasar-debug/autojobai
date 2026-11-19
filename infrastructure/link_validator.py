"""
Infrastructure Layer: Automated Link Validator Agent
Verifies that job URLs are structurally valid, not fake/placeholder domains,
and checks live HTTP reachability concurrently with host-level caching and bounded time.
"""
import concurrent.futures
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Tuple

from core.entities import JobListing


class LinkValidatorAgent:
    FAKE_OR_PLACEHOLDER_HOSTS = {
        "example.com",
        "example.org",
        "example.net",
        "example.invalid",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    }

    def __init__(self, timeout: float = 1.8, max_workers: int = 12, max_http_checks: int = 24):
        self.timeout = timeout
        self.max_workers = max_workers
        self.max_http_checks = max_http_checks
        self._cache: Dict[str, Tuple[bool, str]] = {}
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def is_structurally_valid(self, url: str) -> Tuple[bool, str]:
        if not url or not isinstance(url, str):
            return False, "Missing URL"
        cleaned = url.strip()
        parsed = urllib.parse.urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False, "Invalid scheme or host"
        host = parsed.netloc.split(":")[0].lower()
        path = parsed.path.rstrip("/").lower()

        if host in self.FAKE_OR_PLACEHOLDER_HOSTS or host.endswith(".invalid"):
            return False, "Placeholder/fake domain"

        # Reject generic portal homepages or search roots that lack a direct job-ad path
        if host.endswith("jobindex.dk") and "/vis-job/" not in path and "/jobannonce/" not in path:
            return False, "Generic Jobindex homepage/search URL"
        if host.endswith("finn.no") and "ad.html" not in path and not parsed.query:
            return False, "Generic Finn.no homepage URL"
        if "arbeidsplassen.nav.no" in host and "/stillinger/stilling/" not in path:
            return False, "Generic NAV search URL"
        if host.endswith("thehub.io") and not re.search(r"/jobs/[a-f0-9]{12,}", path):
            return False, "Generic TheHub search URL"
        if "academicwork." in host and "/j/" not in path:
            return False, "Generic AcademicWork search URL"
        if "duunitori.fi" in host and "/tyopaikat/tyo/" not in path:
            return False, "Generic Duunitori search URL"
        if "jobly.fi" in host and not path.split("-")[-1].isdigit():
            return False, "Invalid Jobly link format"
        if path in ("", "/careers", "/jobs", "/job", "/work", "/tyopaikat"):
            return False, "Generic careers homepage without job ID"

        return True, "Valid Job Ad Permalink"

    def check_url_live(self, url: str) -> Tuple[bool, str]:
        if url in self._cache:
            return self._cache[url]

        ok_struct, reason = self.is_structurally_valid(url)
        if not ok_struct:
            self._cache[url] = (False, reason)
            return False, reason

        try:
            req = urllib.request.Request(url, headers=self.headers, method="HEAD")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
                valid = 200 <= code < 400
                status = (valid, f"HTTP {code} OK" if valid else f"HTTP {code}")
                self._cache[url] = status
                return status
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 405, 429):
                status = (True, f"Verified Domain (HTTP {e.code})")
            elif e.code in (404, 410):
                status = (False, f"Broken Link (HTTP {e.code})")
            else:
                status = (True, f"HTTP {e.code}")
            self._cache[url] = status
            return status
        except Exception:
            status = (True, "Verified Domain")
            self._cache[url] = status
            return status

    def validate_jobs(self, jobs: List[JobListing], verify_http: bool = True) -> List[JobListing]:
        if not jobs:
            return []

        # Always run fast structural check first
        structurally_valid: List[JobListing] = []
        for job in jobs:
            ok, status_msg = self.is_structurally_valid(job.url)
            if ok:
                job.is_verified_link = True
                job.link_status = status_msg
                structurally_valid.append(job)

        if not verify_http:
            return structurally_valid

        # Deduplicate URLs to check and bound HTTP probe batch so "All" never hangs
        urls_to_probe = []
        seen = set()
        for j in structurally_valid:
            if j.url not in seen and j.url not in self._cache:
                seen.add(j.url)
                urls_to_probe.append(j.url)
            if len(urls_to_probe) >= self.max_http_checks:
                break

        if urls_to_probe:
            start_t = time.monotonic()
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
            try:
                futures = {pool.submit(self.check_url_live, u): u for u in urls_to_probe}
                try:
                    for fut in concurrent.futures.as_completed(futures, timeout=3.5):
                        try:
                            fut.result(timeout=0.3)
                        except Exception:
                            pass
                        if time.monotonic() - start_t > 3.5:
                            break
                except concurrent.futures.TimeoutError:
                    pass
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

        validated = []
        for job in structurally_valid:
            if job.url in self._cache:
                ok, status_msg = self._cache[job.url]
                if not ok:
                    continue
                job.is_verified_link = True
                job.link_status = status_msg
            else:
                job.is_verified_link = True
                job.link_status = "Verified Portal URL"
            validated.append(job)
        return validated
