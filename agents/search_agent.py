"""
Search Agent - Queries PubMed for recent publications using the Entrez API.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent responsible for searching PubMed for medical literature."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str = "user@example.com"):
        """
        Initialize the Search Agent.

        Args:
            email: Email for Entrez API (recommended by NCBI for tracking)
        """
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MedLitMonitor/1.0"
        })

    def search(
        self,
        drug_name: str,
        therapeutic_area: Optional[str] = None,
        days_back: int = 7,
        max_results: int = 50
    ) -> list[dict]:
        """
        Search PubMed for recent publications.

        Args:
            drug_name: Name of the drug to search for
            therapeutic_area: Optional therapeutic area to include in search
            days_back: Number of days to look back (default 7)
            max_results: Maximum number of results to return

        Returns:
            List of publication dictionaries with metadata
        """
        logger.info(f"[SearchAgent] Starting search for drug: {drug_name}")
        if therapeutic_area:
            logger.info(f"[SearchAgent] Therapeutic area filter: {therapeutic_area}")
        logger.info(f"[SearchAgent] Date range: last {days_back} days")

        # Build the search query
        query = self._build_query(drug_name, therapeutic_area, days_back)
        logger.info(f"[SearchAgent] Query: {query}")

        # Step 1: Search for PMIDs
        pmids = self._search_pmids(query, max_results)
        if not pmids:
            logger.warning("[SearchAgent] No publications found matching criteria")
            return []

        logger.info(f"[SearchAgent] Found {len(pmids)} publications")

        # Step 2: Fetch full details for each PMID
        publications = self._fetch_details(pmids)
        logger.info(f"[SearchAgent] Retrieved details for {len(publications)} publications")

        return publications

    def _build_query(
        self,
        drug_name: str,
        therapeutic_area: Optional[str],
        days_back: int
    ) -> str:
        """Build the PubMed search query."""
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        date_filter = (
            f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : '
            f'"{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
        )

        # Build query terms
        query_parts = [f'"{drug_name}"[Title/Abstract]']

        if therapeutic_area:
            query_parts.append(f'"{therapeutic_area}"[Title/Abstract]')

        # Combine with date filter
        terms = " AND ".join(query_parts)
        query = f"({terms}) AND {date_filter}"

        return query

    def _search_pmids(self, query: str, max_results: int) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "email": self.email,
            "sort": "date"
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            pmids = data.get("esearchresult", {}).get("idlist", [])
            return pmids

        except requests.exceptions.Timeout:
            logger.error("[SearchAgent] PubMed search timed out")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"[SearchAgent] PubMed API error: {e}")
            raise
        except Exception as e:
            logger.error(f"[SearchAgent] Unexpected error during search: {e}")
            raise

    def _fetch_details(self, pmids: list[str]) -> list[dict]:
        """Fetch detailed information for a list of PMIDs."""
        if not pmids:
            return []

        url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email
        }

        try:
            # Rate limiting - be nice to NCBI
            time.sleep(0.34)  # ~3 requests per second max

            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()

            publications = self._parse_pubmed_xml(response.text)
            return publications

        except requests.exceptions.Timeout:
            logger.error("[SearchAgent] PubMed fetch timed out")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"[SearchAgent] PubMed API error: {e}")
            raise
        except Exception as e:
            logger.error(f"[SearchAgent] Error fetching publication details: {e}")
            raise

    def _parse_pubmed_xml(self, xml_text: str) -> list[dict]:
        """Parse PubMed XML response into structured data."""
        publications = []

        try:
            root = ElementTree.fromstring(xml_text)

            for article in root.findall(".//PubmedArticle"):
                pub = self._parse_article(article)
                if pub:
                    publications.append(pub)

        except ElementTree.ParseError as e:
            logger.error(f"[SearchAgent] XML parsing error: {e}")
            raise

        return publications

    def _parse_article(self, article: ElementTree.Element) -> Optional[dict]:
        """Parse a single PubMed article element."""
        try:
            medline = article.find(".//MedlineCitation")
            if medline is None:
                return None

            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else "Unknown"

            # Get article info
            article_elem = medline.find(".//Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "No title"

            # Abstract
            abstract_parts = []
            abstract_elem = article_elem.find(".//Abstract")
            if abstract_elem is not None:
                for abstract_text in abstract_elem.findall(".//AbstractText"):
                    label = abstract_text.get("Label", "")
                    text = abstract_text.text or ""
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else "No abstract available"

            # Authors
            authors = []
            author_list = article_elem.find(".//AuthorList")
            if author_list is not None:
                for author in author_list.findall(".//Author"):
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None:
                        name = last_name.text
                        if fore_name is not None:
                            name = f"{fore_name.text} {name}"
                        authors.append(name)

            # Publication date
            pub_date = self._extract_pub_date(article_elem)

            # Journal
            journal_elem = article_elem.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else "Unknown Journal"

            return {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "publication_date": pub_date,
                "journal": journal,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            }

        except Exception as e:
            logger.warning(f"[SearchAgent] Error parsing article: {e}")
            return None

    def _extract_pub_date(self, article_elem: ElementTree.Element) -> str:
        """Extract publication date from article element."""
        # Try ArticleDate first (electronic publication)
        article_date = article_elem.find(".//ArticleDate")
        if article_date is not None:
            year = article_date.find("Year")
            month = article_date.find("Month")
            day = article_date.find("Day")
            if year is not None:
                date_str = year.text
                if month is not None:
                    date_str += f"-{month.text.zfill(2)}"
                    if day is not None:
                        date_str += f"-{day.text.zfill(2)}"
                return date_str

        # Fall back to Journal PubDate
        pub_date = article_elem.find(".//Journal/JournalIssue/PubDate")
        if pub_date is not None:
            year = pub_date.find("Year")
            month = pub_date.find("Month")
            if year is not None:
                date_str = year.text
                if month is not None:
                    # Month might be text like "Jan" or numeric
                    month_text = month.text
                    date_str += f"-{month_text}"
                return date_str

        return "Unknown date"
