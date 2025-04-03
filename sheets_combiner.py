import os
import json
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration variables
GOOGLE_SHEETS_CREDENTIALS_FILE = '/Users/johnrock/sheets_combiner_webapp/sheets-combiner-app.json'  # Path to your Google API credentials
OUTPUT_CSV_BASE_NAME = 'combined_requests'  # Base name for the output CSV file
TRACKING_DATA_FILE = 'sheets_tracking_app.json'  # File to store tracking information about previously downloaded data
SPREADSHEETS_CONFIG_FILE = 'spreadsheets_config.json'  # File to store spreadsheet configurations
TRACK_CHANGES = True  # Set to False if you want to download all data every time
FORCE_REFRESH = False  # Set to True to force download of all data regardless of changes

# Get the output directory (same as in app.py)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def load_spreadsheet_config():
    """Load spreadsheet configurations from file"""
    if os.path.exists(SPREADSHEETS_CONFIG_FILE):
        try:
            with open(SPREADSHEETS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading spreadsheet config: {e}")
    return {
        'spreadsheets': [
            ['1MROsPUTNhcOILDI8g-VzAkqH3DpLNHff2BXZG2VW-1Y', 'ALL Requests'],
            ['1EMZKHy7vho_4vKOGWn4ec1AH0KRMzjJ3ySZW09QXbOQ', 'Requests - read.petfools'],
            ['1n-yo9uwO4LvwZ14crK1oLsDxUExVy8LIqIbtzXLLOiI', 'New - EE (Mobile)'],
            ['1GCsztmX9Yg6AGnBDlL4cJmdoDpyrCWfkLSpSKNZ3EkE', 'Content Request Sheet - KaC'],
            ['1euPtdvzK22MASRrSxp-lL5Vp4wPR1JkcmpmWui0VmyU', 'Content Request Sheet - ITS Limited'],
            ['1weaua3feEE0bGIOLZCb9nayhkckm83cKBMsbzYGhTHY', 'Content Request Sheet - read.FollowSports'],
            ['1bdtvuklG0cr2Dy9NLrYOBCzNBN_WARCF-XvlPDIknjM', 'Content Request Sheet - Westside']
        ]
    }

def save_spreadsheet_config(config):
    """Save spreadsheet configurations to file"""
    try:
        with open(SPREADSHEETS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Saved spreadsheet config to {SPREADSHEETS_CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving spreadsheet config: {e}")

def get_output_csv_path():
    """Generate output CSV path with timestamp to ensure uniqueness"""
    current_datetime = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    return os.path.join(OUTPUT_DIR, f"{OUTPUT_CSV_BASE_NAME}_{current_datetime}.csv")

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
        print(f"Failed to setup Google Sheets API: {e}")
        return None

def load_tracking_data():
    """Load tracking data from previous runs"""
    if os.path.exists(TRACKING_DATA_FILE):
        try:
            with open(TRACKING_DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tracking data: {e}")
    return {
        'last_run': None,
        'sheets_data': {}
    }

def save_tracking_data(tracking_data):
    """Save tracking data for future runs"""
    try:
        with open(TRACKING_DATA_FILE, 'w') as f:
            json.dump(tracking_data, f, indent=2)
        print(f"Saved tracking data to {TRACKING_DATA_FILE}")
    except Exception as e:
        print(f"Error saving tracking data: {e}")

def calculate_row_hash(row):
    """Create a hash of a row's contents to detect changes"""
    # Create a unique identifier for the row based on its content
    # We'll use a combination of relevant columns to create a unique hash
    row_str = str(row.values)
    return hash(row_str)

def calculate_content_hash(data_frame):
    """Calculate a hash for the entire DataFrame to detect any changes"""
    if data_frame is None or len(data_frame) == 0:
        return hash("empty")
    
    # Create a more detailed string representation of the DataFrame
    # Include both values and column names
    content_str = f"{data_frame.columns.tolist()}{data_frame.values.tolist()}"
    return hash(content_str)

def get_sheet_metadata(service, spreadsheet_id, sheet_name):
    """Get metadata about the sheet to detect changes"""
    try:
        # Get the sheet properties
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        
        # Find the specific sheet
        for sheet in spreadsheet.get('sheets', []):
            if sheet.get('properties', {}).get('title') == sheet_name:
                grid_props = sheet.get('properties', {}).get('gridProperties', {})
                return {
                    'row_count': grid_props.get('rowCount', 0),
                    'column_count': grid_props.get('columnCount', 0),
                    'modified_time': spreadsheet.get('properties', {}).get('modifiedTime', '')
                }
        
        return None
    except Exception as e:
        print(f"Error getting sheet metadata: {e}")
        return None

def download_sheet_data(service, spreadsheet_id, sheet_name, tracking_data):
    """Download data from a specific Google Sheet tab and identify new/changed rows"""
    try:
        print(f"\nProcessing sheet: {sheet_name}")
        
        # Get sheet metadata to check for changes
        metadata = get_sheet_metadata(service, spreadsheet_id, sheet_name)
        if metadata is None:
            print(f"Could not get metadata for spreadsheet {spreadsheet_id}, sheet {sheet_name}")
            return None
        
        # Create a unique key for this sheet
        sheet_key = f"{spreadsheet_id}_{sheet_name}"
        
        # Check if we have previous data for this sheet
        previous_metadata = tracking_data['sheets_data'].get(sheet_key, {}).get('metadata', {})
        previous_content_hash = tracking_data['sheets_data'].get(sheet_key, {}).get('content_hash', 0)
        previous_row_hashes = tracking_data['sheets_data'].get(sheet_key, {}).get('row_hashes', [])
        
        print(f"Previous metadata: {previous_metadata}")
        print(f"Current metadata: {metadata}")
        
        # Check for metadata changes that would indicate new or modified data
        row_count_changed = metadata['row_count'] != previous_metadata.get('row_count', 0)
        modified_time_changed = metadata['modified_time'] != previous_metadata.get('modified_time', '')
        
        print(f"Row count changed: {row_count_changed}")
        print(f"Modified time changed: {modified_time_changed}")
        
        # If we're tracking changes and nothing has changed, we might be able to skip
        # But we'll still download to check content hash
        if TRACK_CHANGES and not row_count_changed and not modified_time_changed:
            print(f"No metadata changes detected in {sheet_name} - checking content anyway")
        
        # Get the data from Google Sheets
        print(f"Downloading data from {sheet_name}...")
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            print(f'No data found in spreadsheet {spreadsheet_id}, sheet {sheet_name}.')
            return None
        
        print(f"Downloaded {len(values)} rows from {sheet_name}")
        
        # Get headers (first row)
        headers = values[0]
        print(f"Headers: {headers}")
        
        # Handle potential mismatch in column counts
        data_rows = []
        for row in values[1:]:
            # If row has fewer columns than headers, extend it with None values
            if len(row) < len(headers):
                row = row + [None] * (len(headers) - len(row))
            # If row has more columns than headers, truncate it
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
        initial_row_count = len(df)
        print(f"Initial row count: {initial_row_count}")
        
        # Check if we have both columns A and B
        if len(headers) > 1:
            column_a_name = headers[0]  # First column
            column_b_name = headers[1]  # Second column
            
            print(f"Filtering for column A = 'New Request' and column B not empty")
            print(f"Column A name: {column_a_name}")
            print(f"Column B name: {column_b_name}")
            
            # Filter for "New Request" in column A and non-empty column B
            filtered_df = df[(df[column_a_name] == "New Request") & 
                        (df[column_b_name].notna()) & 
                        (df[column_b_name] != "")]
                    
            filtered_row_count = len(filtered_df)
            
            print(f"Filtered from {initial_row_count} to {filtered_row_count} rows")
            
            # If no rows match our criteria, return None
            if filtered_row_count == 0:
                print(f"No rows match the filter criteria in {sheet_name}")
                return None
            
            # Use the filtered DataFrame from now on
            df = filtered_df
        else:
            print(f"Warning: Spreadsheet {spreadsheet_id}, sheet {sheet_name} doesn't have enough columns. Skipping.")
            return None
        
        # Calculate hashes for each row and filter out previously downloaded rows
        current_row_hashes = []
        new_rows = []
        
        for _, row in df.iterrows():
            row_hash = calculate_row_hash(row)
            current_row_hashes.append(row_hash)
            if row_hash not in previous_row_hashes:
                new_rows.append(row)
        
        # Convert new rows back to DataFrame
        if new_rows:
            df = pd.DataFrame(new_rows)
            print(f"Found {len(new_rows)} new rows out of {len(df)} total rows")
        else:
            print(f"No new rows found in {sheet_name}")
            return None
        
        # Calculate hash of the current filtered content
        current_content_hash = calculate_content_hash(df)
        sheet_key = f"{spreadsheet_id}_{sheet_name}"
        
        print(f"Current content hash: {current_content_hash}")
        print(f"Previous content hash: {previous_content_hash}")
        
        # Compare with previous content hash
        if current_content_hash == previous_content_hash:
            print(f"Content is identical to previous run for {sheet_name} after filtering - skipping")
            
            # Still update the metadata
            tracking_data['sheets_data'][sheet_key]['metadata'] = metadata
            tracking_data['sheets_data'][sheet_key]['last_checked'] = datetime.now().isoformat()
            
            return None
        
        print(f"Content has changed in {sheet_name} (hash: {current_content_hash} vs previous: {previous_content_hash})")
        
        # Update tracking data for this sheet
        tracking_data['sheets_data'][sheet_key] = {
            'metadata': metadata,
            'content_hash': current_content_hash,
            'row_hashes': current_row_hashes,  # Store all row hashes, including previously downloaded ones
            'last_processed': datetime.now().isoformat()
        }
        
        print(f"Downloaded {len(df)} new or changed rows from spreadsheet {spreadsheet_id}, sheet {sheet_name}")
        return df
    
    except HttpError as error:
        print(f"Google Sheets API error: {error}")
        return None
    except Exception as e:
        print(f"Error downloading sheet: {e}")
        import traceback
        traceback.print_exc()
        return None

def combine_and_save_data():
    """Download data from multiple spreadsheets and combine into one CSV"""
    print(f"Starting data download at {datetime.now()}")
    
    # Generate output CSV path with current date
    output_csv_path = get_output_csv_path()
    
    # Load tracking data from previous runs
    tracking_data = load_tracking_data()
    tracking_data['last_run'] = datetime.now().isoformat()
    
    # Load spreadsheet configurations
    config = load_spreadsheet_config()
    spreadsheets_to_download = config['spreadsheets']
    
    # Setup Google Sheets API
    service = setup_google_sheets_api()
    if not service:
        return False
    
    # List to store all dataframes
    all_dfs = []
    
    # Download data from each spreadsheet
    for spreadsheet_info in spreadsheets_to_download:
        spreadsheet_id, sheet_name = spreadsheet_info
        
        df = download_sheet_data(service, spreadsheet_id, sheet_name, tracking_data)
        if df is not None and not df.empty:
            all_dfs.append(df)
    
    # If no data was downloaded, exit
    if not all_dfs:
        print("No new data was downloaded from any spreadsheet.")
        
        # Still save the tracking data with updated metadata
        save_tracking_data(tracking_data)
        return False
    
    # Combine all dataframes
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Save to CSV
    combined_df.to_csv(output_csv_path, index=False)
    print(f"Successfully combined {len(combined_df)} rows from {len(all_dfs)} sheets into {output_csv_path}")
    
    # Save tracking data for future runs
    save_tracking_data(tracking_data)
    
    return True

def main():
    """Main function to combine data from Google Sheets"""
    print("Starting Google Sheets to CSV combiner")
    
    # Load spreadsheet configurations
    config = load_spreadsheet_config()
    spreadsheets_to_download = config['spreadsheets']
    
    # Check if we have any spreadsheets configured
    if not spreadsheets_to_download:
        print("Error: No spreadsheets configured. Please add spreadsheet information to the configuration file.")
        return
    
    # Combine data from all configured spreadsheets
    combine_and_save_data()
    
    print(f"Process completed at {datetime.now()}")

if __name__ == "__main__":
    main()