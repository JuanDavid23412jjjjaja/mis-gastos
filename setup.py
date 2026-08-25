import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN_PATH, CLIENT_SECRETS_PATH, CREDENTIALS_DIR


def setup():
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)

    if not os.path.exists(CLIENT_SECRETS_PATH):
        print("ERROR: No se encontro client_secret.json en credentials/")
        return False

    with open(CLIENT_SECRETS_PATH) as f:
        secrets = json.load(f)
    client_id = secrets.get("installed", {}).get("client_id", "")
    print(f"Client ID: {client_id[:20]}...")

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            token = json.load(f)
        if "refresh_token" in token:
            print("Token existente encontrado.")
            try:
                from sheets_db import get_or_create_spreadsheet, setup_spreadsheet
                sh = get_or_create_spreadsheet()
                setup_spreadsheet(sh)
                print(f"Spreadsheet: {sh.url}")
                print("Setup OK!")
                return True
            except Exception as e:
                print(f"Token invalido: {e}")
                print("Generando nuevo token...")

    print("\nNecesitas autenticar. Abre esta URL en tu navegador:")
    auth_uri = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={client_id}"
        f"&redirect_uri=http://localhost"
        f"&response_type=code"
        f"&scope=https://mail.google.com/+https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/gmail.readonly+https://www.googleapis.com/auth/gmail.modify"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    print(auth_uri)
    print("\nPega el codigo de autorizacion:")
    code = input("> ").strip()

    import requests
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": secrets["installed"]["client_secret"],
        "redirect_uri": "http://localhost",
        "grant_type": "authorization_code",
    })
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}")
        return False

    token_data = resp.json()
    from datetime import datetime, timedelta
    new_token = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_in": token_data.get("expires_in", 3600),
        "scope": token_data.get("scope", ""),
        "token_type": "Bearer",
        "expiry": (datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat(),
        "client_id": client_id,
        "client_secret": secrets["installed"]["client_secret"],
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(new_token, f, indent=2)
    print("Token guardado!")

    from sheets_db import get_or_create_spreadsheet, setup_spreadsheet
    sh = get_or_create_spreadsheet()
    setup_spreadsheet(sh)
    print(f"Spreadsheet: {sh.url}")
    print("Setup OK!")
    return True


if __name__ == "__main__":
    setup()
