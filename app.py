import streamlit as st
import pyzipper
import os, shutil, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="EOD Portal", layout="centered")
st.title("🏦 Professional EOD Data Uploader")

# --- DROPDOWN SECTION ---
col1, col2, col3 = st.columns(3)
with col1:
    days_range = st.selectbox("Range Select Karein", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2:
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    current_month = datetime.now().month - 1
    selected_month = st.selectbox("Month", months, index=current_month)
with col3:
    current_year = datetime.now().year
    selected_year = st.selectbox("Year", [current_year, current_year-1], index=0)

final_date = f"{days_range} {selected_month} {selected_year}"

# --- UPLOAD & PASSWORD ---
zip_password = st.text_input("Enter ZIP Password", type="password")
uploaded_file = st.file_uploader("Upload ZIP File", type="zip")

if st.button("🚀 FINAL SUBMIT"):
    if not uploaded_file or not zip_password:
        st.error("❌ File aur Password dono zaroori hain!")
    else:
        try:
            extract_dir = "temp_extract"
            if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
            os.makedirs(extract_dir)

            # --- PASSWORD CHECK POPUP LOGIC ---
            with pyzipper.AESZipFile(uploaded_file) as zf:
                try:
                    zf.extractall(extract_dir, pwd=zip_password.encode())
                except:
                    st.error("🚨 GALAT PASSWORD! Kripya sahi password dalein aur dobara koshish karein.")
                    st.stop() 

            # --- GOOGLE SHEET CONNECT ---
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")

            # --- DATA PROCESSING (Colab Logic) ---
            station_id, total_sum = None, 0
            for file in os.listdir(extract_dir):
                if file.endswith(".html"):
                    path = os.path.join(extract_dir, file)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        soup = BeautifulSoup(f, "html.parser")
                        for row in soup.find_all("tr"):
                            cols = row.find_all("td")
                            if len(cols) >= 2 and "Station ID" in cols[0].get_text():
                                station_id = cols[1].get_text(strip=True)
                        tables = pd.read_html(path)
                        for df in tables:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            col = next((c for c in df.columns if "total amount charged" in c), None)
                            if col:
                                cleaned = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                                total_sum += pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()

            # --- FINAL UPLOAD ---
            if station_id:
                try:
                    worksheet = spreadsheet.worksheet(str(station_id))
                except:
                    worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                    worksheet.append_row(["Date Range", "Station ID", "Total Amount"])
                
                worksheet.append_row([final_date, station_id, int(total_sum)])
                st.success(f"✅ Data for Station {station_id} uploaded successfully!")
                st.balloons()
            
            shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
