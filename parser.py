import re


def parse_davivienda_email(body, subject=""):
    transactions = []
    tarjeta = ""
    tarjeta_match = re.search(r"terminada en (\*{4}\d{4})", body)
    if tarjeta_match:
        tarjeta = tarjeta_match.group(1)

    blocks = re.split(r'\n\s*\n', body)
    if len(blocks) <= 1:
        blocks = body.split("\n")

    current = {}
    for line in body.split("\n"):
        line = line.strip()

        fecha_m = re.search(r"Fecha:\s*(\d{4}/\d{2}/\d{2})", line)
        if fecha_m:
            if current.get("fecha") and current.get("monto", 0) > 0:
                current["tarjeta"] = tarjeta
                current["banco"] = "Davivienda"
                transactions.append(current)
            current = {"fecha": fecha_m.group(1), "hora": "", "monto": 0.0, "comercio": "", "tipo": ""}

        hora_m = re.search(r"Hora:\s*(\d{2}:\d{2}:\d{2})", line)
        if hora_m:
            current["hora"] = hora_m.group(1)

        valor_m = re.search(r"Valor Transacci[oó]n:\s*([\d.,]+)", line)
        if valor_m:
            raw = valor_m.group(1).replace(".", "").replace(",", "")
            try:
                current["monto"] = float(raw)
            except:
                pass

        tipo_m = re.search(r"Clase de Movimiento:\s*(.+)", line)
        if tipo_m:
            current["tipo"] = tipo_m.group(1).strip().rstrip(".")

        lugar_m = re.search(r"Lugar de Transacci[oó]n:\s*(.+)", line)
        if lugar_m:
            current["comercio"] = lugar_m.group(1).strip()

        envio_m = re.search(r"Envi[oó] a:\s*(.+)", line)
        if envio_m and not current.get("comercio"):
            current["comercio"] = envio_m.group(1).strip()

        destino_m = re.search(r"Destino:\s*(.+)", line)
        if destino_m and not current.get("comercio"):
            current["comercio"] = destino_m.group(1).strip()

        recarga_m = re.search(r"N[uú]mero a recargar:\s*(.+)", line)
        if recarga_m and not current.get("comercio"):
            current["comercio"] = "Recarga " + recarga_m.group(1).strip()

        cuota_m = re.search(r"Cuota de Manejo:\s*([\d.,]+)", line)
        if cuota_m:
            raw = cuota_m.group(1).replace(".", "").replace(",", "")
            try:
                current["monto"] = float(raw)
            except:
                pass
            current["comercio"] = "CUOTA DE MANEJO"
            current["tipo"] = "Cuota de Manejo"

    if current.get("fecha") and current.get("monto", 0) > 0:
        current["tarjeta"] = tarjeta
        current["banco"] = "Davivienda"
        if not current.get("comercio"):
            current["comercio"] = current.get("tipo", "Sin descripcion")
        transactions.append(current)

    return transactions


