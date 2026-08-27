import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "token.json")
CLIENT_SECRETS_PATH = os.path.join(CREDENTIALS_DIR, "client_secret.json")

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]

SPREADSHEET_NAME = "MisGastos"
TAB_TRANSACTIONS = "TRANSACCIONES"
TAB_CATEGORIES = "CATEGORIAS"
TAB_INCOME = "INGRESOS"
TAB_RULES = "REGLAS"
TAB_RETURNS = "DEVOLUCIONES"
TAB_DUPLICATES = "DUPLICADOS"
TAB_STATEMENTS = "EXTRACTOS"
TAB_SAVINGS = "CUENTA_AHORROS"

TRANSACTION_COLUMNS = [
    "ID", "Fecha", "Hora", "Tarjeta", "Banco", "Monto",
    "Comercio", "Categoria", "Subcategoria", "Mes", "Ano",
    "Fuente", "Notas"
]

CATEGORY_COLUMNS = ["Categoria", "PalabrasClave", "Color", "PresupuestoMensual"]
INCOME_COLUMNS = ["ID", "Fecha", "Fuente", "Monto", "Notas"]
RULE_COLUMNS = ["PalabraClave", "Categoria", "AprendidoDe"]
RETURN_COLUMNS = ["ID", "FechaTxn", "HoraTxn", "Comercio", "Monto", "Banco", "Tarjeta", "Motivo", "Estado", "FechaDevolucion"]
DUPLICATE_COLUMNS = ["ID", "GrupoID", "FechaTxn", "HoraTxn", "Comercio", "Monto", "NumTxns", "Tipo", "Estado", "Comentario", "VerificadoEn"]
STATEMENT_COLUMNS = ["ID", "Producto", "Tarjeta", "Fecha", "Descripcion", "Valor", "Signo", "Periodo", "Fuente"]
SAVINGS_COLUMNS = ["ID", "Mes", "Fecha", "Descripcion", "Valor", "Tipo", "Oficina", "SaldoAnterior", "NuevoSaldo"]

DEFAULT_CATEGORIES = {
    "Transporte": {
        "keywords": ["UBER", "DIDI", "INDRIVER", "BEAT", "TAXI", "BICI", "METRO", "BUS", "ENVIOS RAPPI", "RAPPI*ENVIO"],
        "color": "#3498db", "budget": 150000
    },
    "Comida": {
        "keywords": ["MCDONALD", "BURGER", "PIZZA", "STARBUCK", "STARBUCC", "CAFE", "CAFETERIA", "RESTAURANTE", "ALMUERZO", "CENA", "DESAYUNO", "COMIDA", "SUBWAY", "WENDYS", "POPEYES", "KFC", "HAMBURGUESA", "SANDWICH", "HELADO", "REPOSTERIA"],
        "color": "#e74c3c", "budget": 400000
    },
    "Rappi": {
        "keywords": ["RAPPI"],
        "color": "#ff6b35", "budget": 300000
    },
    "Mercado": {
        "keywords": ["MERCADO LIBRE", "MERCADO PAGO", "EXITO", "CARULLA", "D1", "ARA", "OLIMPICA", "MAKRO", "TIENDA", "SUPERSOL"],
        "color": "#2ecc71", "budget": 300000
    },
    "Cuota Manejo": {
        "keywords": ["CUOTA DE MANEJO", "COMISION", "ANUALIDAD", "CUOTA MANEJO"],
        "color": "#9b59b6", "budget": 0
    },
    "Suscripciones": {
        "keywords": ["NETFLIX", "SPOTIFY", "AMAZON PRIME", "DISNEY", "HBO", "YOUTUBE", "OPENAI", "CHATGPT", "APPLE.COM/BILL", "GOOGLE", "PARAMOUNT", "HULU", "CRUNCHYROLL"],
        "color": "#1abc9c", "budget": 100000
    },
    "Servicios": {
        "keywords": ["CLARO", "MOVISTAR", "ETB", "ENERGIA", "GAS", "AGUA", "TELEFONO", "INTERNET", "WIFI", "PERSONAL", "TIGO"],
        "color": "#f39c12", "budget": 200000
    },
    "Compras Online": {
        "keywords": ["AMAZON", "FALABELLA", "LINIO", "EBAY", "ALIEXPRESS", "SHEIN"],
        "color": "#e67e22", "budget": 200000
    },
    "Salud": {
        "keywords": ["FARMACIA", "DROGAS", "CLINICA", "HOSPITAL", "DOCTOR", "MEDICO", "EPS", "CRUZ VERDE", "LA REBAJA", "COLSUBSIDIO"],
        "color": "#16a085", "budget": 100000
    },
    "Educacion": {
        "keywords": ["UDEA", "UNIVERSIDAD", "COLEGIO", "SANBONI", "COURSERA", "UDEMY", "PLATZI", "EDX"],
        "color": "#2980b9", "budget": 100000
    },
    "Otros": {
        "keywords": [],
        "color": "#95a5a6", "budget": 200000
    }
}

DAILY_ALERT_THRESHOLD = 100000
MONTHLY_ALERT_THRESHOLD = 1500000

BANK_SENDERS = {
    "davivienda": ["notificaciones@davivienda.com", "davivienda@davivienda.com"],
    "rappibank": ["notificaciones@rappibank.com", "rappibank@rappi.com"]
}

def get_credentials():
    import json
    is_cloud = os.environ.get("STREAMLIT_CLOUD") or os.environ.get("GITHUB_ACTIONS")
    if is_cloud:
        data = {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN"),
        }
        if os.environ.get("SPREADSHEET_NAME"):
            data["spreadsheet_name"] = os.environ["SPREADSHEET_NAME"]
        return data
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return json.load(f)
    return None

def get_cedula():
    return os.environ.get("CEDULA", "1110597861")

def get_send_email():
    return os.environ.get("SEND_EMAIL", "juandroide7@gmail.com")

def get_spreadsheet_name():
    creds = get_credentials()
    if creds and creds.get("spreadsheet_name"):
        return creds["spreadsheet_name"]
    env_name = os.environ.get("SPREADSHEET_NAME")
    if env_name:
        return env_name
    return SPREADSHEET_NAME

def save_token(token_data):
    if os.environ.get("GITHUB_ACTIONS"):
        return
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    import json
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)
