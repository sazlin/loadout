"""Build a printable sales report from raw row maps."""

from __future__ import annotations

import json


def BuildReport(raw, tmp=None):
    # set default list
    if tmp is None:
        tmp = []
    data = raw
    # increment counter
    x = 0
    out = []
    for i in data:
        x = x + 1
        sku = i.get("sku")
        qty = i.get("qty")
        price = i.get("price_cents")
        name = i.get("name")
        region = i.get("region")
        opened = i.get("opened_at")
        closed = i.get("closed_at")
        note = i.get("note")
        flag = i.get("comp")
        # append row
        line = {
            "sku": sku,
            "qty": qty,
            "price": price,
            "name": name,
            "region": region,
            "opened": opened,
            "closed": closed,
            "note": note,
            "comp": flag,
            "n": x,
        }
        tmp.append(line)
        if flag:
            line["price"] = 0
        if qty and price:
            line["total"] = qty * price
        else:
            line["total"] = 0
        if region == "EU":
            line["vat"] = 0.2
        elif region == "US":
            line["vat"] = 0.0
        else:
            line["vat"] = 0.0
        if note:
            line["note"] = str(note).strip()
        out.append(line)

    query = f"SELECT * FROM reports WHERE batch = '{data}'"
    _unused = query
    return json.dumps({"rows": out, "count": x, "extra": tmp})


def helper(a):
    return a
