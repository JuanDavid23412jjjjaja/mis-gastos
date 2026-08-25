import gspread
import hashlib
from datetime import datetime
from config import (
    SPREADSHEET_NAME, TAB_TRANSACTIONS, TAB_CATEGORIES,
    TAB_INCOME, TAB_RULES, TAB_RETURNS, TRANSACTION_COLUMNS, CATEGORY_COLUMNS,
    INCOME_COLUMNS, RULE_COLUMNS, RETURN_COLUMNS, DEFAULT_CATEGORIES
)


def get_client():
    from google.oauth2.credentials import Credentials
    from config import get_credentials, CLIENT_SECRETS_PATH
    import json
    import requests as req

    creds_data = get_credentials()
    if not creds_data:
        raise Exception("No hay credenciales. Ejecuta setup.py primero.")

    refresh_token = creds_data.get("refresh_token")
    access_token = creds_data.get("access_token")

    if not access_token:
        with open(CLIENT_SECRETS_PATH) as f:
            secrets = json.load(f)
        installed = secrets.get("installed", {})
        data = {
            "client_id": installed.get("client_id"),
            "client_secret": installed.get("client_secret"),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        resp = req.post("https://oauth2.googleapis.com/token", data=data)
        if resp.status_code == 200:
            access_token = resp.json()["access_token"]
        else:
            raise Exception("No se pudo refrescar el token.")

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data.get("client_id", "812463761660-dmr9nk7e5adtrmabhq44bfk3bnu0g36v.apps.googleusercontent.com"),
        client_secret=creds_data.get("client_secret", "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"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


def get_or_create_spreadsheet():
    client = get_client()
    try:
        sh = client.open(SPREADSHEET_NAME)
        return sh
    except gspread.SpreadsheetNotFound:
        sh = client.create(SPREADSHEET_NAME)
        setup_spreadsheet(sh)
        return sh


def setup_spreadsheet(sh=None):
    if sh is None:
        sh = get_or_create_spreadsheet()

    existing = [s.title for s in sh.worksheets()]

    if TAB_TRANSACTIONS not in existing:
        ws = sh.add_worksheet(title=TAB_TRANSACTIONS, rows=1000, cols=len(TRANSACTION_COLUMNS))
        ws.update(range_name="A1", values=[TRANSACTION_COLUMNS])
        ws.format("A1:M1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}})

    if TAB_CATEGORIES not in existing:
        ws = sh.add_worksheet(title=TAB_CATEGORIES, rows=50, cols=len(CATEGORY_COLUMNS))
        ws.update(range_name="A1", values=[CATEGORY_COLUMNS])
        rows = []
        for cat, data in DEFAULT_CATEGORIES.items():
            rows.append([cat, ",".join(data.get("keywords", [])), data.get("color", "#999"), data.get("budget", 0)])
        ws.update(range_name="A2", values=rows)
        ws.format("A1:D1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}})

    if TAB_INCOME not in existing:
        ws = sh.add_worksheet(title=TAB_INCOME, rows=500, cols=len(INCOME_COLUMNS))
        ws.update(range_name="A1", values=[INCOME_COLUMNS])
        ws.format("A1:E1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}})

    if TAB_RULES not in existing:
        ws = sh.add_worksheet(title=TAB_RULES, rows=200, cols=len(RULE_COLUMNS))
        ws.update(range_name="A1", values=[RULE_COLUMNS])
        ws.format("A1:C1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}})

    if TAB_RETURNS not in existing:
        ws = sh.add_worksheet(title=TAB_RETURNS, rows=500, cols=len(RETURN_COLUMNS))
        ws.update(range_name="A1", values=[RETURN_COLUMNS])
        ws.format("A1:J1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}})

    return sh


def make_txn_id(fecha, hora, tarjeta, comercio):
    raw = f"{fecha}-{hora}-{tarjeta}-{comercio}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def txn_to_row(txn):
    fecha = txn.get("fecha", "")
    mes = ""
    ano = ""
    if fecha:
        try:
            dt = datetime.strptime(fecha, "%Y/%m/%d")
            mes = dt.strftime("%Y-%m")
            ano = dt.year
        except:
            pass
    return [
        make_txn_id(fecha, txn.get("hora", ""), txn.get("tarjeta", ""), txn.get("comercio", "")),
        fecha,
        txn.get("hora", ""),
        txn.get("tarjeta", ""),
        txn.get("banco", ""),
        txn.get("monto", 0),
        txn.get("comercio", ""),
        txn.get("categoria", "Otros"),
        txn.get("subcategoria", ""),
        mes,
        ano,
        txn.get("fuente", "email"),
        txn.get("notas", ""),
    ]


def save_transactions(transactions):
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_TRANSACTIONS)

    existing_ids = set()
    try:
        all_vals = ws.get_all_values()
        for row in all_vals[1:]:
            if row and row[0]:
                existing_ids.add(row[0])
    except:
        pass

    new_rows = []
    for txn in transactions:
        row = txn_to_row(txn)
        if row[0] not in existing_ids:
            new_rows.append(row)
            existing_ids.add(row[0])

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(new_rows)


def get_transactions_df():
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_TRANSACTIONS)
    all_vals = ws.get_all_values()
    if len(all_vals) <= 1:
        return []
    headers = all_vals[0]
    rows = []
    for row in all_vals[1:]:
        if row and row[0]:
            rows.append(dict(zip(headers, row)))
    return rows


def get_categories_config():
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_CATEGORIES)
    all_vals = ws.get_all_values()
    if len(all_vals) <= 1:
        return {}
    config = {}
    for row in all_vals[1:]:
        if row and row[0]:
            config[row[0]] = {
                "palabras_clave": [k.strip() for k in row[1].split(",") if k.strip()],
                "color": row[2] if len(row) > 2 else "#999",
                "presupuesto": int(row[3]) if len(row) > 3 and row[3].isdigit() else 0,
            }
    return config


def add_rule(palabra_clave, categoria, origen="manual"):
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_RULES)
    ws.append_rows([[palabra_clave.upper(), categoria, origen]], value_input_option="USER_ENTERED")


def get_rules():
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_RULES)
    all_vals = ws.get_all_values()
    if len(all_vals) <= 1:
        return []
    rules = []
    for row in all_vals[1:]:
        if row and row[0]:
            rules.append({
                "palabra_clave": row[0],
                "categoria": row[1] if len(row) > 1 else "Otros",
                "origen": row[2] if len(row) > 2 else "manual",
            })
    return rules


def add_income(fecha, fuente, monto, notas=""):
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_INCOME)
    import hashlib
    id_val = hashlib.md5(f"{fecha}-{fuente}-{monto}".encode()).hexdigest()[:12]
    ws.append_rows([[id_val, fecha, fuente, monto, notas]], value_input_option="USER_ENTERED")


def update_txn_category(row_id, new_category):
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_TRANSACTIONS)
    all_vals = ws.get_all_values()
    for i, row in enumerate(all_vals):
        if row and row[0] == row_id:
            ws.update_cell(i + 1, 8, new_category)
            return True
    return False


