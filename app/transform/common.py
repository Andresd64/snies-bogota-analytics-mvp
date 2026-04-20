"""Common transformation utilities for SNIES datasets."""

import pandas as pd
from pathlib import Path
from typing import List
from ..utils.logger import get_logger


logger = get_logger(__name__)


def read_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, dtype=str)


def normalise_column(name: str) -> str:
    """Normalise column names by removing accents, converting to lower case and replacing spaces with underscores."""
    import unicodedata
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    return only_ascii.lower().strip().replace(' ', '_')


def standardise_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: normalise_column(c) for c in df.columns})
    return df


def filter_bogota_years(df: pd.DataFrame, year_col: str, city_col: str, years: List[int]) -> pd.DataFrame:
    df[year_col] = df[year_col].astype(int)
    df = df[df[year_col].isin(years)]
    # Normalise city names to ensure Bogota detection
    return df[df[city_col].str.contains('bogota', case=False, na=False)]
