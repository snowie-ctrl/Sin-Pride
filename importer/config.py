"""
Every setting the importer reads. The admin address and token come from .env, which is never committed; the rest are
plain constants, so a change to one is reviewed in git like any other code. Other modules read these as config.NAME
when they run, never with `from config import NAME`, so the tests can repoint every folder and mode in one place.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SOURCES_FILE = BASE_DIR / "sources.json"
RULES_DIR = BASE_DIR / "rules"
CACHE_DIR = BASE_DIR / "cache"          # git-ignored: each source's files at its pinned commit
REPORT_DIR = BASE_DIR / "reports"       # git-ignored: each run's change report and the normalised catalog

ADMIN_BASE = os.getenv("ADMIN_BASE", "").strip().rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
PUBLISH = os.getenv("PUBLISH", "dry").strip()   # "on" publishes; anything else is a dry run

HIDE_GUARD = 0.10                       # more than this share of the catalog hidden stops the import (spec §8)
PARALLEL = 4                            # pictures fetched at once