def parse_rappibank_email(body, subject=""):
    transactions = []
    tarjeta = ""
    tarjeta_match = re.search(r"terminada en (\*{4}\d{4})", body)
    if tarjeta_match:
        tarjeta = tarjeta_match.group(1)
    if not tarjeta:
        tarjeta_match = re.search(r"RappiCard\s*.*?(\d{4})", body)
        if tarjeta_match:
            tarjeta = "****" + tarjeta_match.group(1)

    current = {}
    for line in body.split("\n"):
        line = line.strip()

        fecha_m = re.search(r"Fecha:\s*(\d{4}/\d{2}/\d{2})", line)
        if fecha_m:
            if current.get("fecha") and current.get("monto", 0) > 0 and current.get("comercio"):
                current["tarjeta"] = tarjeta
                current["banco"] = "RappiBank"
                transactions.append(current)
            current = {"fecha": fecha_m.group(1), "hora": "", "monto": 0.0, "comercio": ""}
        fecha_m2 = re.search(r"Fecha:\s*(\d{2}/\d{2}/\d{4})", line)
        if fecha_m2:
            parts = fecha_m2.group(1).split("/")
            if current.get("fecha") and current.get("monto", 0) > 0 and current.get("comercio"):
                current["tarjeta"] = tarjeta
                current["banco"] = "RappiBank"
                transactions.append(current)
            current = {"fecha": f"{parts[2]}/{parts[1]}/{parts[0]}", "hora": "", "monto": 0.0, "comercio": ""}

        hora_m = re.search(r"Hora:\s*(\d{2}:\d{2}:\d{2})", line)
        if hora_m:
            current["hora"] = hora_m.group(1)

        valor_m = re.search(r"Valor:\s*([\d.,]+)", line)
        if valor_m:
            raw = valor_m.group(1).replace(".", "").replace(",", "")
            try:
                current["monto"] = float(raw)
            except:
                pass
        valor_m2 = re.search(r"Monto:\s*([\d.,]+)", line)
        if valor_m2 and not current.get("monto"):
            raw = valor_m2.group(1).replace(".", "").replace(",", "")
            try:
                current["monto"] = float(raw)
            except:
                pass
        valor_m3 = re.search(r"Transacci[oó]n por:\s*\$?\s*([\d.,]+)", line)
        if valor_m3 and not current.get("monto"):
            raw = valor_m3.group(1).replace(".", "").replace(",", "")
            try:
                current["monto"] = float(raw)
            except:
                pass

        comercio_m = re.search(r"Lugar:\s*(.+)", line)
        if comercio_m:
            current["comercio"] = comercio_m.group(1).strip()
        comercio_m2 = re.search(r"Comercio:\s*(.+)", line)
        if comercio_m2 and not current.get("comercio"):
            current["comercio"] = comercio_m2.group(1).strip()
        comercio_m3 = re.search(r"Descripci[oó]n:\s*(.+)", line)
        if comercio_m3 and not current.get("comercio"):
            current["comercio"] = comercio_m3.group(1).strip()
        comercio_m4 = re.search(r"En\s+(.+?)\s+por", line)
        if comercio_m4 and not current.get("comercio"):
            current["comercio"] = comercio_m4.group(1).strip()

    if current.get("fecha") and current.get("monto", 0) > 0 and current.get("comercio"):
        current["tarjeta"] = tarjeta
        current["banco"] = "RappiBank"
        transactions.append(current)

    return transactions


def parse_rappicard_email(body, subject=""):
    import html as html_mod
    transactions = []
    body_clean = html_mod.unescape(body)
    if "rappicard" not in subject.lower() and "rappicard" not in body_clean.lower():
        return []

    tarjeta = ""
    tarjeta_match = re.search(r"\*(\d{4})", body_clean)
    if tarjeta_match:
        tarjeta = "****" + tarjeta_match.group(1)

    monto = 0.0
    monto_m = re.search(r"Monto\s*\$?([\d.,]+)", body_clean)
    if monto_m:
        raw = monto_m.group(1).replace(".", "").replace(",", "")
        try:
            monto = float(raw)
        except:
            pass

    comercio = ""
    comercio_m = re.search(r"Comercio\s+(.+?)(?:\s+Fecha)", body_clean)
    if comercio_m:
        comercio = comercio_m.group(1).strip()

    fecha = ""
    hora = ""
    fecha_m = re.search(r"Fecha de la transacci[oó]n\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", body_clean)
    if fecha_m:
        fecha = fecha_m.group(1).replace("-", "/")
        hora = fecha_m.group(2)

    if fecha and monto > 0 and comercio:
        transactions.append({
            "fecha": fecha,
            "hora": hora,
            "tarjeta": tarjeta,
            "monto": monto,
            "comercio": comercio,
            "tipo": "Compra",
            "banco": "RappiCard",
        })

    return transactions


def parse_email(body, subject="", banco=""):
    if "rappicard" in subject.lower():
        txns = parse_rappicard_email(body, subject)
        if txns:
            return txns

    if banco == "davivienda" or not banco:
        txns = parse_davivienda_email(body, subject)
        if txns:
            return txns
    if banco == "rappibank" or not banco:
        txns = parse_rappibank_email(body, subject)
        if txns:
            return txns
    return parse_davivienda_email(body, subject)
