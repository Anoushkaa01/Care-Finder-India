import ast
import json
import math
import os
import re
from html import escape
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd
import pydeck as pdk
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

try:
    from streamlit_geolocation import streamlit_geolocation
except ImportError:
    streamlit_geolocation = None

# ============================================================
# CARE FINDER INDIA — UI 7.8
# Patient-friendly dark interface, explainable dataset search
# ============================================================

st.set_page_config(
    page_title="Care Finder India",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

VERSION = "UI 7.8"
TABLE = os.getenv("UC_TABLE_NAME", "workspace.default.care_finder_facilities")
RADIUS_KM = 60

SERVICES = [
    "Dialysis", "NICU", "MRI", "Trauma Care", "Burn Care",
    "General Emergency", "Emergency C-section",
]
EMERGENCY_SERVICES = ["General Emergency", "Trauma Care", "Emergency C-section"]
NAV_OPTIONS = [
    "Find Hospitals & Care", "View Hospitals on Map", "Compare Hospitals",
    "Find Emergency Care", "How It Works",
]

# Approximate city reference points; not facility-location verification.
CITY_CENTERS = {
    "patna": (25.5941, 85.1376), "hajipur": (25.6858, 85.2095),
    "jaipur": (26.9124, 75.7873), "lucknow": (26.8467, 80.9462),
    "unnao": (26.5471, 80.4878), "pune": (18.5204, 73.8567),
    "badlapur": (19.1552, 73.2655), "ahmedabad": (23.0225, 72.5714),
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090),
    "noida": (28.5355, 77.3910), "ghaziabad": (28.6692, 77.4538),
    "hyderabad": (17.3850, 78.4867), "mumbai": (19.0760, 72.8777),
    "moradabad": (28.8386, 78.7733), "azamgarh": (26.0686, 83.1836),
}
CITY_STATES = {
    "patna": "bihar", "hajipur": "bihar", "jaipur": "rajasthan",
    "lucknow": "uttar pradesh", "unnao": "uttar pradesh",
    "pune": "maharashtra", "badlapur": "maharashtra",
    "ahmedabad": "gujarat", "delhi": "delhi", "new delhi": "delhi",
    "noida": "uttar pradesh", "ghaziabad": "uttar pradesh",
    "hyderabad": "telangana", "mumbai": "maharashtra",
    "moradabad": "uttar pradesh", "azamgarh": "uttar pradesh",
}
EVIDENCE_FIELDS = ("evidence_list", "procedure_list", "capability_list")
FIELD_LABELS = {
    "evidence_list": "General information",
    "procedure_list": "Procedures recorded",
    "capability_list": "Services recorded",
}

VALID_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand",
    "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
    "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal",
    "andaman and nicobar islands", "chandigarh",
    "dadra and nagar haveli and daman and diu", "delhi",
    "jammu and kashmir", "ladakh", "lakshadweep", "puducherry",
}
STATE_ALIASES = {
    "up": "uttar pradesh", "u.p": "uttar pradesh",
    "mp": "madhya pradesh", "m.p": "madhya pradesh",
    "mh": "maharashtra", "tn": "tamil nadu", "wb": "west bengal",
    "orissa": "odisha", "uttaranchal": "uttarakhand",
    "nct of delhi": "delhi", "new delhi": "delhi",
    "j&k": "jammu and kashmir", "pondicherry": "puducherry",
}
INVALID_CITY_NAMES = {
    "unknown", "none", "null", "nan", "na", "n a", "not available",
    "not specified", "india", "other", "hospital", "clinic", "dentistry",
    "internalmedicine", "emergency", "dialysis", "mri", "nicu",
}

# ============================================================
# 1. PRESENTATION — dark mode only
# ============================================================

