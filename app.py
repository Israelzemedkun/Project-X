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
import uuid
import folium
from folium.plugins import AntPath, Draw, Fullscreen
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

# Declare custom MapLibre GL JS component
_MAPLIBRE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__ if "__file__" in locals() else "app.py")), "maplibre_component")
_maplibre_component = components.declare_component("maplibre_map", path=_MAPLIBRE_DIR)

# ==========================================
# PAGE CONFIGURATION (VERSION 3.2 - MAPLIBRE EXPERIMENT)
# ==========================================
st.set_page_config(
    page_title="Lion Delivery Dispatch v3.2 (MapLibre)",
    page_icon="🚚",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 100% !important;
}

/* Header Banner */
.lion-header-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 20px;
    color: #ffffff;
    box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.lion-brand-wrap {
    display: flex;
    align-items: center;
    gap: 16px;
}
.lion-logo-badge {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
}
.lion-title {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
    color: #ffffff;
}
.lion-subtitle {
    font-size: 12.5px;
    color: #94a3b8;
    margin: 2px 0 0 0;
    font-weight: 500;
}
.lion-status-badges {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
}
.lion-badge {
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 11.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.lion-badge.live {
    background: rgba(34, 197, 94, 0.15);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.3);
}
.lion-badge.mode {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.3);
}
.lion-badge.wh {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

/* KPI Metric Cards */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 20px;
}
@media (max-width: 900px) {
    .kpi-container { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 500px) {
    .kpi-container { grid-template-columns: 1fr; }
}
.kpi-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(15, 23, 42, 0.06);
    position: relative;
    overflow: hidden;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px -4px rgba(15, 23, 42, 0.1), 0 0 0 1px rgba(15, 23, 42, 0.1);
}
.kpi-card-stripe {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
}
.kpi-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.kpi-value {
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
    margin-bottom: 4px;
}
.kpi-sub {
    font-size: 11.5px;
    color: #64748b;
    font-weight: 500;
}

/* Map Header Bar */
.map-toolbar-header {
    background: #ffffff;
    border-radius: 12px;
    padding: 12px 18px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05), 0 0 0 1px rgba(15, 23, 42, 0.06);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

/* Lasso Panel Container */
.lasso-panel-box {
    background: #ffffff;
    border-radius: 14px;
    padding: 18px 22px;
    margin-top: 14px;
    margin-bottom: 20px;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(245, 158, 11, 0.35);
    border-left: 5px solid #f59e0b;
}

/* Driver Cards */
.driver-dispatch-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 16px;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(15, 23, 42, 0.08);
    transition: all 0.2s ease;
}
.driver-dispatch-card:hover {
    box-shadow: 0 8px 24px -4px rgba(15, 23, 42, 0.1), 0 0 0 1px rgba(15, 23, 42, 0.12);
}
.driver-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
    margin-bottom: 14px;
}
.driver-title-grp {
    display: flex;
    align-items: center;
    gap: 10px;
}
.driver-color-pill {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.driver-card-name {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
}
.driver-stat-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.stat-pill {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 4px 10px;
    font-size: 11.5px;
    font-weight: 700;
    color: #334155;
}
.nav-link-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #eff6ff;
    color: #1d4ed8 !important;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
    text-decoration: none !important;
    transition: all 0.15s ease;
}
.nav-link-btn:hover {
    background: #1d4ed8;
    color: #ffffff !important;
    border-color: #1d4ed8;
}
.stop-chip-container {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
    margin-bottom: 12px;
}
.stop-chip {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11.5px;
    color: #334155;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.stop-chip.return-leg {
    background: #fffbeb;
    border-color: #fde68a;
    color: #92400e;
}

/* Polished Streamlit buttons */
.stButton>button {
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    transition: all 0.15s ease !important;
}
.stDownloadButton>button {
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
}

/* Sidebar refinement */
[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 13px !important;
    font-weight: 800 !important;
    color: #1e293b !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    margin-top: 14px !important;
    margin-bottom: 6px !important;
}

