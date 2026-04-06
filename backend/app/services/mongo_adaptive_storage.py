from __future__ import annotations

from functools import lru_cache
from typing import Any

from pymongo.errors import PyMongoError
from scrapling.core.storage import StorageSystemMixin
from scrapling.core.utils import _StorageTools

from .database import get_database, utc_now


ADAPTIVE_ELEMENT_COLLECTION_NAME = "adaptive_elements"


@lru_cache(64, typed=True)
class MongoAdaptiveStorageSystem(StorageSystemMixin):
    def __init__(self, url: str | None = None):
        super().__init__(url)
        self.collection = None
        self.disabled = False

        try:
            collection = get_database()[ADAPTIVE_ELEMENT_COLLECTION_NAME]
            collection.create_index([("url", 1), ("identifier", 1)], unique=True)
            collection.create_index("updatedAt")
            self.collection = collection
        except PyMongoError:
            self.disabled = True

    def save(self, element, identifier: str) -> None:
        if self.disabled or self.collection is None:
            return None

        url = self._get_base_url()
        element_data = _StorageTools.element_to_dict(element)
        now = utc_now()
        try:
            self.collection.update_one(
                {"url": url, "identifier": identifier},
                {
                    "$set": {
                        "url": url,
                        "identifier": identifier,
                        "elementData": element_data,
                        "updatedAt": now,
                    },
                    "$setOnInsert": {
                        "createdAt": now,
                    },
                },
                upsert=True,
            )
        except PyMongoError:
            self.disabled = True

    def retrieve(self, identifier: str) -> dict[str, Any] | None:
        if self.disabled or self.collection is None:
            return None

        url = self._get_base_url()
        try:
            document = self.collection.find_one({"url": url, "identifier": identifier})
        except PyMongoError:
            self.disabled = True
            return None
        if not isinstance(document, dict):
            return None
        element_data = document.get("elementData")
        return element_data if isinstance(element_data, dict) else None
