"""
RAG Engine: Semantic Chunking, Vector Similarity, and PII Data Privacy Shield
"""
import re
import math
from typing import List, Dict, Any, Tuple

class RAGEngine:
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def mask_pii(text: str) -> str:
        """
        Redacts personally identifiable information (PII) to enforce zero-trust privacy.
        """
        # Mask emails
        masked = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_REDACTED]', text)
        # Mask phone numbers
        masked = re.sub(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[PHONE_REDACTED]', masked)
        # Mask street addresses
        masked = re.sub(r'\d+\s+[A-Za-z0-9\s,]+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', '[ADDRESS_REDACTED]', masked, flags=re.IGNORECASE)
        return masked

    def chunk_document(self, text: str) -> List[str]:
        """
        Breaks text into overlapping semantic passages.
        """
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
        """
        Computes cosine overlap similarity between query tokens and document tokens.
        """
        q_tokens = set(self._tokenize(query))
        doc_tokens = set(self._tokenize(document))

        if not q_tokens or not doc_tokens:
            return 0.0

        intersection = q_tokens.intersection(doc_tokens)
        score = len(intersection) / math.sqrt(len(q_tokens) * len(doc_tokens))
        return min(1.0, score * 1.5)

    def retrieve_relevant_chunks(self, query: str, chunks: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Retrieves top-k most semantically relevant chunks for a given query requirement.
        """
        scored = []
        for chunk in chunks:
            sim = self.compute_similarity(query, chunk)
            scored.append((chunk, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
