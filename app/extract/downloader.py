"""
Module responsible for discovering, downloading and validating SNIES datasets.

This module scrapes the official SNIES portal to find the URLs of the required datasets (Docentes and
Estudiantes Matriculados for 2022–2024).  It downloads each file, performs basic validation and
saves it to the data/raw directory.  If discovery fails or a download fails validation, the module
will attempt to use a fallback URL provided in `app/config/sources.yml`.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
import openpyxl
import yaml

from ..utils.logger import get_logger


logger = get_logger(__name__)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
MANIFEST_PATH = Path(__file__).resolve().parents[2] / "logs" / "manifest.json"


def fetch_portal_links(base_url: str) -> Dict[str, str]:
    """Fetch the SNIES portal page and extract links to Excel files.

    Returns a mapping from the visible link text to the absolute URL.
    """
    logger.info(f"Fetching SNIES portal: {base_url}")
    resp = requests.get(base_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    link_map: Dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        # Consider only xlsx files
        if href.lower().endswith(".xlsx"):
            # Build absolute URL
            if href.startswith("http"):
                url = href
            else:
                url = requests.compat.urljoin(base_url, href)
            link_map[text] = url
    logger.info(f"Discovered {len(link_map)} xlsx links on portal")
    return link_map


def load_fallback_config() -> Dict[str, Dict[str, str]]:
    config_path = Path(__file__).resolve().parents[1] / "config" / "sources.yml"
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def get_dataset_name(dataset_type: str, year: int) -> str:
    # Build a string that we expect to see in the portal link text
    # The portal uses names like "Docentes_2024" or "Estudiantes_Matriculados_2024"
    if dataset_type == "docentes":
        return f"Docentes {year}"
    elif dataset_type == "matriculados":
        return f"Estudiantes Matriculados {year}"
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")


def download_file(url: str, dest: Path) -> Path:
    logger.info(f"Downloading {url}")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


def validate_xlsx(path: Path) -> bool:
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
        # Access first sheet
        _ = wb.sheetnames
        wb.close()
        return True
    except Exception as e:
        logger.warning(f"Validation failed for {path.name}: {e}")
        return False


def download_and_validate(dataset_type: str, year: int, base_url: str, fallback_cfg: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Attempt to download and validate a dataset for a given type and year.

    Returns a manifest record describing the outcome.
    """
    record = {
        "type": dataset_type,
        "year": year,
        "url": None,
        "status": "missing",
        "path": None,
        "size": 0,
    }
    dataset_name = get_dataset_name(dataset_type, year)
    # Discover links from portal
    try:
        link_map = fetch_portal_links(base_url)
    except Exception as e:
        logger.error(f"Failed to fetch portal: {e}")
        link_map = {}
    # Choose discovered URL if possible
    url = None
    for text, link in link_map.items():
        if dataset_name.lower() in text.lower():
            url = link
            break
    # Fallback
    if url is None:
        url = fallback_cfg.get(dataset_type, {}).get(str(year))
        if url:
            logger.info(f"Using fallback URL for {dataset_type} {year}: {url}")
    if not url:
        logger.error(f"No URL found for {dataset_name}")
        return record
    record["url"] = url
    # Download
    filename = f"{dataset_type}_{year}.xlsx"
    dest_path = DATA_DIR / filename
    try:
        download_file(url, dest_path)
    except Exception as e:
        logger.error(f"Download failed for {dataset_name}: {e}")
        record["status"] = "download_error"
        return record
    # Validate
    size = dest_path.stat().st_size
    record["size"] = size
    if size == 0:
        logger.error(f"File {filename} is empty")
        record["status"] = "empty_file"
        return record
    if not validate_xlsx(dest_path):
        record["status"] = "invalid_format"
        return record
    record["status"] = "validated"
    record["path"] = str(dest_path)
    logger.info(f"Downloaded and validated {filename} ({size} bytes)")
    return record


def run_downloader(years: List[int], base_url: str, dry_run: bool = False) -> List[Dict[str, str]]:
    fallback_cfg = load_fallback_config()
    manifest: List[Dict[str, str]] = []
    for dataset_type in ["docentes", "matriculados"]:
        for year in years:
            record = download_and_validate(dataset_type, year, base_url, fallback_cfg)
            manifest.append(record)
    # Save manifest
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Saved manifest to {MANIFEST_PATH}")
    if dry_run:
        logger.info("DRY_RUN_ONLY is true; skipping transformations and loading")
    return manifest
