"""
Infrastructure Layer: Concrete RAG Engine Implementation
Implements IRAGEngine: Semantic Chunking, Vector Similarity, and Zero-Trust PII Masking
"""
import re
import math
from typing import List, Tuple
from core.interfaces import IRAGEngine

class RAGEngineImpl(IRAGEngine):
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def mask_pii(self, text: str) -> str:
        """Zero-Trust PII Redaction for phone, email, and address"""
        masked = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_REDACTED]', text)
        masked = re.sub(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[PHONE_REDACTED]', masked)
        masked = re.sub(r'\d+\s+[A-Za-z0-9\s,]+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', '[ADDRESS_REDACTED]', masked, flags=re.IGNORECASE)
        return masked

    def chunk_document(self, text: str) -> List[str]:
        words = text.split()
        if not words:
            return []
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            i += (self.chunk_size - self.chunk_overlap)
        return chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', text.lower()).split() if len(w) > 2]

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
