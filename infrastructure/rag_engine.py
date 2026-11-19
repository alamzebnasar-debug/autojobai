"""
Infrastructure Layer: Concrete RAG Engine Implementation
Implements IRAGEngine: Semantic Chunking, Vector Similarity, Zero-Trust PII Masking,
and CV Header/Contact Sanitization.
"""
import math
import re
from typing import List, Tuple
from core.interfaces import IRAGEngine


class RAGEngineImpl(IRAGEngine):
    def __init__(self, chunk_size: int = 120, chunk_overlap: int = 20):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def mask_pii(self, text: str) -> str:
        """Zero-Trust PII Redaction for email, phone, URLs, and street addresses"""
        masked = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_REDACTED]", text)
        masked = re.sub(r"https?://\S+|www\.\S+", "[URL_REDACTED]", masked)
        masked = re.sub(
            r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}",
            "[PHONE_REDACTED]",
            masked,
        )
        masked = re.sub(
            r"\d+\s+[A-Za-z0-9\s,]+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
            "[ADDRESS_REDACTED]",
            masked,
            flags=re.IGNORECASE,
        )
        return masked

    @staticmethod
    def extract_clean_body(text: str) -> str:
        """
        Strips the top personal header block (name, citizenship, location, LinkedIn/GitHub/Portfolio,
        contact details) and cleans leftover punctuation/redaction artifacts so RAG chunks and summaries
        only contain professional experience, skills, and achievements.
        """
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""

        # If CV contains an explicit section marker (SUMMARY, PROFILE, EXPERIENCE, SKILLS),
        # drop any personal header lines immediately preceding it (if within top 8 lines).
        section_re = re.compile(
            r"^(summary|professional summary|profile|about me|experience|work experience|skills|core competencies)\b",
            flags=re.IGNORECASE,
        )
        start_idx = 0
        for idx, line in enumerate(lines[:10]):
            if section_re.match(line):
                # Strip the section label itself if it's on its own or inline like "SUMMARY ..."
                lines[idx] = section_re.sub("", line).strip(" :|-")
                start_idx = idx
                break
        else:
            # No explicit section marker found: skip first line if it looks like a Name/Contact header
            if len(lines) > 1 and (
                "|" in lines[0]
                or "@" in lines[0]
                or any(w in lines[0].lower() for w in ("linkedin", "github", "portfolio", "citizen"))
                or len(lines[0].split()) <= 6
            ):
                start_idx = 1

        body_lines = []
        contact_line_re = re.compile(
            r"(linkedin|github|portfolio|citizen|@|\[email_redacted\]|\[phone_redacted\]|\[url_redacted\]|\[address_redacted\])",
            flags=re.IGNORECASE,
        )
        for line in lines[start_idx:]:
            if not line:
                continue
            # Remove contact badges/tokens inside lines
            cleaned = re.sub(r"\[(EMAIL|PHONE|URL|ADDRESS|NAME|PII)_REDACTED\]", "", line, flags=re.IGNORECASE)
            cleaned = re.sub(r"\([^)]*citizen[^)]*\)", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\b(LinkedIn|GitHub|Portfolio)\b", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", cleaned)
            cleaned = re.sub(r"https?://\S+|www\.\S+", "", cleaned)
            cleaned = re.sub(r"\s*[,|•·]+\s*([,|•·]\s*)+", ", ", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;|-:")
            if not cleaned:
                continue
            # Skip short leftover header lines that only held contact info
            if len(cleaned.split()) <= 3 and contact_line_re.search(line):
                continue
            body_lines.append(cleaned)

        return "\n".join(body_lines)

    @classmethod
    def extract_experience_highlights(cls, text: str, max_items: int = 4) -> List[str]:
        """
        Extracts clean, anonymized experience and project impact clauses from PDF/DOCX CVs
        (handling both bullet lines without trailing periods and standard sentences).
        """
        if not text:
            return []

        cleaned = cls.extract_clean_body(text) or text
        # Split on newlines, bullets, or sentence boundaries
        raw_clauses = re.split(r"(?:\r?\n|•|▪|◦|(?<=[.!?])\s+)", cleaned)

        action_or_tech = re.compile(
            r"\b(led|built|architected|designed|developed|implemented|engineered|managed|delivered|"
            r"optimized|automated|scaled|deployed|reduced|increased|migrated|integrated|created|"
            r"spearheaded|directed|maintained|collaborated|mentored|python|c#|\.net|azure|aws|"
            r"docker|kubernetes|rag|llm|fastapi|react|sql|api|cloud|microservices|healthcare|"
            r"clinical|finance|ifrs|marketing|supply chain|operations|logistics|experience)\b",
            flags=re.IGNORECASE,
        )

        highlights: List[str] = []
        seen = set()
        for clause in raw_clauses:
            c = re.sub(r"^[\-\*\d\.\)\s]+", "", clause).strip(" ,;:-")
            c = re.sub(r"\s+", " ", c)
            if len(c) < 28:
                continue
            words = c.split()
            if len(words) < 5:
                continue
            # Reject unspaced PDF-mashed lines (e.g. "SeniorSoftwareEngineerwithadecade...")
            if any(len(w) > 28 and "/" not in w and "-" not in w for w in words):
                continue
            alpha_ratio = sum(ch.isalpha() for ch in c) / max(1, len(c))
            if alpha_ratio < 0.62:
                continue
            # Skip generic single-label headings
            if re.match(r"^(summary|experience|education|skills|projects|certifications|languages)$", c, re.IGNORECASE):
                continue
            if not action_or_tech.search(c):
                continue

            if len(c) > 190:
                c = c[:190].rsplit(" ", 1)[0].rstrip(" ,;:-")
            key = c.lower()[:60]
            if key not in seen:
                seen.add(key)
                highlights.append(c.rstrip("."))
            if len(highlights) >= max_items:
                break

        return highlights

    def chunk_document(self, text: str) -> List[str]:
        clean_text = self.extract_clean_body(text) or text
        # Preserve line/bullet breaks so downstream sanitizers parse individual bullets cleanly
        normalized = " • ".join([ln.strip() for ln in clean_text.splitlines() if ln.strip()])
        words = normalized.split()
        if not words:
            return []
        chunks = []
        i = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        while i < len(words):
            chunk = " ".join(words[i : i + self.chunk_size])
            chunks.append(chunk)
            i += step
        return chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w for w in re.sub(r"[^a-zA-Z0-9]", " ", text.lower()).split() if len(w) > 2]

    def compute_similarity(self, query: str, document: str) -> float:
        q_tokens = set(self._tokenize(query))
        doc_tokens = set(self._tokenize(document))
        if not q_tokens or not doc_tokens:
            return 0.0
        intersection = q_tokens.intersection(doc_tokens)
        score = len(intersection) / math.sqrt(len(q_tokens) * len(doc_tokens))
        return min(1.0, score * 1.5)

    def retrieve_relevant_chunks(self, query: str, chunks: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        scored = [(c, self.compute_similarity(query, c)) for c in chunks]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
