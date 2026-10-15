import csv
import io
import math
import re
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
import folium
from folium.plugins import AntPath, Fullscreen
import numpy as np
import requests
import streamlit as st
from streamlit_folium import st_folium

# Open-Source AI & Operations Research Imports
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from sklearn.cluster import AgglomerativeClustering
from sklearn.ensemble import RandomForestRegressor

# ==========================================
# PAGE CONFIGURATION & FLEET ROSTER
# ==========================================
st.set_page_config(
    page_title="Lion Delivery AI Dispatch Portal",
    page_icon="🚚",
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

# Safe UAE Highway Waypoints (Keeps routes strictly inside UAE borders)
UAE_MASAFI_WAYPOINT = (25.3180, 56.1660)

# UAE Traffic & Urban Parking Multipliers (6:30 AM Departure)
CITY_TRAFFIC_FACTOR = {
    "Dubai": 1.35,
    "Sharjah": 1.40,
    "Ajman": 1.15,
    "Abu Dhabi": 1.20,
    "Al Ain": 1.05,
    "Ras Al Khaimah": 1.05,
    "Umm Al Quwain": 1.05,
    "Fujairah / East Coast": 1.10,
    "Other UAE Corridor": 1.10
}
MINUTES_PER_BAG_HANDOVER = 8.0

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
    "User-Agent": "LionDeliveryDispatchApp/2.0 (ai-dispatch-portal; contact@liondelivery.local)"
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


# ==========================================
# 2. SCIKIT-LEARN RANDOM FOREST ETA MODEL
# ==========================================
@st.cache_resource(show_spinner=False)
def get_trained_eta_model():
    """
    Train a Scikit-Learn RandomForestRegressor on UAE delivery leg profiles:
    Features: [leg_km, traffic_multiplier, is_highway_leg, bags_at_stop, stop_seq]
    Target: leg_total_minutes (driving + parking + customer handover)
    """
    rng = np.random.RandomState(42)
    n_samples = 600

    leg_km = rng.uniform(0.5, 140.0, n_samples)
    traffic_mult = rng.choice([1.05, 1.10, 1.15, 1.20, 1.35, 1.40], n_samples)
    is_highway = (leg_km >= 20.0).astype(float)
    bags_count = rng.choice([1, 1, 1, 2, 3], n_samples)
    stop_seq = rng.randint(1, 22, n_samples)

    # Realistic UAE speed curve + urban parking & handover overhead
    speed_kmh = np.where(is_highway == 1.0, 88.0, 36.0)
    drive_mins = (leg_km / speed_kmh) * 60.0 * traffic_mult
    parking_overhead = np.where(traffic_mult >= 1.30, 3.5, 1.5)
    handover_mins = bags_count * MINUTES_PER_BAG_HANDOVER + parking_overhead

    y_mins = drive_mins + handover_mins
    X_train = np.column_stack([leg_km, traffic_mult, is_highway, bags_count, stop_seq])

    rf_model = RandomForestRegressor(n_estimators=80, max_depth=10, random_state=42)
    rf_model.fit(X_train, y_mins)
    return rf_model


def predict_driver_finish_time(stops):
    """Predict shift completion time from 6:30 AM using Scikit-Learn Random Forest."""
    if not stops:
        return "06:30 AM", 0.0

    rf_model = get_trained_eta_model()
    features = []
    for idx, s in enumerate(stops, start=1):
        leg_km = float(s.get("Leg_Distance_KM", 0.0) or 0.0)
        city = s.get("City_Area", "Other UAE Corridor")
        t_mult = CITY_TRAFFIC_FACTOR.get(city, 1.15)
        is_hwy = 1.0 if leg_km >= 20.0 else 0.0
        bags = int(float(s.get("Bags", 1) or 1))
        features.append([leg_km, t_mult, is_hwy, bags, idx])

    X_pred = np.array(features)
    predicted_leg_mins = rf_model.predict(X_pred)
    total_shift_mins = float(np.sum(predicted_leg_mins))

    start_time = datetime.strptime("06:30", "%H:%M")
    finish_dt = start_time + timedelta(minutes=total_shift_mins)
    return finish_dt.strftime("%I:%M %p"), round(total_shift_mins / 60.0, 1)


# ==========================================
# 3. BORDER CONTROL & UAE GEOFENCING
# ==========================================
def is_in_oman(lat, lon):
    if 25.240 <= lat <= 25.345 and 56.270 <= lon <= 56.380:
        return True
    if lat >= 26.04:
        return True
    if lat >= 25.620 and lon >= 56.275:
        return True
    if 24.15 <= lat <= 24.45 and lon >= 55.775:
        return True
    if 24.78 <= lat <= 24.88 and lon >= 56.140:
        return True
    if lat < 24.0 and lon >= 55.80:
        return True
    return False


# ==========================================
# 4. URL RESOLUTION & OSRM ROAD MATRICES
# ==========================================
@st.cache_data(show_spinner=False)
def resolve_google_maps_url(url):
    if not url:
        return None, None

    unquoted = urllib.parse.unquote(url)
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


# ==========================================
# 5. GOOGLE OR-TOOLS & SCIKIT-LEARN SOLVERS
# ==========================================
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


def optimize_route_order(route, dist_matrix):
    """
    Google OR-Tools Open-TSP Solver (Guided Local Search):
    Finds the optimal one-way stop sequence starting from the Ajman Warehouse (node 0)
    and ending at the final stop without returning to the warehouse.
    """
    if not route:
        return [], 0.0
    if len(route) == 1:
        return list(route), dist_matrix[0][route[0]]

    # Nodes in sub-problem: 0 = Warehouse, 1..len(route) = route stops, len(route)+1 = Dummy open sink
    sub_nodes = [0] + list(route)
    num_sub = len(sub_nodes)
    sink_idx = num_sub  # Open-end dummy node with 0 distance from any stop

    manager = pywrapcp.RoutingIndexManager(num_sub + 1, 1, [0], [sink_idx])
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == sink_idx or to_node == sink_idx:
            return 0
        real_from = sub_nodes[from_node]
        real_to = sub_nodes[to_node]
        return int(round(dist_matrix[real_from][real_to] * 1000))

    transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.FromMilliseconds(250)

    solution = routing.SolveWithParameters(search_params)
    if solution:
        ordered = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if 1 <= node < sink_idx:
                ordered.append(sub_nodes[node])
            index = solution.Value(routing.NextVar(index))

        total_km = dist_matrix[0][ordered[0]]
        for k in range(len(ordered) - 1):
            total_km += dist_matrix[ordered[k]][ordered[k + 1]]
        return ordered, total_km

    # Fallback if solver times out
    unvisited = set(route)
    ordered = []
    curr = 0
    while unvisited:
        nxt = min(unvisited, key=lambda n: dist_matrix[curr][n])
        ordered.append(nxt)
        unvisited.remove(nxt)
        curr = nxt
    total_km = dist_matrix[0][ordered[0]] + sum(dist_matrix[ordered[k]][ordered[k + 1]] for k in range(len(ordered) - 1))
    return ordered, total_km


def build_balanced_morning_routes(dist_matrix, valid_stops, target_drivers, max_capacity, min_capacity, max_route_km):
    """
    Combines Scikit-Learn Agglomerative Road-Network Clustering with
    Google OR-Tools route sequencing, capacity splitting, and highway relief.
    """
    num_stops = len(valid_stops)
    if num_stops == 0:
        return []

    demand_list = [s["bags"] for s in valid_stops]
    city_list = [s["city"] for s in valid_stops]
    total_bags = sum(demand_list)

    min_drivers_needed = math.ceil(total_bags / max_capacity)
    k_clusters = min(max(target_drivers, min_drivers_needed), len(FLEET_DRIVERS), num_stops)

    # ------------------------------------------------------------------
    # STAGE 1: SCIKIT-LEARN AGGLOMERATIVE CLUSTERING ON ROAD MATRIX
    # ------------------------------------------------------------------
    stop_dist_matrix = np.zeros((num_stops, num_stops))
    for i in range(num_stops):
        for j in range(num_stops):
            if i != j:
                road_d = 0.5 * (dist_matrix[i + 1][j + 1] + dist_matrix[j + 1][i + 1])
                if not are_cities_compatible({city_list[i]}, {city_list[j]}):
                    road_d += 10000.0  # Hard directional barrier for Scikit-Learn
                elif city_list[i] == city_list[j] and city_list[i] in DISTANT_CITIES:
                    road_d *= 0.25     # Keep distant cities tightly grouped together
                stop_dist_matrix[i, j] = road_d

    if num_stops > k_clusters:
        clustering = AgglomerativeClustering(
            n_clusters=k_clusters,
            metric="precomputed",
            linkage="average"
        )
        labels = clustering.fit_predict(stop_dist_matrix)
        raw_clusters = {}
        for stop_idx, lbl in enumerate(labels, start=1):
            raw_clusters.setdefault(int(lbl), []).append(stop_idx)
        initial_routes = list(raw_clusters.values())
    else:
        initial_routes = [[i] for i in range(1, num_stops + 1)]

    def route_bags(r):
        return sum(demand_list[n - 1] for n in r)

    def route_cities(r):
        return set(city_list[n - 1] for n in r)

    # ------------------------------------------------------------------
    # STAGE 2: SPLIT ANY OVER-CAPACITY CLUSTER (>21 BAGS) USING OR-TOOLS
    # ------------------------------------------------------------------
    routes = []
    for cluster in initial_routes:
        ordered_c, _ = optimize_route_order(cluster, dist_matrix)
        if route_bags(ordered_c) <= max_capacity:
            routes.append(ordered_c)
        else:
            current_chunk = []
            current_bags = 0
            for node in ordered_c:
                b = demand_list[node - 1]
                if current_bags + b <= max_capacity:
                    current_chunk.append(node)
                    current_bags += b
                else:
                    if current_chunk:
                        routes.append(optimize_route_order(current_chunk, dist_matrix)[0])
                    current_chunk = [node]
                    current_bags = b
            if current_chunk:
                routes.append(optimize_route_order(current_chunk, dist_matrix)[0])

    # ------------------------------------------------------------------
    # STAGE 3: MERGE COMPATIBLE CORRIDORS DOWN TO TARGET DRIVERS
    # ------------------------------------------------------------------
    while len(routes) > k_clusters:
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

    # ------------------------------------------------------------------
    # STAGE 4: ABSORB TINY ROUTES (1-5 BAGS) & APPLY HIGHWAY RELIEF
    # ------------------------------------------------------------------
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
            if len(active_drivers) < num_routes:
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
    for meta, d_name in zip(route_meta, ordered_driver_queue):
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

    est_finish, est_hrs = predict_driver_finish_time(reordered_rows)
    for row in reordered_rows:
        row["Est_Finish_Time"] = est_finish
        row["Est_Shift_Hours"] = est_hrs

    return reordered_rows


def build_google_maps_nav_link(wh_lat, wh_lon, stops):
    pts = [f"{wh_lat:.6f},{wh_lon:.6f}"]
    for s in stops[:9]:
        lat, lon = float(s['Resolved_Lat']), float(s['Resolved_Lon'])
        if lon >= 56.0 and f"{UAE_MASAFI_WAYPOINT[0]},{UAE_MASAFI_WAYPOINT[1]}" not in pts:
            pts.append(f"{UAE_MASAFI_WAYPOINT[0]:.6f},{UAE_MASAFI_WAYPOINT[1]:.6f}")
        pts.append(f"{lat:.6f},{lon:.6f}")
    return "https://www.google.com/maps/dir/" + "/".join(pts)


# ==========================================
# 6. SIDEBAR: SETTINGS & DRIVER ROTATION
# ==========================================
db_stats = get_recent_driver_stats()
default_far_yesterday = [d for d, st_info in db_stats.items() if st_info["went_far_yesterday"]]

st.sidebar.title("🚚 AI Dispatch & Rotation")
uploaded_file = st.sidebar.file_uploader("1. Upload 'lion_delivery_all_bags.csv'", type=["csv"])

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

st.sidebar.markdown("### ⚙️ OR-Tools & Scikit-Learn Settings")
target_drivers_input = st.sidebar.slider("Target Morning Drivers", min_value=3, max_value=7, value=5)
max_bags_input = st.sidebar.slider("Max Bags per Driver", min_value=15, max_value=25, value=21)
min_bags_input = st.sidebar.slider("Min Bags per Driver (No tiny runs)", min_value=3, max_value=10, value=6)
max_dist_input = st.sidebar.number_input("Max Warehouse Road Distance (KM)", value=180.0, step=10.0)


# ==========================================
# 7. MAIN APPLICATION PIPELINE
# ==========================================
st.title("Ajman Warehouse 6:30 AM AI Dispatch Portal")
st.caption("Powered by Google OR-Tools (Guided Local Search) & Scikit-Learn (Road-Network Clustering + Random Forest ETA)")

wh_lat, wh_lon = resolve_google_maps_url(WAREHOUSE_URL)
if not wh_lat:
    st.error("Failed to resolve warehouse coordinates from URL.")
    st.stop()

if uploaded_file is None:
    st.info("👋 Upload today's scraped `lion_delivery_all_bags.csv` in the sidebar to run OR-Tools & Scikit-Learn optimization.")
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

content = uploaded_file.getvalue().decode("utf-8-sig").splitlines()
reader = csv.DictReader(content)
raw_rows = list(reader)
fieldnames = reader.fieldnames or []
bag_col = fieldnames[0] if fieldnames else "Bag_Number"

if "dispatch_data" not in st.session_state or st.sidebar.button("🔄 Re-Run OR-Tools & Scikit-Learn"):
    with st.spinner("Running Scikit-Learn Road Clustering, Google OR-Tools Solver, and Random Forest ETA..."):
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

            est_finish, est_hrs = predict_driver_finish_time(route_temp_rows)
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
kpi1.metric("Active Drivers (6:30 AM)", f"{len(active_driver_ids)} / 7")
kpi2.metric("Total Bags Assigned", total_bags_assigned)
kpi3.metric("Resting Drivers Today", ", ".join(resting_drivers_today) if resting_drivers_today else "None")
kpi4.metric("Excluded Stops (>180km / Oman)", len(excluded_bags))

# ==========================================
# 8. MANUAL STOP & DRIVER SWAP CONTROLS
# ==========================================
ctrl_tab1, ctrl_tab2 = st.tabs(["🔄 Move Single Bag (OR-Tools Re-Sequence)", "🔀 Swap Drivers Between Routes"])

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
            else:
                master_rows[selected_bag_idx]["Assigned_Driver"] = "NOT GOING"

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
# 9. INTERACTIVE MAP (SNAP-TO-ROADS)
# ==========================================
m = folium.Map(location=[wh_lat, wh_lon], zoom_start=9, tiles=None, control_scale=True)
Fullscreen(position="topleft").add_to(m)

folium.TileLayer("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google Maps", name="Google Maps", control=True).add_to(m)
folium.Marker(location=[wh_lat, wh_lon], popup="Ajman Warehouse (6:30 AM)", icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(m)

for d_idx, d_name in enumerate(active_driver_ids):
    color = DRIVER_COLORS[d_idx % len(DRIVER_COLORS)]
    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))

    waypoints = [(wh_lat, wh_lon)] + [(float(s["Resolved_Lat"]), float(s["Resolved_Lon"])) for s in d_stops]
    road_polyline = get_osrm_route_geometry(waypoints)
    AntPath(locations=road_polyline, color=color, weight=4, opacity=0.85, tooltip=d_name).add_to(m)

    for s in d_stops:
        badge_html = (
            f'<div style="background:{color}; color:#fff; border-radius:50%; '
            f'width:22px; height:22px; text-align:center; font-weight:bold; '
            f'font-size:11px; line-height:22px; border:2px solid #fff;">'
            f'{s["Stop_Sequence"]}</div>'
        )
        badge = folium.DivIcon(html=badge_html, icon_size=(22, 22), icon_anchor=(11, 11))
        popup_text = (
            f"<b>{d_name} — Stop #{s['Stop_Sequence']}</b><br>"
            f"Bag: {s.get(bag_col, '')}<br>"
            f"City: {s.get('City_Area', '')}<br>"
            f"RF Est. Finish: {s.get('Est_Finish_Time', '')}"
        )
        folium.Marker(
            location=[float(s["Resolved_Lat"]), float(s["Resolved_Lon"])],
            popup=popup_text,
            tooltip=f"{s.get(bag_col, '')} • Stop #{s['Stop_Sequence']} • {d_name}",
            icon=badge
        ).add_to(m)