/* Active Work & Live Map Styles */
.active-work-driver-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 18px;
    box-shadow: 0 4px 14px -2px rgba(15, 23, 42, 0.05);
}
.active-driver-badge-hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
    margin-bottom: 14px;
}
.bag-tile-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
    margin-top: 10px;
    margin-bottom: 14px;
}
.bag-tile-item {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 10px 12px;
    transition: all 0.15s ease;
}
.bag-tile-item:hover {
    border-color: #15803d;
    box-shadow: 0 4px 12px rgba(21, 128, 61, 0.08);
}
.bag-tile-code {
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    font-family: 'JetBrains Mono', monospace;
}
.bag-tile-cust {
    font-size: 12px;
    font-weight: 600;
    color: #334155;
    margin-top: 2px;
}
.bag-tile-ref {
    font-size: 11px;
    color: #64748b;
    margin-top: 2px;
}
.run-detail-row {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}
.status-pill-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
}
.live-counter-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 10px;
    margin-bottom: 16px;
}
@media (max-width: 1200px) {
    .live-counter-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 600px) {
    .live-counter-grid { grid-template-columns: repeat(2, 1fr); }
}
.live-counter-pill {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px 10px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}
.live-counter-val {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
}
.live-counter-lbl {
    font-size: 10.5px;
    font-weight: 700;
    color: #64748b;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.order-list-scroll-box {
    max-height: 650px;
    overflow-y: auto;
    padding-right: 6px;
}
</style>
""", unsafe_allow_html=True)

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


# ==========================================
# LION DELIVERY ACTIVE WORK & LIVE MAP API CLIENT
# ==========================================
LION_CLASSIFICATION_INFO = {
    "UNASSIGNED": {"label": "Unassigned", "color": "#64748b", "symbol": "U"},
    "ASSIGNED": {"label": "Waiting to Start", "color": "#2563eb", "symbol": "A"},
    "OUT_FOR_DELIVERY": {"label": "Out for Delivery", "color": "#15803d", "symbol": "O"},
    "ARRIVED": {"label": "Arrived", "color": "#f59e0b", "symbol": "!"},
    "DELIVERED": {"label": "Delivered", "color": "#86a890", "symbol": "D"},
    "RETRY": {"label": "Retry", "color": "#d97706", "symbol": "R"},
    "RESCHEDULED": {"label": "Rescheduled", "color": "#7c3aed", "symbol": "S"},
    "RETURN_REQUIRED": {"label": "Return Required", "color": "#dc2626", "symbol": "!"},
    "RETURNED": {"label": "Returned", "color": "#94a3b8", "symbol": "RT"},
    "BLOCKED": {"label": "Blocked", "color": "#991b1b", "symbol": "X"},
}


def fetch_lion_active_work(token, search="", driver="", date_from="", date_to=""):
    clean_tok = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_tok}",
        "Accept": "application/json"
    }
    params = {
        "page_size": "50",
        "ordering": "newest",
        "view": "ACTIVE"
    }
    if search:
        params["search"] = search
    if driver:
        params["driver"] = driver
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    url = "https://api.liondelivery.ae/api/v1/dispatcher/operations/admin-routes/"
    try:
        resp = api_session.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], dict) and "results" in data["data"]:
                    results = data["data"]["results"]
                elif "results" in data:
                    results = data["results"]
                elif "data" in data and isinstance(data["data"], list):
                    results = data["data"]
            return results, None
        return None, f"API Error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def fetch_lion_run_reassignment_stops(token, run_id):
    clean_tok = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_tok}",
        "Accept": "application/json"
    }
    url = f"https://api.liondelivery.ae/api/v1/dispatcher/operations/delivery-runs/{run_id}/reassignment/"
    try:
        resp = api_session.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"], None
            return data, None
        return None, f"API Error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def fetch_lion_drivers_workload(token):
    clean_tok = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_tok}",
        "Accept": "application/json"
    }
    url = "https://api.liondelivery.ae/api/v1/dispatcher/drivers/workload/"
    try:
        resp = api_session.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"], None
            return data, None
        return None, f"API Error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def reassign_lion_bags(token, source_run_id, stop_ids, target_driver_id, reason="Dispatcher manual reassignment"):
    clean_tok = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_tok}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    url = f"https://api.liondelivery.ae/api/v1/dispatcher/operations/delivery-runs/{source_run_id}/reassignment/"
    payload = {
        "stop_ids": [int(sid) for sid in stop_ids],
        "target_driver_id": int(target_driver_id),
        "reason": reason.strip() or "Dispatcher manual reassignment"
    }
    try:
        resp = api_session.post(url, headers=headers, json=payload, timeout=25)
        if resp.status_code in (200, 201):
            return resp.json(), None
        return None, f"Reassignment error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def fetch_lion_live_map(token):
    clean_tok = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_tok}",
        "Accept": "application/json"
    }
    url = "https://api.liondelivery.ae/api/v1/dispatcher/live-map/"
    try:
        resp = api_session.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"], None
            return data, None
        return None, f"API Error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


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

    # Pre-compute per-route KM once to avoid redundant optimize_route_order calls inside O(n²) loop
    route_km_cache = {id(r): optimize_route_order(r, dist_matrix, city_list)[1] for r in local_routes}

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

                    km_a = route_km_cache.get(id(r_a), optimize_route_order(r_a, dist_matrix, city_list)[1])
                    km_b = route_km_cache.get(id(r_b), optimize_route_order(r_b, dist_matrix, city_list)[1])
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
                merged_route = optimize_route_order(
                    local_routes[i_a] + local_routes[i_b], dist_matrix, city_list
                )
                local_routes[i_a] = merged_route[0]
                route_km_cache[id(local_routes[i_a])] = merged_route[1]
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


# (add_uae_state_grid_to_map removed — use add_uae_state_grid_to_map_custom instead)


# ==========================================
# 6. SIDEBAR: DUAL INPUT (CSV UPLOAD + AUTO-LOGIN API SYNC)
# ==========================================
db_stats = get_recent_driver_stats()
default_far_yesterday = [d for d, st_info in db_stats.items() if st_info["went_far_yesterday"]]

st.sidebar.title("🧪 V3.2 LAB — MapLibre Dispatch")

map_engine_choice = st.sidebar.radio(
    "🗺️ Map Rendering Engine",
    options=["MapLibre GL JS (Hardware-Accelerated 3D)", "Folium / Leaflet (Legacy 2D)"],
    index=0,
    help="MapLibre uses GPU WebGL rendering, 3D tilt/rotation, and vector styling."
)

selected_driver_filter = st.sidebar.selectbox(
    "🔍 View Driver on Map",
    options=["Show All Drivers"] + FLEET_DRIVERS,
    index=0
)
show_state_grid = st.sidebar.checkbox("🗺️ Show Real Emirate Borders on Map", value=True)
if show_state_grid:
    border_opacity = st.sidebar.slider("Border Fill Opacity", min_value=0.0, max_value=0.40, value=0.06, step=0.02)
else:
    border_opacity = 0.0

route_line_opacity = st.sidebar.slider("Driver Route Line Opacity", min_value=0.2, max_value=1.0, value=0.88, step=0.1)

# ----------------------------------------------------
# LION DELIVERY PORTAL CREDENTIALS & API SESSION
# ----------------------------------------------------
secret_email = ""
secret_pass = ""
secret_token = ""
try:
    secret_email = st.secrets.get("LION_EMAIL", "")
    secret_pass = st.secrets.get("LION_PASSWORD", "")
    secret_token = st.secrets.get("LION_API_TOKEN", "")
except Exception:
    secret_email = ""

if "lion_auth_token" not in st.session_state and secret_token:
    st.session_state["lion_auth_token"] = secret_token

st.sidebar.markdown("### 🔐 Lion Delivery Portal Access")
ld_user = st.sidebar.text_input("Lion Delivery Email", value=secret_email, key="ld_user_input")
ld_pass = st.sidebar.text_input("Lion Delivery Password", value=secret_pass, type="password", key="ld_pass_input")

with st.sidebar.expander("🔧 Advanced API / Token Override"):
    auth_url = st.text_input(
        "Login Endpoint URL",
        value="https://api.liondelivery.ae/api/v1/auth/login/",
        key="ld_auth_url_input"
    )
    api_endpoint = st.text_input(
        "Location-Board Endpoint",
        value=DEFAULT_LOCATION_BOARD_API,
        key="ld_loc_board_input"
    )
    manual_bearer = st.text_input(
        "Optional Direct Bearer Token",
        value=secret_token,
        type="password",
        key="ld_manual_token_input"
    )

auth_col1, auth_col2 = st.sidebar.columns([1.2, 1])
if auth_col1.button("🔑 Login / Refresh", use_container_width=True, key="btn_login_auth"):
    if ld_user and ld_pass:
        with st.spinner("Logging into Lion Delivery... marathon"):
            fresh_tok, err_msg = obtain_fresh_jwt_token(auth_url, ld_user, ld_pass)
            if fresh_tok:
                st.session_state["lion_auth_token"] = fresh_tok
                st.sidebar.success("✅ Logged in!")
                st.rerun()
            elif manual_bearer.strip():
                st.session_state["lion_auth_token"] = manual_bearer.strip()
                st.sidebar.success("✅ Token saved!")
                st.rerun()
            else:
                st.sidebar.error(f"Login failed: {err_msg}")
    elif manual_bearer.strip():
        st.session_state["lion_auth_token"] = manual_bearer.strip()
        st.sidebar.success("✅ Token saved!")
        st.rerun()
    else:
        st.sidebar.error("Enter email and password.")

if st.session_state.get("lion_auth_token"):
    auth_col2.markdown('<div style="padding-top:6px; font-size:12px; font-weight:700; color:#16a34a;">🟢 Connected</div>', unsafe_allow_html=True)
else:
    auth_col2.markdown('<div style="padding-top:6px; font-size:12px; font-weight:600; color:#64748b;">⚪ Offline</div>', unsafe_allow_html=True)

st.sidebar.markdown("### 📂 1. Load Delivery Orders (Planner)")
data_source = st.sidebar.radio(
    "Input Method:",
    ["Upload CSV File", "⚡ Live API Sync (location-board)"],
    index=0,
    key="planner_data_source_radio"
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
    if st.sidebar.button("⚡ Sync Live Location-Board Bags", type="primary", use_container_width=True):
        active_token = st.session_state.get("lion_auth_token", "")
        if not active_token:
            if ld_user and ld_pass:
                with st.spinner("Logging in for fresh access token... marathon"):
                    fresh_tok, err_msg = obtain_fresh_jwt_token(auth_url, ld_user, ld_pass)
                    if fresh_tok:
                        active_token = fresh_tok
                        st.session_state["lion_auth_token"] = fresh_tok
                    elif manual_bearer.strip():
                        active_token = manual_bearer.strip()
                        st.session_state["lion_auth_token"] = active_token
            elif manual_bearer.strip():
                active_token = manual_bearer.strip()
                st.session_state["lion_auth_token"] = active_token

        if active_token:
            with st.spinner("Pulling location-board bags... marathon"):
                pulled_rows, pull_err = pull_all_location_board_bags(api_endpoint, active_token)
                if pull_err:
                    st.sidebar.error(pull_err)
                elif pulled_rows:
                    st.session_state["api_raw_rows"] = pulled_rows
                    st.session_state["api_sync_counter"] = st.session_state.get("api_sync_counter", 0) + 1
                    st.sidebar.success(f"✅ Synced {len(pulled_rows)} bags!")
                else:
                    st.sidebar.warning("Connected, but 0 bags found on location-board.")
        else:
            st.sidebar.error("Please enter email & password to log in.")

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
max_route_km_input = st.sidebar.number_input("Max Total Route Length (KM)", value=600.0, step=25.0, help="Hard cap on a single driver's one-way route distance.")


# ==========================================
# 7. MAIN APPLICATION PIPELINE
# ==========================================
wh_lat, wh_lon = resolve_google_maps_url(WAREHOUSE_URL)
if not wh_lat:
    wh_lat, wh_lon = 25.4052, 55.5136

st.markdown(f"""
<div class="lion-header-card">
  <div class="lion-brand-wrap">
    <div class="lion-logo-badge">🦁</div>
    <div>
      <h1 class="lion-title">Lion Delivery Dispatch Command</h1>
      <p class="lion-subtitle">UAE Smart Multi-Corridor Dispatch, Live Tracking & Operations Center</p>
    </div>
  </div>
  <div class="lion-status-badges">
    <span class="lion-badge live">🟢 System Live</span>
    <span class="lion-badge wh">🏠 Ajman Base</span>
    <span class="lion-badge mode">⚡ MapLibre GL 3D</span>
  </div>