def mark_as_returned(txn_id, motivo="No especificado"):
    from datetime import datetime
    sh = get_or_create_spreadsheet()

    ws_txn = sh.worksheet(TAB_TRANSACTIONS)
    all_vals = ws_txn.get_all_values()
    txn_data = None
    for row in all_vals[1:]:
        if row and row[0] == txn_id:
            txn_data = row
            break

    if not txn_data:
        return False

    ws_ret = sh.worksheet(TAB_RETURNS)
    existing_ids = set()
    try:
        ret_vals = ws_ret.get_all_values()
        for row in ret_vals[1:]:
            if row and row[0]:
                existing_ids.add(row[0])
    except:
        pass

    if txn_id in existing_ids:
        return False

    return_row = [
        txn_id,
        txn_data[1] if len(txn_data) > 1 else "",
        txn_data[2] if len(txn_data) > 2 else "",
        txn_data[6] if len(txn_data) > 6 else "",
        txn_data[5] if len(txn_data) > 5 else "",
        txn_data[4] if len(txn_data) > 4 else "",
        txn_data[3] if len(txn_data) > 3 else "",
        motivo,
        "Pendiente",
        datetime.now().strftime("%Y/%m/%d"),
    ]
    ws_ret.append_rows([return_row], value_input_option="USER_ENTERED")
    return True


def get_returns_df():
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_RETURNS)
    all_vals = ws.get_all_values()
    if len(all_vals) <= 1:
        return []
    headers = all_vals[0]
    rows = []
    for row in all_vals[1:]:
        if row and row[0]:
            rows.append(dict(zip(headers, row)))
    return rows


def get_returned_txn_ids():
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_RETURNS)
    all_vals = ws.get_all_values()
    ids = set()
    for row in all_vals[1:]:
        if row and row[0]:
            ids.add(row[0])
    return ids


def update_return_status(return_id, new_status):
    sh = get_or_create_spreadsheet()
    ws = sh.worksheet(TAB_RETURNS)
    all_vals = ws.get_all_values()
    for i, row in enumerate(all_vals):
        if row and row[0] == return_id:
            ws.update_cell(i + 1, 9, new_status)
            return True
    return False
