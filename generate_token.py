"""
Generate OAuth2 token.json from GOOGLE_CREDENTIALS env var.

Usage:
    python generate_token.py

Requires: pip install google-auth-oauthlib python-dotenv

This will:
1. Read GOOGLE_CREDENTIALS from .env
2. Open a browser for Google login
3. Print the token JSON to paste into .env as GOOGLE_TOKEN_JSON
"""

import json
import os
import tempfile

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        print("ERROR: GOOGLE_CREDENTIALS not found in .env")
        return

    # write credentials to temp file (InstalledAppFlow needs a file)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(creds_json)
        tmp_path = f.name

    try:
        flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
        creds = flow.run_local_server(port=0)

        token_json = creds.to_json()
        print("\n=== Add this to your .env ===\n")
        print(f"GOOGLE_TOKEN_JSON={token_json}")
        print("\n=== Done ===")
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()