</div>
""", unsafe_allow_html=True)

tab_planner, tab_active_work, tab_live_map = st.tabs([
    "🧭 1. Dispatch Route Planner & Optimizer",
    "🏃 2. Dispatched Drivers (Active Work)",
    "🗺️ 3. Live Operations Map"
])

with tab_planner:
    if not raw_rows:
        st.info("👋 Upload `lion_delivery_all_bags.csv` OR switch to **⚡ Live API Sync (location-board)** in the sidebar to run route optimization.")
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
    else:
        current_config_sig = (
            "v3.1_real_geojson_borders",
            source_name,
            raw_bytes_len,
            target_drivers_input,
            max_bags_local_input,
            max_bags_distant_input,
            min_bags_input,
            max_dist_input,
            max_route_km_input,
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
                    max_route_km=max_route_km_input
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

        dispatch_pct = round((total_bags_assigned / max(1, len(master_rows))) * 100, 1)

        st.markdown(f"""
          </div>
          <div class="lion-status-badges">
            <span class="lion-badge live">🟢 System Live</span>
            <span class="lion-badge wh">🏠 Ajman WH Start</span>
            <span class="lion-badge mode">⚡ MapLibre 3D</span>
          </div>
        </div>

        <div class="kpi-container">
          <div class="kpi-card">
            <div class="kpi-card-stripe" style="background:#2563eb;"></div>
            <div class="kpi-label"><span>🚚</span> Active Drivers</div>
            <div class="kpi-value">{len(active_driver_ids)} <span style="font-size:16px; font-weight:600; color:#64748b;">/ 7</span></div>
            <div class="kpi-sub">Assigned on delivery routes today</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-card-stripe" style="background:#16a34a;"></div>
            <div class="kpi-label"><span>🎒</span> Total Bags Assigned</div>
            <div class="kpi-value">{total_bags_assigned} <span style="font-size:16px; font-weight:600; color:#64748b;">/ {len(master_rows)}</span></div>
            <div class="kpi-sub">{dispatch_pct}% total orders dispatched</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-card-stripe" style="background:#8b5cf6;"></div>
            <div class="kpi-label"><span>☕</span> Resting Drivers</div>
            <div class="kpi-value" style="font-size:16px; font-weight:700; line-height:1.4; padding-top:4px;">{", ".join(resting_drivers_today) if resting_drivers_today else "None (Full Fleet Active)"}</div>
            <div class="kpi-sub">Rotated off today</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-card-stripe" style="background:{'#ef4444' if excluded_bags else '#10b981'};"></div>
            <div class="kpi-label"><span>🚫</span> Excluded Orders</div>
            <div class="kpi-value" style="color:{'#dc2626' if excluded_bags else '#16a34a'};">{len(excluded_bags)}</div>
            <div class="kpi-sub">> {int(max_dist_input)}km cutoff or Oman border</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 8px;">
            <span style="font-size: 14px; font-weight: 700; color: #0f172a;">🛠️ Dispatch Adjustment Controls</span>
            <span style="font-size: 12px; color: #64748b; margin-left: 8px;">Reassign individual orders or swap full driver routes</span>
        </div>
        """, unsafe_allow_html=True)
        ctrl_tab1, ctrl_tab2 = st.tabs(["🔄 Move Single Bag", "🔀 Swap Drivers Between Routes"])

        with ctrl_tab1:
            col_re1, col_re2, col_re3 = st.columns([3, 2, 1.8])
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
            col_re3.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if col_re3.button("⚡ Move & Re-Sequence", use_container_width=True):
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
            sc1, sc2, sc3 = st.columns([2, 2, 1.8])
            swap_driver_a = sc1.selectbox("Driver 1", options=FLEET_DRIVERS, index=0)
            swap_driver_b = sc2.selectbox("Driver 2", options=FLEET_DRIVERS, index=1)
            sc3.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if sc3.button("🔀 Swap Entire Route", use_container_width=True):
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
        # 9. UNIFIED MAP — ROUTES + POLYGON DRAW SELECTOR (MAPLIBRE GL JS / FOLIUM)
        # ==========================================
        route_coords_for_bounds = [(wh_lat, wh_lon)]
        legend_chips = []
        legend_chips_data = []
        seen_marker_coords = {}
        ml_routes = []
        ml_stops = []
        ml_excluded = []

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

            waypoints = [(wh_lat, wh_lon)] + [(float(s["Resolved_Lat"]), float(s["Resolved_Lon"])) for s in d_stops]
            for pt in waypoints:
                route_coords_for_bounds.append(pt)

            road_polyline = get_osrm_route_geometry(waypoints)
            ml_routes.append({
                "driver_name": d_name,
                "color": color,
                "total_bags": total_bags,
                "total_km": total_km,
                "coordinates": [[pt[1], pt[0]] for pt in road_polyline]
            })

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
                ml_stops.append({
                    "raw_lat": raw_lat,
                    "raw_lon": raw_lon,
                    "disp_lat": disp_lat,
                    "disp_lon": disp_lon,
                    "sequence": str(s.get("Stop_Sequence", "")),
                    "bag": str(s.get(bag_col, "")),
                    "area": str(s.get("City_Area", "")),
                    "driver_name": d_name,
                    "color": color,
                    "border_style": border_style,
                    "pin_url": pin_url,
                })

            legend_chips_data.append({
                "driver_name": d_name,
                "color": color,
                "total_bags": total_bags,
                "total_km": total_km,
                "nav_url": primary_nav_url,
            })

            legend_chips.append(
                f'<span style="display:inline-flex; align-items:center; margin-right:14px; margin-bottom:4px; white-space:nowrap;">'
                f'<span style="background:{color}; width:11px; height:11px; border-radius:50%; display:inline-block; margin-right:5px; border:1px solid #fff;"></span>'
                f'<b>{d_name}:</b>&nbsp;{total_bags} bags ({total_km} km)&nbsp;'
                f'<a href="{primary_nav_url}" target="_blank" style="color:#1a73e8; text-decoration:none; font-weight:bold;">[🗺️ Nav]</a>'
                f'</span>'
            )

        if selected_driver_filter == "Show All Drivers" and excluded_bags:
            for ex_stop in excluded_bags:
                ex_lat, ex_lon = float(ex_stop["Resolved_Lat"]), float(ex_stop["Resolved_Lon"])
                route_coords_for_bounds.append((ex_lat, ex_lon))
                is_om = "OMAN" in ex_stop["Driver_ID"]
                icon_color = "#e65100" if is_om else "#212121"
                ex_label = "OUTSIDE UAE (OMAN)" if is_om else f"EXCLUDED ({ex_stop.get('Driver_ID', '')})"
                ml_excluded.append({
                    "lat": ex_lat,
                    "lon": ex_lon,
                    "bag": str(ex_stop.get(bag_col, "")),
                    "label": ex_label,
                    "icon_color": icon_color,
                })

        # Render selected engine
        if map_engine_choice.startswith("MapLibre"):
            map_data = {
                "warehouse": {
                    "lat": wh_lat,
                    "lon": wh_lon,
                    "name": "Ajman Warehouse (6:30 AM Start)"
                },
                "borders": fetch_uae_real_borders_geojson() if show_state_grid else [],
                "show_borders": show_state_grid,
                "border_opacity": border_opacity,
                "route_line_opacity": route_line_opacity,
                "driver_filter": selected_driver_filter,
                "routes": ml_routes,
                "stops": ml_stops,
                "excluded_stops": ml_excluded,
                "legend_chips": legend_chips_data,
                "active_drawing": st.session_state.get("last_lasso_drawing", None),
                "clear_drawing": st.session_state.pop("lasso_clear_requested", False),
            }

            st.markdown("""
        <div class="map-toolbar-header">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">🗺️</span>
            <b style="font-size:15px; color:#0f172a;">Unified Route & Stop Map</b>
            <span style="background:#eff6ff; color:#2563eb; font-size:11px; font-weight:800; padding:2px 8px; border-radius:12px; border:1px solid #bfdbfe;">MapLibre WebGL 3D</span>
          </div>
          <div style="display:flex; align-items:center; gap:12px; font-size:12px; color:#64748b; font-weight:600;">
            <span>⚡ <b>3D View:</b> Ctrl + Drag</span>
            <span>•</span>
            <span>✏️ <b>Lasso Tool:</b> Click ⬡ Draw Shape</span>
            <span>•</span>
            <span>🗺️ <b>Base Layers:</b> Top-Right</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
            map_ver = st.session_state.get("map_version", 0)
            map_output = _maplibre_component(
                map_data=map_data,
                key=f"maplibre_dispatch_map_{map_ver}",
                default=None
            )
        else:
            # Legacy Folium Map
            m = folium.Map(location=[wh_lat, wh_lon], zoom_start=9, tiles=None, control_scale=True)
            Fullscreen(position="topleft", force_separate_button=True).add_to(m)

            Draw(
                export=False,
                position="topleft",
                draw_options={
                    "polyline": False,
                    "polygon": True,
                    "circle": False,
                    "marker": False,
                    "circlemarker": False,
                    "rectangle": True,
                },
                edit_options={"edit": False}
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

            folium.TileLayer(
                "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
                attr="Google Maps",
                name="Google Maps (Streets)",
                overlay=False,
                control=True
            ).add_to(m)

            if show_state_grid:
                grid_fg = folium.FeatureGroup(name="🗺️ UAE Emirate Borders (Real GeoJSON)", show=True)
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
                        style_function=lambda feat, c=state_color, op=border_opacity: {
                            "color": c,
                            "weight": 2.5,
                            "opacity": 0.9,
                            "dashArray": "6, 4",
                            "fillColor": c,
                            "fillOpacity": op,
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

            folium.Marker(
                location=[wh_lat, wh_lon],
                popup="<b>Ajman Warehouse (6:30 AM Start)</b>",
                tooltip="Ajman Warehouse",
                icon=folium.Icon(color="black", icon="home", prefix="fa")
            ).add_to(m)

            for r_entry in ml_routes:
                d_name = r_entry["driver_name"]
                color = r_entry["color"]
                total_bags = r_entry["total_bags"]
                total_km = r_entry["total_km"]
                fg = folium.FeatureGroup(name=f"{d_name} ({total_bags} bags | {total_km} km)", show=True)
                folium_polyline = [[pt[1], pt[0]] for pt in r_entry["coordinates"]]
                AntPath(locations=folium_polyline, color=color, weight=5, opacity=route_line_opacity, tooltip=d_name).add_to(fg)

                for s in ml_stops:
                    if s["driver_name"] != d_name:
                        continue
                    badge_html = (
                        f'<div style="background:{s["color"]}; color:#fff; border-radius:50%; '
                        f'width:24px; height:24px; text-align:center; font-weight:bold; '
                        f'font-size:11px; line-height:24px; border:{s["border_style"]}; '
                        f'box-shadow:0 2px 4px rgba(0,0,0,0.4);">'
                        f'{s["sequence"]}</div>'
                    )
                    badge = folium.DivIcon(html=badge_html, icon_size=(24, 24), icon_anchor=(12, 12))
                    popup_html = (
                        f'<div style="font-family:Arial,sans-serif; font-size:12px; min-width:200px;">'
                        f'<b>{d_name} — Stop #{s["sequence"]}</b><br>'
                        f'<b>Bag:</b> {s["bag"]}<br>'
                        f'<b>State/Zone:</b> {s["area"]}<br>'
                        f'<a href="{s["pin_url"]}" target="_blank" style="color:#1a73e8; font-weight:bold;">Open Pin ↗</a>'
                        f'</div>'
                    )
                    folium.Marker(
                        location=[s["disp_lat"], s["disp_lon"]],
                        popup=folium.Popup(popup_html, max_width=280),
                        tooltip=f"{s['bag']} • Stop #{s['sequence']} ({s['area']})",
                        icon=badge
                    ).add_to(fg)
                fg.add_to(m)

            if selected_driver_filter == "Show All Drivers" and ml_excluded:
                ex_fg = folium.FeatureGroup(name=f"🚫 Excluded Stops ({len(ml_excluded)})", show=True)
                for ex_stop in ml_excluded:
                    warn_html = (
                        f'<div style="background:{ex_stop["icon_color"]}; color:#fff; border-radius:50%; '
                        f'width:24px; height:24px; text-align:center; font-weight:bold; '
                        f'font-size:11px; line-height:24px; border:2px solid #ff5252;">✕</div>'
                    )
                    warn_badge = folium.DivIcon(html=warn_html, icon_size=(24, 24), icon_anchor=(12, 12))
                    folium.Marker(
                        location=[ex_stop["lat"], ex_stop["lon"]],
                        popup=f"<b>🚫 {ex_stop['label']}</b><br>Bag: {ex_stop['bag']}",
                        tooltip=f"🚫 {ex_stop['label']}: {ex_stop['bag']}",
                        icon=warn_badge
                    ).add_to(ex_fg)
                ex_fg.add_to(m)

            if len(route_coords_for_bounds) > 1:
                all_lats = [c[0] for c in route_coords_for_bounds]
                all_lons = [c[1] for c in route_coords_for_bounds]
                m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]], padding=(35, 35))

            if legend_chips:
                bottom_bar_html = (
                    '<div style="position:fixed; bottom:10px; left:10px; right:10px; z-index:9999; '
                    'background:rgba(255,255,255,0.94); padding:7px 12px; border-radius:8px; '
                    'box-shadow:0 2px 8px rgba(0,0,0,0.25); font-family:Arial,sans-serif; '
                    'font-size:12px; display:flex; flex-wrap:wrap; align-items:center;">'
                    '<span style="margin-right:14px; font-weight:bold;">🏠 Ajman WH</span>'
                    + "".join(legend_chips)
                    + '</div>'
                )
                m.get_root().html.add_child(folium.Element(bottom_bar_html))

            folium.LayerControl(collapsed=True, position="topright").add_to(m)
            st.info("✏️ **Folium Legacy Mode:** Use polygon or rectangle draw tool (top-left) to lasso pins.")
            map_output = st_folium(m, width="100%", height=800, returned_objects=["last_active_drawing"])

        # ==========================================
        # 9.1 LASSO ASSIGNMENT PANEL — directly below the map
        # ==========================================
        def point_in_polygon(lat, lon, poly_coords_lonlat):
            """Ray-casting algorithm. poly_coords_lonlat is a list of (lon, lat) GeoJSON tuples."""
            x, y = lon, lat
            inside = False
            n = len(poly_coords_lonlat)
            for i in range(n):
                x1, y1 = poly_coords_lonlat[i]
                x2, y2 = poly_coords_lonlat[(i + 1) % n]
                if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
                    inside = not inside
            return inside

        if map_output and isinstance(map_output, dict):
            if map_output.get("last_active_drawing"):
                st.session_state["last_lasso_drawing"] = map_output.get("last_active_drawing")
            elif "last_active_drawing" in map_output and map_output.get("last_active_drawing") is None:
                st.session_state["last_lasso_drawing"] = None

        _active_drawing = st.session_state.get("last_lasso_drawing", None)
        if _active_drawing and _active_drawing.get("geometry"):
            _geom_type   = _active_drawing["geometry"]["type"]
            _geom_coords = _active_drawing["geometry"]["coordinates"]

            # GeoJSON stores coordinates as [lon, lat]
            _poly_pts = []
            if _geom_type == "Polygon":
                _poly_pts = [(pt[0], pt[1]) for pt in _geom_coords[0]]

            if _poly_pts:
                _lasso_hits = [
                    r for r in master_rows
                    if r.get("Resolved_Lat")
                    and point_in_polygon(
                        float(r["Resolved_Lat"]),
                        float(r["Resolved_Lon"]),
                        _poly_pts
                    )
                ]

                if _lasso_hits:
                    st.markdown(f"""
        <div class="lasso-panel-box">
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
            <div>
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:20px;">🎯</span>
                <b style="font-size:16px; color:#0f172a;">Lasso Selection Active: {len(_lasso_hits)} Stop(s) Captured</b>
              </div>
              <div style="font-size:12.5px; color:#64748b; margin-top:2px;">
                Select the target driver below to reassign these stops and auto-resequence routes.
              </div>
            </div>
            <span style="background:#fef3c7; color:#b45309; font-size:11.5px; font-weight:800; padding:4px 12px; border-radius:20px; border:1px solid #fde68a;">
              Ready to Reassign
            </span>
          </div>
        </div>
        """, unsafe_allow_html=True)

                    # Show a compact table of what was captured
                    st.dataframe(
                        [
                            {
                                "Bag Code": r.get(bag_col, ""),
                                "Current Driver": r.get("Assigned_Driver") or r.get("Driver_ID", "UNASSIGNED"),
                                "Delivery Area": r.get("City_Area", ""),
                                "Stop Sequence": r.get("Stop_Sequence", "-"),
                            }
                            for r in _lasso_hits
                        ],
                        use_container_width=True,
                        hide_index=True,
                        height=min(220, 38 + len(_lasso_hits) * 35)
                    )

                    _la_col1, _la_col2, _la_col3 = st.columns([3, 2, 1])
                    with _la_col1:
                        _lasso_driver = st.selectbox(
                            "Assign selected pins to driver:",
                            options=FLEET_DRIVERS,
                            key="lasso_drv_target"
                        )
                    with _la_col2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        assign_btn = st.button("⚡ Assign & Re-Sequence", type="primary", use_container_width=True)
                    with _la_col3:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        clear_btn = st.button("❌ Clear Shape", use_container_width=True)

                    if clear_btn:
                        st.session_state["last_lasso_drawing"] = None
                        st.session_state["lasso_clear_requested"] = True
                        st.session_state["map_version"] = st.session_state.get("map_version", 0) + 1
                        st.rerun()

                    if assign_btn:
                        # ██ SNAPSHOT old driver names BEFORE we modify any rows.
                        _old_drivers = {
                            _hit.get("Assigned_Driver") or _hit.get("Driver_ID", "").split(" (")[0]
                            for _hit in _lasso_hits
                            if (_hit.get("Assigned_Driver") or _hit.get("Driver_ID"))
                            and "NOT GOING" not in (_hit.get("Assigned_Driver") or "")
                            and "NOT GOING" not in (_hit.get("Driver_ID") or "")
                        }

                        # Determine the Driver_ID to stamp on new rows.
                        # Use the existing Driver_ID for _lasso_driver if they already have stops (preserves corridor label); otherwise plain name.
                        _existing_for_new = [
                            r for r in master_rows
                            if (r.get("Assigned_Driver") == _lasso_driver or r.get("Driver_ID", "").split(" (")[0] == _lasso_driver)
                            and " (" in r.get("Driver_ID", "")
                        ]
                        _new_did = _existing_for_new[0]["Driver_ID"] if _existing_for_new else _lasso_driver

                        # Update every matching row in master_rows
                        for _hit in _lasso_hits:
                            _bag_key = _hit.get(bag_col, "")
                            for _row in master_rows:
                                if _row.get(bag_col) == _bag_key:
                                    _row["Assigned_Driver"] = _lasso_driver
                                    _row["Driver_ID"]       = _new_did
                                    _row["Dispatch_Status"] = "ASSIGNED_LASSO_SELECTION"

                        # Re-sequence ALL touched drivers — old ones lose bags, new one gains them
                        _touched = _old_drivers | {_lasso_driver}
                        for _drv in _touched:
                            if not _drv or "NOT GOING" in _drv:
                                continue
                            _di = [
                                i for i, r in enumerate(master_rows)
                                if (r.get("Assigned_Driver") == _drv or r.get("Driver_ID", "").split(" (")[0] == _drv) and r.get("Resolved_Lat")
                            ]
                            _dr = [master_rows[i] for i in _di]
                            if _dr:
                                _upd = resequence_driver_stops(_dr, wh_lat, wh_lon)
                                for i, u in zip(_di, _upd):
                                    master_rows[i] = u
                            else:
                                # Driver now has zero stops — nothing to resequence, counts are 0
                                pass

                        st.session_state["dispatch_data"] = master_rows
                        st.session_state["last_lasso_drawing"] = None
                        st.session_state["lasso_clear_requested"] = True
                        st.session_state["map_version"] = st.session_state.get("map_version", 0) + 1
                        st.success(f"✅ {len(_lasso_hits)} bag(s) assigned to **{_lasso_driver}** and routes re-sequenced.")
                        st.rerun()
                else:
                    st.info("🔍 No pins found inside the drawn shape — try drawing a larger polygon.")

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
            mime="text/csv",
            use_container_width=True
        )

        if btn_col2.button("💾 Confirm & Log Today's Routes to Rotation History", use_container_width=True):
            log_dispatch_to_db(master_rows)
            st.success("✅ Saved today's driver assignments to rotation history!")

        st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="margin-bottom: 14px;">
            <div style="font-size: 18px; font-weight: 800; color: #0f172a;">📲 Driver Route Plans & Turn-by-Turn Navigation</div>
            <div style="font-size: 12.5px; color: #64748b; font-weight: 500;">
                Primary corridor stops dispatched first, followed by return-leg cluster deliveries heading back toward the Ajman warehouse.
            </div>
        </div>
        """, unsafe_allow_html=True)

        for d_idx, d_name in enumerate(active_driver_ids):
            if selected_driver_filter != "Show All Drivers" and selected_driver_filter.lower() not in d_name.lower():
                continue

            d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
            if not d_stops:
                continue

            d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))
            drv_color = DRIVER_COLORS[d_idx % len(DRIVER_COLORS)]
            nav_links = build_google_maps_nav_links(wh_lat, wh_lon, d_stops)

            one_way_km = d_stops[0].get("Route_OneWay_KM", "0")
            est_fin = d_stops[0].get("Est_Finish_Time", "N/A")
            est_hrs = d_stops[0].get("Est_Shift_Hours", "N/A")

            primary_stops = [s for s in d_stops if s.get("Stop_Phase") == "Primary City"]
            return_stops = [s for s in d_stops if s.get("Stop_Phase") == "Return-Leg Cluster"]

            nav_btns_html = " ".join(
                f'<a href="{url}" target="_blank" class="nav-link-btn">{html.escape(lbl)}</a>'
                for lbl, url in nav_links
            )

            primary_chips_html = "".join(
                f'<span class="stop-chip"><strong>#{s.get("Stop_Sequence", "")}</strong> {html.escape(str(s.get(bag_col, "")))} <span style="color:#64748b; font-size:10.5px;">({html.escape(str(s.get("City_Area", "")))})</span></span>'
                for s in primary_stops
            )

            return_section_html = ""
            if return_stops:
                return_chips_html = "".join(
                    f'<span class="stop-chip return-leg"><strong>#{s.get("Stop_Sequence", "")}</strong> {html.escape(str(s.get(bag_col, "")))} <span style="color:#92400e; font-size:10.5px;">({html.escape(str(s.get("City_Area", "")))})</span></span>'
                    for s in return_stops
                )
                return_section_html = f"""
                <div style="margin-top: 10px;">
                    <div style="font-size: 11.5px; font-weight: 700; color: #b45309; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
                        🔄 2️⃣ Return-Leg Cluster ({len(return_stops)} stops)
                    </div>
                    <div class="stop-chip-container">{return_chips_html}</div>
                </div>
                """

            card_html = f"""
            <div class="driver-dispatch-card">
                <div class="driver-card-header">
                    <div class="driver-title-grp">
                        <span class="driver-color-pill" style="background-color: {drv_color};"></span>
                        <span class="driver-card-name">{html.escape(d_name)}</span>
                    </div>
                    <div class="driver-stat-pills">
                        <span class="stat-pill">🎒 {len(d_stops)} Bags</span>
                        <span class="stat-pill">🛣️ {one_way_km} km</span>
                        <span class="stat-pill">⏱️ Finish: {html.escape(str(est_fin))}</span>
                        <span class="stat-pill">⏳ Shift: {html.escape(str(est_hrs))} hrs</span>
                    </div>
                </div>
                <div style="margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                    <span style="font-size: 12px; font-weight: 700; color: #475569;">Turn-by-Turn Navigation:</span>
                    {nav_btns_html}
                </div>
                <div>
                    <div style="font-size: 11.5px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
                        1️⃣ Outbound Primary Corridor ({len(primary_stops)} stops)
                    </div>
                    <div class="stop-chip-container">{primary_chips_html}</div>
                </div>
                {return_section_html}
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

            # 1-Click WhatsApp text generator
            primary_lines = "\n".join(
                f"  #{s.get('Stop_Sequence', '')} - {s.get(bag_col, '')} ({s.get('City_Area', '')})"
                for s in primary_stops
            )
            return_lines = "\n".join(
                f"  #{s.get('Stop_Sequence', '')} - {s.get(bag_col, '')} ({s.get('City_Area', '')})"
                for s in return_stops
            ) if return_stops else "  None"

            nav_links_wa = "\n".join(f"• {lbl.replace(' ↗', '')}: {url}" for lbl, url in nav_links)

            wa_msg = (
                f"🚚 *LION DELIVERY DISPATCH — {date.today().strftime('%A, %d %b %Y')}*\n"
                f"👤 *Driver:* {d_name}\n"
                f"📦 *Total Bags:* {len(d_stops)} | 🛣️ *Distance:* ~{one_way_km} km\n"
                f"⏱️ *Est. Finish:* {est_fin} (Total Shift: ~{est_hrs} hrs)\n\n"
                f"🗺️ *Google Maps Navigation:*\n{nav_links_wa}\n\n"
                f"1️⃣ *Outbound Primary Stops ({len(primary_stops)}):*\n{primary_lines}\n"
            )
            if return_stops:
                wa_msg += f"\n2️⃣ *Return-Leg Cluster Stops ({len(return_stops)}):*\n{return_lines}\n"
            wa_msg += "\n⚠️ *Strict Stop Sequence:* Please deliver bags in numerical order to ensure timely customer delivery and route efficiency. Drive safely! 🦁"

            with st.expander(f"💬 1-Click WhatsApp Dispatch Message for {d_name}", expanded=False):
                st.caption("Click the copy icon in the upper-right corner of the code box below to paste directly into WhatsApp:")
                st.code(wa_msg, language="text")



        # (lasso panel now lives directly below the map — see section 9.1)

