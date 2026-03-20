"""
Regulatory Policy Retrieval Agent

Responsibilities:
- Accept extracted customer profile fields
- Perform semantic search over the regulatory corpus in Qdrant
- Determine applicable due diligence tier (standard vs enhanced)
- Flag PEP status and high-risk jurisdictions
- Return ranked regulatory passages with source citations
"""

import structlog
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient

from core.config import settings
from core.models import (
    DocumentIntelligenceOutput,
    RegulatoryRetrievalOutput,
    RegulatoryPassage,
    DDType,
)

log = structlog.get_logger()

# Keywords that suggest PEP status in a name or document context
PEP_INDICATOR_TERMS = [
    "minister", "senator", "ambassador", "governor", "president",
    "member of parliament", "judge", "general", "director general",
]

TOP_K_PASSAGES = 5

class RegulatoryRetrievalAgent:
    """
    Retrieves relevant regulatory passages from the indexed corpus using
    semantic similarity search. Applies deterministic rules for PEP detection
    and high-risk jurisdiction classification before retrieval.

    Country risk data is loaded from data/fatf_high_risk_countries.json at
    initialisation time. To update the country lists, edit that JSON file
    and restart the service — no code changes required.
    """

    def __init__(self) -> None:
        self._embedder = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key,
            task_type="retrieval_query",
        )
        self._qdrant = QdrantClient(
            url=settings.qdrant_url,
            **( {"api_key": settings.qdrant_api_key} if settings.qdrant_api_key else {} )
        )

        # Load country risk data from file once at startup
        # Updating the FATF list requires only a JSON edit + restart,
        fatf_data = settings.load_fatf_countries()
        self._high_risk_countries: set[str] = (
            fatf_data["blacklist"] | fatf_data["greylist"]
        )
        self._blacklisted_countries: set[str] = fatf_data["blacklist"]

        log.info(
            "regulatory_retrieval_agent.initialised",
            high_risk_country_count=len(self._high_risk_countries),
            blacklisted_country_count=len(self._blacklisted_countries),
        )

    async def retrieve(
        self, doc_output: DocumentIntelligenceOutput, query: str
    ) -> RegulatoryRetrievalOutput:
        """
        Retrieve applicable regulatory passages for a given customer profile.

        Args:
            doc_output: Structured output from the Document Intelligence Agent
            query: Original user query for additional semantic context

        Returns:
            RegulatoryRetrievalOutput with passages, flags, and DD tier
        """
        log.info("regulatory_retrieval_agent.started")

        fields = doc_output.extracted_fields
        nationality = (fields.nationality or "").upper()
        full_name = (fields.full_name or "").lower()

        # Deterministic rule-based checks
        pep_flag = self._check_pep(full_name)
        high_risk_jurisdiction = nationality in self._high_risk_countries
        blacklisted = nationality in self._blacklisted_countries
        dd_type = DDType.ENHANCED if (pep_flag or high_risk_jurisdiction) else DDType.STANDARD

        log.info(
            "regulatory_retrieval_agent.flags",
            nationality=nationality,
            pep=pep_flag,
            high_risk=high_risk_jurisdiction,
            blacklisted=blacklisted,
            dd_type=dd_type,
        )

        semantic_query = self._build_query(fields, query, pep_flag, high_risk_jurisdiction)
        passages = await self._semantic_search(semantic_query)
        applicable_frameworks = self._determine_frameworks(pep_flag, high_risk_jurisdiction)

        output = RegulatoryRetrievalOutput(
            passages=passages,
            due_diligence_type=dd_type,
            pep_flag=pep_flag,
            high_risk_jurisdiction=high_risk_jurisdiction,
            applicable_frameworks=applicable_frameworks,
        )

        log.info(
            "regulatory_retrieval_agent.completed",
            passages_retrieved=len(passages),
            dd_type=dd_type,
        )
        return output

    def _check_pep(self, full_name_lower: str) -> bool:
        """Simple keyword-based PEP indicator check against known title terms."""
        return any(term in full_name_lower for term in PEP_INDICATOR_TERMS)

    def _build_query(self, fields, query: str, pep: bool, high_risk: bool) -> str:
        """Construct a rich semantic query string combining customer context."""
        parts = [query]
        if fields.nationality:
            parts.append(f"customer nationality {fields.nationality}")
        if pep:
            parts.append("politically exposed person enhanced due diligence requirements")
        if high_risk:
            parts.append("high-risk jurisdiction FATF enhanced due diligence MAS Notice 626")
        parts.append("KYC AML customer identity verification Singapore MAS")
        return " ".join(parts)

    async def _semantic_search(self, query: str) -> list[RegulatoryPassage]:
        """
        Embed the query and retrieve top-K passages from Qdrant.
        """
        query_vector = await self._embedder.aembed_query(query)

        results = self._qdrant.query_points(
            collection_name=settings.qdrant_collection_name,
            query=query_vector,
            limit=TOP_K_PASSAGES,
            with_payload=True,
        )

        passages = []
        for hit in results.points:
            payload = hit.payload or {}
            passages.append(
                RegulatoryPassage(
                    source=payload.get("source", "unknown"),
                    clause=f"chunk_{payload.get('chunk_index', 0)}",
                    content=payload.get("text", ""),
                    relevance_score=round(hit.score, 4),
                )
            )
        return passages

    def _determine_frameworks(self, pep: bool, high_risk: bool) -> list[str]:
        """Return the list of regulatory frameworks applicable to this customer."""
        frameworks = ["MAS Notice 626", "MAS AML/CFT Guidelines"]
        if pep:
            frameworks.append("FATF Recommendation 12 (PEPs)")
            frameworks.append("MAS Notice 626 — Paragraph 9 (PEPs)")
        if high_risk:
            frameworks.append("FATF Recommendation 19 (High-Risk Countries)")
            frameworks.append("MAS Notice 626 — Paragraph 10 (High-Risk Countries)")
        return frameworks