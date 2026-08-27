import base64
import os
import re
import subprocess
import tempfile

from config import get_cedula
from gmail_reader import get_access_token

EXTRACT_QUERIES = {
    "cuenta_ahorros": "subject:(Extractos Portafolio)",
    "tarjeta_credito": 'subject:("Extracto tarjeta de Crédito Banco Davivienda")',
    "rappicard": "subject:(extracto de tu RappiCard)",
}


def _gmail_request(url):
    token = get_access_token()
    import requests
    return requests.get(url, headers={"Authorization": f"Bearer {token}"}).json()


def _find_attachment(payload):
    if payload.get("body", {}).get("attachmentId"):
        return payload
    for p in payload.get("parts", []):
        r = _find_attachment(p)
        if r:
            return r
    return None


def _download_attachment(msg_id, att_payload, out_path):
    import requests
    token = get_access_token()
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}/attachments/{att_payload['body']['attachmentId']}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return False
    raw = base64.urlsafe_b64decode(r.json().get("data", ""))
    with open(out_path, "wb") as f:
        f.write(raw)
    return True


def download_extract(tipo, max_results=3):
    query = EXTRACT_QUERIES[tipo]
    import requests
    token = get_access_token()
    msgs = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query, "maxResults": max_results},
    ).json().get("messages", [])

    results = []
    for m in msgs:
        mid = m["id"]
        full = _gmail_request(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full")
        att = _find_attachment(full.get("payload", {}))
        if not att:
            continue
        fn = re.sub(r"[^A-Za-z0-9._-]", "_", att.get("filename", "extracto.pdf"))
        out = os.path.join(tempfile.gettempdir(), f"{tipo}_{fn}")
        if _download_attachment(mid, att, out):
            results.append({"msg_id": mid, "path": out, "tipo": tipo})
    return results


def decrypt_pdf(path):
    cedula = get_cedula()
    dec_path = path.replace(".pdf", "_dec.pdf")
    cmd = ["qpdf", "--decrypt", "--password=" + cedula, path, dec_path]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.exists(dec_path):
        return None
    return dec_path


def _extract_text(path):
    import pdfplumber
    texts = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            texts.append(pg.extract_text() or "")
    return "\n".join(texts)


def parse_cuenta_ahorros(text):
    movs = []
    periodo = ""
    m_periodo = re.search(r"INFORME DEL MES:\s*([A-Za-z]+)\s*/\s*(\d{4})", text)
    mes_map = {"ENERO":1,"FEBRERO":2,"MARZO":3,"ABRIL":4,"MAYO":5,"JUNIO":6,"JULIO":7,"AGOSTO":8,"SEPTIEMBRE":9,"OCTUBRE":10,"NOVIEMBRE":11,"DICIEMBRE":12}
    if m_periodo:
        mn = m_periodo.group(1).upper()
        ano = m_periodo.group(2)
        periodo = f"{ano}-{mes_map.get(mn, 0):02d}"

    lines = text.split("\n")
    for line in lines:
        m = re.match(r"^(\d{2}) (\d{2}) \$[\s]*([\d.,]+)([+-])\s*(\d{4}) (.+)$", line.strip())
        if m:
            dd, mm = m.group(1), m.group(2)
            valor = float(m.group(3).replace(",", ""))
            signo = m.group(4)
            oficina = m.group(5)
            desc = m.group(6).strip()
            periodo_year = periodo[:4] if periodo else "2026"
            movs.append({
                "fecha": f"{periodo_year}/{mm}/{dd}",
                "descripcion": desc,
                "valor": valor,
                "signo": signo,
                "oficina": oficina,
                "periodo": periodo,
                "producto": "cuenta_ahorros",
                "tarjeta": "1620",
                "fuente": "extracto_portafolio",
            })
    return movs, periodo


def parse_tarjeta_credito(text):
    movs = []
    periodo = ""
    m_periodo = re.search(r"Periodo de facturación:\s*(\d{2})/(\w{3})/(\d{4})", text)
    if m_periodo:
        periodo = m_periodo.group(3)
    else:
        periodos = re.findall(r"Periodo de facturación:\s*([\d/]+)", text)
        if periodos:
            periodo = periodos[0]

    # movimientos del mes
    m_block = re.search(r"Detalle de movimientos del mes\s*(.*?)(?:Movimientos meses anteriores|Usted no tiene)", text, re.DOTALL)
    block = ""
    if m_block:
        block = m_block.group(1)
    for line in block.split("\n"):
        m = re.match(r"^(\d{2}\w{3}\d{4})\s+(.+?)\s+\$([\d.,]+)\s+(\d+ de \d+)", line.strip())
        if m:
            fecha_raw = m.group(1)
            desc = m.group(2).strip()
            raw_valor = m.group(3)
            if desc.endswith("Aplicada") or "intereses" in desc.lower():
                continue
            raw_valor = m.group(3)
            valor = float(raw_valor.replace(",", ""))
            dt = _parse_short_date(fecha_raw, periodo)
            movs.append({
                "fecha": dt,
                "descripcion": desc,
                "valor": valor,
                "signo": "+",
                "oficina": "",
                "periodo": periodo,
                "producto": "tarjeta_credito",
                "tarjeta": "2422",
                "fuente": "extracto_tarjeta",
            })
    return movs, periodo


def _parse_short_date(fecha_raw, periodo_year=None):
    # e.g. 28Jul2026 -> 2026/07/28
    mes_map = {"ENE":1,"FEB":2,"MAR":3,"ABR":4,"MAY":5,"JUN":6,"JUL":7,"AGO":8,"SEP":9,"OCT":10,"NOV":11,"DIC":12}
    m = re.match(r"(\d{2})(\w{3})(\d{4})", fecha_raw)
    if not m:
        return ""
    dd = m.group(1)
    mm = mes_map.get(m.group(2).upper()[:3], 0)
    yy = m.group(3)
    return f"{yy}/{mm:02d}/{dd}"


def parse_rappicard(text):
    movs = []
    periodo = ""
    m_periodo = re.search(r"Periodo facturado\s*\n\s*Desde (\d{1,2} \w{3} \d{4})", text)
    if not m_periodo:
        periodos = re.findall(r"Desde (\d{1,2} \w{3} \d{4})", text)
        if periodos:
            from datetime import datetime
            try:
                dt = datetime.strptime(periodos[0], "%d %b %Y")
                periodo = str(dt.year)
            except:
                pass

    lines = text.split("\n")
    pending_desc = ""
    for line in lines:
        # A suelta línea de descripción (sin tipo de tarjeta) que precede un detalle
        if not re.match(r"^(Virtual|Física)\s+", line.strip()) and line.strip() and not line.strip().startswith("$") \
           and not re.match(r"^[A-Za-z]+ \d{4}", line.strip()) and "utilización" not in line.lower() \
           and "su cuota" not in line.lower() and "saldo" not in line.lower() and not line.strip().startswith("Desde"):
            if len(line.strip()) > 2 and not re.search(r"\d de \d", line):
                pending_desc = line.strip()
        m = re.match(r"^(Virtual|Física)\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\s+\$([\d.,]+)", line.strip())
        if m:
            tarjeta = m.group(1)
            fecha = m.group(2).replace("-", "/")
            desc_tok = m.group(3).strip()
            raw_valor = m.group(4)
            if desc_tok.startswith("$"):
                desc = pending_desc if pending_desc else "COMPRA"
                valor = float(desc_tok.lstrip("$").replace(".", "").replace(",", "."))
            else:
                desc = desc_tok
                valor = float(raw_valor.replace(".", "").replace(",", "."))
            tarjeta_num = "9096" if tarjeta == "Virtual" else "0174"
            movs.append({
                "fecha": fecha,
                "descripcion": desc,
                "valor": valor,
                "signo": "+",
                "oficina": "",
                "periodo": periodo,
                "producto": "rappicard",
                "tarjeta": tarjeta_num,
                "fuente": "extracto_rappicard",
            })
            pending_desc = ""
    return movs, periodo


def parse_extract_file(path, tipo):
    dec = decrypt_pdf(path)
    if not dec:
        return None
    text = _extract_text(dec)
    if tipo == "cuenta_ahorros":
        movs, periodo = parse_cuenta_ahorros(text)
    elif tipo == "tarjeta_credito":
        movs, periodo = parse_tarjeta_credito(text)
    elif tipo == "rappicard":
        movs, periodo = parse_rappicard(text)
    else:
        return None
    return {"movimientos": movs, "periodo": periodo}


def process_all_extracts():
    from sheets_db import save_statements, save_savings_rows, get_savings_rows
    all_movs = []
    for tipo in EXTRACT_QUERIES:
        files = download_extract(tipo, max_results=1)
        for f in files:
            parsed = parse_extract_file(f["path"], tipo)
            if parsed:
                all_movs.extend(parsed["movimientos"])

    saved = save_statements(all_movs)

    # Build savings aggregation from cuenta_ahorros movements
    savings_movs = [m for m in all_movs if m["producto"] == "cuenta_ahorros"]
    savings_rows = []
    for m in savings_movs:
        import hashlib
        rid = hashlib.md5(f"{m['fecha']}-{m['descripcion']}-{m['valor']}".encode()).hexdigest()[:12]
        # determine saldo from context
        savings_rows.append({
            "id": rid,
            "mes": m["periodo"],
            "fecha": m["fecha"],
            "descripcion": m["descripcion"],
            "valor": m["valor"],
            "tipo": "ingreso" if m["signo"] == "+" else "gasto",
            "oficina": m.get("oficina", ""),
            "saldo_anterior": "",
            "nuevo_saldo": "",
        })

    saved_savings = save_savings_rows(savings_rows)
    return {"extractos_guardados": saved, "ahorros_guardados": saved_savings, "total_movs": len(all_movs)}
