"""
CLI entrypoint for the ingestion pipeline.

Usage:
  # Ingest all collections
  uv run python -m ingestion

  # Ingest specific collections only
  uv run python -m ingestion --collections clinical nursing

  # Point to a different data directory
  uv run python -m ingestion --data-dir /path/to/data
"""
import argparse
from pathlib import Path

from ingestion.pipeline import run_ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="MediBot ingestion pipeline")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Root data directory (default: ./data)",
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        choices=["general", "clinical", "nursing", "billing", "equipment"],
        default=None,
        help="Which collections to ingest (default: all)",
    )
    args = parser.parse_args()
    run_ingestion(data_dir=args.data_dir, collections=args.collections)


if __name__ == "__main__":
    main()