# ==========================================
# 8. TAB 2: DISPATCHED DRIVERS & ACTIVE WORK (/dispatcher/active-work)
# ==========================================
with tab_active_work:
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
        <div>
            <div style="font-size: 20px; font-weight: 800; color: #0f172a;">🏃 Dispatched Drivers & Active Work</div>
            <div style="font-size: 12.5px; color: #64748b; font-weight: 500;">
                Live operational runs, assigned bag codes, stop sequences, and exact GPS coordinates from <code>/dispatcher/active-work</code>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    token = st.session_state.get("lion_auth_token")
    if not token and ld_user and ld_pass:
        with st.spinner("Connecting to Lion Delivery API..."):
            fresh_tok, err_msg = obtain_fresh_jwt_token(auth_url, ld_user, ld_pass)
            if fresh_tok:
                st.session_state["lion_auth_token"] = fresh_tok
                token = fresh_tok

    if not token:
        st.warning("⚠️ **Authentication Required**: Please enter your Lion Delivery credentials in the sidebar and click **🔑 Login / Refresh** to view live dispatched drivers.")
    else:
        act_col1, act_col2, act_col3 = st.columns([2.5, 1, 1.2])
        act_search = act_col1.text_input("🔍 Filter by Driver Name or Bag Reference", placeholder="Type driver or bag...", key="act_search_input")
        refresh_act = act_col2.button("🔄 Refresh Active Work", use_container_width=True, key="btn_refresh_act")

        # Check cache or fetch
        if "cached_active_work" not in st.session_state or refresh_act:
            with st.spinner("Fetching active operational runs from portal..."):
                act_data, act_err = fetch_lion_active_work(token, search=act_search.strip())
                if act_err:
                    st.error(f"Failed to fetch active work: {act_err}")
                    act_data = []
                st.session_state["cached_active_work"] = act_data

        active_runs = st.session_state.get("cached_active_work", [])

        # Also fetch workload for reassignment targets
        if "cached_workload" not in st.session_state or refresh_act:
            wl_data, _ = fetch_lion_drivers_workload(token)
            if wl_data:
                st.session_state["cached_workload"] = wl_data

        fleet_workload = st.session_state.get("cached_workload", [])

        if not active_runs:
            st.info("ℹ️ No active operational runs found for today on `/dispatcher/active-work`.")
        else:
            # Group runs by driver
            drivers_runs_map = {}
            for run in active_runs:
                drv = run.get("driver") or run.get("driver_name") or "Unassigned Driver"
                if act_search and act_search.lower() not in drv.lower() and not any(act_search.lower() in (str(o.get("bag_code", "")).lower() + str(o.get("order_reference", "")).lower()) for o in run.get("orders", [])):
                    continue
                if drv not in drivers_runs_map:
                    drivers_runs_map[drv] = []
                drivers_runs_map[drv].append(run)

            total_active_deliveries = sum(
                sum(len(r.get("orders", [])) or r.get("remaining_stops", 0) for r in r_list)
                for r_list in drivers_runs_map.values()
            )
            act_col3.markdown(
                f'<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:6px 12px; text-align:center;">'
                f'<span style="font-size:11px; color:#166534; font-weight:700;">ACTIVE DELIVERIES</span><br>'
                f'<strong style="font-size:17px; color:#15803d;">{total_active_deliveries} Bags</strong>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Interactive Map data collection
            active_map_stops = []
            seen_act_coords = {}

            # Render driver cards
            for d_idx, (drv_name, drv_runs) in enumerate(drivers_runs_map.items()):
                d_color = DRIVER_COLORS[d_idx % len(DRIVER_COLORS)]
                all_orders = []
                for r in drv_runs:
                    all_orders.extend(r.get("orders", []))

                total_items = sum(r.get("remaining_stops", len(r.get("orders", []))) for r in drv_runs)
                num_runs = len(drv_runs)

                st.markdown(f"""
                <div class="active-work-driver-card">
                    <div class="active-driver-badge-hdr">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span class="driver-color-pill" style="background-color: {d_color};"></span>
                            <span style="font-size: 17px; font-weight: 800; color: #0f172a;">{html.escape(drv_name)}</span>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <span class="stat-pill" style="background:#f0fdf4; border-color:#bbf7d0; color:#166534;">
                                🚀 {num_runs} Active Work • {total_items} item(s)
                            </span>
                            <span class="stat-pill">
                                📦 {len(all_orders)} active deliveries
                            </span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # Bag Grid (Screenshot 1)
                if all_orders:
                    bag_cards_html = []
                    for ord_item in all_orders:
                        b_code = str(ord_item.get("bag_code", "") or "")
                        c_name = str(ord_item.get("customer_name", "") or "")
                        o_ref = str(ord_item.get("order_reference", "") or "")
                        stat = str(ord_item.get("status", "PENDING") or "").replace("_", " ")
                        bag_cards_html.append(
                            f'<div class="bag-tile-item">'
                            f'<div class="bag-tile-code">{html.escape(b_code)}</div>'
                            f'<div class="bag-tile-cust">{html.escape(c_name)}</div>'
                            f'<div class="bag-tile-ref">{html.escape(o_ref)} · <strong style="color:#d97706;">{html.escape(stat)}</strong></div>'
                            f'</div>'
                        )
                    st.markdown(f'<div class="bag-tile-grid">{"".join(bag_cards_html)}</div>', unsafe_allow_html=True)

                # Expandable run details and bag actions (Screenshot 2 & 3)
                with st.expander(f"▼ Internal run details and Bag actions ({num_runs})"):
                    for run_idx, run_obj in enumerate(drv_runs):
                        run_id = run_obj.get("id") or f"run_{run_idx}"
                        run_family = run_obj.get("family", "DELIVERY")
                        run_code = run_obj.get("reference") or run_obj.get("run_code") or f"Run #{run_id}"
                        run_type = run_obj.get("type", "Delivery")
                        run_status = str(run_obj.get("status", "IN_PROGRESS")).replace("_", " ")
                        comp_stops = run_obj.get("completed_stops", 0)
                        tot_stops = run_obj.get("total_stops", len(run_obj.get("orders", [])))

                        r_col1, r_col2, r_col3 = st.columns([3, 1.2, 1.8])
                        r_col1.markdown(
                            f'<div style="padding-top:4px;">'
                            f'<strong style="font-size:14px; color:#0f172a;">{html.escape(str(run_code))}</strong>'
                            f'<span style="font-size:12px; color:#64748b; margin-left:8px;">{html.escape(str(run_type))} detail</span>'
                            f'<span class="lion-badge mode" style="margin-left:8px;">{html.escape(str(run_status))}</span>'
                            f'<span style="font-size:12px; font-weight:700; color:#334155; margin-left:8px;">{comp_stops}/{tot_stops} stops</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                        if run_family == "DELIVERY":
                            portal_link = f"https://app.liondelivery.ae/dispatcher/delivery-runs/{run_id}"
                        elif run_family == "PICKUP":
                            portal_link = f"https://app.liondelivery.ae/dispatcher/pickup-routes/{run_id}"
                        else:
                            portal_link = f"https://app.liondelivery.ae/dispatcher/delivery-runs/{run_id}"

                        r_col2.markdown(f'<a href="{portal_link}" target="_blank" class="nav-link-btn" style="width:100%; text-align:center;">View Details ↗</a>', unsafe_allow_html=True)

                        view_stops_key = f"view_stops_{d_idx}_{run_idx}_{run_id}"
                        toggle_reassign = r_col3.toggle("Reassign Eligible Bags", key=view_stops_key)

                        if toggle_reassign:
                            st.markdown(
                                f'<div style="background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:12px; margin-top:10px; margin-bottom:10px;">'
                                f'<strong style="color:#92400e; font-size:13px;">Eligible Bags in {html.escape(str(run_code))}</strong>'
                                f'<p style="font-size:11.5px; color:#78350f; margin:2px 0 0 0;">'
                                f'Select untouched Bags only. Custody, attempts, completed work and returns remain locked.'
                                f'</p></div>',
                                unsafe_allow_html=True
                            )

                            cache_run_key = f"run_stops_{run_id}"
                            if cache_run_key not in st.session_state:
                                with st.spinner(f"Loading exact Bag locations for {run_code}..."):
                                    run_detail, run_err = fetch_lion_run_reassignment_stops(token, run_id)
                                    if run_err:
                                        st.error(f"Failed to load run details: {run_err}")
                                        run_detail = {}
                                    st.session_state[cache_run_key] = run_detail

                            run_detail_data = st.session_state.get(cache_run_key, {})
                            stops_list = run_detail_data.get("stops", []) if isinstance(run_detail_data, dict) else []

                            if not stops_list:
                                st.info("No stop details found for this run.")
                            else:
                                tbl_rows = []
                                eligible_stop_options = {}
                                for s in stops_list:
                                    s_id = s.get("id")
                                    b_code = s.get("bag_code", "")
                                    o_ref = s.get("order_reference", "")
                                    cust = s.get("customer", "")
                                    part = s.get("partner", "")
                                    loc = f"{s.get('area', '')} · {s.get('city_zone') or s.get('emirate', '')}"
                                    stat = s.get("status", "").replace("_", " ")
                                    inelig = s.get("ineligibility_reason", "")
                                    is_elig = s.get("eligible", False)
                                    lat = s.get("latitude")
                                    lon = s.get("longitude")

                                    map_u = s.get("customer_location_url", "")
                                    if lat and lon:
                                        map_u = f"https://www.google.com/maps?q={lat},{lon}"
                                        coord_str = f"{float(lat):.5f}, {float(lon):.5f}"
                                        ckey = (round(float(lat), 5), round(float(lon), 5))
                                        dup = seen_act_coords.get(ckey, 0)
                                        seen_act_coords[ckey] = dup + 1
                                        active_map_stops.append({
                                            "raw_lat": float(lat),
                                            "raw_lon": float(lon),
                                            "disp_lat": float(lat) + (dup * 0.00014),
                                            "disp_lon": float(lon) + (dup * 0.00014),
                                            "sequence": str(s.get("sequence", len(active_map_stops)+1)),
                                            "bag": str(b_code),
                                            "area": str(loc),
                                            "driver_name": drv_name,
                                            "color": d_color,
                                            "border_style": "2px solid #fff",
                                            "pin_url": map_u
                                        })
                                    else:
                                        coord_str = "No coordinates"

                                    if is_elig:
                                        eligible_stop_options[s_id] = f"{b_code} ({o_ref}) - {cust} - {loc}"

                                    tbl_rows.append({
                                        "Eligible": "✅ Yes" if is_elig else f"🔒 {inelig or 'Locked'}",
                                        "Bag Code": b_code,
                                        "Order Reference": o_ref,
                                        "Customer": cust,
                                        "Partner": part,
                                        "Location Area": loc,
                                        "Status": stat,
                                        "GPS Coordinates": coord_str,
                                        "Google Maps": map_u
                                    })

                                st.dataframe(tbl_rows, use_container_width=True)

                                # Interactive Reassignment Block
                                if eligible_stop_options and fleet_workload:
                                    st.markdown("##### 🔀 Reassign Selected Bags in Portal")
                                    re_col1, re_col2, re_col3 = st.columns([2, 1.5, 1])
                                    selected_reassign_stops = re_col1.multiselect(
                                        "Select Untouched Bags to Move",
                                        options=list(eligible_stop_options.keys()),
                                        format_func=lambda sid: eligible_stop_options[sid],
                                        key=f"re_stops_{d_idx}_{run_idx}_{run_id}"
                                    )
                                    target_drivers_opts = [
                                        d for d in fleet_workload
                                        if d.get("driver_id") != run_obj.get("driver_id")
                                    ]
                                    target_drv_choice = re_col2.selectbox(
                                        "Move To Target Driver",
                                        options=target_drivers_opts,
                                        format_func=lambda d: f"{d.get('driver_name', '')} ({d.get('total_active_tasks', 0)} active tasks)",
                                        key=f"re_target_{d_idx}_{run_idx}_{run_id}"
                                    )
                                    reason_txt = re_col1.text_input("Reassignment Reason", value="Dispatcher manual route balancing", key=f"re_reason_{d_idx}_{run_idx}_{run_id}")

                                    if re_col3.button("⚡ Execute Reassignment", key=f"re_exec_{d_idx}_{run_idx}_{run_id}", disabled=not selected_reassign_stops):
                                        if selected_reassign_stops and target_drv_choice:
                                            tgt_id = target_drv_choice.get("driver_id")
                                            with st.spinner("Executing reassignment on Lion Delivery API..."):
                                                re_res, re_err = reassign_lion_bags(token, run_id, selected_reassign_stops, tgt_id, reason_txt)
                                                if re_err:
                                                    st.error(f"Reassignment failed: {re_err}")
                                                else:
                                                    st.success(f"✅ Successfully reassigned {len(selected_reassign_stops)} bags to {target_drv_choice.get('driver_name')}!")
                                                    st.session_state.pop("cached_active_work", None)
                                                    st.session_state.pop(cache_run_key, None)
                                                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

            # Map of all active stops
            if active_map_stops:
                st.markdown("---")
                st.markdown("""
                <div style="margin-top:14px; margin-bottom:10px;">
                    <span style="font-size:16px; font-weight:800; color:#0f172a;">🗺️ Dispatched Drivers Interactive Route Map</span>
                    <span style="font-size:12px; color:#64748b; margin-left:8px;">Live bag coordinates assigned to on-duty drivers</span>
                </div>
                """, unsafe_allow_html=True)

                act_map_data = {
                    "warehouse": {"lat": wh_lat, "lon": wh_lon, "label": "Ajman Warehouse Base"},
                    "routes": [],
                    "stops": active_map_stops,
                    "excluded": [],
                    "clear_drawing": False
                }
                _maplibre_component(map_data=act_map_data, key="maplibre_active_work_map", default=None)


# ==========================================
# 9. TAB 3: LIVE OPERATIONS MAP (/dispatcher/live-map)
# ==========================================
with tab_live_map:
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
        <div>
            <div style="font-size: 20px; font-weight: 800; color: #0f172a;">🗺️ Live Operations Map</div>
            <div style="font-size: 12.5px; color: #64748b; font-weight: 500;">
                Order-level operational positions across the UAE. Driver GPS is not displayed. Direct feed from <code>/dispatcher/live-map</code>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    token = st.session_state.get("lion_auth_token")
    if not token and ld_user and ld_pass:
        with st.spinner("Connecting to Lion Delivery API..."):
            fresh_tok, err_msg = obtain_fresh_jwt_token(auth_url, ld_user, ld_pass)
            if fresh_tok:
                st.session_state["lion_auth_token"] = fresh_tok
                token = fresh_tok

    if not token:
        st.warning("⚠️ **Authentication Required**: Please enter your Lion Delivery credentials in the sidebar and click **🔑 Login / Refresh** to sync the Live Map.")
    else:
        # Check cache or fetch
        btn_col_lm1, btn_col_lm2 = st.columns([3, 1])
        refresh_lm = btn_col_lm2.button("🔄 Refresh Live Map", use_container_width=True, key="btn_refresh_live_map")

        if "cached_live_map" not in st.session_state or refresh_lm:
            with st.spinner("Loading live orders from portal..."):
                lm_data, lm_err = fetch_lion_live_map(token)
                if lm_err:
                    st.error(f"Failed to fetch live map: {lm_err}")
                    lm_data = {}
                st.session_state["cached_live_map"] = lm_data

        live_map_obj = st.session_state.get("cached_live_map", {})
        raw_markers = live_map_obj.get("markers", []) if isinstance(live_map_obj, dict) else []
        summary = live_map_obj.get("summary", {}) if isinstance(live_map_obj, dict) else {}

        # Compute dynamic counts if summary is missing
        if not summary and raw_markers:
            summary = {
                "total": len(raw_markers),
                "unassigned": sum(1 for m in raw_markers if m.get("map_classification") == "UNASSIGNED"),
                "waiting_to_start": sum(1 for m in raw_markers if m.get("map_classification") == "ASSIGNED"),
                "out_for_delivery": sum(1 for m in raw_markers if m.get("map_classification") == "OUT_FOR_DELIVERY"),
                "follow_up": sum(1 for m in raw_markers if m.get("map_classification") == "FOLLOW_UP"),
                "delivered": sum(1 for m in raw_markers if m.get("map_classification") == "DELIVERED"),
                "return_required": sum(1 for m in raw_markers if m.get("map_classification") == "RETURN_REQUIRED"),
                "returned": sum(1 for m in raw_markers if m.get("map_classification") == "RETURNED")
            }

        # 8 Operational Position Counters (exact match with Screenshot 4)
        total_cnt = summary.get("total", len(raw_markers))
        unassign_cnt = summary.get("unassigned", 0)
        waiting_cnt = summary.get("waiting_to_start", summary.get("assigned", 0))
        out_cnt = summary.get("out_for_delivery", 0)
        followup_cnt = summary.get("follow_up", 0)
        delivered_cnt = summary.get("delivered", 0)
        ret_req_cnt = summary.get("return_required", 0)
        returned_cnt = summary.get("returned", 0)

        st.markdown(f"""
        <div class="live-counter-grid">
            <div class="live-counter-pill">
                <div class="live-counter-val">{total_cnt}</div>
                <div class="live-counter-lbl">Total</div>
            </div>
            <div class="live-counter-pill">
                <div class="live-counter-val">{unassign_cnt}</div>
                <div class="live-counter-lbl">Unassigned</div>
            </div>
            <div class="live-counter-pill active" style="border-color:#2563eb;">
                <div class="live-counter-val" style="color:#2563eb;">{waiting_cnt}</div>
                <div class="live-counter-lbl" style="color:#2563eb;">Waiting to Start</div>
            </div>
            <div class="live-counter-pill" style="border-color:#15803d;">
                <div class="live-counter-val" style="color:#15803d;">{out_cnt}</div>
                <div class="live-counter-lbl" style="color:#15803d;">Out for Delivery</div>
            </div>
            <div class="live-counter-pill">
                <div class="live-counter-val">{followup_cnt}</div>
                <div class="live-counter-lbl">Follow-up</div>
            </div>
            <div class="live-counter-pill">
                <div class="live-counter-val">{delivered_cnt}</div>
                <div class="live-counter-lbl">Delivered</div>
            </div>
            <div class="live-counter-pill" style="border-color:#dc2626;">
                <div class="live-counter-val" style="color:#dc2626;">{ret_req_cnt}</div>
                <div class="live-counter-lbl" style="color:#dc2626;">Return Required</div>
            </div>
            <div class="live-counter-pill">
                <div class="live-counter-val">{returned_cnt}</div>
                <div class="live-counter-lbl">Returned</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Filters Bar
        f_col1, f_col2 = st.columns([2.5, 1.5])
        lm_search = f_col1.text_input("🔍 Search bag, order number, customer, area", placeholder="Search orders...", key="lm_search_input")
        classification_options = ["All Classifications"] + [v["label"] for v in LION_CLASSIFICATION_INFO.values()]
        selected_classification = f_col2.selectbox("Filter Status", options=classification_options, key="lm_class_select")

        # Filter markers
        filtered_markers = []
        for m in raw_markers:
            m_class = m.get("map_classification", "")
            class_info = LION_CLASSIFICATION_INFO.get(m_class, {"label": m_class, "color": "#64748b", "symbol": "•"})

            if selected_classification != "All Classifications" and class_info["label"] != selected_classification:
                continue

            if lm_search:
                q = lm_search.lower()
                bag_str = str(m.get("bag_reference", "")).lower()
                ord_str = str(m.get("order_reference", "")).lower()
                part_str = str(m.get("partner_name", "")).lower()
                area_str = str(m.get("effective_area", "") or m.get("area", "")).lower()
                drv_str = str(m.get("driver_name", "")).lower()
                if not any(q in s for s in (bag_str, ord_str, part_str, area_str, drv_str)):
                    continue

            filtered_markers.append(m)

        # 2-Column Layout (Matching Screenshot 4)
        col_list, col_live_map = st.columns([1.1, 2])

        with col_list:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <strong style="font-size:15px; color:#0f172a;">Orders ({len(filtered_markers)})</strong>
                <span style="font-size:11px; color:#64748b;">Bag-first view</span>
            </div>
            """, unsafe_allow_html=True)

            orders_html = []
            for m in filtered_markers[:150]:
                b_ref = m.get("bag_reference", "")
                o_ref = m.get("order_reference", "")
                p_name = m.get("partner_name", "")
                area = m.get("effective_area") or m.get("area") or ""
                zone = m.get("city_zone") or ""
                em = m.get("emirate") or ""
                loc_txt = " · ".join(dict.fromkeys(p for p in [area, zone, em] if p))
                d_name = m.get("driver_name") or "Unassigned"
                m_class = m.get("map_classification", "")
                c_info = LION_CLASSIFICATION_INFO.get(m_class, {"label": m_class, "color": "#64748b", "symbol": "•"})

                lat = m.get("latitude")
                lon = m.get("longitude")
                pin_url = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "#"

                orders_html.append(f"""
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:10px 12px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                        <div>
                            <strong style="font-size:13px; color:#0f172a; font-family:'JetBrains Mono',monospace;">{html.escape(b_ref)}</strong><br>
                            <span style="font-size:11px; color:#64748b;">{html.escape(o_ref)}</span>
                        </div>
                        <span class="status-pill-badge" style="background-color:{c_info['color']};">
                            {c_info['symbol']} {c_info['label']}
                        </span>
                    </div>
                    <div style="font-size:12px; font-weight:600; color:#334155; margin-top:4px;">{html.escape(p_name)}</div>
                    <div style="font-size:11px; color:#64748b; margin-top:2px;">{html.escape(loc_txt)}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px; font-size:11px;">
                        <span style="color:#475569; font-weight:600;">👤 {html.escape(d_name)}</span>
                        <a href="{pin_url}" target="_blank" style="color:#2563eb; font-weight:700; text-decoration:none;">View Map ↗</a>
                    </div>
                </div>
                """)

            st.markdown(f'<div class="order-list-scroll-box">{"".join(orders_html)}</div>', unsafe_allow_html=True)
            if len(filtered_markers) > 150:
                st.caption(f"Showing first 150 of {len(filtered_markers)} orders in list (all plotted on map).")

        with col_live_map:
            live_map_stops = []
            seen_lm_coords = {}
            for idx, m in enumerate(filtered_markers):
                lat = m.get("latitude")
                lon = m.get("longitude")
                if not lat or not lon:
                    continue
                try:
                    f_lat = float(lat)
                    f_lon = float(lon)
                except ValueError:
                    continue

                ckey = (round(f_lat, 5), round(f_lon, 5))
                dup = seen_lm_coords.get(ckey, 0)
                seen_lm_coords[ckey] = dup + 1

                m_class = m.get("map_classification", "")
                c_info = LION_CLASSIFICATION_INFO.get(m_class, {"label": m_class, "color": "#64748b", "symbol": "•"})

                pin_url = f"https://www.google.com/maps?q={f_lat},{f_lon}"
                b_ref = m.get("bag_reference", "")
                p_name = m.get("partner_name", "")
                d_name = m.get("driver_name", "Unassigned")
                area_txt = m.get("effective_area") or m.get("area") or ""

                live_map_stops.append({
                    "raw_lat": f_lat,
                    "raw_lon": f_lon,
                    "disp_lat": f_lat + (dup * 0.00014),
                    "disp_lon": f_lon + (dup * 0.00014),
                    "sequence": c_info["symbol"],
                    "bag": f"{b_ref} ({c_info['label']})",
                    "area": f"{p_name} • {area_txt} • {d_name}",
                    "driver_name": d_name,
                    "color": c_info["color"],
                    "border_style": "2px solid #fff",
                    "pin_url": pin_url
                })

            if live_map_stops:
                lm_component_data = {
                    "warehouse": {"lat": wh_lat, "lon": wh_lon, "label": "Ajman Warehouse Base"},
                    "routes": [],
                    "stops": live_map_stops,
                    "excluded": [],
                    "clear_drawing": False
                }
                _maplibre_component(map_data=lm_component_data, key="maplibre_live_operations_map", default=None)
            else:
                st.info("No orders with valid coordinates match the current filters.")
