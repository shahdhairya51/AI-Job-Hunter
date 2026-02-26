import json
import os
import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials

# Define scopes required for Google Sheets (read/write)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class SheetsTracker:
    def __init__(self, sheet_name="Job AI Tracker"):
        self.sheet_name = sheet_name
        self.client = self._authenticate()
        self.sheet = self._get_or_create_sheet()

    def _authenticate(self):
        # Prefer Service Account Authentication for truly headless automated execution
        if os.path.exists('service_account.json'):
            print("Authenticating with Service Account...")
            creds = Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
            return gspread.authorize(creds)
            
        # Fallback to User OAuth Flow if Service Account JSON is missing
        print("Authenticating with OAuth User Flow...")
        creds = None
        if os.path.exists('token.json'):
            creds = OAuthCredentials.from_authorized_user_file('token.json', SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise Exception("Missing 'service_account.json' OR 'credentials.json' for Google Sheets!")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
                
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                
        return gspread.authorize(creds)

    def _get_or_create_sheet(self):
        try:
            spreadsheet = self.client.open(self.sheet_name)
            worksheet = spreadsheet.sheet1
            return worksheet
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"Spreadsheet '{self.sheet_name}' not found. Creating anew...")
            spreadsheet = self.client.create(self.sheet_name)
            worksheet = spreadsheet.sheet1
            # Add Headers
            headers = [
                "Date Added", "Company", "Title", "Location", "Source", "URL",
                "Description", "ATS Score", "Resume Version", "Status", 
                "Date Applied", "Screenshot", "Notes", "Last Updated"
            ]
            worksheet.insert_row(headers, 1)
            # Share sheet if using service account
            if os.path.exists('service_account.json'):
                print("If you are using a Service Account, remember to manually share the new sheet with your main Google Account.")
            return worksheet

    def track_jobs(self, jobs_file="jobs_found.json"):
        if not os.path.exists(jobs_file):
            print("No jobs found file to process.")
            return
            
        with open(jobs_file, "r") as f:
            jobs = json.load(f)

        if not jobs:
            print("No jobs to process in file.")
            return

        print(f"Checking {len(jobs)} jobs against Google Sheets Tracker.")
        
        existing_records = self.sheet.get_all_records(expected_headers=[])
        existing_urls = {record.get("URL", "") for record in existing_records}
        existing_signatures = {f"{record.get('Company', '').lower()}::{record.get('Title', '').lower()}" for record in existing_records}

        new_rows = []
        added_count = 0
        
        for job in jobs:
            signature = f"{job['company'].lower()}::{job['title'].lower()}"
            if job['url'] in existing_urls or signature in existing_signatures:
                continue
                
            row = [
                job.get('date', ''),
                job.get('company', ''),
                job.get('title', ''),
                job.get('location', ''),
                job.get('source', ''),
                job.get('url', ''),
                job.get('description', '')[:300], # First 300 chars
                job.get('ats_score', ''),
                job.get('resume_version', ''),
                job.get('status', 'NEW'),
                job.get('date_applied', ''),
                job.get('screenshot', ''),
                job.get('notes', ''),
                job.get('last_updated', '')
            ]
            new_rows.append(row)
            existing_urls.add(job['url'])
            existing_signatures.add(signature)
            added_count += 1
            
        if new_rows:
            # Append all new rows at once
            self.sheet.append_rows(new_rows)
            print(f"Successfully added {added_count} NEW jobs to tracking sheet.")
        else:
            print("No NEW jobs to add. All duplicates.")

if __name__ == "__main__":
    tracker = SheetsTracker()
    tracker.track_jobs()
