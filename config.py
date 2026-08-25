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

TRANSACTION_COLUMNS = [
    "ID", "Fecha", "Hora", "Tarjeta", "Banco", "Monto",
    "Comercio", "Categoria", "Subcategoria", "Mes", "Ano",
    "Fuente", "Notas"
]

CATEGORY_COLUMNS = ["Categoria", "PalabrasClave", "Color", "PresupuestoMensual"]
INCOME_COLUMNS = ["ID", "Fecha", "Fuente", "Monto", "Notas"]
RULE_COLUMNS = ["PalabraClave", "Categoria", "AprendidoDe"]
RETURN_COLUMNS = ["ID", "FechaTxn", "HoraTxn", "Comercio", "Monto", "Banco", "Tarjeta", "Motivo", "Estado", "FechaDevolucion"]

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
    if os.environ.get("STREAMLIT_CLOUD"):
        return {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        }
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return json.load(f)
    return None

def save_token(token_data):
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    import json
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)
