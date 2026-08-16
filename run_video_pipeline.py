"""
Video Pipeline Runner - Part 2: Video Generation & Packaging (1Video10Sec)
==========================================================================
Executes the next production-ready Level 10 video generation and packaging.

Usage:
  python run_video_pipeline.py            (Process next ready Level 10 video)
  python run_video_pipeline.py --all      (Loop through and process all available videos)
"""

import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline_packager import run_next_level10_package, run_all_level10_packaging_loop


def main():
    parser = argparse.ArgumentParser(description="Video Pipeline Runner (1Video10Sec)")
    parser.add_argument("--all", action="store_true", help="Process all available ideas")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser launch for fast execution")
    args = parser.parse_args()

    if args.all:
        run_all_level10_packaging_loop(skip_browser=args.skip_browser)
    else:
        run_next_level10_package(skip_browser=args.skip_browser)


if __name__ == "__main__":
    main()