for ex_stop in excluded_bags:
    lat, lon = float(ex_stop["Resolved_Lat"]), float(ex_stop["Resolved_Lon"])
    is_om = "OMAN" in ex_stop["Driver_ID"]
    icon_color = "#e65100" if is_om else "#212121"
    label = "OUTSIDE UAE (OMAN)" if is_om else "TOO FAR (>180km)"

    warn_html = (
        f'<div style="background:{icon_color}; color:#fff; border-radius:50%; '
        f'width:22px; height:22px; text-align:center; font-weight:bold; '
        f'font-size:11px; line-height:22px; border:2px solid #fff;">✕</div>'
    )
    warn_badge = folium.DivIcon(html=warn_html, icon_size=(22, 22), icon_anchor=(11, 11))
    folium.Marker(
        location=[lat, lon],
        popup=f"<b>🚫 {label}</b><br>Bag: {ex_stop.get(bag_col, '')}",
        tooltip=f"🚫 {label}: {ex_stop.get(bag_col, '')}",
        icon=warn_badge
    ).add_to(m)

st_folium(m, width="100%", height=500)

# ==========================================
# 10. EXPORT, ROTATION LOG & WHATSAPP CARDS
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
    label="📥 Download Today's Dispatch Plan (CSV)",
    data=csv_buffer.getvalue().encode("utf-8-sig"),
    file_name=f"dispatch_plan_{date.today().isoformat()}.csv",
    mime="text/csv"
)

if btn_col2.button("💾 Confirm & Log Today's Routes to Rotation History"):
    log_dispatch_to_db(master_rows)
    st.success("✅ Saved today's driver assignments to rotation history!")

st.subheader("📲 6:30 AM Driver Dispatch Cards (WhatsApp Ready)")
for d_name in active_driver_ids:
    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))
    nav_link = build_google_maps_nav_link(wh_lat, wh_lon, d_stops)
    one_way_km = d_stops[0].get("Route_OneWay_KM", "0")
    est_fin = d_stops[0].get("Est_Finish_Time", "")
    est_hrs = d_stops[0].get("Est_Shift_Hours", "")
    bag_list_str = ", ".join(f"#{s['Stop_Sequence']}: {s.get(bag_col, '')}" for s in d_stops)

    st.markdown(
        f"**{d_name}** — **{len(d_stops)} bags** | **{one_way_km} km** | "
        f"🤖 RF Est. Finish: **{est_fin}** ({est_hrs} hrs) — [🗺️ Open Route in Google Maps ↗]({nav_link})\n"
        f"> *Stop Order:* `{bag_list_str}`"
    )