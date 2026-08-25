from config import DEFAULT_CATEGORIES


def classify_transaction(comercio, custom_rules=None):
    comercio_upper = comercio.upper().strip()

    if custom_rules:
        for rule in custom_rules:
            keyword = rule.get("palabra_clave", "").upper()
            if keyword and keyword in comercio_upper:
                return rule.get("categoria", "Otros")

    best_match = "Otros"
    best_score = 0

    for categoria, data in DEFAULT_CATEGORIES.items():
        for keyword in data.get("keywords", []):
            keyword_upper = keyword.upper()
            if keyword_upper in comercio_upper:
                score = len(keyword_upper)
                if score > best_score:
                    best_score = score
                    best_match = categoria

    return best_match


def classify_batch(transactions, custom_rules=None):
    for txn in transactions:
        txn["categoria"] = classify_transaction(txn.get("comercio", ""), custom_rules)
    return transactions


def get_category_color(categoria):
    data = DEFAULT_CATEGORIES.get(categoria, DEFAULT_CATEGORIES.get("Otros", {}))
    return data.get("color", "#95a5a6")


def get_category_budget(categoria):
    data = DEFAULT_CATEGORIES.get(categoria, {})
    return data.get("budget", 0)


def get_all_categories():
    return list(DEFAULT_CATEGORIES.keys())
