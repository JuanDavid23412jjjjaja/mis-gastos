import base64
import json
import re
import requests
from datetime import datetime, timedelta
from config import get_credentials, save_token, CLIENT_SECRETS_PATH, TOKEN_PATH


def strip_html(html):
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_access_token():
    import os
    creds = get_credentials()
    if not creds:
        return None
    if "access_token" in creds and "expiry" in creds:
        if datetime.fromisoformat(creds["expiry"]) > datetime.now():
            return creds["access_token"]
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    if (not client_id or not client_secret) and os.path.exists(CLIENT_SECRETS_PATH):
        with open(CLIENT_SECRETS_PATH) as f:
            secrets = json.load(f)
        installed = secrets.get("installed", {})
        client_id = client_id or installed.get("client_id")
        client_secret = client_secret or installed.get("client_secret")
    data = {
        "client_id": client_id,
        "client_secret": client_secret or "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",
        "refresh_token": creds.get("refresh_token"),
        "grant_type": "refresh_token",
    }
    resp = requests.post("https://oauth2.googleapis.com/token", data=data)
    if resp.status_code == 200:
        token_data = resp.json()
        new_token = {
            "access_token": token_data["access_token"],
            "refresh_token": creds.get("refresh_token"),
            "expires_in": token_data.get("expires_in", 3600),
            "scope": token_data.get("scope", ""),
            "token_type": "Bearer",
            "expiry": (datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat(),
        }
        save_token(new_token)
        return token_data["access_token"]
    return None

def search_emails(query, max_results=100):
    token = get_access_token()
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}&maxResults={max_results}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get("messages", [])

def get_email_body(msg_id):
    token = get_access_token()
    if not token:
        return ""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return ""
    msg = resp.json()
    payload = msg.get("payload", {})
    body = extract_body(payload)
    if "<html" in body.lower() or "<body" in body.lower():
        body = strip_html(body)
    return body

def extract_body(payload):
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        sub_parts = part.get("parts", [])
        for sub in sub_parts:
            if sub.get("mimeType") == "text/plain" and sub.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(sub["body"]["data"]).decode("utf-8", errors="replace")
            if sub.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(sub["body"]["data"]).decode("utf-8", errors="replace")
    return ""

def get_email_subject(msg_id):
    token = get_access_token()
    if not token:
        return ""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return ""
    msg = resp.json()
    headers_list = msg.get("payload", {}).get("headers", [])
    for h in headers_list:
        if h["name"] == "Subject":
            return h["value"]
    return ""

def get_bank_emails(days_back=90):
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    queries = [
        f"subject:(DAVIVIENDA) after:{cutoff}",
        f"subject:(RappiCard) after:{cutoff}",
        f"from:notificaciones@davivienda.com after:{cutoff}",
        f"from:davivienda after:{cutoff}",
        f"subject:(notificacion davivienda) after:{cutoff}",
    ]
    all_msgs = []
    seen_ids = set()
    for q in queries:
        msgs = search_emails(q, max_results=200)
        for m in msgs:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                all_msgs.append(m)
    return all_msgs

def send_email(to, subject, body_html):
    token = get_access_token()
    if not token:
        return False
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    raw = base64.urlsafe_b64encode(
        f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n{body_html}".encode()
    ).decode()
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    resp = requests.post(url, headers=headers, json={"raw": raw})
    return resp.status_code == 200
