import streamlit as st
import pandas as pd
import random
from google import genai
import plotly.express as px

# -----------------------------
# SESSION STATE INIT
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_chat" not in st.session_state:
    st.session_state.show_chat = False

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="ZeroBackhaul - SmartTruck", layout="wide")
st.title("🚚 ZeroBackhaul - SmartTruck Optimizer")
st.caption("Detect empty trucks and optimize their routes for profit, fuel savings, and CO₂ reduction")

# -----------------------------
# GEMINI CLIENT
# -----------------------------
client = genai.Client(api_key="AIzaSyBcS5Ve1dA6zq-uf2pBR60kbzkxboTMNUc")  # replace with your API key

# -----------------------------
# FUNCTIONS
# -----------------------------
def classify_truck(poids_reel, poids_declare):
    if poids_reel == 0 and poids_declare > 0:
        return "Empty"
    elif poids_reel < poids_declare:
        return "Partially Loaded"
    else:
        return "Full"

def get_route_ai_reasoning(truck_id, route_plan, fuel_saved, co2_reduced):
    prompt = f"""
    You are a logistics AI assistant.
    Truck ID: {truck_id}
    Route Plan: {route_plan}
    Estimated Fuel Saved: ${fuel_saved:.2f}
    Estimated CO₂ Reduced: {co2_reduced:.1f} kg

    Explain in detail:
    1. Why these stops were chosen
    2. How they increase profit
    3. How they reduce empty kilometers
    4. Why the fuel saved is exactly ${fuel_saved:.2f}
    5. Why the CO₂ reduction is exactly {co2_reduced:.1f} kg

    Provide a structured explanation in a clear, readable way.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

def optimize_route(truck, demand_data):
    if truck["Status"] != "Empty":
        return [], 0, 0
    nearby = demand_data.copy()
    nearby["distance"] = ((nearby["Latitude"] - truck["Latitude"])**2 + (nearby["Longitude"] - truck["Longitude"])**2)**0.5 * 111
    nearby = nearby[nearby["distance"] <= 300].sort_values(by="Profit", ascending=False)
    selected = nearby.head(2)
    route_plan = []
    total_profit = 0
    distance_saved = 0
    for _, row in selected.iterrows():
        route_plan.append({
            "Ville": row["Ville"],
            "Volume": row["Volume"],
            "Profit": row["Profit"]
        })
        total_profit += row["Profit"]
        distance_saved += row["distance"]
    return route_plan, total_profit, distance_saved

# -----------------------------
# INPUT SECTION
# -----------------------------
st.subheader("📥 Upload Fleet & Demand Data")
fleet_file = st.file_uploader("Upload fleet CSV", type="csv")
demand_file = st.file_uploader("Upload demand CSV", type="csv")

df = pd.DataFrame()
demand_data = pd.DataFrame()

if fleet_file:
    df = pd.read_csv(fleet_file)
if demand_file:
    demand_data = pd.read_csv(demand_file)

if df.empty and st.button("⚡ Simulate Fleet"):
    villes = ["Paris", "Madrid", "Berlin", "Lisbonne", "Rome", "Casablanca", "Rabat", "Fes", "Marrakech"]
    trucks = []
    for i in range(10):
        lat = random.uniform(30.0, 52.0)
        lon = random.uniform(-10.0, 15.0)
        poids = random.choice([0, random.randint(1000, 2500)])
        declare = 2500
        trucks.append({
            "Truck_ID": f"T{i+1}",
            "Poids_reel": poids,
            "Poids_declare": declare,
            "Ville": random.choice(villes),
            "Latitude": lat,
            "Longitude": lon
        })
    df = pd.DataFrame(trucks)

# -----------------------------
# PROCESS DATA
# -----------------------------
if not df.empty:
    df["Status"] = df.apply(lambda r: classify_truck(r["Poids_reel"], r["Poids_declare"]), axis=1)
    df["Capacity %"] = df.apply(lambda r: min((r["Poids_reel"] / max(r["Poids_declare"], 1)) * 100, 100), axis=1)
    COST_PER_EMPTY_TRUCK = 300
    FUEL_COST_PER_KM = 1.2  # approximate $ per km
    CO2_PER_KM = 0.25       # approximate kg CO2 per km
    df["Empty_Cost"] = df["Status"].apply(lambda s: COST_PER_EMPTY_TRUCK if s=="Empty" else 0)
    df["Map_Size"] = df["Status"].apply(lambda s: 20 if s=="Empty" else 8)
    df["Empty_Distance"] = df.apply(lambda r: 100 if r["Status"]=="Empty" else 0, axis=1)
    df["Fuel_Loss"] = df["Empty_Distance"] * FUEL_COST_PER_KM
    df["CO2_Loss"] = df["Empty_Distance"] * CO2_PER_KM
# -----------------------------
# DASHBOARD
# -----------------------------
st.divider()
st.markdown("## 📊 Fleet Dashboard")
if not df.empty:
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    col1.metric("Total Trucks", len(df))
    col2.metric("Empty", len(df[df["Status"]=="Empty"]))
    col3.metric("Partial", len(df[df["Status"]=="Partially Loaded"]))
    col4.metric("Full", len(df[df["Status"]=="Full"]))
    col5.metric("💸 Empty Cost", f"${df['Empty_Cost'].sum()}")
    col6.metric("⛽ Fuel Loss from Empty Trucks", f"${df['Fuel_Loss'].sum():.2f}")
    col7.metric("💚 CO₂ Lost due to Empty Trucks", f"{df['CO2_Loss'].sum():.1f} kg")
    status_counts = df["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    fig_bar = px.bar(
        status_counts,
        x="Status",
        y="Count",
        color="Status",
        color_discrete_map={"Empty":"green","Partially Loaded":"orange","Full":"red"}
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_map = px.scatter_mapbox(
        df, lat="Latitude", lon="Longitude", color="Status",
        size="Map_Size", hover_name="Truck_ID",
        hover_data=["Ville","Poids_reel","Poids_declare","Capacity %"],
        color_discrete_map={"Empty":"#00FF00","Partially Loaded":"#FFA500","Full":"#FF0000"},
        zoom=4, height=550
    )
    fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

# -----------------------------
# ROUTE OPTIMIZER DISPLAY
# -----------------------------
st.subheader("🛣️ Route Optimizer for Empty Trucks")
if not df.empty and not demand_data.empty:
    for _, truck in df[df["Status"]=="Empty"].iterrows():
        route_plan, total_profit, distance_saved = optimize_route(truck, demand_data)
        fuel_saved = distance_saved * FUEL_COST_PER_KM
        co2_reduced = distance_saved * CO2_PER_KM
        with st.expander(f"Truck {truck['Truck_ID']} - Optimized Return Route"):
            if route_plan:
                st.markdown("**Suggested Stops:**")
                for stop in route_plan:
                    st.markdown(f"- {stop['Ville']}: Volume {stop['Volume']} kg, Profit ${stop['Profit']}")
                st.markdown(f"**Estimated Additional Profit:** ${total_profit}")
                st.markdown(f"**Estimated Empty Kilometers Saved:** {int(distance_saved)} km")
                st.markdown(f"💡 Fuel Saved: ${fuel_saved:.2f}")
                st.markdown(f"💚 CO₂ Reduced: {co2_reduced:.1f} kg")

                ai_route_text = get_route_ai_reasoning(truck["Truck_ID"], route_plan, fuel_saved, co2_reduced)
                st.markdown("💡 AI Insight for Route")
                st.markdown(ai_route_text.replace("\n","  \n"))
            else:
                st.info("No nearby shipments found.")