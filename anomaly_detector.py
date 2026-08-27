from collections import defaultdict
from config import DEFAULT_CATEGORIES


def normalize_comercio(name):
    skip = ["*DEBITO*", "*CREDITO*", "ATENTAMENTE", "BANCO DAVIVIENDA", "BANCO", "S.A."]
    clean = name.upper()
    for s in skip:
        clean = clean.replace(s, "")
    clean = clean.strip()
    clean = " ".join(clean.split())
    return clean


def detect_duplicates(txns):
    groups = defaultdict(list)
    for t in txns:
        monto = t.get("monto", 0)
        fecha = t.get("fecha", "")
        comercio = normalize_comercio(t.get("comercio", ""))
        key = (fecha, monto, comercio[:15])
        groups[key].append(t)

    duplicates = []
    for key, items in groups.items():
        if len(items) > 1:
            fecha, monto, comercio_key = key
            try:
                monto_f = float(monto)
            except (TypeError, ValueError):
                monto_f = 0.0
            first = items[0]
            fecha_id = first.get("fecha", "").replace("/", "")
            comercio_id = comercio_key.replace(" ", "_")[:15]
            grupo_id = f"DUP-{fecha_id}-{monto_f:.0f}-{comercio_id}"
            duplicates.append({
                "tipo": "duplicado",
                "grupo_id": grupo_id,
                "mensaje": f"{len(items)} transacciones de ${monto_f:,.0f} en {normalize_comercio(items[0]['comercio'])}",
                "transacciones": items,
                "n_transacciones": len(items),
                "fecha": first.get("fecha", ""),
                "hora": first.get("hora", ""),
                "comercio": first.get("comercio", ""),
                "monto": monto_f,
                "severidad": "alta",
            })

    return duplicates


def save_duplicate_groups(groups):
    from sheets_db import save_duplicates
    import hashlib
    payload = []
    for g in groups:
        if not g.get("grupo_id"):
            continue
        gid = g["grupo_id"]
        stable_id = hashlib.md5(gid.encode()).hexdigest()[:12]
        payload.append({
            "grupo_id": gid,
            "id": gid + "-" + stable_id,
            "fecha": g.get("fecha", ""),
            "hora": g.get("hora", ""),
            "comercio": normalize_comercio(g.get("comercio", "")),
            "monto": g.get("monto", 0),
            "n_transacciones": g.get("n_transacciones", len(g.get("transacciones", []))),
            "tipo": "por_definir",
        })
    return save_duplicates(payload)


def detect_fees(txns):
    fee_keywords = [
        "CUOTA DE MANEJO", "COMISION", "ANUALIDAD", "CUOTA MANEJO",
        "SEGURO", "INTERES", "INTERESES", "MORA", "RECARGO",
        "IMPTO GOBIERNO", "IVA", "RETENCION",
    ]

    alerts = []
    for t in txns:
        comercio = t.get("comercio", "").upper()
        for kw in fee_keywords:
            if kw in comercio:
                alerts.append({
                    "tipo": "cuota_manejo",
                    "mensaje": f"Cobro bancario detectado: {t['comercio'][:50]} - ${t['monto']:,.0f}",
                    "transaccion": t,
                    "severidad": "alta",
                    "color": "#e74c3c",
                })
                break
    return alerts


def detect_forgotten_subscriptions(txns_hoy, historial):
    sub_cats = ["Suscripciones"]

    historial_by_cat = defaultdict(list)
    for t in historial:
        cat = t.get("Categoria", "")
        if cat in sub_cats:
            historial_by_cat[cat].append(t)

    alerts = []
    for t in txns_hoy:
        cat = t.get("categoria", "")
        if cat not in sub_cats:
            continue

        comercio = normalize_comercio(t.get("comercio", ""))
        same_comercio = [h for h in historial if normalize_comercio(h.get("Comercio", "")) == comercio]

        if len(same_comercio) >= 2:
            meses = set()
            for h in same_comercio:
                mes = h.get("Mes", "")
                if mes:
                    meses.add(mes)

            if len(meses) >= 2:
                alerts.append({
                    "tipo": "suscripcion_olvidada",
                    "mensaje": f"Suscripcion recurrente ({len(meses)} meses): {comercio[:40]} - ${t['monto']:,.0f}/mes",
                    "transaccion": t,
                    "severidad": "media",
                    "color": "#f39c12",
                })

    return alerts


def detect_unusual_amounts(txns_hoy, historial):
    cat_amounts = defaultdict(list)
    for t in historial:
        cat = t.get("Categoria", "")
        try:
            monto = float(t.get("Monto", 0))
            if monto > 0:
                cat_amounts[cat].append(monto)
        except:
            pass

    cat_avg = {}
    for cat, amounts in cat_amounts.items():
        cat_avg[cat] = sum(amounts) / len(amounts) if amounts else 0

    alerts = []
    for t in txns_hoy:
        cat = t.get("categoria", "")
        monto = t.get("monto", 0)
        avg = cat_avg.get(cat, 0)

        if avg > 0 and monto > avg * 3:
            alerts.append({
                "tipo": "monto_inusual",
                "mensaje": f"Monto inusual en {cat}: ${monto:,.0f} (promedio: ${avg:,.0f}, {monto/avg:.1f}x)",
                "transaccion": t,
                "severidad": "media",
                "color": "#e67e22",
            })

    return alerts


def detect_all(txns_hoy, historial):
    return {
        "duplicados": detect_duplicates(txns_hoy),
        "cuotas": detect_fees(txns_hoy),
        "suscripciones": detect_forgotten_subscriptions(txns_hoy, historial),
        "inusuales": detect_unusual_amounts(txns_hoy, historial),
    }
