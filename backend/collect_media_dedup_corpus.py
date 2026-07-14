import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from app.media.benchmark_corpus_collector import BenchmarkCorpusCollector


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a labeled Wikimedia corpus.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--pairs-per-category", type=int, default=100)
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--ffmpeg-path")
    arguments = parser.parse_args()
    userAgent = os.getenv("WIKIMEDIA_USER_AGENT")
    if not userAgent:
        parser.error("WIKIMEDIA_USER_AGENT is required.")
    manifest, provenance = asyncio.run(
        BenchmarkCorpusCollector(
            userAgent,
            os.getenv("PEXELS_API_KEY"),
            os.getenv("PIXABAY_API_KEY"),
            arguments.ffmpeg_path,
        ).collect(
            arguments.output.resolve(),
            arguments.pairs_per_category,
            tuple(arguments.categories) if arguments.categories else None,
        )
    )
    json.dump(
        {"manifest": str(manifest), "provenance": str(provenance)},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
