import base64
import csv
import html
import io
import json
import math
import os
import re
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
import folium
from folium.plugins import AntPath, Draw, Fullscreen
import requests
import streamlit as st
from streamlit_folium import st_folium

# ==========================================
# PAGE CONFIGURATION (VERSION 3.0)
# ==========================================
st.set_page_config(
    page_title="Lion Delivery Dispatch v3.0",
    page_icon="🚚",
    layout="wide"
)

WAREHOUSE_URL = "https://maps.app.goo.gl/KxepQZ1YGK4qYeND7"
DEFAULT_LOCATION_BOARD_API = "https://api.liondelivery.ae/api/v1/dispatcher/operations/location-board/"
DB_PATH = "dispatch_history.db"

FLEET_DRIVERS = [
    "Ahmed Nasir",
    "Ahmed Kamal",
    "Dawit",
    "Hafiz Mohammed",
    "Kaleab Argaw",
    "Lema Sisay",
    "Mustefa Kassa"
]

DISTANT_CITIES = {"Al Ain", "Abu Dhabi", "Fujairah / East Coast", "Ras Al Khaimah"}
UAE_MASAFI_WAYPOINT = (25.3180, 56.1660)

UAE_AREA_FALLBACK_COORDS = {
    "al ain": (24.2075, 55.7447),
    "remah": (24.1528, 55.3019),
    "shuwaib": (24.7380, 55.7843),
    "sweihan": (24.4667, 55.3333),
    "ruga": (24.4815, 55.3089),
    "hili": (24.2790, 55.7790),
    "mezyad": (24.0520, 55.8480),
    "abu dhabi": (24.4539, 54.3773),
    "shamkha": (24.3934, 54.7078),
    "shakhbout": (24.3644, 54.6186),
    "khalifa city": (24.4205, 54.5775),
    "baniyas": (24.3036, 54.6342),
    "mohammed bin zayed": (24.3540, 54.5380),
    "mbz": (24.3540, 54.5380),
    "mussafah": (24.3582, 54.5029),
    "shahama": (24.5367, 54.6822),
    "yas": (24.4950, 54.6050),
    "saadiyat": (24.5400, 54.4300),
    "fujairah": (25.1288, 56.3265),
    "khor fakkan": (25.3392, 56.3419),
    "khorfakkan": (25.3392, 56.3419),
    "kalba": (25.0742, 56.3553),
    "dibba": (25.5925, 56.2617),
    "hatta": (24.8051, 56.1206),
    "mleiha": (25.1314, 55.8856),
    "dhaid": (25.2881, 55.8814),
    "madam": (24.9554, 55.7625),
    "ras al khaimah": (25.7895, 55.9432),
    "rak": (25.7895, 55.9432),
    "umm al quwain": (25.5647, 55.5552),
    "uaq": (25.5647, 55.5552),
    "ajman": (25.4052, 55.5136),
    "rawda": (25.3880, 55.5240),
    "nuaimiya": (25.3900, 55.4600),
    "jurf": (25.4320, 55.5450),
    "al nahda": (25.2982, 55.3712),
    "al khan": (25.3225, 55.3653),
    "majaz": (25.3314, 55.3854),
    "taawun": (25.3125, 55.3742),
    "qasimia": (25.3468, 55.3948),
    "muwaileh": (25.3117, 55.4578),
    "rahmaniya": (25.3522, 55.5450),
    "sharjah": (25.3463, 55.4209),
    "deira": (25.2711, 55.3275),
    "bur dubai": (25.2532, 55.2972),
    "warqa": (25.1972, 55.4144),
    "mirdif": (25.2225, 55.4194),
    "quasis": (25.2769, 55.3850),
    "qusais": (25.2769, 55.3850),
    "muhaisnah": (25.2750, 55.4090),
    "barsha": (25.1028, 55.1953),
    "jumeirah": (25.1916, 55.2428),
    "marina": (25.0805, 55.1403),
    "business bay": (25.1850, 55.2650),
    "downtown": (25.1972, 55.2744),
    "silicon oasis": (25.1215, 55.3773),
    "international city": (25.1667, 55.4083),
    "jvc": (25.0550, 55.2090),
    "jebel ali": (24.9857, 55.0273),
    "dubai": (25.2048, 55.2708),
}

DRIVER_COLORS = [
    "#e6194B",  # Red
    "#3cb44b",  # Green
    "#4363d8",  # Blue
    "#f58231",  # Orange
    "#911eb4",  # Purple
    "#008080",  # Teal
    "#e60073",  # Magenta
]

api_session = requests.Session()
api_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://app.liondelivery.ae",
    "Referer": "https://app.liondelivery.ae/"
})

maps_session = requests.Session()
maps_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
})


# ==========================================
# 1. SQLITE ROTATION MEMORY
# ==========================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS dispatch_log ("
            "dispatch_date TEXT, driver_name TEXT, primary_city TEXT, "
            "is_distant INTEGER, total_bags INTEGER, one_way_km REAL, "
            "est_finish_time TEXT, PRIMARY KEY (dispatch_date, driver_name))"
        )


def get_recent_driver_stats(days_back=7):
    init_db()
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    stats = {
        d: {
            "km_7d": 0.0,
            "bags_7d": 0,
            "distant_count_7d": 0,
            "went_far_yesterday": False,
            "last_city": "None"
        }
        for d in FLEET_DRIVERS
    }

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT dispatch_date, driver_name, primary_city, is_distant, total_bags, one_way_km "
            "FROM dispatch_log WHERE dispatch_date >= ? ORDER BY dispatch_date ASC",
            (cutoff,)
        )
        for d_date, d_name, p_city, is_dist, bags, km in cur.fetchall():
            if d_name not in stats:
                continue
            stats[d_name]["km_7d"] += float(km or 0.0)
            stats[d_name]["bags_7d"] += int(bags or 0)
            stats[d_name]["distant_count_7d"] += int(is_dist or 0)
            stats[d_name]["last_city"] = p_city
            if d_date == yesterday_str and int(is_dist or 0) == 1:
                stats[d_name]["went_far_yesterday"] = True

    return stats


def log_dispatch_to_db(master_rows):
    init_db()
    today_str = date.today().isoformat()
    driver_summary = {}

    for r in master_rows:
        d_name = r.get("Assigned_Driver", "")
        if not d_name or "NOT GOING" in d_name or d_name == "UNASSIGNED":
            continue
        if d_name not in driver_summary:
            driver_summary[d_name] = {
                "cities": set(),
                "bags": int(r.get("Route_Total_Bags", 0) or 0),
                "km": float(r.get("Route_OneWay_KM", 0.0) or 0.0),
                "finish": r.get("Est_Finish_Time", "")
            }
        driver_summary[d_name]["cities"].add(r.get("City_Area", ""))

    with sqlite3.connect(DB_PATH) as conn:
        for d_name, info in driver_summary.items():
            is_dist = 1 if (info["cities"] & DISTANT_CITIES) else 0
            c_str = ", ".join(sorted(info["cities"]))
            conn.execute(
                "INSERT OR REPLACE INTO dispatch_log "
                "(dispatch_date, driver_name, primary_city, is_distant, total_bags, one_way_km, est_finish_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (today_str, d_name, c_str, is_dist, info["bags"], info["km"], info["finish"])
            )


def predict_driver_finish_time(stops, total_one_way_km):
    if not stops:
        return "06:30 AM", 0.0
    total_bags = sum(int(float(s.get("Bags", 1) or 1)) for s in stops)
    est_hours = round(1.5 + (total_one_way_km / 50.0) + (total_bags * 0.14), 1)
    start_time = datetime.strptime("06:30", "%H:%M")
    finish_dt = start_time + timedelta(hours=est_hours)
    return finish_dt.strftime("%I:%M %p"), est_hours


# ==========================================
# 2. BORDER CONTROL & GRANULAR UAE CITY DETECTION
# ==========================================
def is_in_oman(lat, lon):
    if lat >= 26.08:
        return True
    if lat < 24.72 and lon >= 56.08:
        return True
    if lat < 24.45 and lon >= 56.00:
        return True
    if lat < 23.95 and lon >= 55.65:
        return True
    return False


def identify_uae_city(lat, lon):
    if lon < 54.95:
        return "Abu Dhabi"

    if 24.40 <= lat <= 24.58 and 55.20 <= lon <= 55.45:
        return "Al Ain"

    if (lon >= 55.70 and 24.72 <= lat < 25.58) or (lon >= 55.95 and lat >= 24.60) or (lon >= 56.12 and lat >= 25.58):
        return "Fujairah / East Coast"

    if lat < 24.38:
        return "Al Ain"
    if lat < 24.75 and 55.35 <= lon < 55.98:
        return "Al Ain"

    if lat < 24.78 and lon < 55.35:
        return "Abu Dhabi"

    if lat >= 25.58 and 55.65 <= lon < 56.12:
        return "Ras Al Khaimah"

    if 25.48 <= lat < 25.62 and 55.50 <= lon < 55.70:
        return "Umm Al Quwain"

    if 25.365 <= lat < 25.48 and 55.40 <= lon <= 55.58:
        return "Ajman"

    if 25.25 <= lat < 25.48 and 55.34 <= lon <= 55.56:
        return "Sharjah (City)"

    if 24.95 <= lat < 25.48 and 55.56 < lon < 55.70:
        return "Sharjah (Far Inland)"

    if 24.75 <= lat < 25.32 and 54.95 <= lon <= 55.60:
        return "Dubai"

    return "Sharjah (Far Inland)"


