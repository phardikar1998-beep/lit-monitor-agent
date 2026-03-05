"""
Analysis Agent - Uses Claude API to analyze publication abstracts.
"""

import json
import logging
import os
import time
from typing import Callable, Optional

import anthropic

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Agent responsible for analyzing publications using Claude."""

    def __init__(self, drug_name: str, therapeutic_area: Optional[str] = None):
        """
        Initialize the Analysis Agent.

        Args:
            drug_name: The drug being monitored (for relevance scoring)
            therapeutic_area: Optional therapeutic area for context
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Set it with: export ANTHROPIC_API_KEY='your-key-here'"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.drug_name = drug_name
        self.therapeutic_area = therapeutic_area
        self.model = "claude-sonnet-4-20250514"

    def analyze_publications(
        self,
        publications: list[dict],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[dict]:
        """
        Analyze a list of publications and enrich with relevance scores and summaries.

        Args:
            publications: List of publication dictionaries from SearchAgent
            progress_callback: Optional callback(current_index, total) for progress updates

        Returns:
            List of enriched publication dictionaries
        """
        logger.info(f"[AnalysisAgent] Starting analysis of {len(publications)} publications")

        enriched = []
        for i, pub in enumerate(publications, 1):
            if progress_callback:
                progress_callback(i, len(publications))
            logger.info(f"[AnalysisAgent] Analyzing publication {i}/{len(publications)}: {pub['pmid']}")

            try:
                analysis = self._analyze_single(pub)
                enriched_pub = {**pub, **analysis}
                enriched.append(enriched_pub)
                logger.info(f"[AnalysisAgent] Relevance: {analysis['relevance']}")

            except anthropic.RateLimitError:
                logger.warning("[AnalysisAgent] Rate limited, waiting 60 seconds...")
                time.sleep(60)
                # Retry once
                try:
                    analysis = self._analyze_single(pub)
                    enriched_pub = {**pub, **analysis}
                    enriched.append(enriched_pub)
                except Exception as e:
                    logger.error(f"[AnalysisAgent] Failed to analyze {pub['pmid']} after retry: {e}")
                    enriched.append(self._create_fallback_analysis(pub))

            except anthropic.APIError as e:
                logger.error(f"[AnalysisAgent] API error analyzing {pub['pmid']}: {e}")
                enriched.append(self._create_fallback_analysis(pub))

            except Exception as e:
                logger.error(f"[AnalysisAgent] Unexpected error analyzing {pub['pmid']}: {e}")
                enriched.append(self._create_fallback_analysis(pub))

            # Small delay between requests to be respectful of rate limits
            time.sleep(0.5)

        logger.info("[AnalysisAgent] Analysis complete")
        return enriched

    def _analyze_single(self, publication: dict) -> dict:
        """Analyze a single publication."""
        prompt = self._build_analysis_prompt(publication)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse the response
        response_text = response.content[0].text
        return self._parse_analysis_response(response_text)

    def _build_analysis_prompt(self, publication: dict) -> str:
        """Build the analysis prompt for Claude."""
        context = f"Drug being monitored: {self.drug_name}"
        if self.therapeutic_area:
            context += f"\nTherapeutic area: {self.therapeutic_area}"

        return f"""You are a medical affairs analyst reviewing scientific publications for relevance to a pharmaceutical company's drug monitoring program.

{context}

Analyze the following publication:

Title: {publication['title']}

Abstract: {publication['abstract']}

Journal: {publication['journal']}
Publication Date: {publication['publication_date']}

Provide your analysis in the following JSON format (respond with ONLY the JSON, no other text):

{{
    "relevance": "High|Medium|Low",
    "relevance_rationale": "Brief explanation of why this relevance level was assigned",
    "summary": "2-3 sentence summary highlighting key findings",
    "study_design": "Type of study (e.g., RCT, meta-analysis, cohort study, case report, review, etc.) or 'Not specified' if unclear",
    "primary_endpoints": "Main outcomes measured, or 'Not specified' if unclear",
    "notable_results": "Key numerical results or findings, or 'Not specified' if none mentioned"
}}

Relevance criteria:
- HIGH: Directly mentions or studies {self.drug_name}, or presents data that could directly impact its use
- MEDIUM: Studies competitor drugs in the same class, similar indications, or related mechanisms that could indirectly affect {self.drug_name}'s positioning
- LOW: Generally related to the therapeutic area but not directly relevant to {self.drug_name} or its competitive landscape"""

    def _parse_analysis_response(self, response_text: str) -> dict:
        """Parse Claude's analysis response."""
        try:
            # Try to extract JSON from the response
            # Handle case where response might have markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
                text = text.strip()

            analysis = json.loads(text)

            # Validate required fields
            required_fields = [
                "relevance", "relevance_rationale", "summary",
                "study_design", "primary_endpoints", "notable_results"
            ]
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = "Not available"

            # Normalize relevance to expected values
            relevance = analysis.get("relevance", "Low").strip().capitalize()
            if relevance not in ["High", "Medium", "Low"]:
                relevance = "Low"
            analysis["relevance"] = relevance

            return analysis

        except json.JSONDecodeError as e:
            logger.warning(f"[AnalysisAgent] Failed to parse JSON response: {e}")
            # Return a basic analysis based on text response
            return {
                "relevance": "Low",
                "relevance_rationale": "Unable to parse structured analysis",
                "summary": response_text[:500] if response_text else "Analysis unavailable",
                "study_design": "Not specified",
                "primary_endpoints": "Not specified",
                "notable_results": "Not specified"
            }

    def _create_fallback_analysis(self, publication: dict) -> dict:
        """Create a fallback analysis when API call fails."""
        return {
            **publication,
            "relevance": "Low",
            "relevance_rationale": "Analysis unavailable due to processing error",
            "summary": f"[Auto-generated] {publication['title']}",
            "study_design": "Not analyzed",
            "primary_endpoints": "Not analyzed",
            "notable_results": "Not analyzed"
        }
