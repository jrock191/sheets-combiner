# Google Sheets Combiner

A Streamlit web application that combines data from multiple Google Sheets into a single CSV file.

## Features

- Configure multiple Google Sheets to combine
- View statistics about the combined data
- Download the combined data as CSV
- Simple and intuitive interface

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Place your Google Sheets API credentials file (`sheets-combiner-app.json`) in the same directory as `app.py`

## Running the App

1. Navigate to the project directory
2. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```
3. The app will open in your default web browser

## Deployment

This app can be deployed on Streamlit Cloud:

1. Create a Streamlit Cloud account at https://streamlit.io/cloud
2. Connect your GitHub repository
3. Configure the deployment with your Google Sheets API credentials
4. Deploy the app

## Usage

1. Add Google Sheets by entering their IDs and sheet names in the sidebar
2. Click "Combine Data" to fetch and combine the data
3. View statistics and download the combined data as CSV

## Security

- Keep your Google Sheets API credentials file secure
- Only share the deployed app URL with authorized users
- The app only requires read-only access to your Google Sheets