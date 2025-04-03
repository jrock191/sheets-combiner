import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE = 'sheets-combiner-app.json'
OUTPUT_CSV_BASE_NAME = 'combined_requests'
TRACKING_DATA_FILE = 'sheets_tracking_app.json'
SPREADSHEETS_CONFIG_FILE = 'spreadsheets_config.json'
TRACK_CHANGES = True

# Initialize session state
if 'spreadsheets' not in st.session_state:
    st.session_state.spreadsheets = []

def load_spreadsheet_config():
    """Load spreadsheet configurations from file"""
    if os.path.exists(SPREADSHEETS_CONFIG_FILE):
        try:
            with open(SPREADSHEETS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading spreadsheet config: {e}")
    return {'spreadsheets': []}

def save_spreadsheet_config(config):
    """Save spreadsheet configurations to file"""
    try:
        with open(SPREADSHEETS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        st.error(f"Error saving spreadsheet config: {e}")

def setup_google_sheets_api():
    """Setup the Google Sheets API client"""
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_FILE, 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        st.error(f"Failed to setup Google Sheets API: {e}")
        return None

def download_sheet_data(service, spreadsheet_id, sheet_name):
    """Download data from a specific Google Sheet tab"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            st.warning(f'No data found in spreadsheet {spreadsheet_id}, sheet {sheet_name}.')
            return None
        
        # Get headers (first row)
        headers = values[0]
        
        # Handle potential mismatch in column counts
        data_rows = []
        for row in values[1:]:
            if len(row) < len(headers):
                row = row + [None] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            data_rows.append(row)
        
        # Convert to DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # Add source information columns
        df['source_spreadsheet'] = spreadsheet_id
        df['source_sheet'] = sheet_name
        
        # Filter to include only rows where:
        # 1. Column A (index 0) reads "New Request"
        # 2. Column B (index 1) is not empty
        if len(headers) > 1:
            column_a_name = headers[0]
            column_b_name = headers[1]
            
            df = df[(df[column_a_name] == "New Request") & 
                   (df[column_b_name].notna()) & 
                   (df[column_b_name] != "")]
        
        return df
    except Exception as e:
        st.error(f"Error downloading sheet: {e}")
        return None

def combine_data():
    """Combine data from all configured spreadsheets"""
    service = setup_google_sheets_api()
    if not service:
        return None
    
    all_dfs = []
    config = load_spreadsheet_config()
    
    for spreadsheet_id, sheet_name in config['spreadsheets']:
        with st.spinner(f"Downloading data from {sheet_name}..."):
            df = download_sheet_data(service, spreadsheet_id, sheet_name)
            if df is not None and not df.empty:
                all_dfs.append(df)
    
    if not all_dfs:
        st.warning("No data was downloaded from any spreadsheet.")
        return None
    
    return pd.concat(all_dfs, ignore_index=True)

# Streamlit UI
st.set_page_config(page_title="Google Sheets Combiner", layout="wide")

st.title("Google Sheets Combiner")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # Add new spreadsheet
    st.subheader("Add New Spreadsheet")
    new_id = st.text_input("Spreadsheet ID")
    new_sheet = st.text_input("Sheet Name")
    if st.button("Add Spreadsheet"):
        if new_id and new_sheet:
            config = load_spreadsheet_config()
            config['spreadsheets'].append([new_id, new_sheet])
            save_spreadsheet_config(config)
            st.success("Spreadsheet added successfully!")
            st.experimental_rerun()
    
    # List current spreadsheets
    st.subheader("Current Spreadsheets")
    config = load_spreadsheet_config()
    for i, (spreadsheet_id, sheet_name) in enumerate(config['spreadsheets']):
        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            st.text_input("ID", value=spreadsheet_id, key=f"id_{i}", disabled=True)
        with col2:
            st.text_input("Sheet", value=sheet_name, key=f"sheet_{i}", disabled=True)
        with col3:
            if st.button("Remove", key=f"remove_{i}"):
                config['spreadsheets'].pop(i)
                save_spreadsheet_config(config)
                st.experimental_rerun()

# Main content
if st.button("Combine Data"):
    with st.spinner("Combining data from all spreadsheets..."):
        combined_df = combine_data()
        
        if combined_df is not None:
            st.success(f"Successfully combined {len(combined_df)} rows!")
            
            # Show statistics
            st.subheader("Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.write("Total Rows:", len(combined_df))
                st.write("Columns:", ", ".join(combined_df.columns))
            with col2:
                st.write("Data by Source:")
                st.write(combined_df['source_sheet'].value_counts())
            
            # Download button
            csv = combined_df.to_csv(index=False)
            st.download_button(
                label="Download Combined CSV",
                data=csv,
                file_name=f"{OUTPUT_CSV_BASE_NAME}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
                mime='text/csv',
            )
            
            # Show data preview
            st.subheader("Data Preview")
            st.dataframe(combined_df.head()) 