from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    return MongoClient(uri, tz_aware=True)


def get_database() -> Database:
    database_name = os.getenv("MONGODB_DB_NAME", "acrtech_ai_marketer")
    return get_mongo_client()[database_name]


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower()
    return normalized or None
