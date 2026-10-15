import csv
import math
import re
import time
import urllib.parse
import folium
from folium.plugins import AntPath, Fullscreen
import requests
import streamlit as st
from streamlit_folium import st_folium

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Lion Delivery Dispatch Portal",
    page_icon="🚚",
    layout="wide"
)

WAREHOUSE_URL = "https://maps.app.goo.gl/KxepQZ1YGK4qYeND7"
DISTANT_CITIES = {"Al Ain", "Abu Dhabi", "Fujairah / East Coast", "Ras Al Khaimah"}

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
# HELPER ROUTING FUNCTIONS
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
    demand_list = [s["bags"] for s in valid_stops]
    city_list = [s["city"] for s in valid_stops]

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

    # 1. Lock same-city clusters
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

    # 2. Merge corridors down to target drivers
    while len(routes) > target_drivers:
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

    # 3. Absorb 1-5 bag routes
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

    # 4. Highway relief
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


def build_google_maps_nav_link(wh_lat, wh_lon, stops):
    pts = [f"{wh_lat:.6f},{wh_lon:.6f}"] + [
        f"{float(s['Resolved_Lat']):.6f},{float(s['Resolved_Lon']):.6f}" for s in stops[:10]
    ]
    return "https://www.google.com/maps/dir/" + "/".join(pts)


# ==========================================
# SIDEBAR CONTROLS
# ==========================================
st.sidebar.title("🚚 Dispatch Settings")
target_drivers_input = st.sidebar.slider("Target Morning Drivers", min_value=3, max_value=7, value=5)
max_bags_input = st.sidebar.slider("Max Bags per Driver", min_value=15, max_value=25, value=21)
min_bags_input = st.sidebar.slider("Min Bags per Driver (No tiny runs)", min_value=3, max_value=10, value=6)
max_dist_input = st.sidebar.number_input("Max Warehouse Road Distance (KM)", value=180.0, step=10.0)

uploaded_file = st.sidebar.file_uploader("Upload 'lion_delivery_all_bags.csv'", type=["csv"])


# ==========================================
# MAIN APPLICATION LOGIC
# ==========================================
st.title("Ajman Warehouse Delivery Dispatcher")

wh_lat, wh_lon = resolve_google_maps_url(WAREHOUSE_URL)
if not wh_lat:
    st.error("Failed to resolve warehouse coordinates from URL.")
    st.stop()

if uploaded_file is None:
    st.info("👋 Upload today's scraped `lion_delivery_all_bags.csv` in the sidebar to generate routes.")
    st.stop()

# Load CSV data
content = uploaded_file.getvalue().decode("utf-8-sig").splitlines()
reader = csv.DictReader(content)
raw_rows = list(reader)
fieldnames = reader.fieldnames or []
bag_col = fieldnames[0] if fieldnames else "Bag_Number"

