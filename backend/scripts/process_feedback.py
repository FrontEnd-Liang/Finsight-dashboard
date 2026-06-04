#!/usr/bin/env python3
"""
Process pending downvote feedback and patch backend/data/corpus.json.

Uses REFINEMENT_* model (NOT DeepSeek). Schedule via cron / Task Scheduler.

Examples:
  python scripts/process_feedback.py
  python scripts/process_feedback.py --dry-run
  python scripts/process_feedback.py --limit 5 --reingest
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from repo root or backend/
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config import get_settings
from feedback_processor import process_pending_feedback, reingest_library

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("process_feedback")


def main() -> int:
    parser = argparse.ArgumentParser(description="Process downvote feedback into corpus.json")
    parser.add_argument("--limit", type=int, default=10, help="Max pending rows per run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Call refinement model but do not write corpus.json",
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="After patching, reload corpus.json into Supabase vectors",
    )
    args = parser.parse_args()

    settings = get_settings()
    summary = process_pending_feedback(
        settings, limit=args.limit, dry_run=args.dry_run
    )
    logger.info("Done: %s", summary)

    if args.reingest and not args.dry_run:
        any_processed = any(
            r.get("status") == "processed" for r in summary.get("results", [])
        )
        if any_processed:
            count = reingest_library(settings)
            logger.info("Re-ingested %s documents into vector store", count)
        else:
            logger.info("No corpus patches applied; skip reingest")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
