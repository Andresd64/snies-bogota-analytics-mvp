"""
Entry point for the SNIES Bogotá Analytics MVP pipeline.

This script orchestrates the following steps:

1. Discover dataset URLs and download the six required files (docentes and matriculados for 2022–2024).
2. Validate each downloaded file and save a manifest.
3. If DRY_RUN_ONLY is set, exit after validation.
4. Transform the validated datasets into normalised DataFrames.
5. Create database schemas and tables.
6. Load the DataFrames into staging tables.
7. Aggregate counts and compute the student‑teacher ratio.
8. Create a view for BI consumption.

Environment variables control the behaviour of the pipeline; see `.env.example` for details.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .utils.logger import get_logger
from .extract.downloader import run_downloader
from .transform.students import transform_students
from .transform.teachers import transform_teachers
from .load.loader import create_schemas_and_tables, load_dataframe, compute_and_load_facts


logger = get_logger(__name__)


def main():
    # Configurable years; default to 2022–2024
    years_str = os.getenv("YEARS", "2022,2023,2024")
    years: List[int] = [int(y.strip()) for y in years_str.split(",") if y.strip().isdigit()]
    base_url = os.getenv("SNIES_BASE_URL", "https://snies.mineducacion.gov.co/portal/ESTADISTICAS/Bases-consolidadas/")
    dry_run = os.getenv("DRY_RUN_ONLY", "false").lower() == "true"
    strict = os.getenv("STRICT_REQUIRED_FILES", "true").lower() == "true"

    logger.info(f"Starting pipeline for years {years} (dry_run={dry_run}, strict={strict})")
    manifest = run_downloader(years, base_url, dry_run=dry_run)

    if dry_run:
        logger.info("Dry run complete; exiting before transform and load.")
        return

    # Check required files
    errors = [m for m in manifest if m.get("status") != "validated"]
    if errors and strict:
        logger.error(f"Missing or invalid required files: {[e['type'] + '_' + str(e['year']) for e in errors]}")
        sys.exit(1)
    # Proceed with available files (if strict is false we might skip missing)

    # Transform
    students_frames: List[pd.DataFrame] = []
    teachers_frames: List[pd.DataFrame] = []
    for rec in manifest:
        if rec.get("status") != "validated":
            logger.warning(f"Skipping {rec['type']} {rec['year']} due to status {rec['status']}")
            continue
        path = Path(rec["path"])
        if rec["type"] == "matriculados":
            df_students = transform_students(path, years)
            if not df_students.empty:
                students_frames.append(df_students)
        elif rec["type"] == "docentes":
            df_teachers = transform_teachers(path, years)
            if not df_teachers.empty:
                teachers_frames.append(df_teachers)
    # Concatenate
    students_df = pd.concat(students_frames, ignore_index=True) if students_frames else pd.DataFrame()
    teachers_df = pd.concat(teachers_frames, ignore_index=True) if teachers_frames else pd.DataFrame()

    if strict and (students_df.empty or teachers_df.empty):
        logger.error("Required data is missing after transformation")
        sys.exit(1)

    # Create DB objects
    create_schemas_and_tables()
    # Load into staging
    load_dataframe(students_df, "staging.students")
    load_dataframe(teachers_df, "staging.teachers")
    # Compute and load fact table and view
    compute_and_load_facts()
    logger.info("Pipeline completed successfully")


if __name__ == "__main__":
    main()
