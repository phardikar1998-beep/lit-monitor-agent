#!/usr/bin/env python3
"""
Medical Literature Monitor - Multi-Agent System

A system for monitoring medical literature relevant to pharmaceutical products.
Uses three coordinated agents:
  1. SearchAgent - Queries PubMed for recent publications
  2. AnalysisAgent - Analyzes abstracts using Claude AI
  3. ReportAgent - Generates formatted digest reports

Usage:
    python main.py --drug "adalimumab"
    python main.py --drug "adalimumab" --therapeutic-area "rheumatoid arthritis"
    python main.py --drug "pembrolizumab" --days 14 --max-results 100

Environment Variables:
    ANTHROPIC_API_KEY: Required for the Analysis Agent
"""

import argparse
import logging
import sys
from datetime import datetime

from agents import SearchAgent, AnalysisAgent, ReportAgent


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Medical Literature Monitor - Track recent publications for pharmaceutical drugs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --drug "adalimumab"
  python main.py --drug "adalimumab" --therapeutic-area "rheumatoid arthritis"
  python main.py --drug "pembrolizumab" --days 14 --max-results 100

Environment Variables:
  ANTHROPIC_API_KEY    Your Anthropic API key (required)
        """
    )

    parser.add_argument(
        "--drug", "-d",
        required=True,
        help="Name of the drug to monitor (e.g., 'adalimumab', 'pembrolizumab')"
    )

    parser.add_argument(
        "--therapeutic-area", "-t",
        help="Optional therapeutic area filter (e.g., 'rheumatoid arthritis', 'oncology')"
    )

    parser.add_argument(
        "--days", "-D",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )

    parser.add_argument(
        "--max-results", "-m",
        type=int,
        default=50,
        help="Maximum number of publications to retrieve (default: 50)"
    )

    parser.add_argument(
        "--output-dir", "-o",
        default="reports",
        help="Directory to save reports (default: reports)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip AI analysis (useful for testing search functionality)"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Print banner
    print("\n" + "=" * 60)
    print("  MEDICAL LITERATURE MONITOR")
    print("=" * 60)
    print(f"  Drug: {args.drug}")
    if args.therapeutic_area:
        print(f"  Therapeutic Area: {args.therapeutic_area}")
    print(f"  Date Range: Last {args.days} days")
    print(f"  Max Results: {args.max_results}")
    print("=" * 60 + "\n")

    try:
        # ============================================
        # AGENT 1: Search Agent
        # ============================================
        logger.info("=" * 50)
        logger.info("PHASE 1: LITERATURE SEARCH")
        logger.info("=" * 50)

        search_agent = SearchAgent()
        publications = search_agent.search(
            drug_name=args.drug,
            therapeutic_area=args.therapeutic_area,
            days_back=args.days,
            max_results=args.max_results
        )

        if not publications:
            logger.warning("No publications found. Try adjusting search parameters.")
            print("\nNo publications found matching your criteria.")
            print("Suggestions:")
            print("  - Try a longer date range (--days 30)")
            print("  - Check the drug name spelling")
            print("  - Remove the therapeutic area filter")
            return 0

        logger.info(f"Found {len(publications)} publications")

        # ============================================
        # AGENT 2: Analysis Agent
        # ============================================
        if args.skip_analysis:
            logger.info("Skipping analysis phase (--skip-analysis flag set)")
            # Add placeholder analysis
            for pub in publications:
                pub["relevance"] = "Medium"
                pub["relevance_rationale"] = "Analysis skipped"
                pub["summary"] = pub.get("title", "No title")
                pub["study_design"] = "Not analyzed"
                pub["primary_endpoints"] = "Not analyzed"
                pub["notable_results"] = "Not analyzed"
            analyzed_publications = publications
        else:
            logger.info("")
            logger.info("=" * 50)
            logger.info("PHASE 2: AI-POWERED ANALYSIS")
            logger.info("=" * 50)

            analysis_agent = AnalysisAgent(
                drug_name=args.drug,
                therapeutic_area=args.therapeutic_area
            )
            analyzed_publications = analysis_agent.analyze_publications(publications)

        # ============================================
        # AGENT 3: Report Agent
        # ============================================
        logger.info("")
        logger.info("=" * 50)
        logger.info("PHASE 3: REPORT GENERATION")
        logger.info("=" * 50)

        report_agent = ReportAgent(output_dir=args.output_dir)
        report_path = report_agent.generate_report(
            publications=analyzed_publications,
            drug_name=args.drug,
            therapeutic_area=args.therapeutic_area,
            days_back=args.days
        )

        # ============================================
        # Summary
        # ============================================
        print("\n" + "=" * 60)
        print("  MONITORING COMPLETE")
        print("=" * 60)

        # Count by relevance
        high = sum(1 for p in analyzed_publications if p.get("relevance") == "High")
        medium = sum(1 for p in analyzed_publications if p.get("relevance") == "Medium")
        low = sum(1 for p in analyzed_publications if p.get("relevance") == "Low")

        print(f"\n  Publications analyzed: {len(analyzed_publications)}")
        print(f"    - High relevance:   {high}")
        print(f"    - Medium relevance: {medium}")
        print(f"    - Low relevance:    {low}")
        print(f"\n  Report saved to: {report_path}")
        print("\n" + "=" * 60 + "\n")

        return 0

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nError: {e}")
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\nOperation cancelled.")
        return 130

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nAn unexpected error occurred: {e}")
        print("Check the logs for more details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