# ==========================================
# 3. SHORT-LINK & URL RESOLUTION + LIVE API
# ==========================================
@st.cache_data(show_spinner=False)
def geocode_uae_text_fallback(area_text):
    if not area_text:
        return None, None

    cleaned = str(area_text).lower().replace("_", " ").replace("+", " ").strip()
    if cleaned in ("", "uae corridor", "none", "null", "maps", "google"):
        return None, None

    for key, (lat, lon) in UAE_AREA_FALLBACK_COORDS.items():
        if key in cleaned:
            return lat, lon

    try:
        q = urllib.parse.quote(f"{cleaned}, United Arab Emirates")
        nom_url = f"https://nominatim.openstreetmap.org/search?q={q}&countrycodes=ae&format=json&limit=1"
        resp = maps_session.get(nom_url, timeout=6)
        if resp.status_code == 200 and resp.json():
            hit = resp.json()[0]
            return float(hit["lat"]), float(hit["lon"])
    except Exception:
        pass

    return None, None


@st.cache_data(show_spinner=False)
def resolve_google_maps_url(url):
    if not url:
        return None, None

    raw_url = str(url).strip().strip("'").strip('"')
    unquoted = urllib.parse.unquote(raw_url)

    patterns = [
        r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
        r"/dir/[^/]+/(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"[?&]q=(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"[?&]ll=(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"/search/(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"@(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)",
        r"center=(-?\d+\.\d+)[,%2C]+(-?\d+\.\d+)",
        r"(2[2-6]\.\d{4,})\s*,\s*[+]?(5[1-6]\.\d{4,})",
    ]

    for pat in patterns:
        match = re.search(pat, unquoted)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if 22.0 <= lat <= 26.5 and 51.0 <= lon <= 56.6:
                return lat, lon

    if unquoted.startswith("http"):
        try:
            resp = maps_session.get(raw_url, allow_redirects=True, timeout=12)
            final_url = urllib.parse.unquote(resp.url)

            for pat in patterns:
                match = re.search(pat, final_url)
                if match:
                    lat, lon = float(match.group(1)), float(match.group(2))
                    if 22.0 <= lat <= 26.5 and 51.0 <= lon <= 56.6:
                        return lat, lon

            body_text = html.unescape(resp.text[:150000])
            html_patterns = patterns + [
                r"\[null,null,(2[2-6]\.\d{4,}),(5[1-6]\.\d{4,})\]",
                r"\[(5[1-6]\.\d{5,}),(2[2-6]\.\d{5,})\]",
            ]
            for pat in html_patterns:
                match = re.search(pat, body_text)
                if match:
                    v1, v2 = float(match.group(1)), float(match.group(2))
                    if 22.0 <= v1 <= 26.5 and 51.0 <= v2 <= 56.6:
                        return v1, v2
                    if 22.0 <= v2 <= 26.5 and 51.0 <= v1 <= 56.6:
                        return v2, v1

            place_match = re.search(r"/maps/place/([^/?&@]+)", final_url)
            if place_match:
                place_name = urllib.parse.unquote_plus(place_match.group(1))
                lat, lon = geocode_uae_text_fallback(place_name)
                if lat and lon:
                    return lat, lon
        except Exception:
            pass

    return None, None


def extract_row_coordinates(row, url_col):
    lat_val = row.get("Latitude") or row.get("latitude") or row.get("Lat")
    lon_val = row.get("Longitude") or row.get("longitude") or row.get("Lon")
    if lat_val and lon_val:
        try:
            lat_f = float(str(lat_val).strip().strip("'"))
            lon_f = float(str(lon_val).strip().strip("'"))
            if 22.0 <= lat_f <= 26.5 and 51.0 <= lon_f <= 56.6:
                return lat_f, lon_f, False
        except ValueError:
            pass

    lat, lon = resolve_google_maps_url(row.get(url_col, ""))
    if lat and lon:
        return lat, lon, False

    for val in row.values():
        if val and ("http" in str(val) or "maps" in str(val) or re.search(r"2[345]\.\d{4,}", str(val))):
            lat, lon = resolve_google_maps_url(str(val))
            if lat and lon:
                return lat, lon, False

    area_candidates = [
        row.get("Area", ""),
        row.get("Address", ""),
        row.get("Emirate", ""),
        row.get("area_snapshot", ""),
        row.get("address_snapshot", ""),
        row.get("emirate_snapshot", ""),
        row.get("city_zone_snapshot", ""),
    ]
    combined_area = " ".join(str(x) for x in area_candidates if x and "http" not in str(x)).strip()
    lat, lon = geocode_uae_text_fallback(combined_area)
    if lat and lon:
        return lat, lon, True

    return None, None, True


def find_access_jwt_in_response(obj):
    raw_text = json.dumps(obj)
    matches = re.findall(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw_text)
    fallback_jwt = None
    for jwt_str in matches:
        fallback_jwt = jwt_str
        try:
            payload_b64 = jwt_str.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
            if payload.get("token_type") == "access":
                return jwt_str
        except Exception:
            pass
    return fallback_jwt


def obtain_fresh_jwt_token(custom_login_url, email_or_user, password):
    candidate_urls = []
    if custom_login_url and custom_login_url.strip():
        candidate_urls.append(custom_login_url.strip())

    for default_u in [
        "https://api.liondelivery.ae/api/v1/auth/login/",
        "https://api.liondelivery.ae/api/v1/users/login/",
        "https://api.liondelivery.ae/api/v1/accounts/login/",
        "https://api.liondelivery.ae/api/v1/auth/token/",
        "https://api.liondelivery.ae/api/v1/token/",
    ]:
        if default_u not in candidate_urls:
            candidate_urls.append(default_u)

    user_clean = email_or_user.strip()
    payloads = [
        {"email": user_clean, "password": password},
        {"username": user_clean, "password": password},
    ]

    last_err = ""
    for url in candidate_urls:
        for pl in payloads:
            try:
                resp = api_session.post(url, json=pl, timeout=12)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    tok = find_access_jwt_in_response(data)
                    if tok:
                        return tok, None
                elif resp.status_code != 404:
                    last_err = f"{url} returned {resp.status_code}: {resp.text[:180]}"
            except Exception as e:
                last_err = str(e)

    return None, last_err or "Could not find matching login endpoint."


def pull_all_location_board_bags(base_endpoint, bearer_token):
    clean_tok = bearer_token.replace("Bearer ", "").strip()
    headers = {
        "authorization": f"Bearer {clean_tok}",
        "accept": "application/json"
    }

    def find_records(obj, found=None):
        if found is None:
            found = []
        if not obj or not isinstance(obj, (dict, list)):
            return found
        if isinstance(obj, list):
            for el in obj:
                find_records(el, found)
            return found
        raw_str = json.dumps(obj)
        if re.search(r"LD-BAG-\d+", raw_str, re.I) and "results" not in obj and "data" not in obj and "items" not in obj:
            found.append(obj)
            return found
        for key in obj:
            find_records(obj[key], found)
        return found

    base_clean = base_endpoint.split("?")[0].strip()
    extracted_map = {}

    for page_num in range(1, 35):
        page_url = f"{base_clean}?page={page_num}&page_size=100"
        resp = api_session.get(page_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            if page_num == 1:
                return None, f"API Error {resp.status_code}: {resp.text[:200]}"
            break

        data = resp.json()
        records = find_records(data)
        if not records:
            break

        added_this_page = 0
        for rec in records:
            s = rec.get("stop") if isinstance(rec.get("stop"), dict) else rec
            rec_json_str = json.dumps(rec)

            bag_match = re.search(r"LD-BAG-\d+", rec_json_str, re.I)
            bag_code = s.get("bag_code") or s.get("bag_number") or (bag_match.group(0).upper() if bag_match else None)
            if not bag_code:
                continue

            lat = s.get("latitude") or rec.get("latitude") or s.get("lat") or rec.get("lat") or ""
            lon = s.get("longitude") or rec.get("longitude") or s.get("lng") or rec.get("lng") or ""

            url_match = re.search(
                r"https?://(?:maps\.app\.goo\.gl/[^\s\"'\\<>]+|goo\.gl/maps/[^\s\"'\\<>]+|(?:www\.)?google\.com/maps[^\s\"'\\<>]+)",
                rec_json_str,
                re.I
            )
            map_url = url_match.group(0) if url_match else ""
            if not map_url and lat and lon:
                map_url = f"https://www.google.com/maps?q={lat},{lon}"

            area_parts = [
                str(s.get("area_snapshot") or rec.get("area_snapshot") or s.get("area") or rec.get("area") or ""),
                str(s.get("address_snapshot") or rec.get("address_snapshot") or s.get("address") or rec.get("address") or ""),
                str(s.get("city_zone_snapshot") or rec.get("city_zone_snapshot") or ""),
                str(s.get("emirate_snapshot") or rec.get("emirate_snapshot") or s.get("emirate") or rec.get("emirate") or ""),
            ]
            clean_area = " - ".join(dict.fromkeys(p.strip() for p in area_parts if p.strip() and "http" not in p)) or "UAE Corridor"

            if bag_code not in extracted_map:
                extracted_map[bag_code] = {
                    "Bag_Number": str(bag_code),
                    "Map_URL": str(map_url),
                    "Latitude": str(lat),
                    "Longitude": str(lon),
                    "Area": clean_area,
                    "Customer": str(s.get("customer_name_snapshot") or rec.get("customer_name") or ""),
                    "Phone": str(s.get("customer_phone_snapshot") or rec.get("customer_phone") or ""),
                    "Bags": 1
                }
                added_this_page += 1

        if added_this_page == 0 or len(records) < 100:
            break

    return list(extracted_map.values()), None


@st.cache_data(show_spinner=False)
def get_osrm_route_geometry(coords_latlon):
    if len(coords_latlon) < 2:
        return coords_latlon

    def query_osrm(pts):
        coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in pts)
        url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
        try:
            resp = maps_session.get(url, timeout=15).json()
            if resp.get("code") == "Ok" and resp.get("routes"):
                geojson_coords = resp["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in geojson_coords]
        except Exception:
            pass
        return pts

    return query_osrm(coords_latlon)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.25


@st.cache_data(show_spinner=False)
def build_road_distance_matrix(coords):
    n = len(coords)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1])

    chunk_size = 75
    chunks = [list(range(k, min(k + chunk_size, n))) for k in range(0, n, chunk_size)]

    try:
        if len(chunks) == 1:
            coord_str = ";".join(f"{coords[idx][1]:.6f},{coords[idx][0]:.6f}" for idx in chunks[0])
            osrm_url = f"http://router.project-osrm.org/table/v1/driving/{coord_str}?annotations=distance"
            resp = maps_session.get(osrm_url, timeout=20).json()
            if resp.get("code") == "Ok" and "distances" in resp:
                for r_i, row in enumerate(resp["distances"]):
                    for c_j, d in enumerate(row):
                        if d is not None:
                            matrix[r_i][c_j] = d / 1000.0
        else:
            for a in range(len(chunks)):
                for b in range(a, len(chunks)):
                    comb = chunks[a] if a == b else (chunks[a] + chunks[b])
                    coord_str = ";".join(f"{coords[idx][1]:.6f},{coords[idx][0]:.6f}" for idx in comb)
                    osrm_url = f"http://router.project-osrm.org/table/v1/driving/{coord_str}?annotations=distance"
                    resp = maps_session.get(osrm_url, timeout=20).json()
                    if resp.get("code") == "Ok" and "distances" in resp:
                        for l_i, g_i in enumerate(comb):
                            for l_j, g_j in enumerate(comb):
                                d = resp["distances"][l_i][l_j]
                                if d is not None:
                                    matrix[g_i][g_j] = d / 1000.0
    except Exception:
        pass

    return matrix


# ==========================================
# 4. V3 SEQUENCING: PRIMARY CITY FIRST -> RETURN LEG SECOND
# ==========================================
def sequence_node_group(nodes, start_from_node, dist_matrix, end_pull_node=None, lock_first_node=None):
    if not nodes:
        return []
    if len(nodes) == 1:
        return list(nodes)

    unvisited = set(nodes)
    ordered = []

    if lock_first_node is not None and lock_first_node in unvisited:
        ordered.append(lock_first_node)
        unvisited.remove(lock_first_node)
        curr = lock_first_node
    else:
        curr = start_from_node

    while unvisited:
        nxt = min(unvisited, key=lambda n: dist_matrix[curr][n])
        ordered.append(nxt)
        unvisited.remove(nxt)
        curr = nxt

    def eval_seq(seq):
        d = dist_matrix[start_from_node][seq[0]] if lock_first_node is None else 0.0
        for k in range(len(seq) - 1):
            d += dist_matrix[seq[k]][seq[k + 1]]
        if end_pull_node is not None:
            d += 0.35 * dist_matrix[seq[-1]][end_pull_node]
        return d

    start_swap_idx = 1 if lock_first_node is not None else 0
    improved = True
    while improved and len(ordered) - start_swap_idx > 1:
        improved = False
        best_d = eval_seq(ordered)
        for i in range(start_swap_idx, len(ordered) - 1):
            for j in range(i + 1, len(ordered)):
                cand = ordered[:i] + ordered[i:j + 1][::-1] + ordered[j + 1:]
                c_d = eval_seq(cand)
                if c_d + 1e-6 < best_d:
                    ordered = cand
                    best_d = c_d
                    improved = True

    return ordered


def optimize_route_order(route, dist_matrix, stop_cities=None):
    if not route:
        return [], 0.0
    if len(route) == 1:
        return list(route), dist_matrix[0][route[0]]

    if stop_cities is None:
        ordered = sequence_node_group(route, 0, dist_matrix)
    else:
        primary_nodes = [n for n in route if stop_cities[n - 1] in DISTANT_CITIES]
        backfill_nodes = [n for n in route if stop_cities[n - 1] not in DISTANT_CITIES]

        if not primary_nodes:
            ordered = sequence_node_group(route, 0, dist_matrix)
        else:
            if backfill_nodes:
                anchor = min(backfill_nodes, key=lambda b: dist_matrix[0][b])
            else:
                anchor = 0

            farthest_primary = max(primary_nodes, key=lambda p: dist_matrix[anchor][p])
            primary_seq = sequence_node_group(
                primary_nodes,
                start_from_node=0,
                dist_matrix=dist_matrix,
                end_pull_node=anchor,
                lock_first_node=farthest_primary
            )

            if backfill_nodes:
                backfill_seq = sequence_node_group(
                    backfill_nodes,
                    start_from_node=primary_seq[-1],
                    dist_matrix=dist_matrix,
                    end_pull_node=0
                )
            else:
                backfill_seq = []

            ordered = primary_seq + backfill_seq

    total_km = dist_matrix[0][ordered[0]]
    for k in range(len(ordered) - 1):
        total_km += dist_matrix[ordered[k]][ordered[k + 1]]

    return ordered, total_km


# ==========================================
# 5. CORRIDOR CLUSTERING & MICRO-CLUSTER BACKFILL
# ==========================================
def are_cities_compatible_v2(cities_a, cities_b, allow_fuj_rak_combo=False):
    comb = cities_a | cities_b
    distant_in_comb = comb & DISTANT_CITIES

    if "Al Ain" in comb:
        if comb - {"Al Ain", "Sharjah (City)", "Ajman"}:
            return False

    if "Fujairah / East Coast" in comb:
        if comb & {"Al Ain", "Abu Dhabi", "Dubai"}:
            return False

    if len(distant_in_comb) > 1:
        if not (allow_fuj_rak_combo and distant_in_comb == {"Fujairah / East Coast", "Ras Al Khaimah"}):
            return False

    if "Ras Al Khaimah" in comb:
        if comb & {"Dubai", "Abu Dhabi", "Al Ain"}:
            return False

    has_north = bool(comb & {"Ras Al Khaimah", "Umm Al Quwain", "Fujairah / East Coast"})
    has_south = bool(comb & {"Dubai", "Abu Dhabi", "Al Ain"})
    if has_north and has_south:
        return False

    if "Abu Dhabi" in comb:
        if comb - {"Abu Dhabi", "Dubai"}:
            return False

    return True


def extract_micro_cluster(candidate_nodes, demand_list, dist_matrix, anchor_node, max_bags_to_add, max_radius_km=3.8):
    if not candidate_nodes or max_bags_to_add <= 0:
        return []

    best_cluster = []
    best_score = float("inf")

    for seed in candidate_nodes:
        if demand_list[seed - 1] > max_bags_to_add:
            continue

        neighbors = sorted(
            [n for n in candidate_nodes if n != seed],
            key=lambda n: max(dist_matrix[seed][n], dist_matrix[n][seed])
        )

        cluster = [seed]
        cluster_bags = demand_list[seed - 1]
        spread_km = 0.0

        for nb in neighbors:
            d_seed = max(dist_matrix[seed][nb], dist_matrix[nb][seed])
            if d_seed > max_radius_km:
                break
            nb_bags = demand_list[nb - 1]
            if cluster_bags + nb_bags <= max_bags_to_add:
                cluster.append(nb)
                cluster_bags += nb_bags
                spread_km = max(spread_km, d_seed)
            if cluster_bags == max_bags_to_add:
                break

        dist_from_anchor = dist_matrix[anchor_node][seed]
        shortfall_penalty = (max_bags_to_add - cluster_bags) * 18.0
        score = (spread_km * 4.0) + (dist_from_anchor * 0.25) + shortfall_penalty

        if score < best_score:
            best_score = score
            best_cluster = cluster

    return best_cluster


def build_v2_morning_routes(
    dist_matrix,
    valid_stops,
    target_drivers,
    max_local_bags,
    max_distant_bags,
    min_driver_bags,
    max_route_km
):
    num_stops = len(valid_stops)
    if num_stops == 0:
        return []

    demand_list = [s["bags"] for s in valid_stops]
    city_list = [s["city"] for s in valid_stops]
    lat_list = [s["lat"] for s in valid_stops]
    lon_list = [s["lon"] for s in valid_stops]

    def route_bags(r):
        return sum(demand_list[n - 1] for n in r)

    def route_cities(r):
        return set(city_list[n - 1] for n in r)

    distant_buckets = {dc: [] for dc in DISTANT_CITIES}
    local_pool = []

    for node in range(1, num_stops + 1):
        c = city_list[node - 1]
        if c in DISTANT_CITIES:
            distant_buckets[c].append(node)
        else:
            local_pool.append(node)

    distant_routes = []
    for dc in ["Al Ain", "Abu Dhabi", "Fujairah / East Coast", "Ras Al Khaimah"]:
        nodes = distant_buckets[dc]
        if not nodes:
            continue
        ordered_dc, _ = optimize_route_order(nodes, dist_matrix, city_list)
        if route_bags(ordered_dc) <= max_local_bags:
            distant_routes.append(ordered_dc)
        else:
            chunk, c_bags = [], 0
            for n in ordered_dc:
                b = demand_list[n - 1]
                if c_bags + b <= max_local_bags:
                    chunk.append(n)
                    c_bags += b
                else:
                    distant_routes.append(chunk)
                    chunk, c_bags = [n], b
            if chunk:
                distant_routes.append(chunk)

    fuj_routes = [r for r in distant_routes if route_cities(r) == {"Fujairah / East Coast"}]
    rak_routes = [r for r in distant_routes if route_cities(r) == {"Ras Al Khaimah"}]

    if len(fuj_routes) == 1 and len(rak_routes) == 1:
        f_r, r_r = fuj_routes[0], rak_routes[0]
        f_bags, r_bags = route_bags(f_r), route_bags(r_r)
        if (f_bags < min_driver_bags or r_bags < min_driver_bags) and (f_bags + r_bags <= max_distant_bags):
            distant_routes.remove(f_r)
            distant_routes.remove(r_r)
            combined_fr, _ = optimize_route_order(f_r + r_r, dist_matrix, city_list)
            distant_routes.append(combined_fr)

    remaining_local_driver_slots = max(1, target_drivers - len(distant_routes))
    local_driver_capacity = remaining_local_driver_slots * max_local_bags

    def distant_backfill_priority(r):
        rc = route_cities(r)
        if "Fujairah / East Coast" in rc or "Ras Al Khaimah" in rc:
            return 0
        if "Al Ain" in rc:
            return 1
        return 2

    distant_routes.sort(key=distant_backfill_priority)

    for d_route in distant_routes:
        curr_bags = route_bags(d_route)
        rc = route_cities(d_route)
        local_bags_left = sum(demand_list[n - 1] for n in local_pool)
        local_overflow = max(0, local_bags_left - local_driver_capacity)

        if "Al Ain" in rc or "Abu Dhabi" in rc:
            if local_overflow <= 0 and curr_bags >= min_driver_bags:
                continue
            if local_overflow > 0:
                bags_needed = min(local_overflow, max(0, max_distant_bags - curr_bags))
            else:
                bags_needed = max(0, min_driver_bags - curr_bags)
        else:
            if local_overflow > 0:
                bags_needed = min(local_overflow, max(0, max_distant_bags - curr_bags))
            elif curr_bags < min_driver_bags:
                bags_needed = min_driver_bags - curr_bags
            else:
                continue

        if bags_needed <= 0 or not local_pool:
            continue

        if "Al Ain" in rc:
            eligible = [
                n for n in local_pool
                if city_list[n - 1] in {"Sharjah (City)", "Ajman"}
                and 25.26 <= lat_list[n - 1] <= 25.47
                and 55.34 <= lon_list[n - 1] <= 55.56
                and dist_matrix[0][n] <= 28.0
            ]
            radius = 3.5
            anchor_for_backfill = 0
        elif "Abu Dhabi" in rc:
            eligible = [
                n for n in local_pool
                if city_list[n - 1] == "Dubai" and lon_list[n - 1] < 55.45
            ]
            radius = 4.0
            ordered_primary, _ = optimize_route_order(d_route, dist_matrix, city_list)
            anchor_for_backfill = ordered_primary[-1]
        else:
            eligible = [
                n for n in local_pool
                if city_list[n - 1] in {"Sharjah (City)", "Sharjah (Far Inland)", "Ajman", "Umm Al Quwain"}
            ]
            radius = 4.5
            ordered_primary, _ = optimize_route_order(d_route, dist_matrix, city_list)
            anchor_for_backfill = ordered_primary[-1]

        if not eligible:
            continue

        micro_cluster = extract_micro_cluster(
            candidate_nodes=eligible,
            demand_list=demand_list,
            dist_matrix=dist_matrix,
            anchor_node=anchor_for_backfill,
            max_bags_to_add=bags_needed,
            max_radius_km=radius
        )

        for n in micro_cluster:
            d_route.append(n)
            local_pool.remove(n)

    local_routes = [[n] for n in local_pool]

    for i_idx in range(len(local_pool)):
        for j_idx in range(i_idx + 1, len(local_pool)):
            n_i, n_j = local_pool[i_idx], local_pool[j_idx]
            if dist_matrix[n_i][n_j] < 0.15:
                r_i = next((idx for idx, r in enumerate(local_routes) if n_i in r), -1)
                r_j = next((idx for idx, r in enumerate(local_routes) if n_j in r), -1)
                if r_i != -1 and r_j != -1 and r_i != r_j:
                    if route_bags(local_routes[r_i]) + route_bags(local_routes[r_j]) <= max_local_bags:
                        local_routes[r_i].extend(local_routes[r_j])
                        local_routes.pop(r_j)

    total_deliverable_bags = sum(demand_list)
    min_fleet_needed = math.ceil(total_deliverable_bags / max_local_bags)
    overall_target = min(max(target_drivers, min_fleet_needed), len(FLEET_DRIVERS))
    target_local_count = max(1, overall_target - len(distant_routes))

    for same_area_only in [True, False]:
        while len(local_routes) > target_local_count:
            best_pair, best_score = None, -float("inf")
            for a in range(len(local_routes)):
                for b in range(a + 1, len(local_routes)):
                    r_a, r_b = local_routes[a], local_routes[b]
                    if route_bags(r_a) + route_bags(r_b) > max_local_bags:
                        continue
                    c_a, c_b = route_cities(r_a), route_cities(r_b)
                    if same_area_only and c_a != c_b:
                        continue
                    if not are_cities_compatible_v2(c_a, c_b):
                        continue

                    _, km_a = optimize_route_order(r_a, dist_matrix, city_list)
                    _, km_b = optimize_route_order(r_b, dist_matrix, city_list)
                    _, km_comb = optimize_route_order(r_a + r_b, dist_matrix, city_list)

                    if km_comb <= max_route_km:
                        savings = (km_a + km_b) - km_comb
                        small_bonus = 35.0 if min(route_bags(r_a), route_bags(r_b)) < min_driver_bags else 0.0
                        score = savings + small_bonus
                        if score > best_score:
                            best_score = score
                            best_pair = (a, b)

            if best_pair is not None:
                i_a, i_b = best_pair
                local_routes[i_a] = optimize_route_order(
                    local_routes[i_a] + local_routes[i_b], dist_matrix, city_list
                )[0]
                local_routes.pop(i_b)
            else:
                break

    all_routes = distant_routes + local_routes

    changed = True
    while changed and len(all_routes) > 1:
        changed = False
        all_routes.sort(key=lambda r: route_bags(r))
        smallest = all_routes[0]
        smallest_cities = route_cities(smallest)

        if smallest_cities & {"Al Ain", "Abu Dhabi", "Fujairah / East Coast"}:
            break

        if route_bags(smallest) < min_driver_bags:
            temp = [list(r) for r in all_routes[1:]]
            all_absorbed = True
            for node in smallest:
                b_idx, b_detour = None, float("inf")
                n_city = {city_list[node - 1]}
                for idx, t_r in enumerate(temp):
                    t_cities = route_cities(t_r)
                    if t_cities & {"Al Ain", "Abu Dhabi"}:
                        continue
                    is_t_distant = bool(t_cities & DISTANT_CITIES)
                    cap = max_distant_bags if (is_t_distant and not (n_city & DISTANT_CITIES)) else max_local_bags
                    if route_bags(t_r) + demand_list[node - 1] > cap:
                        continue
                    if not are_cities_compatible_v2(t_cities, n_city, allow_fuj_rak_combo=True):
                        continue
                    _, o_km = optimize_route_order(t_r, dist_matrix, city_list)
                    _, n_km = optimize_route_order(t_r + [node], dist_matrix, city_list)
                    detour = n_km - o_km
                    if n_km <= max_route_km and detour < b_detour:
                        b_detour, b_idx = detour, idx
                if b_idx is not None:
                    temp[b_idx].append(node)
                else:
                    all_absorbed = False
                    break
            if all_absorbed:
                all_routes = [optimize_route_order(r, dist_matrix, city_list)[0] for r in temp]
                changed = True

    return [optimize_route_order(r, dist_matrix, city_list)[0] for r in all_routes]


def get_primary_route_label(route, valid_stops):
    primary_distant = []
    return_cities = []
    for node in route:
        c = valid_stops[node - 1]["city"]
        if c in DISTANT_CITIES:
            if c not in primary_distant:
                primary_distant.append(c)
        else:
            if c not in return_cities:
                return_cities.append(c)

    if primary_distant:
        p_str = " + ".join(primary_distant)
        if return_cities:
            return f"{p_str} ➔ Return: {', '.join(return_cities)}"
        return p_str

    city_bags = {}
    for node in route:
        c = valid_stops[node - 1]["city"]
        city_bags[c] = city_bags.get(c, 0) + valid_stops[node - 1]["bags"]
    sorted_c = sorted(city_bags.keys(), key=lambda c: city_bags[c], reverse=True)
    return " / ".join(sorted_c)


def assign_drivers_with_rotation(routes, valid_stops, dist_matrix, far_yesterday_names, resting_today_names):
    stats = get_recent_driver_stats()
    for d in far_yesterday_names:
        if d in stats:
            stats[d]["went_far_yesterday"] = True

    available_pool = [d for d in FLEET_DRIVERS if d not in resting_today_names]
    num_routes = len(routes)

    if len(available_pool) > num_routes:
        available_pool.sort(
            key=lambda d: (
                stats[d]["went_far_yesterday"],
                stats[d]["distant_count_7d"],
                stats[d]["km_7d"]
            )
        )
        active_drivers = available_pool[:num_routes]
    else:
        active_drivers = list(available_pool)
        for d in resting_today_names:
            if len(active_drivers) < num_routes and d not in active_drivers:
                active_drivers.append(d)

    city_list = [s["city"] for s in valid_stops]
    route_meta = []
    for r_idx, r in enumerate(routes):
        _, one_way_km = optimize_route_order(r, dist_matrix, city_list)
        r_cities = {valid_stops[n - 1]["city"] for n in r}
        is_distant = bool(r_cities & DISTANT_CITIES)
        max_wh = max(valid_stops[n - 1]["wh_road_km"] for n in r)
        route_meta.append({
            "orig_idx": r_idx,
            "route": r,
            "is_distant": is_distant,
            "one_way_km": one_way_km,
            "max_wh": max_wh
        })

    route_meta.sort(key=lambda x: (x["is_distant"], x["max_wh"], x["one_way_km"]), reverse=True)

    fresh_drivers = [d for d in active_drivers if not stats[d]["went_far_yesterday"]]
    rotated_drivers = [d for d in active_drivers if stats[d]["went_far_yesterday"]]

    fresh_drivers.sort(key=lambda d: (stats[d]["distant_count_7d"], stats[d]["km_7d"]))
    rotated_drivers.sort(key=lambda d: stats[d]["km_7d"])

    ordered_driver_queue = fresh_drivers + rotated_drivers

    assigned_pairs = []
    for idx, meta in enumerate(route_meta):
        d_name = ordered_driver_queue[idx] if idx < len(ordered_driver_queue) else f"Driver {idx + 1}"
        assigned_pairs.append((d_name, meta["route"]))

    return assigned_pairs


def resequence_driver_stops(driver_rows, wh_lat, wh_lon):
    if not driver_rows:
        return []

    coords = [(wh_lat, wh_lon)] + [
        (float(r["Resolved_Lat"]), float(r["Resolved_Lon"])) for r in driver_rows
    ]
    stop_cities = [r.get("City_Area", "") for r in driver_rows]
    dist_mat = build_road_distance_matrix(coords)
    ordered_nodes, one_way_km = optimize_route_order(
        list(range(1, len(driver_rows) + 1)), dist_mat, stop_cities
    )

    reordered_rows = []
    prev_node = 0
    total_bags = sum(int(float(r.get("Bags", 1) or 1)) for r in driver_rows)
    has_distant = any(c in DISTANT_CITIES for c in stop_cities)

    for seq_num, node in enumerate(ordered_nodes, start=1):
        row = dict(driver_rows[node - 1])
        leg_km = dist_mat[prev_node][node]
        prev_node = node
        c_area = row.get("City_Area", "")
        leg_type = "Primary City" if (not has_distant or c_area in DISTANT_CITIES) else "Return-Leg Cluster"

        row["Stop_Sequence"] = seq_num
        row["Stop_Phase"] = leg_type
        row["Leg_Distance_KM"] = round(leg_km, 2)
        row["Route_Total_Bags"] = total_bags
        row["Route_OneWay_KM"] = round(one_way_km, 2)
        reordered_rows.append(row)

    est_finish, est_hrs = predict_driver_finish_time(reordered_rows, one_way_km)
    for row in reordered_rows:
        row["Est_Finish_Time"] = est_finish
        row["Est_Shift_Hours"] = est_hrs

    return reordered_rows


def build_google_maps_nav_links(wh_lat, wh_lon, stops):
    if not stops:
        return []

    links = []
    chunk_size = 9
    for start_i in range(0, len(stops), chunk_size):
        chunk = stops[start_i:start_i + chunk_size]
        if start_i == 0:
            origin_pt = f"{wh_lat:.6f},{wh_lon:.6f}"
        else:
            prev_s = stops[start_i - 1]
            origin_pt = f"{float(prev_s['Resolved_Lat']):.6f},{float(prev_s['Resolved_Lon']):.6f}"

        pts = [origin_pt]
        for s in chunk:
            lat, lon = float(s["Resolved_Lat"]), float(s["Resolved_Lon"])
            if lon >= 55.95 and f"{UAE_MASAFI_WAYPOINT[0]:.6f},{UAE_MASAFI_WAYPOINT[1]:.6f}" not in pts:
                pts.append(f"{UAE_MASAFI_WAYPOINT[0]:.6f},{UAE_MASAFI_WAYPOINT[1]:.6f}")
            pts.append(f"{lat:.6f},{lon:.6f}")

        part_num = (start_i // chunk_size) + 1
        s_first = chunk[0]["Stop_Sequence"]
        s_last = chunk[-1]["Stop_Sequence"]
        label = "🗺️ Open Route in Google Maps ↗" if len(stops) <= chunk_size else f"🗺️ Part {part_num} (Stops #{s_first}–#{s_last}) ↗"
        links.append((label, "https://www.google.com/maps/dir/" + "/".join(pts)))

    return links


# ==========================================
# V3 FEATURE: REAL UAE EMIRATE & REGION BORDERS (GEOJSON)
# ==========================================
UAE_EMIRATE_SPECS = [
    {
        "name": "ABU DHABI",
        "queries": ["Abu Dhabi Emirate, United Arab Emirates", "Abu Dhabi, United Arab Emirates"],
        "color": "#0284c7",
        "label_pos": (24.35, 54.55),
    },
    {
        "name": "AL AIN",
        "queries": ["Al Ain Region, United Arab Emirates", "Al Ain Municipality, United Arab Emirates", "Al Ain, Abu Dhabi, United Arab Emirates"],
        "color": "#d97706",
        "label_pos": (24.22, 55.74),
    },
    {
        "name": "DUBAI",
        "queries": ["Dubai Emirate, United Arab Emirates", "Dubai, United Arab Emirates"],
        "color": "#2563eb",
        "label_pos": (25.10, 55.28),
    },
    {
        "name": "SHARJAH",
        "queries": ["Sharjah Emirate, United Arab Emirates", "Sharjah, United Arab Emirates"],
        "color": "#059669",
        "label_pos": (25.33, 55.52),
    },
    {
        "name": "AJMAN",
        "queries": ["Ajman Emirate, United Arab Emirates", "Ajman, United Arab Emirates"],
        "color": "#dc2626",
        "label_pos": (25.41, 55.48),
    },
    {
        "name": "UMM AL QUWAIN",
        "queries": ["Umm Al Quwain Emirate, United Arab Emirates", "Umm Al Quwain, United Arab Emirates"],
        "color": "#0d9488",
        "label_pos": (25.55, 55.62),
    },
    {
        "name": "RAS AL KHAIMAH",
        "queries": ["Ras Al Khaimah Emirate, United Arab Emirates", "Ras Al Khaimah, United Arab Emirates"],
        "color": "#9333ea",
        "label_pos": (25.78, 55.96),
    },
    {
        "name": "FUJAIRAH",
        "queries": ["Fujairah Emirate, United Arab Emirates", "Fujairah, United Arab Emirates"],
        "color": "#7c3aed",
        "label_pos": (25.14, 56.28),
    },
]


def _extract_al_ain_from_abudhabi_geojson(ad_geojson):
    def clip_ring(ring):
        clipped = []
        for lon, lat in ring:
            in_ruga = (24.40 <= lat <= 24.58 and lon >= 55.20)
            if lon >= 55.32 or in_ruga:
                clipped.append([lon, lat])
            elif lat >= 23.90 and lon >= 55.00:
                clipped.append([55.32, lat])
        return clipped if len(clipped) >= 4 else []

    g_type = ad_geojson.get("type")
    coords = ad_geojson.get("coordinates", [])
    new_polys = []

    if g_type == "Polygon" and coords:
        outer = clip_ring(coords[0])
        if outer:
            new_polys.append([outer])
    elif g_type == "MultiPolygon":
        for poly in coords:
            if poly:
                outer = clip_ring(poly[0])
                if outer:
                    new_polys.append([outer])

    if new_polys:
        return {"type": "MultiPolygon", "coordinates": new_polys}
    return None


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fetch_uae_real_borders_geojson():
    osm_headers = {
        "User-Agent": "LionDeliveryDispatchV3/3.0 (uae-state-borders; contact@liondelivery.ae)",
        "Accept": "application/json"
    }
    results = []
    abudhabi_geom = None

    for spec in UAE_EMIRATE_SPECS:
        found_geom = None
        for q in spec["queries"]:
            try:
                url = (
                    "https://nominatim.openstreetmap.org/search?"
                    f"q={urllib.parse.quote(q)}&countrycodes=ae&format=json"
                    "&polygon_geojson=1&polygon_threshold=0.0015&limit=5"
                )
                resp = requests.get(url, headers=osm_headers, timeout=10)
                if resp.status_code == 200:
                    hits = resp.json()
                    for h in hits:
                        gj = h.get("geojson", {})
                        if gj.get("type") in ("Polygon", "MultiPolygon"):
                            bbox = [float(x) for x in h.get("boundingbox", [0, 0, 0, 0])]
                            span = abs(bbox[1] - bbox[0]) + abs(bbox[3] - bbox[2])
                            if spec["name"] == "AL AIN" and span < 0.25:
                                continue
                            found_geom = gj
                            break
                if found_geom:
                    break
            except Exception:
                pass

        if spec["name"] == "ABU DHABI" and found_geom:
            abudhabi_geom = found_geom

        if spec["name"] == "AL AIN" and not found_geom and abudhabi_geom:
            found_geom = _extract_al_ain_from_abudhabi_geojson(abudhabi_geom)

        if found_geom:
            results.append({
                "name": spec["name"],
                "color": spec["color"],
                "label_pos": spec["label_pos"],
                "geojson": found_geom
            })

    return results


def add_uae_state_grid_to_map(m, show_by_default=True):
    grid_fg = folium.FeatureGroup(name="🗺️ UAE Emirate Borders (Real GeoJSON)", show=show_by_default)
    borders = fetch_uae_real_borders_geojson()

    for item in borders:
        state_color = item["color"]
        feature = {
            "type": "Feature",
            "properties": {"name": item["name"], "color": state_color},
            "geometry": item["geojson"]
        }

        folium.GeoJson(
            feature,
            style_function=lambda feat, c=state_color: {
                "color": c,
                "weight": 2.5,
                "opacity": 0.9,
                "dashArray": "6, 4",
                "fillColor": c,
                "fillOpacity": 0.06,
            },
            interactive=False
        ).add_to(grid_fg)

        label_html = (
            f'<div style="display:inline-block; background:rgba(255,255,255,0.88); '
            f'color:{state_color}; border:1.5px solid {state_color}; border-radius:4px; '
            f'padding:2px 6px; font-family:Arial,sans-serif; font-size:10px; '
            f'font-weight:800; white-space:nowrap; pointer-events:none; '
            f'box-shadow:0 1px 3px rgba(0,0,0,0.25);">'
            f'{item["name"]}</div>'
        )
        folium.Marker(
            location=item["label_pos"],
            icon=folium.DivIcon(html=label_html, icon_size=(130, 22), icon_anchor=(65, 11))
        ).add_to(grid_fg)

    grid_fg.add_to(m)


# ==========================================
# 6. SIDEBAR: DUAL INPUT (CSV UPLOAD + AUTO-LOGIN API SYNC)
# ==========================================
db_stats = get_recent_driver_stats()
default_far_yesterday = [d for d, st_info in db_stats.items() if st_info["went_far_yesterday"]]

st.sidebar.title("🧪 V3 LAB — Dispatch & Real Borders")

selected_driver_filter = st.sidebar.selectbox(
    "🔍 View Driver on Map",
    options=["Show All Drivers"] + FLEET_DRIVERS,
    index=0
)
show_state_grid = st.sidebar.checkbox("🗺️ Show Real Emirate Borders on Map", value=True)

st.sidebar.markdown("### 📂 1. Load Delivery Orders")
data_source = st.sidebar.radio(
    "Input Method:",
    ["Upload CSV File", "⚡ Live API Sync (location-board)"],
    index=0
)

raw_rows = []
fieldnames = ["Bag_Number", "Map_URL", "Latitude", "Longitude", "Area", "Customer", "Phone", "Bags"]
bag_col = "Bag_Number"
source_name = "manual_csv"
raw_bytes_len = 0

if data_source == "Upload CSV File":
    uploaded_file = st.sidebar.file_uploader("Upload 'lion_delivery_all_bags.csv'", type=["csv"])
    if uploaded_file is not None:
        raw_bytes = uploaded_file.getvalue()
        raw_bytes_len = len(raw_bytes)
        source_name = uploaded_file.name
        content = raw_bytes.decode("utf-8-sig").splitlines()
        reader = csv.DictReader(content)
        raw_rows = list(reader)
        if reader.fieldnames:
            fieldnames = list(reader.fieldnames)
            bag_col = fieldnames[0]
else:
    secret_email = ""
    secret_pass = ""
    secret_token = ""
    try:
        secret_email = st.secrets.get("LION_EMAIL", "sole@gmail.com")
        secret_pass = st.secrets.get("LION_PASSWORD", "")
        secret_token = st.secrets.get("LION_API_TOKEN", "")
    except Exception:
        secret_email = "sole@gmail.com"

    ld_user = st.sidebar.text_input("Lion Delivery Email", value=secret_email)
    ld_pass = st.sidebar.text_input("Lion Delivery Password", value=secret_pass, type="password")

    with st.sidebar.expander("🔧 Advanced API / Token Override"):
        auth_url = st.text_input(
            "Login Endpoint URL",
            value="https://api.liondelivery.ae/api/v1/auth/login/"
        )
        api_endpoint = st.text_input(
            "Location-Board Endpoint",
            value=DEFAULT_LOCATION_BOARD_API
        )
        manual_bearer = st.text_input(
            "Optional Direct Bearer Token",
            value=secret_token,
            type="password"
        )

    if st.sidebar.button("⚡ Fetch Live Location-Board Orders", type="primary"):
        active_token = ""
        if ld_user and ld_pass:
            with st.spinner("Logging in for fresh 15-minute access token..."):
                fresh_tok, err_msg = obtain_fresh_jwt_token(auth_url, ld_user, ld_pass)
                if fresh_tok:
                    active_token = fresh_tok
                elif manual_bearer.strip():
                    active_token = manual_bearer.strip()
                else:
                    st.sidebar.error(f"Auto-login error: {err_msg}")
        elif manual_bearer.strip():
            active_token = manual_bearer.strip()
        else:
            st.sidebar.error("Enter your password (or save LION_PASSWORD in Streamlit Secrets).")

        if active_token:
            with st.spinner("Pulling all pages (including short links) from location-board..."):
                pulled_rows, pull_err = pull_all_location_board_bags(api_endpoint, active_token)
                if pull_err:
                    st.sidebar.error(pull_err)
                elif pulled_rows:
                    st.session_state["api_raw_rows"] = pulled_rows
                    st.session_state["api_sync_counter"] = st.session_state.get("api_sync_counter", 0) + 1
                    st.sidebar.success(f"✅ Synced ALL {len(pulled_rows)} bags from location-board!")
                else:
                    st.sidebar.warning("Connected successfully, but 0 bags are currently on the location-board.")

    if "api_raw_rows" in st.session_state:
        raw_rows = st.session_state["api_raw_rows"]
        raw_bytes_len = len(raw_rows) + st.session_state.get("api_sync_counter", 0)
        source_name = "live_location_board_api"
        fieldnames = ["Bag_Number", "Map_URL", "Latitude", "Longitude", "Area", "Customer", "Phone", "Bags"]
        bag_col = "Bag_Number"

st.sidebar.markdown("### 👥 Driver Rotation Rules")
far_yesterday_input = st.sidebar.multiselect(
    "Went Far Yesterday (Al Ain / Abu Dhabi / Fujairah / RAK):",
    options=FLEET_DRIVERS,
    default=default_far_yesterday
)
resting_today_input = st.sidebar.multiselect(
    "Resting / Off Today:",
    options=FLEET_DRIVERS,
    default=[]
)

st.sidebar.markdown("### ⚙️ Route & Backfill Rules")
target_drivers_input = st.sidebar.slider("Target Morning Drivers", min_value=3, max_value=7, value=6)
max_bags_local_input = st.sidebar.slider("Max Bags (Local Driver - DXB/SHJ)", min_value=15, max_value=25, value=21)
max_bags_distant_input = st.sidebar.slider("Target Cap (Distant Driver w/ Backfill)", min_value=14, max_value=19, value=16)
min_bags_input = st.sidebar.slider("Min Bags per Driver (Combine / Backfill)", min_value=6, max_value=12, value=10)
max_dist_input = st.sidebar.number_input("Max Warehouse Road Distance (KM)", value=260.0, step=10.0)


# ==========================================
# 7. MAIN APPLICATION PIPELINE
# ==========================================
wh_lat, wh_lon = resolve_google_maps_url(WAREHOUSE_URL)
if not wh_lat:
    wh_lat, wh_lon = 25.4052, 55.5136

if not raw_rows:
    st.info("👋 Upload `lion_delivery_all_bags.csv` OR switch to **⚡ Live API Sync (location-board)** in the sidebar.")
    with st.expander("📊 View 7-Day Driver Rotation History"):
        hist_rows = [
            {
                "Driver": d,
                "7-Day KM": round(info["km_7d"], 1),
                "7-Day Bags": info["bags_7d"],
                "Distant Trips (7d)": info["distant_count_7d"],
                "Last Area": info["last_city"]
            }
            for d, info in db_stats.items()
        ]
        st.table(hist_rows)
    st.stop()

current_config_sig = (
    "v3.0_real_geojson_borders",
    source_name,
    raw_bytes_len,
    target_drivers_input,
    max_bags_local_input,
    max_bags_distant_input,
    min_bags_input,
    max_dist_input,
    tuple(sorted(far_yesterday_input)),
    tuple(sorted(resting_today_input))
)

force_rerun = st.sidebar.button("🔄 Re-Run Optimization")

if (
    "dispatch_data" not in st.session_state
    or st.session_state.get("config_sig") != current_config_sig
    or force_rerun
):
    with st.spinner("Resolving short links & running Primary-First Sequencing..."):
        resolved, unresolvable, oman_stops = [], [], []
        url_col = next((c for c in fieldnames if any(k in c.lower() for k in ["url", "link", "map", "location"])), "Map_URL")

        for row in raw_rows:
            lat, lon, is_fallback = extract_row_coordinates(row, url_col)
            if lat and lon:
                if is_in_oman(lat, lon):
                    oman_stops.append({
                        "row_data": row,
                        "lat": lat,
                        "lon": lon,
                        "city": "Oman Territory / Border",
                        "bags": int(float(row.get("Bags", 1) or 1)),
                        "is_fallback": is_fallback
                    })
                else:
                    resolved.append({
                        "row_data": row,
                        "lat": lat,
                        "lon": lon,
                        "bags": int(float(row.get("Bags", 1) or 1)),
                        "city": identify_uae_city(lat, lon),
                        "is_fallback": is_fallback
                    })
            else:
                unresolvable.append(row)

        if not resolved:
            st.error("Could not resolve valid UAE coordinates from the input data.")
            st.stop()

        all_coords = [(wh_lat, wh_lon)] + [(s["lat"], s["lon"]) for s in resolved]
        full_matrix = build_road_distance_matrix(all_coords)

        valid_stops, far_stops = [], []
        for i, stop in enumerate(resolved, start=1):
            stop["wh_road_km"] = full_matrix[0][i]
            if stop["wh_road_km"] > max_dist_input:
                far_stops.append(stop)
            else:
                valid_stops.append(stop)

        deliv_coords = [(wh_lat, wh_lon)] + [(s["lat"], s["lon"]) for s in valid_stops]
        dist_mat = build_road_distance_matrix(deliv_coords)
        valid_cities = [s["city"] for s in valid_stops]

        routes = build_v2_morning_routes(
            dist_mat,
            valid_stops,
            target_drivers=target_drivers_input,
            max_local_bags=max_bags_local_input,
            max_distant_bags=max_bags_distant_input,
            min_driver_bags=min_bags_input,
            max_route_km=600.0
        )

        driver_route_pairs = assign_drivers_with_rotation(
            routes, valid_stops, dist_mat,
            far_yesterday_names=far_yesterday_input,
            resting_today_names=resting_today_input
        )

        final_rows = []
        for d_name, route in driver_route_pairs:
            ordered, total_km = optimize_route_order(route, dist_mat, valid_cities)
            total_bags = sum(valid_stops[n - 1]["bags"] for n in ordered)
            corridor_label = get_primary_route_label(ordered, valid_stops)
            driver_display = f"{d_name} ({corridor_label})"
            has_distant_in_route = any(valid_stops[n - 1]["city"] in DISTANT_CITIES for n in ordered)

            route_temp_rows = []
            prev = 0
            for seq, node in enumerate(ordered, start=1):
                stop = valid_stops[node - 1]
                leg_km = dist_mat[prev][node]
                prev = node
                phase_label = (
                    "Primary City"
                    if (not has_distant_in_route or stop["city"] in DISTANT_CITIES)
                    else "Return-Leg Cluster"
                )
                status_str = "ASSIGNED_AREA_FALLBACK_NO_PIN" if stop.get("is_fallback") else "ASSIGNED_630AM"
                item = dict(stop["row_data"])
                item.update({
                    "Assigned_Driver": d_name,
                    "Driver_ID": driver_display,
                    "Stop_Sequence": seq,
                    "Stop_Phase": phase_label,
                    "City_Area": stop["city"],
                    "Warehouse_Road_KM": round(stop["wh_road_km"], 2),
                    "Leg_Distance_KM": round(leg_km, 2),
                    "Route_Total_Bags": total_bags,
                    "Route_OneWay_KM": round(total_km, 2),
                    "Resolved_Lat": round(stop["lat"], 6),
                    "Resolved_Lon": round(stop["lon"], 6),
                    "Dispatch_Status": status_str
                })
                route_temp_rows.append(item)

            est_finish, est_hrs = predict_driver_finish_time(route_temp_rows, total_km)
            for item in route_temp_rows:
                item["Est_Finish_Time"] = est_finish
                item["Est_Shift_Hours"] = est_hrs
                final_rows.append(item)

        for fs in far_stops:
            item = dict(fs["row_data"])
            item.update({
                "Assigned_Driver": "NOT GOING",
                "Driver_ID": f"NOT GOING - VERY FAR (>{int(max_dist_input)}KM)",
                "Stop_Sequence": "",
                "Stop_Phase": "Excluded",
                "City_Area": fs["city"],
                "Warehouse_Road_KM": round(fs["wh_road_km"], 2),
                "Leg_Distance_KM": "",
                "Route_Total_Bags": "",
                "Route_OneWay_KM": "",
                "Est_Finish_Time": "",
                "Est_Shift_Hours": "",
                "Resolved_Lat": round(fs["lat"], 6),
                "Resolved_Lon": round(fs["lon"], 6),
                "Dispatch_Status": "UNABLE_TO_DELIVER_TOO_FAR"
            })
            final_rows.append(item)

        for os_stop in oman_stops:
            item = dict(os_stop["row_data"])
            item.update({
                "Assigned_Driver": "NOT GOING",
                "Driver_ID": "NOT GOING - OUTSIDE UAE (OMAN)",
                "Stop_Sequence": "",
                "Stop_Phase": "Excluded",
                "City_Area": "Oman Territory",
                "Warehouse_Road_KM": "",
                "Leg_Distance_KM": "",
                "Route_Total_Bags": "",
                "Route_OneWay_KM": "",
                "Est_Finish_Time": "",
                "Est_Shift_Hours": "",
                "Resolved_Lat": round(os_stop["lat"], 6),
                "Resolved_Lon": round(os_stop["lon"], 6),
                "Dispatch_Status": "EXCLUDED_OUTSIDE_UAE"
            })
            final_rows.append(item)

        for bad_row in unresolvable:
            item = dict(bad_row)
            item.update({
                "Assigned_Driver": "UNASSIGNED",
                "Driver_ID": "NOT GOING - MISSING PIN & AREA",
                "Stop_Sequence": "",
                "Stop_Phase": "Missing Location",
                "City_Area": str(bad_row.get("Area") or "Unknown"),
                "Warehouse_Road_KM": "",
                "Leg_Distance_KM": "",
                "Route_Total_Bags": "",
                "Route_OneWay_KM": "",
                "Est_Finish_Time": "",
                "Est_Shift_Hours": "",
                "Resolved_Lat": round(wh_lat, 6),
                "Resolved_Lon": round(wh_lon, 6),
                "Dispatch_Status": "MISSING_COORDINATES_IN_PORTAL"
            })
            final_rows.append(item)

        st.session_state["dispatch_data"] = final_rows
        st.session_state["config_sig"] = current_config_sig

master_rows = st.session_state["dispatch_data"]

active_driver_ids = []
active_named_drivers = []
for r in master_rows:
    d_id = r.get("Driver_ID", "")
    d_name = r.get("Assigned_Driver", "")
    if d_id and "NOT GOING" not in d_id and d_id != "UNASSIGNED":
        if d_id not in active_driver_ids:
            active_driver_ids.append(d_id)
        if d_name and d_name not in active_named_drivers:
            active_named_drivers.append(d_name)

resting_drivers_today = [d for d in FLEET_DRIVERS if d not in active_named_drivers]
total_bags_assigned = sum(int(float(r.get("Bags", 1) or 1)) for r in master_rows if "NOT GOING" not in r["Driver_ID"])
excluded_bags = [r for r in master_rows if "NOT GOING" in r["Driver_ID"]]
no_pin_bags = [
    r for r in master_rows
    if r.get("Dispatch_Status") in ("ASSIGNED_AREA_FALLBACK_NO_PIN", "MISSING_COORDINATES_IN_PORTAL")
]

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Active Drivers", f"{len(active_driver_ids)} / 7")
kpi2.metric("Total Bags Assigned", f"{total_bags_assigned} / {len(master_rows)}")
kpi3.metric("Resting Drivers", ", ".join(resting_drivers_today) if resting_drivers_today else "None")
kpi4.metric(f"Excluded (>{int(max_dist_input)}km / Oman)", len(excluded_bags))

if no_pin_bags:
    with st.expander(f"⚠️ {len(no_pin_bags)} Bag(s) Had No Exact Coordinate Pin (Resolved via Area / Short-Link Fallback)", expanded=True):
        st.table([
            {
                "Bag Code": r.get(bag_col, ""),
                "Map URL": r.get("Map_URL", ""),
                "Portal Area": r.get("Area", ""),
                "Assigned To": r.get("Driver_ID", ""),
                "Stop #": r.get("Stop_Sequence", "-")
            }
            for r in no_pin_bags
        ])

# ==========================================
# 8. MANUAL CONTROLS
# ==========================================
ctrl_tab1, ctrl_tab2 = st.tabs(["🔄 Move Single Bag", "🔀 Swap Drivers Between Routes"])

with ctrl_tab1:
    col_re1, col_re2, col_re3 = st.columns([3, 2, 1.5])
    bag_options = [
        (f"{r.get(bag_col, '')} | {r.get('Driver_ID', '')} (Stop #{r.get('Stop_Sequence', '-')} • {r.get('City_Area', '')})", idx)
        for idx, r in enumerate(master_rows) if r.get("Resolved_Lat")
    ]
    selected_bag_idx = col_re1.selectbox(
        "Select Bag to Reassign",
        options=[idx for _, idx in bag_options],
        format_func=lambda i: next(lbl for lbl, idx in bag_options if idx == i)
    )
    target_driver_choice = col_re2.selectbox(
        "Move To Driver",
        options=active_driver_ids + [f"NOT GOING - VERY FAR (>{int(max_dist_input)}KM)", "NOT GOING - OUTSIDE UAE (OMAN)"]
    )
    if col_re3.button("Move Bag & Re-Sequence"):
        old_drv = master_rows[selected_bag_idx]["Driver_ID"]
        if old_drv != target_driver_choice:
            master_rows[selected_bag_idx]["Driver_ID"] = target_driver_choice
            if "NOT GOING" not in target_driver_choice:
                master_rows[selected_bag_idx]["Assigned_Driver"] = target_driver_choice.split(" (")[0]
                master_rows[selected_bag_idx]["Dispatch_Status"] = "ASSIGNED_MANUAL_OVERRIDE"
            else:
                master_rows[selected_bag_idx]["Assigned_Driver"] = "NOT GOING"
                master_rows[selected_bag_idx]["Dispatch_Status"] = "MANUAL_EXCLUDED"

            for affected_drv in [old_drv, target_driver_choice]:
                if "NOT GOING" not in affected_drv:
                    d_indices = [i for i, r in enumerate(master_rows) if r.get("Driver_ID") == affected_drv]
                    d_rows = [master_rows[i] for i in d_indices]
                    updated_rows = resequence_driver_stops(d_rows, wh_lat, wh_lon)
                    for i, updated_row in zip(d_indices, updated_rows):
                        master_rows[i] = updated_row
                else:
                    for r in master_rows:
                        if r.get("Driver_ID") == affected_drv:
                            r["Stop_Sequence"] = ""
                            r["Stop_Phase"] = "Excluded"
                            r["Leg_Distance_KM"] = ""
                            r["Route_Total_Bags"] = ""
                            r["Route_OneWay_KM"] = ""
                            r["Est_Finish_Time"] = ""
                            r["Est_Shift_Hours"] = ""

            st.session_state["dispatch_data"] = master_rows
            st.rerun()

with ctrl_tab2:
    sc1, sc2, sc3 = st.columns([2, 2, 1.5])
    swap_driver_a = sc1.selectbox("Driver 1", options=FLEET_DRIVERS, index=0)
    swap_driver_b = sc2.selectbox("Driver 2", options=FLEET_DRIVERS, index=1)
    if sc3.button("🔀 Swap Entire Route"):
        if swap_driver_a != swap_driver_b:
            for r in master_rows:
                curr_d = r.get("Assigned_Driver", "")
                curr_id = r.get("Driver_ID", "")
                if curr_d == swap_driver_a and " (" in curr_id:
                    corridor_part = curr_id.split(" (", 1)[1]
                    r["Assigned_Driver"] = swap_driver_b
                    r["Driver_ID"] = f"{swap_driver_b} ({corridor_part}"
                elif curr_d == swap_driver_b and " (" in curr_id:
                    corridor_part = curr_id.split(" (", 1)[1]
                    r["Assigned_Driver"] = swap_driver_a
                    r["Driver_ID"] = f"{swap_driver_a} ({corridor_part}"
            st.session_state["dispatch_data"] = master_rows
            st.rerun()

# ==========================================
# 9. LARGE MAP RENDER (WITH REAL GEOJSON EMIRATE BORDERS)
# ==========================================
m = folium.Map(location=[wh_lat, wh_lon], zoom_start=9, tiles=None, control_scale=True)
Fullscreen(position="topleft", force_separate_button=True).add_to(m)

folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    attr="Google Maps",
    name="Google Maps (Streets)",
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Esri Street Map",
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    attr="Google Satellite",
    name="Google Satellite + Roads",
    overlay=False,
    control=True
).add_to(m)

add_uae_state_grid_to_map(m, show_by_default=show_state_grid)

folium.Marker(
    location=[wh_lat, wh_lon],
    popup="<b>Ajman Warehouse (6:30 AM Start)</b>",
    tooltip="Ajman Warehouse",
    icon=folium.Icon(color="black", icon="home", prefix="fa")
).add_to(m)

route_coords_for_bounds = [(wh_lat, wh_lon)]
legend_chips = []
seen_marker_coords = {}

for d_idx, d_name in enumerate(active_driver_ids):
    if selected_driver_filter != "Show All Drivers" and selected_driver_filter.lower() not in d_name.lower():
        continue

    color = DRIVER_COLORS[d_idx % len(DRIVER_COLORS)]
    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))

    if not d_stops:
        continue

    total_bags = d_stops[0].get("Route_Total_Bags", len(d_stops))
    total_km = d_stops[0].get("Route_OneWay_KM", "0")
    nav_links = build_google_maps_nav_links(wh_lat, wh_lon, d_stops)
    primary_nav_url = nav_links[0][1] if nav_links else "#"

    fg = folium.FeatureGroup(name=f"{d_name} ({total_bags} bags | {total_km} km)", show=True)

    waypoints = [(wh_lat, wh_lon)] + [(float(s["Resolved_Lat"]), float(s["Resolved_Lon"])) for s in d_stops]
    for pt in waypoints:
        route_coords_for_bounds.append(pt)

    road_polyline = get_osrm_route_geometry(waypoints)
    AntPath(locations=road_polyline, color=color, weight=5, opacity=0.88, tooltip=d_name).add_to(fg)

    for s in d_stops:
        raw_lat, raw_lon = float(s["Resolved_Lat"]), float(s["Resolved_Lon"])
        coord_key = (round(raw_lat, 5), round(raw_lon, 5))
        dup_count = seen_marker_coords.get(coord_key, 0)
        seen_marker_coords[coord_key] = dup_count + 1

        disp_lat = raw_lat + (dup_count * 0.00014)
        disp_lon = raw_lon + (dup_count * 0.00014)

        phase_str = s.get("Stop_Phase", "Primary City")
        is_area_fb = s.get("Dispatch_Status") == "ASSIGNED_AREA_FALLBACK_NO_PIN"
        border_style = "2px dotted #ff1744" if is_area_fb else ("2px dashed #ffeb3b" if phase_str == "Return-Leg Cluster" else "2px solid #fff")

        pin_url = f"https://www.google.com/maps?q={raw_lat},{raw_lon}"
        badge_html = (
            f'<div style="background:{color}; color:#fff; border-radius:50%; '
            f'width:24px; height:24px; text-align:center; font-weight:bold; '
            f'font-size:11px; line-height:24px; border:{border_style}; '
            f'box-shadow:0 2px 4px rgba(0,0,0,0.4);">'
            f'{s["Stop_Sequence"]}</div>'
        )
        badge = folium.DivIcon(html=badge_html, icon_size=(24, 24), icon_anchor=(12, 12))
        fb_note = "<br><b style='color:#d50000;'>⚠️ Area-Only Pin (No Exact Coords in Portal)</b>" if is_area_fb else ""
        popup_html = (
            f'<div style="font-family:Arial,sans-serif; font-size:12px; min-width:200px;">'
            f'<b>{d_name} — Stop #{s["Stop_Sequence"]}</b>{fb_note}<br>'
            f'<b>Phase:</b> {phase_str}<br>'
            f'<b>Bag:</b> {s.get(bag_col, "")}<br>'
            f'<b>State/Zone:</b> {s.get("City_Area", "")}<br>'
            f'<b>From WH:</b> {s.get("Warehouse_Road_KM", "")} km (+{s.get("Leg_Distance_KM", "")} km leg)<br>'
            f'<b>Est. Finish:</b> {s.get("Est_Finish_Time", "")}<br>'
            f'<a href="{pin_url}" target="_blank" style="color:#1a73e8; font-weight:bold;">Open Pin ↗</a> | '
            f'<a href="{primary_nav_url}" target="_blank" style="color:#0b8043; font-weight:bold;">Driver Route ↗</a>'
            f'</div>'
        )
        folium.Marker(
            location=[disp_lat, disp_lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{s.get(bag_col, '')} • Stop #{s['Stop_Sequence']} ({phase_str}) • {s.get('City_Area', '')}",
            icon=badge
        ).add_to(fg)

    fg.add_to(m)

    legend_chips.append(
        f'<span style="display:inline-flex; align-items:center; margin-right:14px; margin-bottom:4px; white-space:nowrap;">'
        f'<span style="background:{color}; width:11px; height:11px; border-radius:50%; display:inline-block; margin-right:5px; border:1px solid #fff;"></span>'
        f'<b>{d_name}:</b>&nbsp;{total_bags} bags ({total_km} km)&nbsp;'
        f'<a href="{primary_nav_url}" target="_blank" style="color:#1a73e8; text-decoration:none; font-weight:bold;">[🗺️ Nav]</a>'
        f'</span>'
    )

if selected_driver_filter == "Show All Drivers" and excluded_bags:
    ex_fg = folium.FeatureGroup(name=f"🚫 Excluded Stops ({len(excluded_bags)})", show=True)
    for ex_stop in excluded_bags:
        lat, lon = float(ex_stop["Resolved_Lat"]), float(ex_stop["Resolved_Lon"])
        route_coords_for_bounds.append((lat, lon))
        is_om = "OMAN" in ex_stop["Driver_ID"]
        icon_color = "#e65100" if is_om else "#212121"
        label = "OUTSIDE UAE (OMAN)" if is_om else f"EXCLUDED ({ex_stop.get('Driver_ID', '')})"
        warn_html = (
            f'<div style="background:{icon_color}; color:#fff; border-radius:50%; '
            f'width:24px; height:24px; text-align:center; font-weight:bold; '
            f'font-size:11px; line-height:24px; border:2px solid #ff5252;">✕</div>'
        )
        warn_badge = folium.DivIcon(html=warn_html, icon_size=(24, 24), icon_anchor=(12, 12))
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>🚫 {label}</b><br>Bag: {ex_stop.get(bag_col, '')}<br>Area: {ex_stop.get('Area', '')}",
            tooltip=f"🚫 {label}: {ex_stop.get(bag_col, '')}",
            icon=warn_badge
        ).add_to(ex_fg)
    ex_fg.add_to(m)

