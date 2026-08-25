from datetime import datetime, timedelta
from collections import defaultdict
from gmail_reader import send_email, get_bank_emails, get_email_body, get_email_subject
from parser import parse_email
from classifier import classify_transaction
from sheets_db import save_transactions, get_transactions_df, get_returned_txn_ids
from anomaly_detector import detect_all, normalize_comercio
from config import DEFAULT_CATEGORIES, DAILY_ALERT_THRESHOLD


def sync_today_emails():
    today = datetime.now().strftime("%Y/%m/%d")
    msgs = get_bank_emails(days_back=1)

    txns = []
    for m in msgs:
        body = get_email_body(m["id"])
        subject = get_email_subject(m["id"])
        banco = ""
        if "davivienda" in body.lower() or "davivienda" in subject.lower():
            banco = "davivienda"
        elif "rappi" in body.lower() or "rappi" in subject.lower():
            banco = "rappibank"
        parsed = parse_email(body, subject, banco)
        if parsed:
            for t in parsed:
                t["categoria"] = classify_transaction(t["comercio"])
                t["fuente"] = "email"
            txns.extend(parsed)

    if txns:
        save_transactions(txns)

    return txns


def build_daily_email(txns_hoy, anomalias, return_ids):
    today = datetime.now()
    fecha_str = today.strftime("%d/%m/%Y")

    total = sum(t.get("monto", 0) for t in txns_hoy)
    promedio = total / len(txns_hoy) if txns_hoy else 0

    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0e1117; color: #e0e0e0; padding: 0; margin: 0; }}
        .container {{ max-width: 650px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1d23 0%, #2d3139 100%); padding: 30px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid #ff6b35; }}
        .header h1 {{ color: #ff6b35; margin: 0; font-size: 22px; }}
        .header .date {{ color: #888; margin-top: 5px; font-size: 14px; }}
        .stats {{ display: flex; gap: 12px; margin-bottom: 20px; }}
        .stat-card {{ flex: 1; background: #1a1d23; padding: 15px; border-radius: 10px; text-align: center; }}
        .stat-card .value {{ font-size: 20px; font-weight: bold; color: #ff6b35; }}
        .stat-card .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .section {{ background: #1a1d23; padding: 20px; border-radius: 10px; margin-bottom: 15px; }}
        .section h2 {{ font-size: 16px; color: #fff; margin: 0 0 15px 0; padding-bottom: 8px; border-bottom: 1px solid #333; }}
        .alert {{ background: #2d1a1a; border-left: 3px solid #e74c3c; padding: 10px 14px; border-radius: 0 8px 8px 0; margin-bottom: 8px; }}
        .alert.warning {{ background: #2d2a1a; border-left-color: #f39c12; }}
        .alert.info {{ background: #1a2d2d; border-left-color: #3498db; }}
        .alert .msg {{ font-size: 13px; color: #e0e0e0; }}
        .alert .tag {{ font-size: 10px; font-weight: bold; text-transform: uppercase; margin-bottom: 3px; }}
        .alert .tag.red {{ color: #e74c3c; }}
        .alert .tag.orange {{ color: #f39c12; }}
        .alert .tag.blue {{ color: #3498db; }}
        .txn-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #222; }}
        .txn-row:last-child {{ border-bottom: none; }}
        .txn-merchant {{ font-size: 13px; color: #ccc; }}
        .txn-cat {{ font-size: 11px; color: #888; }}
        .txn-amount {{ font-size: 14px; font-weight: bold; color: #ff6b35; }}
        .txn-amount.fee {{ color: #e74c3c; }}
        .txn-id {{ font-size: 10px; color: #555; font-family: monospace; }}
        .footer {{ text-align: center; color: #555; font-size: 11px; margin-top: 30px; padding-top: 15px; border-top: 1px solid #222; }}
        .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }}
        .badge.returned {{ background: #2d1a2d; color: #e74c3c; border: 1px solid #e74c3c; }}
    </style>
    </head>
    <body>
    <div class="container">

        <div class="header">
            <h1>Tu dia en numeros</h1>
            <div class="date">{fecha_str} - Resumen automatico de gastos</div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="value">${total:,.0f}</div>
                <div class="label">Total hoy</div>
            </div>
            <div class="stat-card">
                <div class="value">{len(txns_hoy)}</div>
                <div class="label">Transacciones</div>
            </div>
            <div class="stat-card">
                <div class="value">${promedio:,.0f}</div>
                <div class="label">Promedio</div>
            </div>
        </div>
    """

    all_alerts = (
        anomalias.get("cuotas", []) +
        anomalias.get("duplicados", []) +
        anomalias.get("suscripciones", []) +
        anomalias.get("inusuales", [])
    )

    if all_alerts:
        html += '<div class="section"><h2>Alertas</h2>'
        for a in all_alerts:
            severity = a.get("severidad", "media")
            css_class = "alert" if severity == "alta" else "alert warning"
            tag_class = "red" if severity == "alta" else "orange"
            tag_label = "COBRO BANCARIO" if a["tipo"] == "cuota_manejo" else \
                        "DUPLICADO" if a["tipo"] == "duplicado" else \
                        "SUSCRIPCION" if a["tipo"] == "suscripcion_olvidada" else "MONTO INUSUAL"

            html += f"""
            <div class="{css_class}">
                <div class="tag {tag_class}">{tag_label}</div>
                <div class="msg">{a['mensaje']}</div>
            </div>
            """
        html += "</div>"

    pending_returns = [t for t in txns_hoy if t.get("id", "") in return_ids]
    if pending_returns:
        html += '<div class="section"><h2>Pendientes de confirmar devolucion</h2>'
        for t in pending_returns:
            html += f"""
            <div class="alert info">
                <div class="tag blue">PENDIENTE</div>
                <div class="msg">{normalize_comercio(t.get('comercio', ''))[:40]} - ${t.get('monto', 0):,.0f} - {t.get('categoria', '')}</div>
            </div>
            """
        html += "</div>"

    if txns_hoy:
        html += '<div class="section"><h2>Detalle del dia</h2>'
        for t in txns_hoy:
            cat = t.get("categoria", "Otros")
            cat_color = DEFAULT_CATEGORIES.get(cat, {}).get("color", "#999")
            is_fee = cat == "Cuota Manejo"
            amount_class = "fee" if is_fee else ""
            is_returned = t.get("id", "") in return_ids
            returned_badge = '<span class="badge returned">DEVUELTO</span>' if is_returned else ""

            html += f"""
            <div class="txn-row">
                <div>
                    <div class="txn-merchant">{normalize_comercio(t.get('comercio', ''))[:45]} {returned_badge}</div>
                    <div class="txn-cat"><span style="color:{cat_color};">&#9679;</span> {cat} &middot; {t.get('tarjeta', '')} &middot; {t.get('hora', '')[:5]}</div>
                </div>
                <div class="txn-amount {amount_class}">${t.get('monto', 0):,.0f}</div>
            </div>
            """
        html += "</div>"

    if not txns_hoy:
        html += """
        <div class="section" style="text-align:center; padding: 40px;">
            <div style="font-size: 40px; margin-bottom: 10px;">&#127881;</div>
            <div style="color: #888;">Sin transacciones hoy. Dia tranquilo!</div>
        </div>
        """

    html += f"""
        <div class="footer">
            Generado por MisGastos &middot; {today.strftime('%H:%M')}<br>
            Responde a este correo para marcar devoluciones
        </div>

    </div>
    </body>
    </html>
    """
    return html


def send_daily_report(email="juandroide7@gmail.com"):
    from sheets_db import get_transactions_df as get_all_transactions

    txns_hoy_raw = sync_today_emails()

    all_history = get_all_transactions()

    historial_clean = []
    for t in all_history:
        historial_clean.append({
            "Comercio": t.get("Comercio", ""),
            "Monto": t.get("Monto", 0),
            "Categoria": t.get("Categoria", ""),
            "Mes": t.get("Mes", ""),
        })

    return_ids = get_returned_txn_ids()

    txns_hoy_for_anomaly = []
    for t in txns_hoy_raw:
        txns_hoy_for_anomaly.append({
            "id": t.get("id", ""),
            "monto": t.get("monto", 0),
            "comercio": t.get("comercio", ""),
            "categoria": t.get("categoria", ""),
            "fecha": t.get("fecha", ""),
        })

    anomalias = detect_all(txns_hoy_for_anomaly, historial_clean)

    html = build_daily_email(txns_hoy_raw, anomalias, return_ids)

    today = datetime.now()
    n_txns = len(txns_hoy_raw)
    n_alerts = sum(len(v) for v in anomalias.values())
    subject = f"MisGastos {today.strftime('%d/%m')} - {n_txns} gastos"
    if n_alerts > 0:
        subject += f" ({n_alerts} alerta{'s' if n_alerts > 1 else ''})"

    return send_email(email, subject, html)


def generate_weekly_summary(transactions):
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    week_txns = []
    for t in transactions:
        try:
            dt = datetime.strptime(t.get("fecha", ""), "%Y/%m/%d")
            if week_start.date() <= dt.date() <= week_end.date():
                week_txns.append(t)
        except:
            continue

    total = sum(t.get("monto", 0) for t in week_txns)
    by_cat = defaultdict(float)
    for t in week_txns:
        by_cat[t.get("categoria", "Otros")] += t.get("monto", 0)

    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #0e1117; color: #fafafa; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto;">
        <h1 style="color: #ff6b35;">Resumen Semanal MisGastos</h1>
        <p style="color: #aaa;">{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}</p>
        <div style="background: #1a1d23; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h2 style="color: #ff6b35;">Total: ${total:,.0f} COP</h2>
            <p style="color: #aaa;">{len(week_txns)} transacciones esta semana</p>
        </div>
        <div style="background: #1a1d23; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h3>Por Categoria:</h3>
    """
    for cat, amount in sorted_cats:
        pct = (amount / total * 100) if total > 0 else 0
        html += f"""
            <div style="margin: 10px 0;">
                <div style="display: flex; justify-content: space-between;">
                    <span>{cat}</span>
                    <span style="color: #ff6b35;">${amount:,.0f}</span>
                </div>
                <div style="background: #333; height: 8px; border-radius: 4px; margin-top: 4px;">
                    <div style="background: #ff6b35; height: 100%; width: {pct}%; border-radius: 4px;"></div>
                </div>
            </div>
        """

    html += """
        </div>
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Generado por MisGastos - Dashboard de Control de Gastos
        </p>
    </div>
    </body>
    </html>
    """
    return html


def send_weekly_report(transactions, email="juandroide7@gmail.com"):
    html = generate_weekly_summary(transactions)
    today = datetime.now()
    subject = f"Reporte Semanal MisGastos - {today.strftime('%d/%m/%Y')}"
    return send_email(email, subject, html)
