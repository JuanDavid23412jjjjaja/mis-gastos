import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CATEGORIES, DAILY_ALERT_THRESHOLD, MONTHLY_ALERT_THRESHOLD
from parser import parse_email
from classifier import classify_transaction, get_all_categories, get_category_color
from gmail_reader import get_bank_emails, get_email_body, get_email_subject
from sheets_db import (
    get_or_create_spreadsheet, save_transactions, get_transactions_df,
    get_categories_config, add_rule, get_rules, add_income, update_txn_category,
    setup_spreadsheet, make_txn_id,
    mark_as_returned, get_returns_df, get_returned_txn_ids, update_return_status,
    get_duplicates, update_duplicate_status, get_statements, get_savings_rows
)
from verify_duplicates import verify_duplicates, apply_verification
from anomaly_detector import detect_duplicates, save_duplicate_groups
from reports import send_weekly_report, check_daily_alert


st.set_page_config(
    page_title="MisGastos",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stMetric { background: #1a1d23; padding: 15px; border-radius: 10px; }
    .stMetric label { color: #aaa !important; }
    .stMetric [data-testid="stMetricValue"] { color: #ff6b35 !important; }
    div[data-testid="stSidebar"] { background: #0e1117; }
    .category-pill {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 12px; font-weight: bold; margin: 2px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_sheets():
    try:
        sh = get_or_create_spreadsheet()
        setup_spreadsheet(sh)
        return sh
    except Exception as e:
        st.error(f"Error conectando con Google Sheets: {e}")
        return None


def fmt_cop(value):
    try:
        v = float(value)
        return f"${v:,.0f}"
    except:
        return "$0"


def load_transactions():
    try:
        return get_transactions_df()
    except:
        return []


def sync_emails():
    with st.spinner("Leyendo emails de bancos..."):
        msgs = get_bank_emails(days_back=90)
        new_count = 0
        for msg in msgs:
            try:
                body = get_email_body(msg["id"])
                subject = get_email_subject(msg["id"])
                banco = ""
                if "davivienda" in subject.lower() or "davivienda" in body.lower():
                    banco = "davivienda"
                elif "rappi" in subject.lower() or "rappi" in body.lower():
                    banco = "rappibank"
                txns = parse_email(body, subject, banco)
                if txns:
                    rules = get_rules()
                    custom_rules = [{"palabra_clave": r["palabra_clave"], "categoria": r["categoria"]} for r in rules]
                    for t in txns:
                        t["categoria"] = classify_transaction(t.get("comercio", ""), custom_rules)
                        t["fuente"] = "email"
                    saved = save_transactions(txns)
                    new_count += saved
            except Exception as e:
                continue
        return new_count


def page_resumen():
    st.header("Resumen")
    transactions = load_transactions()
    if not transactions:
        st.info("No hay transacciones. Sincroniza emails o agrega gastos manualmente.")
        return

    df = pd.DataFrame(transactions)
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
    if "Fecha" in df.columns:
        df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%Y/%m/%d", errors="coerce")

    today = datetime.now()
    this_month = today.strftime("%Y-%m")
    last_month = (today - timedelta(days=30)).strftime("%Y-%m")

    col1, col2, col3, col4 = st.columns(4)

    month_df = df[df["Mes"] == this_month] if "Mes" in df.columns else df
    total_mes = month_df["Monto"].sum() if not month_df.empty else 0
    num_txns = len(month_df)
    promedio = total_mes / num_txns if num_txns > 0 else 0

    last_month_df = df[df["Mes"] == last_month] if "Mes" in df.columns else pd.DataFrame()
    total_last = last_month_df["Monto"].sum() if not last_month_df.empty else 0
    diff = total_mes - total_last

    with col1:
        st.metric("Total Mes", fmt_cop(total_mes), delta=f"{fmt_cop(diff)} vs mes anterior")
    with col2:
        st.metric("Transacciones", num_txns)
    with col3:
        st.metric("Promedio", fmt_cop(promedio))
    with col4:
        today_str = today.strftime("%Y/%m/%d")
        gasto_hoy = df[df["Fecha"] == today_str]["Monto"].sum() if not df.empty else 0
        st.metric("Gasto Hoy", fmt_cop(gasto_hoy),
                   delta="Excedido" if gasto_hoy > DAILY_ALERT_THRESHOLD else "Normal",
                   delta_color="inverse")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Gasto por Categoría")
        if not month_df.empty and "Categoria" in month_df.columns:
            cat_data = month_df.groupby("Categoria")["Monto"].sum().reset_index()
            cat_data = cat_data.sort_values("Monto", ascending=False)
            colors = [DEFAULT_CATEGORIES.get(c, {}).get("color", "#999") for c in cat_data["Categoria"]]
            fig = px.bar(cat_data, x="Categoria", y="Monto", color="Categoria",
                         color_discrete_sequence=colors, template="plotly_dark")
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="COP",
                              plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
            st.plotly_chart(fig, width="stretch")

    with col_b:
        st.subheader("Tendencia Diaria")
        if not df.empty and "Fecha_dt" in df.columns:
            daily = df.dropna(subset=["Fecha_dt"]).groupby(df["Fecha_dt"].dt.date)["Monto"].sum().reset_index()
            daily.columns = ["Fecha", "Total"]
            fig = px.line(daily, x="Fecha", y="Total", template="plotly_dark")
            fig.update_layout(xaxis_title="", yaxis_title="COP",
                              plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
            fig.update_traces(line_color="#ff6b35")
            st.plotly_chart(fig, width="stretch")

    st.divider()

    st.subheader("Top 10 Comercios")
    if not month_df.empty and "Comercio" in month_df.columns:
        top_merchants = month_df.groupby("Comercio")["Monto"].sum().reset_index()
        top_merchants = top_merchants.sort_values("Monto", ascending=False).head(10)
        fig = px.bar(top_merchants, x="Comercio", y="Monto", template="plotly_dark",
                     color_discrete_sequence=["#ff6b35"])
        fig.update_layout(xaxis_title="", yaxis_title="COP",
                          plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
        st.plotly_chart(fig, width="stretch")


def page_detalle():
    st.header("Detalle de Transacciones")
    transactions = load_transactions()
    if not transactions:
        st.info("No hay transacciones.")
        return

    df = pd.DataFrame(transactions)
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)

    col1, col2, col3 = st.columns(3)
    with col1:
        meses = sorted(df["Mes"].unique()) if "Mes" in df.columns else []
        mes_sel = st.selectbox("Mes", ["Todos"] + meses, key="detalle_mes")
    with col2:
        cats = sorted(df["Categoria"].unique()) if "Categoria" in df.columns else []
        cat_sel = st.selectbox("Categoría", ["Todas"] + cats, key="detalle_cat")
    with col3:
        bancos = sorted(df["Banco"].unique()) if "Banco" in df.columns else []
        banco_sel = st.selectbox("Banco", ["Todos"] + bancos, key="detalle_banco")

    filtered = df.copy()
    if mes_sel != "Todos":
        filtered = filtered[filtered["Mes"] == mes_sel]
    if cat_sel != "Todas":
        filtered = filtered[filtered["Categoria"] == cat_sel]
    if banco_sel != "Todos":
        filtered = filtered[filtered["Banco"] == banco_sel]

    total = filtered["Monto"].sum()
    st.metric("Total Filtrado", fmt_cop(total))

    if not filtered.empty:
        display_cols = ["Fecha", "Hora", "Banco", "Tarjeta", "Comercio", "Categoria", "Monto", "Fuente"]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[display_cols].sort_values("Fecha", ascending=False),
            width="stretch",
            column_config={
                "Monto": st.column_config.NumberColumn("Monto", format="$%d"),
            }
        )

        st.divider()
        st.subheader("Corregir Categoría")
        cats_list = get_all_categories()
        row_ids = filtered["ID"].tolist() if "ID" in filtered.columns else []
        if row_ids:
            id_sel = st.selectbox("Selecciona transacción", row_ids, key="corr_id")
            new_cat = st.selectbox("Nueva categoría", cats_list, key="corr_cat")
            if st.button("Actualizar"):
                if id_sel and new_cat:
                    update_txn_category(id_sel, new_cat)
                    txn = filtered[filtered["ID"] == id_sel].iloc[0]
                    add_rule(txn.get("Comercio", ""), new_cat, "correccion_usuario")
                    st.success(f"Categoría actualizada a {new_cat}")
                    st.rerun()

        st.divider()
        st.subheader("Marcar Devolución")
        return_ids = get_returned_txn_ids()
        pending_returns = [r for r in get_returns_df() if r.get("Estado") == "Pendiente"]

        if pending_returns:
            st.write("Devoluciones pendientes:")
            for r in pending_returns:
                col_a, col_b, col_c = st.columns([3, 2, 1])
                with col_a:
                    st.write(f"{r.get('Comercio', '')[:40]} - ${int(float(r.get('Monto', 0))):,}")
                with col_b:
                    st.write(f"Motivo: {r.get('Motivo', '')}")
                with col_c:
                    if st.button("Confirmar", key=f"conf_{r['ID']}"):
                        update_return_status(r["ID"], "Confirmada")
                        st.success("Devolución confirmada")
                        st.rerun()

        devolv_ids = [r for r in row_ids if r not in return_ids]
        if devolv_ids:
            id_dev = st.selectbox("Transacción a devolver", devolv_ids, key="dev_id")
            motivo = st.selectbox("Motivo", [
                "No lo pedí",
                "Error de cobro",
                "Devuelto en tienda",
                "Duplicado sospechoso",
                "Otro"
            ], key="dev_motivo")
            if st.button("Marcar como devolución"):
                if id_dev:
                    ok = mark_as_returned(id_dev, motivo)
                    if ok:
                        st.success("Devolución registrada. Aparecerá en el reporte diario.")
                        st.rerun()
                    else:
                        st.warning("Ya está marcada como devuelta.")


def page_categorias():
    st.header("Análisis por Categorías")
    transactions = load_transactions()
    if not transactions:
        st.info("No hay transacciones.")
        return

    df = pd.DataFrame(transactions)
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)

    today = datetime.now()
    this_month = today.strftime("%Y-%m")
    month_df = df[df["Mes"] == this_month] if "Mes" in df.columns else df

    if month_df.empty:
        st.info("No hay datos este mes.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Distribución del Gasto")
        cat_data = month_df.groupby("Categoria")["Monto"].sum().reset_index()
        cat_data = cat_data.sort_values("Monto", ascending=False)
        colors = [DEFAULT_CATEGORIES.get(c, {}).get("color", "#999") for c in cat_data["Categoria"]]
        fig = px.pie(cat_data, values="Monto", names="Categoria",
                     color_discrete_sequence=colors, template="plotly_dark")
        fig.update_layout(plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.subheader("Presupuesto vs Real")
        cat_config = get_categories_config()
        budget_data = []
        for cat in cat_data["Categoria"]:
            real = cat_data[cat_data["Categoria"] == cat]["Monto"].values[0]
            budget = cat_config.get(cat, {}).get("presupuesto", 0)
            budget_data.append({"Categoria": cat, "Real": real, "Presupuesto": budget})
        budget_df = pd.DataFrame(budget_data)
        if not budget_df.empty:
            budget_df = budget_df[budget_df["Presupuesto"] > 0]
            if not budget_df.empty:
                budget_df["Diferencia"] = budget_df["Presupuesto"] - budget_df["Real"]
                budget_df["Estado"] = budget_df["Diferencia"].apply(
                    lambda x: "Dentro" if x >= 0 else "Excedido"
                )
                fig = go.Figure()
                fig.add_trace(go.Bar(name="Real", x=budget_df["Categoria"],
                                     y=budget_df["Real"], marker_color="#ff6b35"))
                fig.add_trace(go.Bar(name="Presupuesto", x=budget_df["Categoria"],
                                     y=budget_df["Presupuesto"], marker_color="#3498db"))
                fig.update_layout(barmode="group", template="plotly_dark",
                                  plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Configura presupuestos en Configuración.")

    st.divider()
    st.subheader("Detalle por Categoría")
    for cat in cat_data["Categoria"]:
        cat_total = cat_data[cat_data["Categoria"] == cat]["Monto"].values[0]
        color = DEFAULT_CATEGORIES.get(cat, {}).get("color", "#999")
        with st.expander(f"{cat} - {fmt_cop(cat_total)}"):
            cat_txns = month_df[month_df["Categoria"] == cat]
            top_merchants = cat_txns.groupby("Comercio")["Monto"].sum().reset_index()
            top_merchants = top_merchants.sort_values("Monto", ascending=False)
            st.dataframe(top_merchants, width="stretch",
                         column_config={"Monto": st.column_config.NumberColumn(format="$%d")})


def page_comparacion():
    st.header("Comparación Mes a Mes")
    transactions = load_transactions()
    if not transactions:
        st.info("No hay transacciones.")
        return

    df = pd.DataFrame(transactions)
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)

    if "Mes" not in df.columns:
        st.info("No hay datos.")
        return

    meses = sorted(df["Mes"].unique())
    if len(meses) < 2:
        st.info("Necesitas al menos 2 meses de datos para comparar.")
        return

    mes1 = st.selectbox("Mes 1", meses, index=len(meses) - 2, key="comp1")
    mes2 = st.selectbox("Mes 2", meses, index=len(meses) - 1, key="comp2")

    df1 = df[df["Mes"] == mes1]
    df2 = df[df["Mes"] == mes2]

    col1, col2, col3 = st.columns(3)
    total1 = df1["Monto"].sum()
    total2 = df2["Monto"].sum()
    diff = total2 - total1

    with col1:
        st.metric(mes1, fmt_cop(total1))
    with col2:
        st.metric(mes2, fmt_cop(total2))
    with col3:
        pct = (diff / total1 * 100) if total1 > 0 else 0
        st.metric("Diferencia", fmt_cop(diff), delta=f"{pct:+.1f}%")

    st.divider()

    st.subheader("Por Categoría")
    cats1 = df1.groupby("Categoria")["Monto"].sum().reset_index()
    cats1.columns = ["Categoria", mes1]
    cats2 = df2.groupby("Categoria")["Monto"].sum().reset_index()
    cats2.columns = ["Categoria", mes2]

    merged = pd.merge(cats1, cats2, on="Categoria", how="outer").fillna(0)
    merged["Diferencia"] = merged[mes2] - merged[mes1]
    merged = merged.sort_values("Diferencia", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(name=mes1, x=merged["Categoria"], y=merged[mes1], marker_color="#3498db"))
    fig.add_trace(go.Bar(name=mes2, x=merged["Categoria"], y=merged[mes2], marker_color="#ff6b35"))
    fig.update_layout(barmode="group", template="plotly_dark",
                      plot_bgcolor="#1a1d23", paper_bgcolor="#1a1d23")
    st.plotly_chart(fig, width="stretch")

    st.dataframe(merged, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="$%d") for c in merged.columns if c != "Categoria"})


def page_configuracion():
    st.header("Configuración")

    tab1, tab2, tab3, tab4 = st.tabs(["Sincronizar", "Entrada Manual", "Reglas", "Presupuestos"])

    with tab1:
        st.subheader("Sincronizar Emails")
        st.write("Lee los emails de notificación de Davivienda y RappiBank.")
        if st.button("Sincronizar Emails", type="primary"):
            new_count = sync_emails()
            if new_count > 0:
                st.success(f"{new_count} transacciones nuevas agregadas.")
            else:
                st.info("No se encontraron transacciones nuevas.")
            st.rerun()

        if st.button("Enviar Reporte Semanal"):
            transactions = load_transactions()
            if transactions:
                ok = send_weekly_report(transactions)
                if ok:
                    st.success("Reporte enviado a tu correo.")
                else:
                    st.error("Error enviando reporte.")

    with tab2:
        st.subheader("Agregar Gasto Manual")
        with st.form("manual_form"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=datetime.now())
                monto = st.number_input("Monto (COP)", min_value=0, step=1000)
            with col2:
                comercio = st.text_input("Comercio/Descripción")
                categoria = st.selectbox("Categoría", get_all_categories())
            notas = st.text_input("Notas (opcional)")
            submitted = st.form_submit_button("Agregar")
            if submitted:
                fecha_str = fecha.strftime("%Y/%m/%d")
                hora_str = datetime.now().strftime("%H:%M:%S")
                txn = {
                    "fecha": fecha_str,
                    "hora": hora_str,
                    "tarjeta": "",
                    "banco": "",
                    "monto": monto,
                    "comercio": comercio,
                    "categoria": categoria,
                    "subcategoria": "",
                    "fuente": "manual",
                    "notas": notas,
                }
                save_transactions([txn])
                st.success("Gasto agregado.")
                st.rerun()

        st.divider()
        st.subheader("Agregar Ingreso")
        with st.form("income_form"):
            col1, col2 = st.columns(2)
            with col1:
                inc_fecha = st.date_input("Fecha ingreso", value=datetime.now(), key="inc_fecha")
                inc_fuente = st.text_input("Fuente (ej: Nómina)")
            with col2:
                inc_monto = st.number_input("Monto (COP)", min_value=0, step=1000, key="inc_monto")
                inc_notas = st.text_input("Notas", key="inc_notas")
            if st.form_submit_button("Agregar Ingreso"):
                add_income(inc_fecha.strftime("%Y/%m/%d"), inc_fuente, inc_monto, inc_notas)
                st.success("Ingreso agregado.")
                st.rerun()

    with tab3:
        st.subheader("Reglas de Clasificación")
        rules = get_rules()
        if rules:
            rules_df = pd.DataFrame(rules)
            st.dataframe(rules_df, width="stretch")

        st.divider()
        st.write("Agregar nueva regla:")
        with st.form("rule_form"):
            keyword = st.text_input("Palabra clave (en comercio)")
            cat = st.selectbox("Categoría", get_all_categories(), key="rule_cat")
            if st.form_submit_button("Agregar Regla"):
                if keyword:
                    add_rule(keyword, cat, "manual")
                    st.success(f"Regla agregada: '{keyword}' → {cat}")
                    st.rerun()

    with tab4:
        st.subheader("Presupuestos Mensuales")
        st.write("Define cuánto quieres gastar por categoría al mes.")
        cat_config = get_categories_config()
        all_cats = get_all_categories()

        with st.form("budget_form"):
            budget_updates = {}
            for cat in all_cats:
                current = cat_config.get(cat, {}).get("presupuesto", DEFAULT_CATEGORIES.get(cat, {}).get("budget", 0))
                budget_updates[cat] = st.number_input(
                    f"{cat}", min_value=0, value=int(current), step=10000,
                    key=f"budget_{cat}"
                )
            if st.form_submit_button("Guardar Presupuestos"):
                sh = get_or_create_spreadsheet()
                ws = sh.worksheet("CATEGORIAS")
                all_vals = ws.get_all_values()
                for i, row in enumerate(all_vals[1:], start=2):
                    cat_name = row[0]
                    if cat_name in budget_updates:
                        ws.update_cell(i, 4, budget_updates[cat_name])
                st.success("Presupuestos actualizados.")
                st.rerun()




def page_duplicados():
    st.title("🔍 Verificación de Duplicados")
    st.markdown("Cargos repetidos se verifican contra los extractos reales de tarjeta.")

    dup_rows = get_duplicates()
    if not dup_rows:
        st.info("Sin duplicados pendientes.")
        return

    df = pd.DataFrame(dup_rows)
    estado = st.selectbox("Filtrar por estado", ["Todos", "pendiente", "verificado"])
    if estado != "Todos":
        df = df[df["Estado"] == estado]
    if df.empty:
        st.info("Sin resultados para el filtro.")
        return

    tipos = {"por_definir": "⏳ Por definir", "duplicado_real": "✅ Duplicado real", "duplicado_cancelado": "❌ Cancelado (sin cargo)"}
    status_map = {"pendiente": "⏳ Pendiente", "verificado": "✅ Verificado"}

    for _, row in df.iterrows():
        with st.expander(f"{row.get('Comercio','')} - ${float(row.get('Monto',0)):,.0f} x{row.get('NumTxns',1)}"):
            cols = st.columns(4)
            cols[0].metric("Fecha", row.get("FechaTxn", ""))
            cols[1].metric("Monto", fmt_cop(float(row.get("Monto", 0))))
            cols[2].metric("N° transacciones", row.get("NumTxns", 1))
            cols[3].metric("Tipo", tipos.get(row.get("Tipo", ""), row.get("Tipo", "")))

            if row.get("Tipo") and row.get("Tipo") != "por_definir":
                st.write(f"**Comentario:** {row.get('Comentario','')}")
                st.write(f"**Verificado en:** {row.get('VerificadoEn','')}")

            c1, c2, c3 = st.columns(3)
            grupo_id = row.get("ID")
            if c1.button(f"✅ Marcar real", key=f"real_{grupo_id}"):
                update_duplicate_status(grupo_id, "duplicado_real", "verificado", "Marcado manualmente", "manual")
                st.rerun()
            if c2.button(f"❌ Cancelado", key=f"canc_{grupo_id}"):
                update_duplicate_status(grupo_id, "duplicado_cancelado", "verificado", "Marcado manualmente", "manual")
                st.rerun()
            if c3.button(f"🔍 Verificar con extracto", key=f"ver_{grupo_id}"):
                stmts = get_statements()
                res = verify_duplicates([row], stmts)
                if res:
                    apply_verification(res)
                    st.success("Verificación completada")
                    st.rerun()

    if st.button("🔍 Verificar todos con extracto", type="primary"):
        pendientes = [r for r in dup_rows if r.get("Estado") == "pendiente"]
        if pendientes:
            stmts = get_statements()
            res = verify_duplicates(pendientes, stmts)
            st.success(f"{apply_verification(res)} duplicados actualizados")
            st.rerun()
        else:
            st.info("Sin duplicados pendientes")


def page_cuenta_ahorros():
    st.title("🏦 Cuenta de Ahorros")
    st.markdown("Trazabilidad de la cuenta 1620 a partir del extracto portafolio mensual.")

    savings = get_savings_rows()
    if not savings:
        st.info("Sin datos de cuenta de ahorros. Ejecuta la sincronización de extractos.")
        return

    df = pd.DataFrame(savings)
    if "Valor" in df.columns:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    if "Mes" in df.columns and "Mes" in df.columns:
        mes = st.selectbox("Mes", sorted(df["Mes"].unique(), reverse=True), index=0)
        dfm = df[df["Mes"] == mes]
    else:
        dfm = df

    ingresos = dfm[dfm["Tipo"] == "ingreso"]["Valor"].sum()
    gastos = dfm[dfm["Tipo"] == "gasto"]["Valor"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt_cop(ingresos))
    c2.metric("Egresos", fmt_cop(gastos))
    c3.metric("Flujo neto", fmt_cop(ingresos - gastos))

    st.subheader("Movimientos")
    disp = dfm[["Fecha", "Descripcion", "Tipo", "Valor", "Oficina"]].copy()
    st.dataframe(disp, use_container_width=True, hide_index=True)


def main():
    st.sidebar.title("MisGastos")
    st.sidebar.markdown("Control de gastos personales")

    if st.sidebar.button("Sincronizar Emails", type="primary"):
        new_count = sync_emails()
        if new_count > 0:
            st.sidebar.success(f"+{new_count} transacciones")
        else:
            st.sidebar.info("Sin nuevas transacciones")
        st.rerun()

    st.sidebar.divider()
    page = st.sidebar.radio(
        "Navegación",
        ["Resumen", "Detalle", "Categorías", "Comparación", "Duplicados", "Cuenta de Ahorros", "Configuración"],
        index=0,
    )

    st.sidebar.divider()
    transactions = load_transactions()
    if transactions:
        df = pd.DataFrame(transactions)
        if "Monto" in df.columns:
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
            total_all = df["Monto"].sum()
            st.sidebar.metric("Total Histórico", fmt_cop(total_all))
            st.sidebar.metric("Total Transacciones", len(df))

    if page == "Resumen":
        page_resumen()
    elif page == "Detalle":
        page_detalle()
    elif page == "Categorías":
        page_categorias()
    elif page == "Comparación":
        page_comparacion()
    elif page == "Duplicados":
        page_duplicados()
    elif page == "Cuenta de Ahorros":
        page_cuenta_ahorros()
    elif page == "Configuración":
        page_configuracion()


if __name__ == "__main__":
    main()