if len(route_coords_for_bounds) > 1:
    lats = [c[0] for c in route_coords_for_bounds]
    lons = [c[1] for c in route_coords_for_bounds]
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(35, 35))

if legend_chips:
    bottom_bar_html = (
        '<div style="position:fixed; bottom:10px; left:10px; right:10px; z-index:9999; '
        'background:rgba(255,255,255,0.94); padding:7px 12px; border-radius:8px; '
        'box-shadow:0 2px 8px rgba(0,0,0,0.25); font-family:Arial,sans-serif; '
        'font-size:12px; display:flex; flex-wrap:wrap; align-items:center;">'
        '<span style="margin-right:14px; font-weight:bold;">🏠 Ajman WH</span>'
        + "".join(legend_chips) +
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(bottom_bar_html))

folium.LayerControl(collapsed=True, position="topright").add_to(m)
st_folium(m, width="100%", height=750, returned_objects=[])

# ==========================================
# 10. EXPORT & WHATSAPP CARDS
# ==========================================
out_fields = list(fieldnames) + [
    f for f in [
        "Assigned_Driver", "Driver_ID", "Stop_Sequence", "Stop_Phase", "City_Area",
        "Warehouse_Road_KM", "Leg_Distance_KM", "Route_Total_Bags",
        "Route_OneWay_KM", "Est_Finish_Time", "Est_Shift_Hours",
        "Resolved_Lat", "Resolved_Lon", "Dispatch_Status"
    ] if f not in fieldnames
]

