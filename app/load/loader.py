"""Database loading and aggregation logic."""

from typing import Any, Iterable
import psycopg2
import psycopg2.extras
from pandas import DataFrame
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.db import get_conn, run_sql_file


logger = get_logger(__name__)


SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def create_schemas_and_tables():
    """Run SQL scripts to create schemas, tables and views."""
    logger.info("Creating database schemas and tables")
    run_sql_file(SQL_DIR / "001_create_schemas.sql")
    run_sql_file(SQL_DIR / "002_create_tables.sql")
    # Views will be created after facts are loaded


def load_dataframe(df: DataFrame, table: str):
    """Load a pandas DataFrame into a PostgreSQL table using execute_values."""
    if df.empty:
        logger.warning(f"Skipping load for {table}, no rows.")
        return
    cols = list(df.columns)
    values: Iterable[Iterable[Any]] = df.itertuples(index=False, name=None)
    insert_query = f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Truncate before insert to ensure idempotency
            cur.execute(f"TRUNCATE {table}")
            psycopg2.extras.execute_values(cur, insert_query, values, page_size=1000)
        logger.info(f"Inserted {len(df)} rows into {table}")
    finally:
        conn.close()


def compute_and_load_facts():
    """Aggregate staging tables and load into analytics.fact_ies_year."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Truncate fact table
            cur.execute("TRUNCATE analytics.fact_ies_year")
            # Insert aggregated data
            cur.execute(
                """
                INSERT INTO analytics.fact_ies_year (year, ies_code, ies_name, sede_city, students, teachers, student_teacher_ratio)
                SELECT
                    s.year,
                    s.ies_code,
                    s.ies_name,
                    s.sede_city,
                    SUM(s.count_students) AS students,
                    SUM(t.count_teachers) AS teachers,
                    CASE WHEN SUM(t.count_teachers) > 0 THEN SUM(s.count_students)::NUMERIC / SUM(t.count_teachers) ELSE NULL END AS ratio
                FROM staging.students s
                JOIN staging.teachers t ON s.year = t.year AND s.ies_code = t.ies_code
                GROUP BY s.year, s.ies_code, s.ies_name, s.sede_city
                ORDER BY s.ies_code, s.year;
                """
            )
            logger.info("Populated analytics.fact_ies_year")
            # Create/update view
            run_sql_file(SQL_DIR / "003_create_views.sql")
            logger.info("Created/updated analytics.mart_student_teacher_ratio view")
    finally:
        conn.close()
