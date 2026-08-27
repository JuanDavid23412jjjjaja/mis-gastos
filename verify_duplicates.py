import re


def _norm_desc(s):
    s = s.upper()
    s = re.sub(r"[\W_]+", " ", s)
    return " ".join(s.split()).strip()


def _same_comercio(dup_desc, stmt_desc, threshold=0.6):
    a = _norm_desc(dup_desc)
    b = _norm_desc(stmt_desc)
    if not a or not b:
        return False
    atokens = set(a.split())
    btokens = set(b.split())
    if not atokens:
        return False
    inter = atokens & btokens
    if not inter:
        return False
    # score by overlap of tokens in the txn comercio
    score = len(inter) / len(atokens)
    return score >= threshold


def _same_monto(dup_monto, stmt_valor, tol=0.5):
    # duplicate pair: 2 cargos del mismo valor; la cancelacion solo deja 1 en extracto.
    # buscamos cualquier cargo cuyo monto coincida dentro de tolerancia (fraccion por cuotas etc)
    try:
        return abs(float(dup_monto) - float(stmt_valor)) / max(float(dup_monto), 1) <= tol
    except:
        return False


def _same_day(dup_fecha, stmt_fecha):
    # formato fechas: 'YYYY/MM/DD'
    try:
        d = dup_fecha.strip().split("/")
        s = stmt_fecha.strip().split("/")
        if len(d) == 3 and len(s) == 3:
            # tolerancia de +/-1 dia
            from datetime import date
            dd = date(int(d[0]), int(d[1]), int(d[2]))
            sd = date(int(s[0]), int(s[1]), int(s[2]))
            return abs((dd - sd).days) <= 1
    except:
        pass
    return False


def verify_duplicates(dup_rows, stmt_rows):
    results = []
    for dup in dup_rows:
        if dup.get("Estado") != "pendiente":
            continue
        monto = dup.get("Monto", 0)
        fecha = dup.get("FechaTxn", "")
        comercio = dup.get("Comercio", "")
        match_found = False
        matched_stmt = None
        for s in stmt_rows:
            if _same_monto(monto, s.get("Valor", 0)) and _same_day(fecha, s.get("Fecha", "")):
                if _same_comercio(comercio, s.get("Descripcion", "")):
                    match_found = True
                    matched_stmt = s
                    break
        if match_found:
            results.append({
                "grupo_id": dup.get("ID"),
                "tipo": "duplicado_real",
                "estado": "verificado",
                "comentario": f"Confirmado en extracto ({matched_stmt.get('Fuente','')})",
                "verificado_en": matched_stmt.get("Fuente", ""),
            })
        else:
            results.append({
                "grupo_id": dup.get("ID"),
                "tipo": "duplicado_cancelado",
                "estado": "verificado",
                "comentario": "No aparece en extracto -> probable cargo cancelado/anulado",
                "verificado_en": "",
            })
    return results


def apply_verification(results):
    from sheets_db import update_duplicate_status
    count = 0
    for r in results:
        ok = update_duplicate_status(
            r["grupo_id"], r["tipo"], r["estado"],
            comentario=r.get("comentario", ""), verificad_en=r.get("verificado_en", "")
        )
        if ok:
            count += 1
    return count