csv_buffer = io.StringIO()
writer = csv.DictWriter(csv_buffer, fieldnames=out_fields)
writer.writeheader()
writer.writerows(master_rows)

btn_col1, btn_col2 = st.columns(2)
btn_col1.download_button(
    label="📥 Download Today's Dispatch Plan (CSV)",
    data=csv_buffer.getvalue().encode("utf-8-sig"),
    file_name=f"dispatch_plan_v3_{date.today().isoformat()}.csv",
    mime="text/csv"
)

if btn_col2.button("💾 Confirm & Log Today's Routes to Rotation History"):
    log_dispatch_to_db(master_rows)
    st.success("✅ Saved today's driver assignments to rotation history!")

st.subheader("📲 Driver Lists & Google Maps Navigation Links (Primary First ➔ Return Cluster)")
for d_name in active_driver_ids:
    if selected_driver_filter != "Show All Drivers" and selected_driver_filter.lower() not in d_name.lower():
        continue

    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))
    nav_links = build_google_maps_nav_links(wh_lat, wh_lon, d_stops)
    links_md = " | ".join(f"[{lbl}]({url})" for lbl, url in nav_links)

    one_way_km = d_stops[0].get("Route_OneWay_KM", "0")
    est_fin = d_stops[0].get("Est_Finish_Time", "")
    est_hrs = d_stops[0].get("Est_Shift_Hours", "")

    primary_stops = [s for s in d_stops if s.get("Stop_Phase"] == "Primary City"]
    return_stops = [s for s in d_stops if s.get("Stop_Phase"] == "Return-Leg Cluster"]

    primary_str = ", ".join(f"#{s['Stop_Sequence']}: {s.get(bag_col, '')} ({s.get('City_Area', '')})" for s in primary_stops)
    return_str = ", ".join(f"#{s['Stop_Sequence']}: {s.get(bag_col, '')} ({s.get('City_Area', '')})" for s in return_stops)

    card_md = (
        f"**{d_name}** — **{len(d_stops)} bags** | **{one_way_km} km** | "
        f"⏱️ Est. Finish: **{est_fin}** ({est_hrs} hrs) — {links_md}\n"
        f"> **1️⃣ Primary Stops ({len(primary_stops)}):** `{primary_str}`"
    )
    if return_stops:
        card_md += f"\n> **2️⃣ Return-Leg Cluster ({len(return_stops)}):** `{return_str}`"

    st.markdown(card_md)