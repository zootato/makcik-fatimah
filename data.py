"""
Data layer – fetches, caches, and queries the Singapore halal establishments dataset.
Geocodes addresses via OneMap API (free, no key needed).
"""

import asyncio
import json
import logging
import math
import random
import re
import os
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

GEOCACHE_FILE = "geocache.json"

# ─── Area boundaries (rough lat/lon boxes for Singapore regions) ───────────────
AREA_BOUNDS = {
    "central":    {"lat_min": 1.270, "lat_max": 1.330, "lon_min": 103.815, "lon_max": 103.870},
    "east":       {"lat_min": 1.300, "lat_max": 1.380, "lon_min": 103.870, "lon_max": 103.965},
    "west":       {"lat_min": 1.290, "lat_max": 1.390, "lon_min": 103.660, "lon_max": 103.785},
    "north":      {"lat_min": 1.380, "lat_max": 1.470, "lon_min": 103.770, "lon_max": 103.845},
    "northeast":  {"lat_min": 1.350, "lat_max": 1.420, "lon_min": 103.845, "lon_max": 103.960},
}

# ─── Cuisine keyword mapping ───────────────────────────────────────────────────
CUISINE_KEYWORDS = {
    "malay":          ["malay", "nasi lemak", "nasi padang", "melayu", "nasi", "mee", "mie"],
    "indian":         ["indian", "mamak", "biryani", "roti prata", "thosai", "dosa", "curry", "briyani"],
    "chinese":        ["chinese", "dim sum", "halal chinese", "muslim chinese", "wonton", "char kway"],
    "western":        ["western", "burger", "steak", "pasta", "pizza", "cafe", "coffee", "sandwich"],
    "middle_eastern": ["middle eastern", "arab", "kebab", "shawarma", "turkish", "lebanese", "mediterranean"],
    "japanese":       ["japanese", "sushi", "ramen", "donburi", "bento", "udon", "soba"],
    "korean":         ["korean", "bbq", "kimchi", "tteok", "bulgogi"],
    "thai":           ["thai", "tomyum", "pad thai", "thai milk tea"],
    "indonesian":     ["indonesian", "padang", "rendang", "ayam penyet", "indomie"],
}

# ─── Field mapping ────────────────────────────────────────────────────────────
FIELD_MAP = {
    "name":       ["name", "organisation_name", "establishment_name", "title", "outletName"],
    "address":    ["address", "full_address", "location", "addressLine"],
    "latitude":   ["latitude", "lat", "y", "LATITUDE"],
    "longitude":  ["longitude", "lng", "lon", "x", "LONGITUDE"],
    # NOTE: "type" in source data = Hawker/Eating Establishment, NOT cuisine — excluded intentionally
    "cuisine":    ["cuisine", "cuisine_type", "food_type", "category", "businessType"],
    "halal_type": ["scheme", "halal_type", "license_type", "cert_type", "certification"],
    "postal_code":["postal", "postal_code", "postcode", "postalCode"],
    "area":       ["area", "region", "zone", "planning_area"],
}


