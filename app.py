import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
import numpy as np

# --- AUTO REFRESH EVERY 2 MINUTES ---
st_autorefresh(interval=120000, key="datarefresh")

# --- CONFIG ---
SHEET_NAME = "wos_crazyjoe_signup"
WORKSHEET_NAME = "responses"
MAX_TARGETS = 6

# --- GOOGLE SHEETS CONNECTION ---
def connect_to_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    return sheet

# --- LOAD DATA ---
def load_data(sheet):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # Ensure required columns exist
    required_cols = ["Player", "X", "Y", "Reinforcing"]
    if df.empty:
        df = pd.DataFrame(columns=required_cols)
    else:
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        df = df[required_cols]

    return df

# --- SAVE SINGLE PLAYER (SAFE, NO CLEAR) ---
def save_player(sheet, player_name, x, y, targets):
    records = sheet.get_all_records()
    found = False
    for i, row in enumerate(records):
        if row["Player"] == player_name:
            sheet.update(f"A{i+2}:D{i+2}", [[player_name, x, y, targets]])
            found = True
            break
    if not found:
        sheet.append_row([player_name, x, y, targets])

# --- APP ---
st.title("🔥 Alliance Troop Coordination")
st.markdown(
    """
    1. Enter your player name and city coordinates and click 'Join Event'.
    2. Select players from the list to reinforce and click 'Save Targets'.
    """
)

sheet = connect_to_sheet()
df = load_data(sheet)

# --- USER INPUT ---
st.subheader("Join Event")
player_name = st.text_input("Enter your player name")

col1, col2 = st.columns(2)
x_coord = col1.number_input("X Coordinate", value=0)
y_coord = col2.number_input("Y Coordinate", value=0)

if player_name and player_name not in df["Player"].values:
    if st.button("Join Event"):
        df = pd.concat([df, pd.DataFrame([{
            "Player": player_name,
            "X": x_coord,
            "Y": y_coord,
            "Reinforcing": ""
        }])], ignore_index=True)
        # Save with empty targets on join
        save_player(sheet, player_name, x_coord, y_coord, "")
        st.success("Joined event!")
        st.rerun()

# Refresh df
df = load_data(sheet)

# --- DISTANCE CALCULATION ---
if player_name in df["Player"].values:
    df["X"] = pd.to_numeric(df["X"], errors="coerce")
    df["Y"] = pd.to_numeric(df["Y"], errors="coerce")

    player_row = df[df["Player"] == player_name].iloc[0]
    px, py = player_row["X"], player_row["Y"]

    def compute_distance(row):
        if row["Player"] == player_name:
            return 0
        return np.sqrt((row["X"] - px)**2 + (row["Y"] - py)**2)

    df["Distance"] = df.apply(compute_distance, axis=1).round(2)
    df = df.sort_values(by="Distance")
else:
    df["Distance"] = None

# --- SELECT TARGETS ---
if player_name in df["Player"].values:
    st.subheader("Select Reinforcement Targets")
    other_players = [p for p in df["Player"] if p != player_name]

    current_targets = df.loc[
        df["Player"] == player_name, "Reinforcing"
    ].values[0]

    current_targets = current_targets.split(",") if current_targets else []

    selected = st.multiselect(
        f"Select up to {MAX_TARGETS} players to send troops to",
        other_players,
        default=current_targets
    )

    # Validation
    if len(selected) > MAX_TARGETS:
        st.error(f"You can only select up to {MAX_TARGETS} players.")
    else:
        st.caption(f"{len(selected)} / {MAX_TARGETS} targets selected")
        if st.button("Save Targets"):
            df.loc[df["Player"] == player_name, "Reinforcing"] = ",".join(selected)
            save_player(sheet, player_name, x_coord, y_coord, ",".join(selected))
            st.success("Saved!")
            st.rerun()

# --- COMPUTE INCOMING REINFORCEMENTS ---
incoming_counts = {player: 0 for player in df["Player"]}

for _, row in df.iterrows():
    if row["Reinforcing"]:
        targets = [t.strip() for t in row["Reinforcing"].split(",") if t.strip()]
        for t in targets:
            if t in incoming_counts:
                incoming_counts[t] += 1

df["Incoming"] = df["Player"].map(incoming_counts)

# --- DISPLAY TABLE ---
st.subheader("📋 Current Assignments")
st.text("Players highlighted in red have no incoming reinforcements.")

def highlight_unassigned(row):
    if row["Incoming"] == 0:
        return ["background-color: #ff4d4d"] * len(row)
    return [""] * len(row)

styled_df = df.style.apply(highlight_unassigned, axis=1)

st.dataframe(styled_df, use_container_width=True)