# Run optimization and cache in Session State
if "dispatch_data" not in st.session_state or st.sidebar.button("🔄 Re-Run Full Route Optimization"):
    with st.spinner("Resolving delivery coordinates and generating corridor clusters..."):
        resolved, unresolvable = [], []
        url_col = next((c for c in fieldnames if any(k in c.lower() for k in ["url", "link", "map", "location"])), None)

        for row in raw_rows:
            lat, lon = resolve_google_maps_url(row.get(url_col, ""))
            if lat and lon:
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
        routes.sort(key=lambda r: (max(valid_stops[n - 1]["wh_road_km"] for n in r), sum(valid_stops[n - 1]["bags"] for n in r)), reverse=True)

        final_rows = []
        for r_idx, route in enumerate(routes, start=1):
            ordered, total_km = optimize_route_order(route, dist_mat)
            total_bags = sum(valid_stops[n - 1]["bags"] for n in ordered)
            driver_name = f"Driver {r_idx} ({get_primary_route_label(ordered, valid_stops)})"

            prev = 0
            for seq, node in enumerate(ordered, start=1):
                stop = valid_stops[node - 1]
                leg_km = dist_mat[prev][node]
                prev = node
                item = dict(stop["row_data"])
                item.update({
                    "Driver_ID": driver_name,
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
                final_rows.append(item)

        for fs in far_stops:
            item = dict(fs["row_data"])
            item.update({
                "Driver_ID": "NOT GOING - VERY FAR (>180KM)",
                "Stop_Sequence": "",
                "City_Area": fs["city"],
                "Warehouse_Road_KM": round(fs["wh_road_km"], 2),
                "Leg_Distance_KM": "",
                "Route_Total_Bags": "",
                "Route_OneWay_KM": "",
                "Resolved_Lat": round(fs["lat"], 6),
                "Resolved_Lon": round(fs["lon"], 6),
                "Dispatch_Status": "UNABLE_TO_DELIVER_OVER_180KM"
            })
            final_rows.append(item)

        st.session_state["dispatch_data"] = final_rows

master_rows = st.session_state["dispatch_data"]

# Display KPIs
active_driver_ids = sorted(list(set(r["Driver_ID"] for r in master_rows if "NOT GOING" not in r["Driver_ID"] and r["Driver_ID"] != "UNASSIGNED")))
total_bags_assigned = sum(int(float(r.get("Bags", 1) or 1)) for r in master_rows if "NOT GOING" not in r["Driver_ID"])
excluded_bags = [r for r in master_rows if "NOT GOING" in r["Driver_ID"]]

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Active Drivers Today", f"{len(active_driver_ids)} / {7}")
kpi2.metric("Total Bags Assigned", total_bags_assigned)
kpi3.metric("Resting Drivers", 7 - len(active_driver_ids))
kpi4.metric("Excluded Stops (>180 km)", len(excluded_bags))

# Stop Reassignment UI
st.subheader("Manual Stop Adjustment")
col_re1, col_re2, col_re3 = st.columns([3, 2, 1.5])

bag_options = [
    (f"{r.get(bag_col, '')} | {r.get('Driver_ID', '')} (Stop #{r.get('Stop_Sequence', '-')})", idx)
    for idx, r in enumerate(master_rows) if r.get("Resolved_Lat")
]

selected_bag_idx = col_re1.selectbox("Select Bag to Reassign", options=[idx for _, idx in bag_options], format_func=lambda i: next(lbl for lbl, idx in bag_options if idx == i))
target_driver_choice = col_re2.selectbox("Move To Driver", options=active_driver_ids + ["NOT GOING - VERY FAR (>180KM)"])

if col_re3.button("Move & Recalculate"):
    old_drv = master_rows[selected_bag_idx]["Driver_ID"]
    if old_drv != target_driver_choice:
        master_rows[selected_bag_idx]["Driver_ID"] = target_driver_choice
        st.session_state["dispatch_data"] = master_rows
        st.success(f"Moved bag to {target_driver_choice}!")
        st.rerun()

# Build Map
m = folium.Map(location=[wh_lat, wh_lon], zoom_start=9, tiles=None, control_scale=True)
Fullscreen(position="topleft").add_to(m)

folium.TileLayer("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google Maps", name="Google Maps", control=True).add_to(m)
folium.Marker(location=[wh_lat, wh_lon], popup="Ajman Warehouse", icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(m)

for d_idx, d_name in enumerate(active_driver_ids):
    color = DRIVER_COLORS[d_idx % len(DRIVER_COLORS)]
    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))

    pts = [(wh_lat, wh_lon)] + [(float(s["Resolved_Lat"]), float(s["Resolved_Lon"])) for s in d_stops]
    AntPath(locations=pts, color=color, weight=4, opacity=0.85).add_to(m)

    for s in d_stops:
        badge = folium.DivIcon(
            html=f"""<div style="background:{color}; color:#fff; border-radius:50%; width:22px; height:22px; text-align:center; font-weight:bold; font-size:11px; line-height:22px; border:2px solid #fff;">{s['Stop_Sequence']}</div>""",
            icon_size=(22, 22), icon_anchor=(11, 11)
        )
        folium.Marker(
            location=[float(s["Resolved_Lat"]), float(s["Resolved_Lon"])],
            popup=f"<b>{d_name} — Stop #{s['Stop_Sequence']}</b><br>Bag: {s.get(bag_col, '')}<br>City: {s.get('City_Area', '')}",
            tooltip=f"{s.get(bag_col, '')} (Stop #{s['Stop_Sequence']})",
            icon=badge
        ).add_to(m)

st_folium(m, width="100%", height=520)

# CSV Export
out_fields = list(fieldnames) + ["Driver_ID", "Stop_Sequence", "City_Area", "Warehouse_Road_KM", "Leg_Distance_KM", "Route_Total_Bags", "Route_OneWay_KM", "Resolved_Lat", "Resolved_Lon", "Dispatch_Status"]
csv_buffer = ""
with open("temp_dispatch.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=out_fields)
    w.writeheader()
    w.writerows(master_rows)
with open("temp_dispatch.csv", "r", encoding="utf-8-sig") as f:
    csv_buffer = f.read()

st.download_button(
    label="📥 Download Today's Dispatch Plan (CSV)",
    data=csv_buffer,
    file_name="driver_dispatch_plan.csv",
    mime="text/csv"
)

# Driver WhatsApp Navigation Table
st.subheader("Driver Route Navigation Links (WhatsApp Ready)")
for d_name in active_driver_ids:
    d_stops = [r for r in master_rows if r["Driver_ID"] == d_name]
    d_stops.sort(key=lambda x: int(x["Stop_Sequence"]))
    nav_link = build_google_maps_nav_link(wh_lat, wh_lon, d_stops)
    st.markdown(f"**{d_name}** ({len(d_stops)} bags) — [Open Route in Google Maps ↗]({nav_link})")