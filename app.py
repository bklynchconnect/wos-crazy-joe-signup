import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

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

def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(sheet, df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- APP ---
st.title("🔥 Alliance Troop Coordination")

sheet = connect_to_sheet()
df = load_data(sheet)

# Ensure structure
if df.empty:
    df = pd.DataFrame(columns=["Player", "Targets"])

# --- USER INPUT ---
player_name = st.text_input("Enter your player name")

if player_name:
    if player_name not in df["Player"].values:
        if st.button("Join Event"):
            df = pd.concat([df, pd.DataFrame([{
                "Player": player_name,
                "Targets": ""
            }])], ignore_index=True)
            save_data(sheet, df)
            st.success("Joined event!")
            st.rerun()

# Refresh df
df = load_data(sheet)

# --- SELECT TARGETS ---
if player_name in df["Player"].values:
    other_players = [p for p in df["Player"] if p != player_name]

    current_targets = df.loc[
        df["Player"] == player_name, "Targets"
    ].values[0]

    current_targets = current_targets.split(",") if current_targets else []

    selected = st.multiselect(
        f"Select up to {MAX_TARGETS} players to send troops to",
        other_players,
        default=current_targets
    )

    # --- VALIDATION ---
    if len(selected) > MAX_TARGETS:
        st.error(f"You can only select up to {MAX_TARGETS} players.")
    else:
        st.caption(f"{len(selected)} / {MAX_TARGETS} targets selected")

        if st.button("Save Targets"):
            df.loc[df["Player"] == player_name, "Targets"] = ",".join(selected)
            save_data(sheet, df)
            st.success("Saved!")
            st.rerun()

# --- DISPLAY TABLE ---
st.subheader("📋 Current Assignments")
st.dataframe(df)