def apply_dark_theme():
    st.markdown("""
    <style>
    :root { color-scheme: dark; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: #120f1d !important; color: #f5f1ff !important;
    }
    [data-testid="stSidebar"] { background: #281b48 !important; }
    [data-testid="stSidebar"] * { color: #f5f1ff; }
    .block-container { padding-top: 1.7rem; padding-bottom: 3rem; max-width: 1450px; }
    .hero { background: linear-gradient(115deg,#382062,#7350b6); border-radius:18px;
            padding:29px; margin-bottom:22px; color:white; }
    .hero h1 { color:white !important; margin:0 0 9px; font-size:33px; }
    .hero p { color:#eee7ff !important; margin:0; font-size:15px; }
    .mini-card { background:#211a32; border:1px solid #413653; border-radius:15px;
                 padding:18px; margin-bottom:12px; min-height:115px; }
    .mini-label { color:#c1b8d5; font-size:12px; font-weight:650; text-transform:uppercase; }
    .mini-number { color:white; font-size:25px; font-weight:750; margin:5px 0; }
    .mini-note { color:#bab0cd; font-size:12px; }
    [data-testid="stMetricValue"] { color:#f5f1ff !important; }
    [data-testid="stMetricLabel"] { color:#c4bad5 !important; }
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
        background:#191523 !important; color:#f5f1ff !important; border-color:#514367 !important;
    }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {
        background:#191523 !important; color:#f5f1ff !important;
    }
    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background:#ff4b55 !important; color:white !important;
        border:1px solid #ff4b55 !important; font-weight:650;
    }
    [data-testid="stAlert"], [data-testid="stExpander"] { border-radius:12px; }
    .compare-intro { background:#211a32; border:1px solid #413653;
                     border-radius:15px; padding:17px; margin-bottom:15px; }
    .compare-intro p { color:#cbc2dc; margin:0; }
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(
        f'<div class="hero"><h1>{escape(str(title))}</h1>'
        f'<p>{escape(str(subtitle))}</p></div>', unsafe_allow_html=True,
    )


def stat(label, value, note):
    st.markdown(
        f'<div class="mini-card"><div class="mini-label">{escape(str(label))}</div>'
        f'<div class="mini-number">{escape(str(value))}</div>'
        f'<div class="mini-note">{escape(str(note))}</div></div>',
        unsafe_allow_html=True,
    )


def distance_note():
    st.caption("Distances are approximate straight-line estimates. Actual travel distance may be longer.")


def safety_note():
    st.info(
        "These are possible care options based on recorded information. "
        "Services and current availability have not been confirmed. Contact facilities directly."
    )

# ============================================================
# 2. DATABRICKS AND RECORDS
# ============================================================

def table_name():
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+){2}", TABLE):
        raise ValueError("UC_TABLE_NAME must be catalog.schema.table")
    return TABLE


def query_rows(query, args=()):
    cfg = Config()
    host = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
    warehouse = os.environ["DATABRICKS_WAREHOUSE_ID"]
    with sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{warehouse}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, list(args))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


FIELDS = """
unique_id, name, address_line1, address_city, address_stateOrRegion,
address_zipOrPostcode, phone_numbers, location_status,
latitude, longitude, evidence_list, procedure_list, capability_list,
source_urls_list, officialWebsite, repeated_name
"""


@st.cache_data(ttl=3600, show_spinner=False)
def cities_from_table():
    return query_rows(f"""
        SELECT TRIM(address_city) AS city,
               TRIM(address_stateOrRegion) AS state,
               COUNT(*) AS facility_count
        FROM {table_name()}
        WHERE address_city IS NOT NULL AND address_stateOrRegion IS NOT NULL
          AND TRIM(address_city) <> '' AND TRIM(address_stateOrRegion) <> ''
        GROUP BY TRIM(address_city), TRIM(address_stateOrRegion)
    """)


@st.cache_data(ttl=1800, show_spinner=False)
def nearby_rows(lat, lon, radius=RADIUS_KM):
    lat_delta = radius / 110.57
    lon_delta = radius / max(20, 111.32 * math.cos(math.radians(lat)))
    return query_rows(f"""
        SELECT {FIELDS} FROM {table_name()}
        WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
    """, [lat-lat_delta, lat+lat_delta, lon-lon_delta, lon+lon_delta])


@st.cache_data(ttl=1800, show_spinner=False)
def city_rows_raw(raw_pairs):
    """Use original database city/state variants, never cleaned display strings."""
    if not raw_pairs:
        return []
    pairs = tuple(raw_pairs)[:50]
    predicates = " OR ".join(
        ["(LOWER(TRIM(address_city)) = ? AND LOWER(TRIM(address_stateOrRegion)) = ?)"]
        * len(pairs)
    )
    args = [value for city, state in pairs for value in (city.lower(), state.lower())]
    return query_rows(
        f"SELECT {FIELDS} FROM {table_name()} WHERE {predicates}", args,
    )

# ============================================================
# 3. DATA HELPERS
# ============================================================

def _quoted_list_fallback(text):
    """Recover separate quoted items only when list syntax is recognizable.

    Do not split on commas: clinical descriptions may contain commas.
    If structural parsing is uncertain, return None and exclude the blob.
    """
    if not (text.startswith("[") and text.endswith("]")):
        return None

    inside = text[1:-1].strip()
    if not inside:
        return []

    token = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")
    matches = list(token.finditer(inside))
    if not matches:
        return None

    leftovers = token.sub("", inside)
    if leftovers.strip(" \t\r\n,"):
        return None

    values = []
    for match in matches:
        part = match.group(0)
        decoded = None
        for parser in (json.loads, ast.literal_eval):
            try:
                decoded = parser(part)
                break
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
        if not isinstance(decoded, str):
            return None
        values.append(decoded)
    return values


def parse_list(value):
    """Flatten real arrays, JSON/Python lists and double-encoded lists.

    Reject malformed array-looking blobs rather than treating them as
    a service statement; a giant list must never create a false match.
    """
    output = []

    def visit(obj, depth=0):
        if depth > 6 or obj is None or len(output) >= 500:
            return
        if isinstance(obj, (list, tuple, set)):
            for part in obj:
                visit(part, depth + 1)
            return
        if not isinstance(obj, str):
            return

        text = obj.strip()
        if not text or text.casefold() in {"none", "null", "nan"}:
            return

        # Try again after decoding a layer; some SQL connector values
        # are a JSON string whose contents are another JSON array.
        if text.startswith(("[", "\"[", "'[")):
            for parser in (json.loads, ast.literal_eval):
                try:
                    decoded = parser(text)
                except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                    continue
                if decoded != obj:
                    visit(decoded, depth + 1)
                    return

            recovered = _quoted_list_fallback(text)
            if recovered is not None:
                visit(recovered, depth + 1)
                return

            # Unparsed list-like text must not be treated as one claim.
            return

        # Long aggregated claims are not safe evidence for ranking.
        if len(text) > 650:
            return
        output.append(text)

    visit(value)
    return output


def normalize_text(value):
    text = str(value or "")
    for old, new in (("×", "x"), ("✕", "x"), ("–", "-"), ("—", "-"), ("\u00a0", " ")):
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def claim_key(text):
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(text).casefold()).strip()


def evidence_items(row):
    unique = {}
    for field in EVIDENCE_FIELDS:
        for claim in parse_list(row.get(field)):
            text = normalize_text(claim)
            key = claim_key(text)
            if not key:
                continue
            if key not in unique:
                unique[key] = {"text": text, "fields": [field]}
            elif field not in unique[key]["fields"]:
                unique[key]["fields"].append(field)
    return list(unique.values())


def source_urls(value):
    """Normalize duplicate URLs; cap output for readability."""
    unique = {}
    for entry in parse_list(value):
        for link in re.findall(r"https?://[^\s,)\]\"']+", entry):
            link = link.rstrip(".>;,')")
            parsed = urlparse(link)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            # Equivalent URLs with different trailing slash/case are one link.
            key = (parsed.netloc.lower().removeprefix("www.")
                   + parsed.path.rstrip("/").lower()
                   + ("?" + parsed.query if parsed.query else ""))
            unique.setdefault(key, link)
    return list(unique.values())[:8]


# ============================================================
# 4. LOCATION — clean display labels, keep real database values
# ============================================================

def coordinates(row):
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if all(map(math.isfinite, (lat, lon))) and 6 <= lat <= 38 and 68 <= lon <= 98:
            return (lat, lon)
    except (ValueError, TypeError, KeyError):
        pass
    return None


def distance_km(p, q):
    lat1, lon1 = map(math.radians, p)
    lat2, lon2 = map(math.radians, q)
    a = (math.sin((lat2-lat1)/2)**2
         + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)
    return 6371 * 2 * math.asin(min(1, math.sqrt(a)))


def clean_city_name(value):
    city = normalize_text(value).strip(" ,.;:'\"[]")
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,59}", city):
        return None
    city = re.sub(r"\s+", " ", city).strip()
    if city.casefold() in INVALID_CITY_NAMES:
        return None
    return city.title()


def clean_state_name(value):
    state = normalize_text(value).strip(" ,.;:'\"[]").casefold()
    state = re.sub(r"\s+", " ", state)
    state = STATE_ALIASES.get(state, state)
    return state.title() if state in VALID_STATES else None


def build_clean_locations(city_data):
    """One displayed option per clean city/state, with original raw variants attached."""
    grouped = {}
    for row in city_data:
        raw_city, raw_state = row.get("city"), row.get("state")
        city = clean_city_name(raw_city)
        state = clean_state_name(raw_state)
        if not city:
            continue
        known_state = CITY_STATES.get(city.casefold())
        if not state:
            continue
        if known_state:
            expected = known_state.title()
            if state != expected:
                continue
            state = expected
        label = f"{city}, {state}"
        if label not in grouped:
            grouped[label] = {"city": city, "state": state, "raw_pairs": []}
        pair = (str(raw_city).strip(), str(raw_state).strip())
        if pair not in grouped[label]["raw_pairs"]:
            grouped[label]["raw_pairs"].append(pair)
    # Keep immutable pairs for cacheability and Streamlit session state.
    return {
        label: {"city": value["city"], "state": value["state"],
                "raw_pairs": tuple(value["raw_pairs"])}
        for label, value in sorted(grouped.items(), key=lambda it: it[0].casefold())
    }


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_address(address):
    """Geoapify search. Only accept results within India."""
    key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    if not key:
        raise ValueError("Address search requires GEOAPIFY_API_KEY.")
    params = urlencode({"text": address, "filter": "countrycode:in",
                        "format": "json", "limit": 3, "apiKey": key})
    request = Request("https://api.geoapify.com/v1/geocode/search?"+params,
                      headers={"User-Agent": "CareFinderIndia/7.8"})
    try:
        with urlopen(request, timeout=12) as response:
            matches = json.load(response).get("results", [])
    except Exception as exc:
        raise ValueError("Location lookup could not be completed.") from exc
    for item in matches:
        try:
            point = (float(item["lat"]), float(item["lon"]))
            country = str(item.get("country_code", "")).casefold()
            if 6 <= point[0] <= 38 and 68 <= point[1] <= 98 and country == "in":
                return point, item.get("formatted", address)
        except (KeyError, ValueError, TypeError):
            pass
    raise ValueError("No sufficiently clear Indian location was found.")


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_city(city, state):
    """A city geocoder, not a hospital location verification service."""
    key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    if not key:
        return None
    params = urlencode({"city": city, "state": state, "country": "India",
                        "filter": "countrycode:in", "format": "json",
                        "limit": 5, "apiKey": key})
    request = Request("https://api.geoapify.com/v1/geocode/search?"+params,
                      headers={"User-Agent": "CareFinderIndia/7.8"})
    try:
        with urlopen(request, timeout=12) as response:
            matches = json.load(response).get("results", [])
    except Exception:
        return None
    for item in matches:
        try:
            returned_city = normalize_text(item.get("city", "")).casefold()
            returned_state = clean_state_name(item.get("state", ""))
            point = (float(item["lat"]), float(item["lon"]))
            if (returned_city == city.casefold() and returned_state
                    and returned_state.casefold() == state.casefold()
                    and str(item.get("country_code", "")).casefold() == "in"
                    and 6 <= point[0] <= 38 and 68 <= point[1] <= 98):
                return point
        except (KeyError, ValueError, TypeError):
            continue
    return None


def search_center(meta):
    if "point" in meta:
        return meta["point"], meta.get("label", "Selected location")
    city, state = meta["city"], meta["state"]
    city_key = city.casefold()
    if city_key in CITY_CENTERS and CITY_STATES.get(city_key) == state.casefold():
        return CITY_CENTERS[city_key], f"Approximate {city} city center"

    # Prefer an independent city center over estimating it from hospital rows.
    mapped = geocode_city(city, state)
    if mapped:
        return mapped, f"Approximate {city} city center (city lookup)"

    # Fall back to original city/state values in Databricks (not display labels).
    rows = city_rows_raw(meta.get("raw_pairs", ()))
    points = [p for row in rows if (p := coordinates(row)) is not None]
    if not points:
        return None, "Not enough valid coordinates to locate this city"
    if len(points) == 1:
        # Available only as a provisional center, never claimed as verified.
        return points[0], f"Unverified {city} location from one facility record"

    clusters = [[p for p in points if distance_km(seed, p) <= 30]
                for seed in points]
    cluster = max(clusters, key=len)
    if len(cluster) < 2:
        return None, "City records have inconsistent coordinates"
    lat = float(pd.Series([p[0] for p in cluster]).median())
    lon = float(pd.Series([p[1] for p in cluster]).median())
    return (lat, lon), f"Estimated {city} center from facility records (unverified)"


def location_concern(row, search_meta=None):
    """Reject known geographically contradictory records; show uncertainty."""
    city = normalize_text(row.get("address_city")).casefold()
    state = clean_state_name(row.get("address_stateOrRegion"))
    state_key = state.casefold() if state else ""
    point = coordinates(row)
    if point is None:
        return "Missing or invalid coordinates."

    # A facility in a reference city cannot claim coordinates far away.
    if city in CITY_CENTERS:
        if CITY_STATES.get(city) != state_key:
            return "Recorded city and state are inconsistent."
        if distance_km(point, CITY_CENTERS[city]) > 35:
            return "Coordinates are far from the recorded city."
        return None

    if search_meta and "city" in search_meta:
        if city == search_meta["city"].casefold() and state_key == search_meta["state"].casefold():
            return None
        # If a different city is not covered by our reference data, only accept
        # the cross-city record when the dataset itself says its CITY is verified.
        status = normalize_text(row.get("location_status")).casefold()
        if "city verified" not in status or "not city verified" in status:
            return "Nearby record from a different city has unverified coordinates."
    return None


def full_address(row):
    pieces = []
    for field in ("address_line1", "address_city", "address_stateOrRegion"):
        part = normalize_text(row.get(field))
        if part and part.casefold() not in {"none", "null", "nan", "unknown"}:
            if not pieces or part.casefold() != pieces[-1].casefold():
                pieces.append(part)
    pin = normalize_text(row.get("address_zipOrPostcode"))
    if re.fullmatch(r"\d{6}", pin):
        pieces.append(pin)
    if pieces:
        pieces.append("India")
    return ", ".join(pieces)


def parsed_phone_numbers(value):
    """Accept plausible Indian dialable numbers; deduplicate a repeated array."""
    raw = parse_list(value)
    numbers = []
    for item in raw:
        for part in re.split(r"[,;]", item):
            digits = re.sub(r"\D", "", str(part))
            if len(digits) == 10:
                digits = "91" + digits
            elif len(digits) == 11 and digits.startswith("0"):
                digits = "91" + digits[1:]
            if len(digits) == 12 and digits.startswith("91"):
                phone = "+" + digits
                if phone not in numbers:
                    numbers.append(phone)
    return numbers[:4]


def location_note(status):
    status = normalize_text(status)
    if not status:
        return "This facility's map location has not been independently verified."
    if "not city verified" in status.casefold():
        return "Location is within India, but the facility's city and map pin are unverified."
    return "Recorded location status: " + status + ". Please confirm before traveling."

# ============================================================
# 5. MEDICAL PATTERNS AND SCREENING
# ============================================================

CSECTION = (r"\b(?:c[\s-]?sections?|caesarean|cesarean|caesarian|cesarian|lscs|"
            r"lower segment caesarean|lower segment cesarean)\b")
EMERGENCY = r"\b(?:emergency|emergencies|casualty|accident and emergency)\b"
HOURS = r"\b(?:24\s*(?:x|/)\s*7|24[\s-]*hours?|round[\s-]*the[\s-]*clock)\b"
PATTERNS = {
    "Dialysis": r"\b(?:dialysis|ha?emodialysis|peritoneal dialysis)\b",
    "NICU": r"\bnicu\b|\bneonatal intensive care\b|\bnewborn intensive care\b",
    "MRI": r"\bmri\b|\bmagnetic resonance imaging\b",
    "Trauma Care": (r"\btrauma (?:care|surgery|unit|cent(?:er|re)|management|services?)\b|"
                    r"\bpolytrauma\b|\bmajor trauma\b"),
    "Burn Care": r"\bburns?\b|\bburn injuries\b",
    "General Emergency": EMERGENCY,
    "Emergency C-section": CSECTION,
}
NEGATIVE = (r"\b(?:not available|not offered|not provided|unavailable|discontinued|"
            r"suspended|no longer|does not offer|does not provide|does not perform|no dedicated)\b")
PLANNED = r"\b(?:planned|proposed|coming soon|under construction|future facility|intends to offer)\b"
ARTIFACTS = [
    r"\?", r"\b(?:only if|if explicitly stated|if mentioned|when stated)\b",
    r"\b(?:provided content|source text|the text|not specified|not explicitly mentioned)\b",
    r"\b(?:check whether|verify whether|confirm whether|should be listed|does the hospital|is there evidence)\b",
    r"\b(?:no procedures listed|no explicit medical procedures)\b",
]


def is_artifact(text):
    return any(re.search(pattern, text, re.I) for pattern in ARTIFACTS)


def service_negative(text, service):
    for clause in re.split(r"[.;\n]", normalize_text(text)):
        matches = list(re.finditer(PATTERNS[service], clause, re.I))
        negs = list(re.finditer(NEGATIVE, clause, re.I))
        if any(abs(m.start()-n.start()) <= 85 for m in matches for n in negs):
            return True
    return False


def general_emergency(text, name):
    specialist = (r"\b(?:dental|dentistry|eye|ophthalmic|ophthalmology|veterinary)\b"
                  r".{0,45}\b(?:emergency|casualty)\b|"
                  r"\b(?:emergency|casualty)\b.{0,45}\b(?:dental|eye|ophthalmic)\b")
    if re.search(specialist, text, re.I):
        return False
    if re.search(r"\b(?:dental|eye|ophthalmic|veterinary)\b", name, re.I):
        return False
    direct = (r"\bemergency (?:department|unit|ward|medicine|services?|care)\b|"
              r"\baccident and emergency\b|\bcasualty (?:department|unit|services?)\b|"
              + HOURS + r".{0,50}\bemergency\b")
    return bool(re.search(direct, text, re.I))


def explicit_emergency_csection(text):
    direct = (
        r"\bemergency\s+(?:lower\s+segment\s+)?"
        r"(?:caesarean|cesarean|caesarian|cesarian|c[\s-]?section|lscs)\b|"
        r"\b(?:caesarean|cesarean|caesarian|cesarian|c[\s-]?section|lscs)"
        r"\s+(?:for\s+)?emergenc(?:y|ies)\b|"
        r"\bemergency\s+(?:obstetric\s+)?(?:surgery|delivery)\s*"
        r"\([^)]*(?:c[\s-]?section|caesarean|cesarean|lscs)[^)]*\)"
    )
    return bool(re.search(direct, normalize_text(text), re.I))


def mri_direct(text):
    text = normalize_text(text)
    without_center_name = re.sub(
        r"\bCT\s*(?:&|and)\s*MRI\s+Cent(?:er|re)\b",
        "diagnostic center", text, flags=re.I,
    )
    if not re.search(r"\b(?:mri|magnetic resonance imaging)\b", without_center_name, re.I):
        return False
    if (re.search(r"\b(?:first|pioneering|introduced|inaugurated|installed in)\b", text, re.I)
            and re.search(r"\b(?:19|20)\d{2}\b", text)):
        return False
    if re.search(r"\b(?:another hospital|other hospital|network hospitals?|partner hospital)\b", text, re.I):
        return False
    direct = (
        r"\b(?:provides?|provided|offers?|offered|performs?|performed|available|operates?|on[ -]?site)\b"
        r".{0,65}\b(?:mri|magnetic resonance imaging)\b|"
        r"\b(?:mri|magnetic resonance imaging)\b.{0,40}"
        r"\b(?:imaging|scans?|scanner|machine|services?|available|provided|performed|facility|cent(?:er|re))\b|"
        r"\b\d(?:\.\d)?\s*tesla\s+(?:digital\s+)?mri\b"
    )
    return bool(re.search(direct, without_center_name, re.I))


def trauma_direct(text, name):
    text = normalize_text(text)
    if name:
        text = re.sub(re.escape(normalize_text(name)), "the facility", text, flags=re.I)
    if re.search(r"\b(?:named|branding|listed as|called)\b", text, re.I):
        return False
    clinical = (
        r"\btrauma\s+(?:care|surgery|unit|ward|treatment|management|services?|team|resuscitation)\b|"
        r"\b(?:treats?|treating|treatment|management|surgery|care for).{0,40}\b(?:trauma|polytrauma)\b|"
        r"\b(?:polytrauma|major trauma)\s+(?:care|treatment|management|surgery|services?)\b"
    )
    return bool(re.search(clinical, text, re.I))


def classify(service, text, name):
    text = normalize_text(text)
    if not re.search(PATTERNS[service], text, re.I):
        return "none"
    if service_negative(text, service):
        return "negative"
    if is_artifact(text) or re.search(PLANNED, text, re.I):
        return "none"
    if service == "General Emergency":
        return "direct" if general_emergency(text, name) else "supporting"
    if service == "Burn Care":
        pattern = (r"\bburns? (?:care|unit|ward|cent(?:er|re)|treatment|management|"
                   r"services?|department|injur(?:y|ies))\b|"
                   r"\b(?:treatment|management|care|treats?|treating)\b.{0,45}\bburns?\b")
        return "direct" if re.search(pattern, text, re.I) else "supporting"
    if service == "Trauma Care":
        return "direct" if trauma_direct(text, name) else "supporting"
    if service == "Emergency C-section":
        return "direct" if explicit_emergency_csection(text) else "supporting"
    if service == "MRI":
        return "direct" if mri_direct(text) else "supporting"
    action = (r"\b(?:provides?|provided|offered|offers?|performs?|performed|available|has|"
              r"facility|department|unit|cent(?:er|re)|services?|equipment|machine|beds?|"
              r"treatment|operates?)\b")
    return "direct" if re.search(action, text, re.I) else "supporting"

# ============================================================
# 6. FACILITY ATTRIBUTION / CONFLICTS
# ============================================================

def normalized_words(value):
    ignored = {"hospital", "hospitals", "medical", "centre", "center", "super",
               "speciality", "specialty", "the", "of", "and", "at", "healthcare", "health"}
    return {word for word in re.findall(r"[a-z0-9]+", str(value).lower())
            if len(word) > 2 and word not in ignored}


def other_hospital_claim(claim, facility):
    pattern = (r"\b(?:at|operated by|provided by|performed at)\s+"
               r"([A-Za-z0-9&.'-]+(?:\s+[A-Za-z0-9&.'-]+){0,8}?\s+"
               r"(?:Hospital|Hospitals|Medical Cent(?:er|re)))\b")
    match = re.search(pattern, claim, re.I)
    if not match:
        return False
    own, other = normalized_words(facility), normalized_words(match.group(1))
    return bool(own and other and own.isdisjoint(other))


def facility_hold(row):
    name = normalize_text(row.get("name")).casefold()
    city = normalize_text(row.get("address_city")).casefold()
    if "aravind eye hospital" in name and "hyderabad" in city:
        return "Known mixed-source record; identity review required."
    if "st.joseph hospital" in name and "lucknow" in city:
        return "Record includes other facilities in Ghaziabad; identity review required."
    return None


def attribution_issue(row, claim):
    name = normalize_text(row.get("name")).casefold()
    city = normalize_text(row.get("address_city")).casefold()
    address = normalize_text(row.get("address_line1")).casefold()
    text = normalize_text(claim).casefold()
    if ("partha dental" in name and "kothapet" in (name+" "+city+" "+address)
            and "attapur" in text):
        return "Claim concerns a different branch."
    if other_hospital_claim(claim, row.get("name") or ""):
        return "Statement may describe another hospital."
    return None


def clean_evidence(row):
    hold = facility_hold(row)
    if hold:
        return [], [hold]
    accepted, cautions = [], []
    for item in evidence_items(row):
        text = item["text"]
        problem = attribution_issue(row, text)
        if problem:
            caution = problem + " This statement was excluded."
            if caution not in cautions:
                cautions.append(caution)
        elif is_artifact(text) or re.search(PLANNED, text, re.I):
            continue
        else:
            accepted.append(item)
    return accepted, cautions


def evaluate(row, service):
    items, warnings = clean_evidence(row)
    if facility_hold(row):
        return {"eligible": False, "level": "Hold for review", "direct": [],
                "supporting": [], "warnings": warnings}
    direct, supporting, negated = [], [], []
    for item in items:
        label = classify(service, item["text"], row.get("name") or "")
        if label == "direct":
            direct.append(item)
        elif label == "supporting":
            supporting.append(item)
        elif label == "negative":
            negated.append(item)
    if negated:
        warnings.append("Conflicting service information; record withheld.")
    level = ("Conflicting" if negated else "Direct wording" if direct
             else "Supporting only" if supporting else "No usable evidence")
    return {"eligible": bool(direct) and not negated, "level": level,
            "direct": direct, "supporting": supporting, "warnings": warnings}

# ============================================================
# 7. EMERGENCY C-SECTION LEADS
# ============================================================

def has_csection(text):
    return bool(re.search(CSECTION, normalize_text(text), re.I))


def strong_24h_emergency(text):
    text = normalize_text(text)
    if not (re.search(HOURS, text, re.I) and re.search(EMERGENCY, text, re.I)):
        return False
    if re.search(r"\b(?:dental|eye|ophthalmic|veterinary)\b.{0,45}\bemergency\b", text, re.I):
        return False
    if re.search(r"\bambulance\b", text, re.I) and not re.search(
        r"\bemergency (?:department|unit|ward|care|services?)\b", text, re.I
    ):
        return False
    return True


def other_emergency(text):
    text = normalize_text(text)
    pattern = (r"\bemergency (?:department|unit|area|ward|care|services?)\b|"
               r"\baccident and emergency\b|\bcasualty (?:department|unit)\b")
    specialist = r"\b(?:dental|eye|ophthalmic|veterinary)\b.{0,45}\bemergency\b"
    return bool(re.search(pattern, text, re.I)) and not bool(re.search(specialist, text, re.I))


def evaluate_csection(row):
    items, warnings = clean_evidence(row)
    output = {"category": "none", "explicit": [], "csection": [],
              "emergency": [], "warnings": warnings}
    if facility_hold(row):
        return output
    explicit, surgery, emergency_24, emergency_other = [], [], [], []
    for item in items:
        text = item["text"]
        if has_csection(text) and service_negative(text, "Emergency C-section"):
            output["warnings"] = warnings + ["Negative C-section wording; review required."]
            return output
        if re.search(EMERGENCY, text, re.I) and re.search(NEGATIVE, text, re.I):
            output["warnings"] = warnings + ["Potential negative emergency wording; review required."]
            return output
        if explicit_emergency_csection(text):
            explicit.append(item)
        else:
            if has_csection(text):
                surgery.append(item)
            if strong_24h_emergency(text):
                emergency_24.append(item)
            elif other_emergency(text):
                emergency_other.append(item)
    if explicit:
        category, emergency = "explicit", []
    elif surgery and emergency_24:
        category, emergency = "priority", emergency_24
    elif surgery and emergency_other:
        category, emergency = "possible", emergency_other
    else:
        category, emergency = "none", []
    output.update(category=category, explicit=explicit,
                  csection=surgery, emergency=emergency)
    return output

# ============================================================
# 8. RANKING AND SEARCH
# ============================================================

def ranking_points(evidence, km):
    text = " ".join(item["text"] for item in evidence["direct"])
    detail = 0
    if re.search(r"\b(?:provides?|provided|offers?|offered|performs?|performed|treatment)\b", text, re.I):
        detail += 7
    if re.search(r"\b(?:dedicated|unit|department|cent(?:er|re)|available)\b", text, re.I):
        detail += 6
    if re.search(r"\b(?:equipment|scanner|machine|beds?|capacity)\b", text, re.I):
        detail += 2
    detail = min(15, detail)
    proximity = round(max(0, 25*(1-km/RADIUS_KM)), 1)
    return {"evidence": 60, "details": detail, "proximity": proximity,
            "total": round(60 + detail + proximity, 1)}


def ranked_facilities(service, meta):
    center, origin_label = search_center(meta)
    counts = {"examined": 0, "outside_radius": 0, "location_hold": 0,
              "insufficient": 0, "conflicting": 0, "eligible": 0}
    if center is None:
        return [], counts, origin_label
    results = []
    for row in nearby_rows(*center):
        counts["examined"] += 1
        point = coordinates(row)
        if not point:
            continue
        km = distance_km(center, point)
        if km > RADIUS_KM:
            counts["outside_radius"] += 1
            continue
        if location_concern(row, meta):
            counts["location_hold"] += 1
            continue
        evidence = evaluate(row, service)
        if evidence["level"] == "Conflicting":
            counts["conflicting"] += 1
            continue
        if not evidence["eligible"]:
            counts["insufficient"] += 1
            continue
        points = ranking_points(evidence, km)
        website = str(row.get("officialWebsite") or "").strip()
        if not website.startswith(("https://", "http://")):
            website = ""
        results.append({
            "id": str(row.get("unique_id") or ""),
            "name": str(row.get("name") or "Unnamed facility"),
            "address": full_address(row),
            "phones": parsed_phone_numbers(row.get("phone_numbers")),
            "location_status": str(row.get("location_status") or ""),
            "city": str(row.get("address_city") or ""),
            "state": str(row.get("address_stateOrRegion") or ""),
            "lat": point[0], "lon": point[1], "km": round(km, 1),
            "level": evidence["level"], "direct": evidence["direct"],
            "supporting": evidence["supporting"], "warnings": evidence["warnings"],
            "sources": source_urls(row.get("source_urls_list")),
            "website": website, "score": points["total"], "parts": points,
        })
        counts["eligible"] += 1
    results.sort(key=lambda h: (-h["score"], h["km"], h["id"]))
    for i, item in enumerate(results, start=1):
        item["rank"] = i
    return results, counts, origin_label

# ============================================================
# 9. EVIDENCE AND FACILITY CARDS — NO NESTED EXPANDERS
# ============================================================

def evidence_display(item, show_fields=False):
    text = str(item.get("text", "")).strip()
    if not text:
        return
    st.markdown("> " + text)
    if show_fields:
        fields = [FIELD_LABELS.get(f, f) for f in item.get("fields", [])]
        st.caption("Recorded under: " + ", ".join(fields))


def score_explanation(item):
    parts = item["parts"]
    st.write(f"Service information: {parts['evidence']}/60")
    st.write(f"Additional service details: {parts['details']}/15")
    st.write(f"Distance: {parts['proximity']}/25")
    st.caption("This is a dataset match score, not a hospital quality or safety rating.")


def sources_display(item):
    st.caption(
        "These are links recorded with the facility. They may not "
        "support every service statement, or even refer to this branch."
    )
    official = item.get("website", "")
    if official:
        st.markdown(f"[Recorded facility website]({official})")

    links = []
    known = {official.rstrip("/").lower()} if official else set()
    for url in item.get("sources", []):
        if url.rstrip("/").lower() not in known:
            links.append(url)
            known.add(url.rstrip("/").lower())
        if len(links) >= 3:
            break

    if links:
        st.markdown("**Other links attached to this record**")
        for index, url in enumerate(links, 1):
            st.markdown(f"[{index}. {urlparse(url).netloc}]({url})")
    elif not official:
        st.write("No source links recorded for this facility.")


def map_link(item):
    return "https://www.google.com/maps/search/?api=1&" + urlencode(
        {"query": f"{item['lat']},{item['lon']}"}
    )


def contact_actions(item):
    """Works with older Streamlit versions: no link_button key argument."""
    phones = item.get("phones", [])
    if phones:
        st.markdown("**Contact numbers recorded for this facility**")
        st.write(" · ".join(phones))
    cols = st.columns(3)
    with cols[0]:
        if phones:
            st.markdown("[📞 Call Facility](tel:" + phones[0] + ")")
        else:
            st.caption("No phone number recorded")
    with cols[1]:
        st.link_button("📍 View on Map", map_link(item))
    with cols[2]:
        website = item.get("website", "")
        if website.startswith(("http://", "https://")):
            st.link_button("🌐 Website", website)
        else:
            st.caption("No website recorded")


def facility_card(item):
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"### {item['rank']}. {item['name']}")
            st.caption(", ".join(x for x in (item["city"], item["state"]) if x))
            if item["address"]:
                st.write("📍 " + item["address"])
            st.caption("Relevant service information found. Current availability is unconfirmed.")
        with right:
            st.metric("Match Score", f"{item['score']:.1f}/100")
            st.metric("Distance", f"{item['km']:.1f} km")
        for warning in item["warnings"]:
            st.warning("Please verify this facility: " + warning)
        # Expanders must be siblings, not nested.
        with st.expander("Why is this facility listed?"):
            st.markdown("**Services listed for this facility**")
            for claim in item["direct"][:3]:
                evidence_display(claim)
            if item["supporting"]:
                st.markdown("**Other available information**")
                for claim in item["supporting"][:2]:
                    evidence_display(claim)
            st.caption("These statements come from the dataset and have not been independently confirmed.")
        with st.expander("How this match was calculated"):
            score_explanation(item)
        with st.expander("Where this information comes from"):
            sources_display(item)
            st.caption("Recorded dataset fields for the main service statements:")
            for claim in item["direct"][:3]:
                evidence_display(claim, show_fields=True)
            st.info("Contact the facility to confirm its address, services and ability to accept patients.")
        st.caption(location_note(item.get("location_status")))
        contact_actions(item)

# ============================================================
# 10. MAP AND COMPARISON
# ============================================================

def result_map(results, center=None):
    if not results:
        st.info("No matching facilities to show on the map.")
        return
    data = pd.DataFrame([{
        "name": h["name"], "lat": h["lat"], "lon": h["lon"],
        "km": h["km"], "score": h["score"], "rank": h["rank"],
    } for h in results[:50]])
    lat = center[0] if center else float(data["lat"].median())
    lon = center[1] if center else float(data["lon"].median())
    layer = pdk.Layer(
        "ScatterplotLayer", data=data, get_position="[lon, lat]", get_radius=550,
        get_fill_color=[117, 74, 197, 190], get_line_color=[255, 255, 255],
        line_width_min_pixels=1, pickable=True,
    )
    deck = pdk.Deck(
        layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=10),
        tooltip={"html": "<b>{name}</b><br/>Distance: {km} km<br/>Match: {score}"},
    )
    st.pydeck_chart(deck, use_container_width=True)
    distance_note()
    st.caption("Map pins use recorded coordinates, which may contain errors.")


def comparison_page(results, service, location):
    hero("Compare Hospitals", f"Compare potential {service} options near {location}")
    st.markdown(
        '<div class="compare-intro"><p>Compare how far facilities are and how well their '
        'recorded services match your search. These scores do not measure quality of care.</p></div>',
        unsafe_allow_html=True,
    )
    if not results:
        st.info("No matching facilities are available for comparison.")
        return
    a, b = st.columns([2, 1])
    with a:
        sort_choice = st.selectbox("Compare by", ["Best Match", "Closest First"])
    with b:
        count = st.selectbox("Number of facilities", [3, 5, 10], index=1)
    ordered = sorted(
        results,
        key=(lambda h: (h["km"], -h["score"])) if sort_choice == "Closest First"
        else (lambda h: (-h["score"], h["km"])),
    )
    selected = ordered[:count]
    rows = [{
        "Facility": h["name"], "Distance (km)": h["km"],
        "Match Score": round(h["score"], 1),
        "Additional record warning": "Yes" if h["warnings"] else "No",
    } for h in selected]
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, use_container_width=True,
        column_config={
            "Facility": st.column_config.TextColumn("Facility", width="large"),
            "Distance (km)": st.column_config.NumberColumn("Distance", format="%.1f km"),
            "Match Score": st.column_config.ProgressColumn(
                "Match Score", min_value=0, max_value=100, format="%.1f/100",
            ),
            "Additional record warning": st.column_config.TextColumn(
                "Record warning", help="All services are unverified. 'Yes' means an additional concern was found.",
            ),
        },
    )
    distance_note()
    st.caption("Higher match scores reflect text evidence and distance, not clinical quality or availability.")
    st.subheader("Explore individual facilities")
    st.write("Open a facility to see the recorded information behind its match.")
    for h in selected:
        label = f"{h['name']} · {h['km']:.1f} km · Match {h['score']:.1f}/100"
        with st.expander(label):
            st.markdown("**Services listed for this facility**")
            for claim in h["direct"][:3]:
                evidence_display(claim)
            for warning in h["warnings"]:
                st.warning("Please verify: " + warning)
            st.caption("Recorded service descriptions are not independently verified.")
            st.write("📍 " + h["address"])
            st.caption(location_note(h.get("location_status")))
            contact_actions(h)
    with st.expander("How are hospitals compared?"):
        st.write("Service wording: up to 60 points.")
        st.write("Additional recorded details: up to 15 points.")
        st.write("Distance: up to 25 points.")
        st.caption("This is not a measure of clinical quality, safety or live availability.")

# ============================================================
# 11. EMERGENCY CARE
# ============================================================

def csection_page(meta):
    center, label = search_center(meta)
    if center is None:
        st.warning("We couldn't determine a sufficiently reliable location for this search. " + label)
        return
    grouped = {"explicit": [], "priority": [], "possible": []}
    held_locations = 0
    for row in nearby_rows(*center):
        point = coordinates(row)
        if point is None or distance_km(center, point) > RADIUS_KM:
            continue
        if location_concern(row, meta):
            held_locations += 1
            continue
        evidence = evaluate_csection(row)
        category = evidence["category"]
        if category == "none":
            continue
        grouped[category].append({
            "name": str(row.get("name") or "Unnamed facility"),
            "city": str(row.get("address_city") or ""),
            "address": full_address(row),
            "phones": parsed_phone_numbers(row.get("phone_numbers")),
            "website": str(row.get("officialWebsite") or ""),
            "location_status": str(row.get("location_status") or ""),
            "distance": round(distance_km(center, point), 1),
            "lat": point[0], "lon": point[1], **evidence,
        })
    for values in grouped.values():
        values.sort(key=lambda x: x["distance"])
    st.error("For an active medical emergency, seek emergency services immediately. "
             "This directory cannot confirm operating-room readiness or patient acceptance.")
    st.subheader("Facilities with related service information")
    st.write("We look for C-section and emergency-care statements. "
             "None of these entries establishes current emergency surgical availability.")
    cols = st.columns(3)
    metrics = [
        ("Specific C-section emergency claims", len(grouped["explicit"]), "Still unverified"),
        ("Facilities to check first", len(grouped["priority"]), "C-section + 24-hour emergency statements"),
        ("Other facilities to check", len(grouped["possible"]), "Less specific emergency information"),
    ]
    for col, values in zip(cols, metrics):
        with col:
            stat(*values)
    sections = [
        ("1. Explicit emergency C-section information", "explicit",
         "A specific dataset statement does not confirm current availability."),
        ("2. Facilities with separate C-section and 24-hour emergency claims", "priority",
         "These are verification leads, not confirmed emergency surgery providers."),
        ("3. Other possible facilities to contact", "possible",
         "These records include weaker emergency-related statements."),
    ]
    for title, category, description in sections:
        st.subheader(title)
        st.write(description)
        if not grouped[category]:
            st.info("No matching records in this category.")
        for h in grouped[category][:12]:
            with st.container(border=True):
                left, right = st.columns([3, 1])
                with left:
                    st.markdown("### " + h["name"])
                    st.caption(h["city"])
                    if h["address"]:
                        st.write("📍 " + h["address"])
                with right:
                    st.metric("Distance", f"{h['distance']:.1f} km")
                if category == "explicit":
                    st.markdown("**Emergency C-section statements**")
                    for claim in h["explicit"][:4]:
                        evidence_display(claim)
                else:
                    st.markdown("**C-section services mentioned**")
                    for claim in h["csection"][:3]:
                        evidence_display(claim)
                    st.markdown("**Emergency care mentioned**")
                    for claim in h["emergency"][:3]:
                        evidence_display(claim)
                for warning in h["warnings"]:
                    st.warning("Please verify: " + warning)
                st.info("Confirm emergency obstetric surgery capability directly before relying on this facility.")
                st.caption(location_note(h.get("location_status")))
                contact_actions(h)
    if not any(grouped.values()):
        st.warning("No matching records were found. This does not mean the care is unavailable.")
    if held_locations:
        st.caption(f"{held_locations} location records did not pass the available consistency checks.")
    distance_note()

# ============================================================
# 12. APP / SIDEBAR
# ============================================================

apply_dark_theme()

try:
    city_data = cities_from_table()
except Exception as exc:
    st.error("Could not connect to the Databricks facility database.")
    st.code(str(exc))
    st.stop()

locations = build_clean_locations(city_data)
city_options = list(locations)
if "Patna, Bihar" in city_options:
    city_options.remove("Patna, Bihar")
    city_options.insert(0, "Patna, Bihar")
if not city_options:
    st.error("No usable city/state entries were found.")
    st.stop()

# Migrate old navigation labels and avoid touching instantiated widget state.
old_nav = {
    "Explore care": "Find Hospitals & Care", "Map": "View Hospitals on Map",
    "Compare": "Compare Hospitals", "Emergency evidence": "Find Emergency Care",
    "Our method": "How It Works",
}
if "nav" not in st.session_state:
    st.session_state.nav = NAV_OPTIONS[0]
if st.session_state.nav not in NAV_OPTIONS:
    st.session_state.nav = old_nav.get(st.session_state.nav, NAV_OPTIONS[0])
if "pending_nav" in st.session_state:
    st.session_state.nav = st.session_state.pop("pending_nav")

with st.sidebar:
    st.markdown(
        '<div style="font-size:26px;font-weight:800;color:white">✚ Care Finder</div>'
        '<div style="font-size:12px;color:#d4c6ef;margin-bottom:18px">'
        'HEALTHCARE DISCOVERY · INDIA</div>', unsafe_allow_html=True,
    )
    st.markdown("### Find care")
    search_mode = st.radio("Choose your location", ["City", "Address / landmark", "My location"])
    if search_mode == "City":
        with st.form("city_form"):
            service = st.selectbox("What care do you need?", SERVICES)
            chosen = st.selectbox("Where do you need care?", city_options)
            submitted = st.form_submit_button("Find Nearby Care", type="primary", use_container_width=True)
        if submitted:
            st.session_state.search = (service, chosen, locations[chosen])
            st.session_state.pending_nav = "Find Hospitals & Care"
            st.rerun()
    elif search_mode == "Address / landmark":
        with st.form("address_form"):
            service = st.selectbox("What care do you need?", SERVICES)
            address = st.text_input("Where do you need care?", placeholder="Address, PIN code or landmark")
            submitted = st.form_submit_button("Find Nearby Care", type="primary", use_container_width=True)
        if submitted:
            try:
                if not address.strip():
                    raise ValueError("Please enter an address or landmark.")
                point, label = geocode_address(address.strip())
                st.session_state.search = (service, label, {"point": point, "label": label})
                st.session_state.pending_nav = "Find Hospitals & Care"
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
    else:
        shared = streamlit_geolocation() if streamlit_geolocation else None
        with st.form("device_form"):
            service = st.selectbox("What care do you need?", SERVICES)
            submitted = st.form_submit_button("Find Care Near Me", type="primary", use_container_width=True)
        if submitted:
            try:
                point = (float(shared["latitude"]), float(shared["longitude"]))
                if not (6 <= point[0] <= 38 and 68 <= point[1] <= 98):
                    raise ValueError("Location is outside India.")
                st.session_state.search = (service, "My location", {"point": point, "label": "My location"})
                st.session_state.pending_nav = "Find Hospitals & Care"
                st.rerun()
            except (TypeError, KeyError, ValueError):
                st.warning("Share a location within India or choose a city instead.")
        if streamlit_geolocation is None:
            st.caption("Device location is not available. Search by city or address.")
    st.divider()
    st.markdown("### Explore")
    st.radio("Navigation", NAV_OPTIONS, key="nav", label_visibility="collapsed")
    st.divider()
    st.caption("Service availability must be confirmed directly.")

# ============================================================
# 13. PAGES
# ============================================================

nav = st.session_state.nav

if nav == "How It Works":
    hero("How Care Finder Works", "Learn how facilities are matched to your search")
    st.markdown("### How to use Care Finder")
    st.write("**1. Choose the care you need.** Select a service and location.")
    st.write("**2. We search facility information.** The dataset contains descriptions of healthcare services.")
    st.write("**3. We check the statements.** We screen out some unclear, repeated, or conflicting claims.")
    st.write("**4. We show possible facilities.** We consider service wording and recorded distance.")
    st.write("**5. You can inspect each result.** Review the original statements before contacting a facility.")
    st.info("A match score is not a hospital rating or confirmation that treatment is available.")
    with st.expander("Technical approach and exploratory evaluation"):
        st.write("The live application uses explainable service-specific rules and geographic checks.")
        st.dataframe(pd.DataFrame({
            "Method": ["Regex", "NLI", "Hybrid"],
            "Precision": [0.654, 0.390, 0.400],
            "Recall": [1.000, 0.941, 0.941],
            "F1": [0.791, 0.552, 0.561],
        }), hide_index=True, use_container_width=True)
        st.caption("Exploratory Phase 5 results on 140 statements with AI-assisted, manually reviewed labels. "
                   "These figures do not evaluate this deployed version or establish clinical accuracy.")
    st.markdown("### Limitations")
    st.write("Records can be incomplete or misattributed; some city coordinates are uncertain. "
             "Current staffing, emergency readiness, and service availability are not verified.")
    st.stop()

if nav == "Find Emergency Care":
    hero("Find Emergency Care", "Find records mentioning emergency services near your selected city")
    st.error("If someone needs urgent help, contact local emergency services immediately. "
             "Do not delay care while searching this directory.")
    with st.form("emergency_search_form"):
        a, b = st.columns(2)
        with a:
            emergency_service = st.selectbox("What emergency care do you need?", EMERGENCY_SERVICES)
        with b:
            emergency_city = st.selectbox("Where do you need care?", city_options)
        submitted = st.form_submit_button("Find Emergency Care Options", type="primary")
    if submitted:
        st.session_state.emergency_query_data = (emergency_service, emergency_city)
    if "emergency_query_data" in st.session_state:
        selected_service, selected_city = st.session_state.emergency_query_data
        if selected_city not in locations:
            st.warning("This location has changed. Please choose it again.")
            st.stop()
        meta = locations[selected_city]
        if selected_service == "Emergency C-section":
            csection_page(meta)
        else:
            results, audit, origin = ranked_facilities(selected_service, meta)
            if origin.startswith("Not enough"):
                st.warning(origin + ". Search a nearby city or use an address if available.")
            st.write(f"**{len(results)} potential care options** near {selected_city}")
            st.warning("Emergency readiness and patient acceptance are not confirmed.")
            for item in results[:8]:
                facility_card(item)
            if not results:
                st.info("No matching records found here. This does not mean the service is unavailable.")
            distance_note()
    st.stop()

if "search" not in st.session_state:
    hero("Find the Care You Need, Near You.",
         "Find healthcare facilities in India and understand why they match your search")
    cols = st.columns(3)
    for col, metric in zip(cols, [
        ("Types of Care", len(SERVICES), "Searchable medical services"),
        ("Search Area", "60 km", "Around your selected location"),
        ("Availability", "Not Confirmed", "Contact facilities directly"),
    ]):
        with col:
            stat(*metric)
    st.info("Choose a service and location on the left, then select Find Nearby Care.")
    st.stop()

service, location, meta = st.session_state.search

if service == "Emergency C-section":
    hero("Emergency C-section Care Options", f"{location} · recorded facility information")
    csection_page(meta)
    st.stop()

try:
    results, audit, center_label = ranked_facilities(service, meta)
except Exception as exc:
    st.error("We couldn't retrieve facility information.")
    st.code(str(exc))
    st.stop()

# Give the selected page its own heading, avoiding duplicate 'Explore care' banners.
if nav == "Find Hospitals & Care":
    hero("Hospitals & Care Options Near You", f"{service} · {location} · within {RADIUS_KM} km")
    nearest = min((h["km"] for h in results), default=None)
    cols = st.columns(3)
    metrics = [
        ("Potential Care Options", len(results), "Based on recorded service information"),
        ("Closest Facility", f"{nearest:.1f} km" if nearest is not None else "—", "Approximate distance"),
        ("Search Area", f"{RADIUS_KM} km", "From the selected location"),
    ]
    for col, metric in zip(cols, metrics):
        with col:
            stat(*metric)
    st.caption("Search location: " + center_label)
    if "unverified" in center_label.lower():
        st.warning("The city center is estimated from facility coordinates, not independently verified. "
                   "Distances and nearby results may be inaccurate. Try an address search for a more precise starting point.")
    safety_note()
    distance_note()
    if not results:
        if center_label.startswith(("Not enough", "City records")):
            st.warning("We couldn't reliably locate the selected city using its facility records. "
                       "Try a nearby larger city or use an address search.")
        else:
            st.warning("No matching facility information was found within this search area. "
                       "Some records may lack service details or have unverified coordinates. "
                       "This doesn't prove that care is unavailable.")
        st.stop()
    st.subheader("Care Options for You")
    a, b = st.columns([3, 1])
    with a:
        order = st.selectbox("Sort by", ["Best Evidence Match", "Closest First"])
    with b:
        count = st.selectbox("Show", [3, 5, 10, "All"])
    ordered = (sorted(results, key=lambda h: (h["km"], -h["score"]))
               if order == "Closest First" else results)
    displayed = ordered if count == "All" else ordered[:int(count)]
    for item in displayed:
        facility_card(item)
    with st.expander("Search Details"):
        st.write("Facility records checked:", audit["examined"])
        st.write("Outside search area:", audit["outside_radius"])
        st.write("Withheld due to location uncertainty:", audit["location_hold"])
        st.write("Insufficient service information / identity concerns:", audit["insufficient"])
        st.write("Conflicting service information:", audit["conflicting"])
        st.write("Potential options listed:", audit["eligible"])

elif nav == "View Hospitals on Map":
    hero("View Hospitals on Map", f"{service} · {location}")
    if not results:
        st.info("No matching facilities to map for this search.")
    else:
        center, _ = search_center(meta)
        result_map(results, center)

elif nav == "Compare Hospitals":
    comparison_page(results, service, location)

st.caption(f"Care Finder India · {VERSION} · Virtue Foundation dataset · "
           "Databricks + Streamlit · Healthcare discovery prototype")