@dataclass
class Establishment:
    name: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cuisine: str = ""
    halal_type: str = ""
    postal_code: str = ""
    area: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def has_coords(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def inferred_area(self) -> str:
        if self.area:
            return self.area.lower()
        if not self.has_coords:
            return "unknown"
        for area_name, bounds in AREA_BOUNDS.items():
            if (bounds["lat_min"] <= self.latitude <= bounds["lat_max"] and
                    bounds["lon_min"] <= self.longitude <= bounds["lon_max"]):
                return area_name
        return "other"

    @property
    def halal_cert_display(self) -> str:
        ht = self.halal_type.lower()
        if "muis" in ht or "certified" in ht:
            return "MUIS Certified"
        if "muslim" in ht:
            return "Muslim-Owned"
        if "eating establishment" in ht or "hawker" in ht or "food preparation" in ht:
            return "MUIS Certified"
        if ht:
            return f"📋 {self.halal_type}"
        return "⚠️ Check yourself"


def _extract_field(record: dict, canonical: str):
    for possible_key in FIELD_MAP.get(canonical, []):
        if possible_key in record and record[possible_key] is not None:
            return record[possible_key]
    return None


def _parse_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _normalise(record: dict) -> Establishment:
    name = _extract_field(record, "name") or "Unknown Establishment"
    address = _extract_field(record, "address") or "Address not available"
    lat = _parse_float(_extract_field(record, "latitude"))
    lon = _parse_float(_extract_field(record, "longitude"))
    cuisine = str(_extract_field(record, "cuisine") or "")
    halal_type = str(_extract_field(record, "halal_type") or "")
    postal = str(_extract_field(record, "postal_code") or "")
    area = str(_extract_field(record, "area") or "")

    return Establishment(
        name=name, address=address, latitude=lat, longitude=lon,
        cuisine=cuisine, halal_type=halal_type, postal_code=postal,
        area=area, raw=record,
    )


def _clean_address_for_geocoding(address: str, postal: str) -> str:
    """Use postal code if available — far more reliable with OneMap."""
    if postal and len(postal) == 6 and postal.isdigit():
        return f"Singapore {postal}"
    # Strip stall/unit info and just use the building + street
    clean = re.sub(r'\b(stall|mr\d+|s\d+|#[\w-]+)\b', '', address, flags=re.IGNORECASE)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Geocoding ────────────────────────────────────────────────────────────────

def _load_geocache() -> dict:
    """Load cached coordinates from disk."""
    if os.path.exists(GEOCACHE_FILE):
        try:
            with open(GEOCACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_geocache(cache: dict):
    """Save coordinates cache to disk."""
    try:
        with open(GEOCACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning("Could not save geocache: %s", e)


async def _geocode_onemap(
    session: aiohttp.ClientSession,
    address: str,
    sem: asyncio.Semaphore,
) -> Optional[tuple[float, float]]:
    """Geocode a single address via OneMap. Returns (lat, lon) or None."""
    async with sem:
        try:
            url = "https://www.onemap.gov.sg/api/common/elastic/search"
            params = {
                "searchVal": address,
                "returnGeom": "Y",
                "getAddrDetails": "N",
                "pageNum": 1,
            }
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("results", [])
                if results:
                    return float(results[0]["LATITUDE"]), float(results[0]["LONGITUDE"])
        except Exception:
            pass
        return None


async def _geocode_all(establishments: list[Establishment]):
    """
    Geocode all establishments missing coordinates.
    Uses a disk cache so addresses are only looked up once ever.
    Runs up to 10 requests concurrently.
    """
    cache = _load_geocache()
    missing = [e for e in establishments if not e.has_coords]

    if not missing:
        logger.info("All establishments already have coordinates.")
        return

    logger.info("Geocoding %d establishments (this may take a moment)...", len(missing))

    sem = asyncio.Semaphore(10)
    cache_hits = 0
    to_fetch: list[tuple[Establishment, str]] = []

    for e in missing:
        key = _clean_address_for_geocoding(e.address, e.postal_code)
        if key in cache:
            coords = cache[key]
            if coords:
                e.latitude, e.longitude = coords
            cache_hits += 1
        else:
            to_fetch.append((e, key))

    logger.info("Cache hits: %d | Need to fetch: %d", cache_hits, len(to_fetch))

    if not to_fetch:
        return

    async with aiohttp.ClientSession() as session:
        tasks = [_geocode_onemap(session, key, sem) for _, key in to_fetch]
        results = await asyncio.gather(*tasks)

    new_hits = 0
    for (e, key), result in zip(to_fetch, results):
        if result:
            e.latitude, e.longitude = result
            cache[key] = list(result)
            new_hits += 1
        else:
            cache[key] = None  # Cache misses too so we don't retry forever

    _save_geocache(cache)

    total_with_coords = sum(1 for e in establishments if e.has_coords)
    logger.info(
        "Geocoding done. New hits: %d | Total with coords: %d/%d",
        new_hits, total_with_coords, len(establishments)
    )


# ─── Main data class ──────────────────────────────────────────────────────────

class HalalData:
    def __init__(self, source_url: str, refresh_interval: int = 3600):
        self.source_url = source_url
        self.refresh_interval = refresh_interval
        self.establishments: list[Establishment] = []
        self._lock = asyncio.Lock()

    async def refresh(self) -> int:
        logger.info("Fetching halal data from %s", self.source_url)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.source_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.error("Data source returned status %d", resp.status)
                        return len(self.establishments)
                    raw = await resp.text()

            data = json.loads(raw)
            if isinstance(data, dict):
                for key in ("data", "results", "establishments", "records", "items"):
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                else:
                    if not isinstance(data, list):
                        logger.error("Cannot find list in JSON. Keys: %s", list(data.keys())[:10])
                        return len(self.establishments)

            records: list[dict] = data if isinstance(data, list) else []

            async with self._lock:
                self.establishments = [_normalise(r) for r in records]

            logger.info("Loaded %d establishments", len(self.establishments))

            # Geocode missing coords (uses cache, fast on subsequent runs)
            await _geocode_all(self.establishments)

            return len(self.establishments)

        except Exception:
            logger.exception("Failed to fetch/parse halal data")
            return len(self.establishments)

    async def auto_refresh(self, application):
        while True:
            await asyncio.sleep(self.refresh_interval)
            count = await self.refresh()
            logger.info("Auto-refresh: %d establishments loaded", count)

    # ── Query methods ─────────────────────────────────────────────────────

    def get_random(self, count: int = 1) -> list[Establishment]:
        if not self.establishments:
            return []
        return random.sample(self.establishments, min(count, len(self.establishments)))

    def filter_by_cuisine(self, cuisine_key: str) -> list[Establishment]:
        keywords = CUISINE_KEYWORDS.get(cuisine_key, [cuisine_key.lower()])
        results = []
        for e in self.establishments:
            # Search name + address since source data has no cuisine field
            text = f"{e.name} {e.address}".lower()
            if any(kw in text for kw in keywords):
                results.append(e)
        return results

    def filter_by_area(self, area_key: str) -> list[Establishment]:
        return [e for e in self.establishments if e.inferred_area == area_key]

    def query(
        self,
        cuisine: Optional[str] = None,
        area: Optional[str] = None,
        muis_only: bool = False,
    ) -> list[Establishment]:
        pool = list(self.establishments)

        if cuisine and cuisine != "any":
            cuisine_set = set(e.name for e in self.filter_by_cuisine(cuisine))
            pool = [e for e in pool if e.name in cuisine_set]

        if area and area != "any":
            pool = [e for e in pool if e.inferred_area == area]

        if muis_only:
            pool = [
                e for e in pool
                if "muis" in e.halal_type.lower()
                or "certified" in e.halal_type.lower()
                or "eating establishment" in e.halal_type.lower()
                or "food preparation" in e.halal_type.lower()
                or not e.halal_type
            ]

        return pool

    def nearby(
        self,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
        max_results: int = 5,
    ) -> list[tuple[Establishment, float]]:
        results = []
        for e in self.establishments:
            if not e.has_coords:
                continue
            dist = haversine_km(lat, lon, e.latitude, e.longitude)
            if dist <= radius_km:
                results.append((e, dist))
        results.sort(key=lambda x: x[1])
        return results[:max_results]

    def search_text(self, query: str, max_results: int = 5) -> list[Establishment]:
        q = query.lower().strip()
        if not q:
            return []
        scored = []
        for e in self.establishments:
            text = f"{e.name} {e.cuisine} {e.address}".lower()
            if q in text:
                score = 0
                if q in e.name.lower():
                    score += 3
                if q in e.cuisine.lower():
                    score += 2
                if q in e.address.lower():
                    score += 1
                scored.append((e, score))
        scored.sort(key=lambda x: -x[1])
        return [e for e, _ in scored[:max_results]]

    @property
    def total_count(self) -> int:
        return len(self.establishments)