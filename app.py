import csv
import io
import math
import os
import re
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
import folium
from folium.plugins import AntPath, Fullscreen
import requests
import streamlit as st
from streamlit_folium import st_folium

# ==========================================
# PAGE CONFIGURATION (VERSION 1.0)
# ==========================================
st.set_page_config(
    page_title="Lion Delivery Dispatch v2.0 (TEST)",
    page_icon="ðŸšš",
    layout="wide"
)

WAREHOUSE_URL = "https://maps.app.goo.gl/KxepQZ1YGK4qYeND7"
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

DRIVER_COLORS = [
    "#e6194B",  # Red
    "#3cb44b",  # Green
    "#4363d8",  # Blue
    "#f58231",  # Orange
    "#911eb4",  # Purple
    "#008080",  # Teal
    "#e60073",  # Magenta
]

session = requests.Session()
session.headers.update({
    "User-Agent": "LionDeliveryDispatchApp/1.0 (dispatch-portal; contact@liondelivery.local)"
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
    est_hours = round(1.5 + (total_one_way_km / 48.0) + (total_bags * 0.14), 1)
    start_time = datetime.strptime("06:30", "%H:%M")
    finish_dt = start_time + timedelta(hours=est_hours)
    return finish_dt.strftime("%I:%M %p"), est_hours


# ==========================================
# 2. BORDER CONTROL & UAE GEOFENCING
# ==========================================
def is_in_oman(lat, lon):
    # 1. Madha Enclave (Oman enclave inside Fujairah/Sharjah)
    if 25.240 <= lat <= 25.345 and 56.270 <= lon <= 56.380:
        return True
    # 2. Musandam & Dibba Al-Baya (North of UAE)
    if lat >= 26.04:
        return True
    if lat >= 25.620 and lon >= 56.275:
        return True
    # 3. Al Buraimi & Mahdah (East of Al Ain border)
    if 24.15 <= lat <= 24.45 and lon >= 55.775:
        return True
    # 4. East of Hatta / Al Wajajah border
    if 24.78 <= lat <= 24.88 and lon >= 56.140:
        return True
    # 5. General South/East of UAE border fence
    if lat < 24.0 and lon >= 55.80:
        return True
    return False


# ==========================================
# 3. HELPER ROUTING & GEOMETRY FUNCTIONS
# ==========================================
@st.cache_data(show_spinner=False)
def resolve_google_maps_url(url):
    if not url:
        return None, None

    unquoted = urllib.parse.unquote(str(url).strip())
    patterns = [
        r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
        r"[?&]q=(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"/search/(-?\d+\.\d+)\s*,\s*[+]?(-?\d+\.\d+)",
        r"@(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)",
        r"center=(-?\d+\.\d+)%2C(-?\d+\.\d+)",
    ]
    for pat in patterns:
        match = re.search(pat, unquoted)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon

    try:
        resp = session.get(url, allow_redirects=True, timeout=12)
        final_url = urllib.parse.unquote(resp.url)
        for pat in patterns:
            match = re.search(pat, final_url)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon

        for pat in patterns:
            match = re.search(pat, resp.text)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
    except Exception:
        pass

    return None, None


@st.cache_data(show_spinner=False)
def get_osrm_route_geometry(coords_latlon):
    if len(coords_latlon) < 2:
        return coords_latlon

    def query_osrm(pts):
        coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in pts)
        url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
        try:
            resp = session.get(url, timeout=15).json()
            if resp.get("code") == "Ok" and resp.get("routes"):
                geojson_coords = resp["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in geojson_coords]
        except Exception:
            pass
        return pts

    raw_path = query_osrm(coords_latlon)
    crosses_oman = any(is_in_oman(lat, lon) for lat, lon in raw_path)
    if crosses_oman:
        safe_waypoints = [coords_latlon[0]]
        for pt in coords_latlon[1:]:
            if pt[1] >= 56.0:
                safe_waypoints.append(UAE_MASAFI_WAYPOINT)
            safe_waypoints.append(pt)
        safe_path = query_osrm(safe_waypoints)
        return [pt for pt in safe_path if not is_in_oman(pt[0], pt[1])]

    return raw_path


def identify_uae_city(lat, lon):
    if lat < 24.55 and lon >= 55.35:
        return "Al Ain"
    if lon < 54.95 or (lat < 24.70 and lon < 55.35):
        return "Abu Dhabi"
    if lon >= 56.05:
        return "Fujairah / East Coast"
    if lat >= 25.62 and lon >= 55.70:
        return "Ras Al Khaimah"
    if 25.48 <= lat < 25.62 and 55.50 <= lon < 55.85:
        return "Umm Al Quwain"
    if 25.35 <= lat < 25.48 and 55.40 <= lon <= 55.65:
        return "Ajman"
    if 25.25 <= lat < 25.38 and 55.35 <= lon <= 55.75:
        return "Sharjah"
    if 24.80 <= lat < 25.32 and 54.95 <= lon <= 55.65:
        return "Dubai"
    return "Other UAE Corridor"


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

    chunk_size = 45
    chunks = [list(range(k, min(k + chunk_size, n))) for k in range(0, n, chunk_size)]

    try:
        if len(chunks) == 1:
            coord_str = ";".join(f"{coords[idx][1]:.6f},{coords[idx][0]:.6f}" for idx in chunks[0])
            osrm_url = f"http://router.project-osrm.org/table/v1/driving/{coord_str}?annotations=distance"
            resp = session.get(osrm_url, timeout=20).json()
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
                    resp = session.get(osrm_url, timeout=20).json()
                    if resp.get("code") == "Ok" and "distances" in resp:
                        for l_i, g_i in enumerate(comb):
                            for l_j, g_j in enumerate(comb):
                                d = resp["distances"][l_i][l_j]
                                if d is not None:
                                    matrix[g_i][g_j] = d / 1000.0
    except Exception:
        pass

    return matrix


def optimize_route_order(route, dist_matrix):
    if not route:
        return [], 0.0

    unvisited = set(route)
    ordered = []
    curr = 0
    while unvisited:
        nxt = min(unvisited, key=lambda node: dist_matrix[curr][node])
        ordered.append(nxt)
        unvisited.remove(nxt)
        curr = nxt

    def route_distance(seq):
        if not seq:
            return 0.0
        dist = dist_matrix[0][seq[0]]
        for k in range(len(seq) - 1):
            dist += dist_matrix[seq[k]][seq[k + 1]]
        return dist

    improved = True
    while improved and len(ordered) > 1:
        improved = False
        best_dist = route_distance(ordered)
        for i in range(len(ordered) - 1):
            for j in range(i + 1, len(ordered)):
                candidate = ordered[:i] + ordered[i:j + 1][::-1] + ordered[j + 1:]
                cand_dist = route_distance(candidate)
                if cand_dist + 1e-6 < best_dist:
                    ordered = candidate
                    best_dist = cand_dist
                    improved = True

    return ordered, route_distance(ordered)


def are_cities_compatible(cities_a, cities_b):
    comb = cities_a | cities_b
    if len(comb & DISTANT_CITIES) > 1:
        return False
    has_north = bool(comb & {"Ras Al Khaimah", "Umm Al Quwain"})
    has_south = bool(comb & {"Dubai", "Abu Dhabi", "Al Ain"})
    has_east = "Fujairah / East Coast" in comb

    if has_north and (has_south or has_east):
        return False
    if has_east and (has_south or has_north):
        return False
    return True


def get_primary_route_label(route, valid_stops):
    city_bags = {}
    for node in route:
        c = valid_stops[node - 1]["city"]
        city_bags[c] = city_bags.get(c, 0) + valid_stops[node - 1]["bags"]

    for dc in ["Al Ain", "Abu Dhabi", "Fujairah / East Coast", "Ras Al Khaimah"]:
        if dc in city_bags:
            other = [c for c in city_bags if c != dc]
            return f"{dc} + {', '.join(other)} Waypoints" if other else dc

    sorted_c = sorted(city_bags.keys(), key=lambda c: city_bags[c], reverse=True)
    return " / ".join(sorted_c)


def build_balanced_morning_routes(dist_matrix, valid_stops, target_drivers, max_capacity, min_capacity, max_route_km):
    num_stops = len(valid_stops)
    if num_stops == 0:
        return []

    demand_list = [s["bags"] for s in valid_stops]
    city_list = [s["city"] for s in valid_stops]
    total_deliverable_bags = sum(demand_list)

    # Auto-scale active driver count if total volume exceeds target_drivers * max_capacity
    min_drivers_for_capacity = math.ceil(total_deliverable_bags / max_capacity)
    active_target = min(max(target_drivers, min_drivers_for_capacity), len(FLEET_DRIVERS))

    routes = [[i] for i in range(1, num_stops + 1)]

    def route_bags(r):
        return sum(demand_list[n - 1] for n in r)

    def route_cities(r):
        return set(city_list[n - 1] for n in r)

    def find_route(node):
        for idx, r in enumerate(routes):
            if node in r:
                return idx
        return -1

    def try_merge(i_node, j_node, require_same_city=False):
        r_i, r_j = find_route(i_node), find_route(j_node)
        if r_i == -1 or r_j == -1 or r_i == r_j:
            return False
        c_i, c_j = route_cities(routes[r_i]), route_cities(routes[r_j])
        if require_same_city and c_i != c_j:
            return False
        if not are_cities_compatible(c_i, c_j):
            return False

        comb = routes[r_i] + routes[r_j]
        if route_bags(comb) <= max_capacity:
            ordered, km = optimize_route_order(comb, dist_matrix)
            if km <= max_route_km:
                routes[r_i] = ordered
                routes.pop(r_j)
                return True
        return False

    # Stage 1: Lock same-city clusters
    same_city_pairs = []
    for i in range(1, num_stops + 1):
        for j in range(i + 1, num_stops + 1):
            if city_list[i - 1] == city_list[j - 1]:
                score = (min(dist_matrix[0][i], dist_matrix[0][j]) * 2.0) - (dist_matrix[i][j] * 4.0)
                if city_list[i - 1] in DISTANT_CITIES:
                    score += 500.0
                same_city_pairs.append((score, i, j))
    same_city_pairs.sort(key=lambda x: x[0], reverse=True)
    for _, i, j in same_city_pairs:
        try_merge(i, j, require_same_city=True)

    # Stage 2: Merge compatible corridors down to active_target
    while len(routes) > active_target:
        best_pair, best_score = None, -float("inf")
        for a in range(len(routes)):
            for b in range(a + 1, len(routes)):
                r_a, r_b = routes[a], routes[b]
                if route_bags(r_a) + route_bags(r_b) > max_capacity:
                    continue
                if not are_cities_compatible(route_cities(r_a), route_cities(r_b)):
                    continue
                _, km_a = optimize_route_order(r_a, dist_matrix)
                _, km_b = optimize_route_order(r_b, dist_matrix)
                _, km_comb = optimize_route_order(r_a + r_b, dist_matrix)
                if km_comb <= max_route_km:
                    savings = (km_a + km_b) - km_comb
                    score = savings + (40.0 if min(route_bags(r_a), route_bags(r_b)) < min_capacity else 0.0)
                    if score > best_score:
                        best_score, best_pair = score, (a, b)
        if best_pair:
            routes[best_pair[0]] = optimize_route_order(routes[best_pair[0]] + routes[best_pair[1]], dist_matrix)[0]
            routes.pop(best_pair[1])
        else:
            break

    # Stage 3: Absorb tiny 1-5 bag routes
    changed = True
    while changed and len(routes) > 1:
        changed = False
        routes.sort(key=lambda r: route_bags(r))
        smallest = routes[0]
        if route_bags(smallest) < min_capacity:
            temp = [list(r) for r in routes[1:]]
            all_absorbed = True
            for node in smallest:
                b_idx, b_detour = None, float("inf")
                for idx, t_r in enumerate(temp):
                    if route_bags(t_r) + demand_list[node - 1] > max_capacity:
                        continue
                    if not are_cities_compatible(route_cities(t_r), {city_list[node - 1]}):
                        continue
                    _, o_km = optimize_route_order(t_r, dist_matrix)
                    _, n_km = optimize_route_order(t_r + [node], dist_matrix)
                    detour = n_km - o_km
                    if n_km <= max_route_km and detour < b_detour:
                        b_detour, b_idx = detour, idx
                if b_idx is not None:
                    temp[b_idx].append(node)
                else:
                    all_absorbed = False
                    break
            if all_absorbed:
                routes = [optimize_route_order(r, dist_matrix)[0] for r in temp]
                changed = True

    # Stage 4: Highway backfill / relief
    while True:
        best_t, best_d = None, float("inf")
        for l_idx, l_r in enumerate(routes):
            if route_bags(l_r) >= max_capacity - 1:
                continue
            _, l_km = optimize_route_order(l_r, dist_matrix)
            for h_idx, h_r in enumerate(routes):
                if l_idx == h_idx or route_bags(h_r) - route_bags(l_r) < 3 or route_bags(h_r) <= min_capacity:
                    continue
                for node in h_r:
                    nc = city_list[node - 1]
                    if (nc in DISTANT_CITIES and nc not in route_cities(l_r)) or route_bags(l_r) + demand_list[node - 1] > max_capacity:
                        continue
                    if not are_cities_compatible(route_cities(l_r), {nc}):
                        continue
                    _, n_km = optimize_route_order(l_r + [node], dist_matrix)
                    detour = n_km - l_km
                    if n_km <= max_route_km and detour <= 22.0 and detour < best_d:
                        best_d, best_t = detour, (h_idx, l_idx, node)
        if best_t:
            routes[best_t[0]].remove(best_t[2])
            routes[best_t[1]].append(best_t[2])
            routes[best_t[0]], _ = optimize_route_order(routes[best_t[0]], dist_matrix)
            routes[best_t[1]], _ = optimize_route_order(routes[best_t[1]], dist_matrix)
        else:
            break

    return [optimize_route_order(r, dist_matrix)[0] for r in routes]


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

    route_meta = []
    for r_idx, r in enumerate(routes):
        _, one_way_km = optimize_route_order(r, dist_matrix)
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
    dist_mat = build_road_distance_matrix(coords)
    ordered_nodes, one_way_km = optimize_route_order(list(range(1, len(driver_rows) + 1)), dist_mat)

    reordered_rows = []
    prev_node = 0
    total_bags = sum(int(float(r.get("Bags", 1) or 1)) for r in driver_rows)

    for seq_num, node in enumerate(ordered_nodes, start=1):
        row = dict(driver_rows[node - 1])
        leg_km = dist_mat[prev_node][node]
        prev_node = node
        row["Stop_Sequence"] = seq_num
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
    """
    Build multi-stop Google Maps navigation URLs.
    Splits routes > 9 stops into Part 1 (Stops 1-9), Part 2 (Stops 10-18), etc.,
    so Google Maps never truncates stops beyond its 10-waypoint URL limit.
    """
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
            if lon >= 56.0 and f"{UAE_MASAFI_WAYPOINT[0]:.6f},{UAE_MASAFI_WAYPOINT[1]:.6f}" not in pts:
                pts.append(f"{UAE_MASAFI_WAYPOINT[0]:.6f},{UAE_MASAFI_WAYPOINT[1]:.6f}")
            pts.append(f"{lat:.6f},{lon:.6f}")

        part_num = (start_i // chunk_size) + 1
        s_first = chunk[0]["Stop_Sequence"]
        s_last = chunk[-1]["Stop_Sequence"]
        label = "ðŸ—ºï¸ Open Route in Google Maps â†—" if len(stops) <= chunk_size else f"ðŸ—ºï¸ Part {part_num} (Stops #{s_first}â€“#{s_last}) â†—"
        links.append((label, "https://www.google.com/maps/dir/" + "/".join(pts)))

    return links


# ==========================================
# 4. SIDEBAR SETTINGS & DRIVER MAP FILTER
# ==========================================
db_stats = get_recent_driver_stats()
default_far_yesterday = [d for d, st_info in db_stats.items() if st_info["went_far_yesterday"]]

st.sidebar.title("ðŸšš Dispatch & Rotation")

selected_driver_filter = st.sidebar.selectbox(
    "ðŸ” View Driver on Map",
    options=["Show All Drivers"] + FLEET_DRIVERS,
    index=0
)

uploaded_file = st.sidebar.file_uploader("1. Upload 'lion_delivery_all_bags.csv'", type=["csv"])

st.sidebar.markdown("### ðŸ‘¥ Driver Rotation Rules")
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

st.sidebar.markdown("### âš™ï¸ Route Constraints")
target_drivers_input = st.sidebar.slider("Target Morning Drivers", min_value=3, max_value=7, value=5)
max_bags_input = st.sidebar.slider("Max Bags per Driver", min_value=15, max_value=25, value=21)
min_bags_input = st.sidebar.slider("Min Bags per Driver (No tiny runs)", min_value=3, max_value=10, value=6)
max_dist_input = st.sidebar.number_input("Max Warehouse Road Distance (KM)", value=180.0, step=10.0)


# ==========================================
# 5. MAIN APPLICATION PIPELINE
# ==========================================
wh_lat, wh_lon = resolve_google_maps_url(WAREHOUSE_URL)
if not wh_lat:
    st.error("Failed to resolve warehouse coordinates from URL.")
    st.stop()

if uploaded_file is None:
    st.info("ðŸ‘‹ Upload today's scraped `lion_delivery_all_bags.csv` in the sidebar to generate instant routes.")
    with st.expander("ðŸ“Š View 7-Day Driver Rotation History"):
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

raw_bytes = uploaded_file.getvalue()
content = raw_bytes.decode("utf-8-sig").splitlines()
reader = csv.DictReader(content)
raw_rows = list(reader)
fieldnames = reader.fieldnames or []
bag_col = fieldnames[0] if fieldnames else "Bag_Number"

# Auto-detect if file or any sidebar parameter changed
current_config_sig = (
    uploaded_file.name,
    len(raw_bytes),
    target_drivers_input,
    max_bags_input,
    min_bags_input,
    max_dist_input,
    tuple(sorted(far_yesterday_input)),
    tuple(sorted(resting_today_input))
)

force_rerun = st.sidebar.button("ðŸ”„ Re-Run Fast Optimization")

if (
    "dispatch_data" not in st.session_state
    or st.session_state.get("config_sig") != current_config_sig
    or force_rerun
):
    with st.spinner("Processing coordinates and assigning drivers..."):
        resolved, unresolvable, oman_stops = [], [], []
        url_col = next((c for c in fieldnames if any(k in c.lower() for k in ["url", "link", "map", "location"])), None)

        for row in raw_rows:
            lat, lon = resolve_google_maps_url(row.get(url_col, ""))
            if lat and lon:
                if is_in_oman(lat, lon):
                    oman_stops.append({
                        "row_data": row,
                        "lat": lat,
                        "lon": lon,
                        "city": "Oman Territory / Border",
                        "bags": int(float(row.get("Bags", 1) or 1))
                    })
                else:
                    resolved.append({
                        "row_data": row,
                        "lat": lat,
                        "lon": lon,
                        "bags": int(float(row.get("Bags", 1) or 1)),
                        "city": identify_uae_city(lat, lon)
                    })
            else:
                unresolvable.append(row)

        if not resolved:
            st.error("Could not resolve valid UAE coordinates from the uploaded CSV. Check your Map_URL column.")
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

        routes = build_balanced_morning_routes(
            dist_mat, valid_stops,
            target_drivers=target_drivers_input,
            max_capacity=max_bags_input,
            min_capacity=min_bags_input,
            max_route_km=480.0
        )

        driver_route_pairs = assign_drivers_with_rotation(
            routes, valid_stops, dist_mat,
            far_yesterday_names=far_yesterday_input,
            resting_today_names=resting_today_input
        )

        final_rows = []
        for d_name, route in driver_route_pairs:
            ordered, total_km = optimize_route_order(route, dist_mat)
            total_bags = sum(valid_stops[n - 1]["bags"] for n in ordered)
            corridor_label = get_primary_route_label(ordered, valid_stops)
            driver_display = f"{d_name} ({corridor_label})"

            route_temp_rows = []
            prev = 0
            for seq, node in enumerate(ordered, start=1):
                stop = valid_stops[node - 1]
                leg_km = dist_mat[prev][node]
                prev = node
                item = dict(stop["row_data"])
                item.update({
                    "Assigned_Driver": d_name,
                    "Driver_ID": driver_display,
                    "Stop_Sequence": seq,
                    "City_Area": stop["city"],
                    "Warehouse_Road_KM": round(stop["wh_road_km"], 2),
                    "Leg_Distance_KM": round(leg_km, 2),
                    "Route_Total_Bags": total_bags,
                    "Route_OneWay_KM": round(total_km, 2),
                    "Resolved_Lat": round(stop["lat"], 6),
                    "Resolved_Lon": round(stop["lon"], 6),
                    "Dispatch_Status": "ASSIGNED_630AM"
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
                "Driver_ID": "NOT GOING - VERY FAR (>180KM)",
                "Stop_Sequence": "",
                "City_Area": fs["city"],
                "Warehouse_Road_KM": round(fs["wh_road_km"], 2),
                "Leg_Distance_KM": "",
                "Route_Total_Bags": "",
                "Route_OneWay_KM": "",
                "Est_Finish_Time": "",
                "Est_Shift_Hours": "",
                "Resolved_Lat": round(fs["lat"], 6),
                "Resolved_Lon": round(fs["lon"], 6),
                "Dispatch_Status": "UNABLE_TO_DELIVER_OVER_180KM"
            })
            final_rows.append(item)

        for os_stop in oman_stops:
            item = dict(os_stop["row_data"])
            item.update({
                "Assigned_Driver": "NOT GOING",
                "Driver_ID": "NOT GOING - OUTSIDE UAE (OMAN)",
                "Stop_Sequence": "",
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

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Active Drivers", f"{len(active_driver_ids)} / 7")
kpi2.metric("Total Bags Assigned", total_bags_assigned)
kpi3.metric("Resting Drivers", ", ".join(resting_drivers_today) if resting_drivers_today else "None")
kpi4.metric("Excluded Stops", len(excluded_bags))

# ==========================================
# 6. MANUAL CONTROLS
# ==========================================
ctrl_tab1, ctrl_tab2 = st.tabs(["ðŸ”„ Move Single Bag", "ðŸ”€ Swap Drivers Between Routes"])

with ctrl_tab1:
    col_re1, col_re2, col_re3 = st.columns([3, 2, 1.5])
    bag_options = [
        (f"{r.get(bag_col, '')} | {r.get('Driver_ID', '')} (Stop #{r.get('Stop_Sequence', '-')})", idx)
        for idx, r in enumerate(master_rows) if r.get("Resolved_Lat")
    ]
    selected_bag_idx = col_re1.selectbox(
        "Select Bag to Reassign",
        options=[idx for _, idx in bag_options],
        format_func=lambda i: next(lbl for lbl, idx in bag_options if idx == i)
    )
    target_driver_choice = col_re2.selectbox(
        "Move To Driver",
        options=active_driver_ids + ["NOT GOING - VERY FAR (>180KM)", "NOT GOING - OUTSIDE UAE (OMAN)"]
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
    if sc3.button("ðŸ”€ Swap Entire Route"):
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
# 7. LARGE MAP RENDER (FEATURE GROUPS + LEGEND + TILES)
# ==========================================
m = folium.Map(location=[wh_lat, wh_lon], zoom_start=9, tiles=None, control_scale=True)
Fullscreen(position="topleft", force_separate_button=True).add_to(m)

# Base Map Switcher: Google Maps, Esri Street Map, and Google Satellite
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

    # FeatureGroup lets you toggle individual drivers on/off in the top-right layer box
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

        # Offset identical pins by ~15m visually so stacked bag numbers don't hide each other
        disp_lat = raw_lat + (dup_count * 0.00014)
        disp_lon = raw_lon + (dup_count * 0.00014)

        pin_url = f"https://www.google.com/maps?q={raw_lat},{raw_lon}"
        badge_html = (
            f'<div style="background:{color}; color:#fff; border-radius:50%; '
            f'width:24px; height:24px; text-align:center; font-weight:bold; '
            f'font-size:11px; line-height:24px; border:2px solid #fff; '
            f'box-shadow:0 2px 4px rgba(0,0,0,0.4);">'
            f'{s["Stop_Sequence"]}</div>'
        )
        badge = folium.DivIcon(html=badge_html, icon_size=(24, 24), icon_anchor=(12, 12))
        popup_html = (
            f'<div style="font-family:Arial,sans-serif; font-size:12px; min-width:190px;">'
            f'<b>{d_name} â€” Stop #{s["Stop_Sequence"]}</b><br>'
            f'<b>Bag:</b> {s.get(bag_col, "")}<br>'
            f'<b>City:</b> {s.get("City_Area", "")}<br>'
            f'<b>From WH:</b> {s.get("Warehouse_Road_KM", "")} km (+{s.get("Leg_Distance_KM", "")} km leg)<br>'
            f'<b>Est. Finish:</b> {s.get("Est_Finish_Time", "")}<br>'
            f'<a href="{pin_url}" target="_blank" style="color:#1a73e8; font-weight:bold;">Open Pin â†—</a> | '
            f'<a href="{primary_nav_url}" target="_blank" style="color:#0b8043; font-weight:bold;">Driver Route â†—</a>'
            f'</div>'
        )
        folium.Marker(
            location=[disp_lat, disp_lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{s.get(bag_col, '')} â€¢ Stop #{s['Stop_Sequence']} â€¢ {d_name}",
            icon=badge
        ).add_to(fg)

    fg.add_to(m)

    legend_chips.append(
        f'<span style="display:inline-flex; align-items:center; margin-right:14px; margin-bottom:4px; white-space:nowrap;">'
        f'<span style="background:{color}; width:11px; height:11px; border-radius:50%; display:inline-block; margin-right:5px; border:1px solid #fff;"></span>'
        f'<b>{d_name}:</b>&nbsp;{total_bags} bags ({total_km} km)&nbsp;'
        f'<a href="{primary_nav_url}" target="_blank" style="color:#1a73e8; text-decoration:none; font-weight:bold;">[ðŸ—ºï¸ Nav]</a>'
        f'</span>'
    )

# Plot excluded stops in their own toggleable layer when viewing all drivers
if selected_driver_filter == "Show All Drivers" and excluded_bags:
    ex_fg = folium.FeatureGroup(name=f"ðŸš« Excluded Stops ({len(excluded_bags)})", show=True)
    for ex_stop in excluded_bags:
        lat, lon = float(ex_stop["Resolved_Lat"]), float(ex_stop["Resolved_Lon"])
        route_coords_for_bounds.append((lat, lon))
        is_om = "OMAN" in ex_stop["Driver_ID"]
        icon_color = "#e65100" if is_om else "#212121"
        label = "OUTSIDE UAE (OMAN)" if is_om else f"TOO FAR ({ex_stop.get('Warehouse_Road_KM', '>180')} km)"
        warn_html = (
            f'<div style="background:{icon_color}; color:#fff; border-radius:50%; '
            f'width:24px; height:24px; text-align:center; font-weight:bold; '
            f'font-size:11px; line-height:24px; border:2px solid #ff5252;">âœ•</div>'
        )
        warn_badge = folium.DivIcon(html=warn_html, icon_size=(24, 24), icon_anchor=(12, 12))
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>ðŸš« {label}</b><br>Bag: {ex_stop.get(bag_col, '')}",
            tooltip=f"ðŸš« {label}: {ex_stop.get(bag_col, '')}",
            icon=warn_badge
        ).add_to(ex_fg)
    ex_fg.add_to(m)

if len(route_coords_for_bounds) > 1:
    lats = [c[0] for c in route_coords_for_bounds]
    lons = [c[1] for c in route_coords_for_bounds]
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(35, 35))

# Floating bottom summary bar (matches your original screenshot)
if legend_chips:
    bottom_bar_html = (
        '<div style="position:fixed; bottom:10px; left:10px; right:10px; z-index:9999; '
        'background:rgba(255,255,255,0.94); padding:7px 12px; border-radius:8px; '
        'box-shadow:0 2px 8px rgba(0,0,0,0.25); font-family:Arial,sans-serif; '
        'font-size:12px; display:flex; flex-wrap:wrap; align-items:center;">'
        '<span style="margin-right:14px; font-weight:bold;">ðŸ  Ajman WH</span>'
        + "".join(legend_chips) +
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(bottom_bar_html))

folium.LayerControl(collapsed=False, position="topright").add_to(m)

# returned_objects=[] prevents Streamlit from reloading the page when panning/zooming
st_folium(m, width="100%", height=750, returned_objects=[])

# ==========================================
# 8. EXPORT & WHATSAPP CARDS
# ==========================================
out_fields = list(fieldnames) + [
    "Assigned_Driver", "Driver_ID", "Stop_Sequence", "City_Area",
    "Warehouse_Road_KM", "Leg_Distance_KM", "Route_Total_Bags",
    "Route_OneWay_KM", "Est_Finish_Time", "Est_Shift_Hours",
    "Resolved_Lat", "Resolved_Lon", "Dispatch_Status"
]

csv_buffer = io.StringIO()
writer = csv.DictWriter(csv_buffer, fieldnames=out_fields)
writer.writeheader()
writer.writerows(master_rows)

btn_col1, btn_col2 = st.columns(2)
btn_col1.download_button(
    label="ðŸ“¥ Download Today's Dispatch Plan (CSV)",
    data=csv_buffer.getvalue().encode("utf-8-sig"),
    file_name=f"dispatch_plan_{date.today().isoformat()}.csv",
    mime="text/csv"
)

if btn_col2.button("ðŸ’¾ Confirm & Log Today's Routes to Rotation History"):
    log_dispatch_to_db(master_rows)
    st.success("âœ… Saved today's driver assignments to rotation history!")

st.subheader("ðŸ“² Driver Lists & Google Maps Navigation Links")
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
    bag_list_str = ", ".join(f"#{s['Stop_Sequence']}: {s.get(bag_col, '')}" for s in d_stops)

    st.markdown(
        f"**{d_name}** â€” **{len(d_stops)} bags** | **{one_way_km} km** | "
        f"â±ï¸ Est. Finish: **{est_fin}** ({est_hrs} hrs) â€” {links_md}\n"
        f"> *Stop Sequence:* `{bag_list_str}`"
    )
