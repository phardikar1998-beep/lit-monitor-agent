"""
Report Agent - Generates formatted literature digest reports.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ReportAgent:
    """Agent responsible for generating formatted literature digest reports."""

    def __init__(self, output_dir: str = "reports"):
        """
        Initialize the Report Agent.

        Args:
            output_dir: Directory to save report files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        publications: list[dict],
        drug_name: str,
        therapeutic_area: Optional[str] = None,
        days_back: int = 7
    ) -> str:
        """
        Generate a formatted literature digest report.

        Args:
            publications: List of analyzed publication dictionaries
            drug_name: Name of the drug being monitored
            therapeutic_area: Optional therapeutic area
            days_back: Number of days covered

        Returns:
            Path to the generated report file
        """
        logger.info(f"[ReportAgent] Generating report for {len(publications)} publications")

        # Sort publications by relevance
        sorted_pubs = self._sort_by_relevance(publications)

        # Count by relevance
        counts = self._count_by_relevance(sorted_pubs)
        logger.info(f"[ReportAgent] Relevance breakdown - High: {counts['High']}, Medium: {counts['Medium']}, Low: {counts['Low']}")

        # Generate report content
        report_content = self._format_report(
            sorted_pubs, drug_name, therapeutic_area, days_back, counts
        )

        # Save to file
        output_path = self._save_report(report_content, drug_name)
        logger.info(f"[ReportAgent] Report saved to: {output_path}")

        return str(output_path)

    def _sort_by_relevance(self, publications: list[dict]) -> list[dict]:
        """Sort publications by relevance (High > Medium > Low)."""
        relevance_order = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(
            publications,
            key=lambda x: relevance_order.get(x.get("relevance", "Low"), 3)
        )

    def _count_by_relevance(self, publications: list[dict]) -> dict[str, int]:
        """Count publications by relevance level."""
        counts = {"High": 0, "Medium": 0, "Low": 0}
        for pub in publications:
            relevance = pub.get("relevance", "Low")
            if relevance in counts:
                counts[relevance] += 1
        return counts

    def _format_report(
        self,
        publications: list[dict],
        drug_name: str,
        therapeutic_area: Optional[str],
        days_back: int,
        counts: dict[str, int]
    ) -> str:
        """Format the complete report."""
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%H:%M")

        # Header
        lines = [
            "=" * 80,
            "MEDICAL LITERATURE MONITORING DIGEST",
            "=" * 80,
            "",
            f"Drug: {drug_name}",
        ]

        if therapeutic_area:
            lines.append(f"Therapeutic Area: {therapeutic_area}")

        lines.extend([
            f"Period: Last {days_back} days",
            f"Generated: {date_str} at {time_str}",
            "",
            "-" * 80,
            "SUMMARY",
            "-" * 80,
            "",
            f"Total Publications Found: {len(publications)}",
            f"  - High Relevance:   {counts['High']}",
            f"  - Medium Relevance: {counts['Medium']}",
            f"  - Low Relevance:    {counts['Low']}",
            "",
        ])

        if not publications:
            lines.extend([
                "No publications found matching the search criteria.",
                "",
                "=" * 80,
            ])
            return "\n".join(lines)

        # High Relevance Section
        high_pubs = [p for p in publications if p.get("relevance") == "High"]
        if high_pubs:
            lines.extend([
                "=" * 80,
                "HIGH RELEVANCE PUBLICATIONS",
                "=" * 80,
                "",
            ])
            for i, pub in enumerate(high_pubs, 1):
                lines.extend(self._format_publication(pub, i))

        # Medium Relevance Section
        medium_pubs = [p for p in publications if p.get("relevance") == "Medium"]
        if medium_pubs:
            lines.extend([
                "=" * 80,
                "MEDIUM RELEVANCE PUBLICATIONS",
                "=" * 80,
                "",
            ])
            for i, pub in enumerate(medium_pubs, 1):
                lines.extend(self._format_publication(pub, i))

        # Low Relevance Section
        low_pubs = [p for p in publications if p.get("relevance") == "Low"]
        if low_pubs:
            lines.extend([
                "=" * 80,
                "LOW RELEVANCE PUBLICATIONS",
                "=" * 80,
                "",
            ])
            for i, pub in enumerate(low_pubs, 1):
                lines.extend(self._format_publication(pub, i))

        # Footer
        lines.extend([
            "=" * 80,
            "END OF REPORT",
            "=" * 80,
            "",
            "This report was automatically generated by the Medical Literature Monitor.",
            "For questions or feedback, contact your Medical Affairs team.",
        ])

        return "\n".join(lines)

    def _format_publication(self, pub: dict, index: int) -> list[str]:
        """Format a single publication entry."""
        lines = [
            f"[{index}] {pub.get('title', 'No title')}",
            "-" * 40,
            "",
        ]

        # Authors (truncate if too many)
        authors = pub.get("authors", [])
        if authors:
            if len(authors) > 5:
                author_str = ", ".join(authors[:5]) + f", et al. ({len(authors)} authors)"
            else:
                author_str = ", ".join(authors)
            lines.append(f"Authors: {author_str}")
        else:
            lines.append("Authors: Not available")

        lines.extend([
            f"Journal: {pub.get('journal', 'Unknown')}",
            f"Published: {pub.get('publication_date', 'Unknown')}",
            f"PMID: {pub.get('pmid', 'Unknown')}",
            "",
            "SUMMARY:",
            pub.get("summary", "No summary available"),
            "",
            "RELEVANCE RATIONALE:",
            pub.get("relevance_rationale", "No rationale available"),
            "",
            "STUDY DETAILS:",
            f"  Study Design: {pub.get('study_design', 'Not specified')}",
            f"  Primary Endpoints: {pub.get('primary_endpoints', 'Not specified')}",
            f"  Notable Results: {pub.get('notable_results', 'Not specified')}",
            "",
            f"Full Text: {pub.get('url', 'URL not available')}",
            "",
            "",
        ])

        return lines

    def _save_report(self, content: str, drug_name: str) -> Path:
        """Save the report to a file."""
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_drug_name = "".join(c if c.isalnum() else "_" for c in drug_name)
        filename = f"lit_digest_{safe_drug_name}_{timestamp}.txt"

        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def get_report_content(
        self,
        publications: list[dict],
        drug_name: str,
        therapeutic_area: Optional[str] = None,
        days_back: int = 7
    ) -> str:
        """
        Get the report content without saving to file.

        Useful for previewing or sending via email.
        """
        sorted_pubs = self._sort_by_relevance(publications)
        counts = self._count_by_relevance(sorted_pubs)
        return self._format_report(
            sorted_pubs, drug_name, therapeutic_area, days_back, counts
        )
