"""Wardrobe geometry: design dict -> board parts, validation, cut list and price.

Axes (mm): x = width (left->right), y = depth (front=0 -> back), z = height (floor=0).
Item "z" values are measured from the inner bottom of the wardrobe.
"""
import math

import pandas as pd

ROD_SIZE = 25
DOOR_GAP = 3
SLIDE_GAP = 13  # drawer slide clearance on each side
DRAWER_MIN_H = 80

ITEM_LABELS = {"shelf": "מדף", "drawer": "מגירה", "rod": "מוט תלייה"}
MATERIAL_LABELS = {"board": "לוח", "back": "לוח דק (גב/תחתית מגירה)", "door": "דלת"}

DEFAULT_DESIGN = {
    "width": 2400, "height": 2400, "depth": 600,
    "thickness": 18, "back_thickness": 3,
    "doors": True,
    "columns": [
        {"width": 776, "items": [{"type": "rod", "z": 1700}, {"type": "shelf", "z": 1950}]},
        {"width": 776, "items": [
            {"type": "drawer", "z": 0, "h": 200},
            {"type": "drawer", "z": 210, "h": 200},
            {"type": "shelf", "z": 800},
            {"type": "shelf", "z": 1200},
            {"type": "shelf", "z": 1600},
            {"type": "shelf", "z": 1950},
        ]},
        {"width": 776, "items": [{"type": "rod", "z": 1700}, {"type": "shelf", "z": 1950}]},
    ],
    "prices": {"board_m2": 120, "back_m2": 40, "drawer_unit": 80, "rod_unit": 30, "hinge_unit": 8},
}


def _box(name, material, x, y, z, w, d, h):
    return {"name": name, "material": material, "x": x, "y": y, "z": z, "w": w, "d": d, "h": h}


def column_widths(design):
    """Widths of all columns; the last one fills whatever inner width is left."""
    t = design["thickness"]
    cols = design["columns"]
    free = design["width"] - 2 * t - (len(cols) - 1) * t
    fixed = [c["width"] for c in cols[:-1]]
    return fixed + [free - sum(fixed)]


def column_starts(design):
    t = design["thickness"]
    widths = column_widths(design)
    return [t + sum(widths[:i]) + i * t for i in range(len(widths))]


def item_extent(item, t):
    """(bottom, top) of an item, relative to the inner bottom."""
    size = {"shelf": t, "rod": ROD_SIZE, "drawer": item.get("h", 0)}[item["type"]]
    return item["z"], item["z"] + size


def _drawer_parts(item, x, w, t, bt, inner_d):
    h = item["h"]
    z0 = t + item["z"]
    box_h, box_d = h - 40, inner_d - t - 20
    bx, bw, by, bz = x + SLIDE_GAP, w - 2 * SLIDE_GAP, t, z0 + 20
    return [
        _box("חזית מגירה", "board", x, 0, z0, w, t, h),
        _box("דופן מגירה", "board", bx, by, bz, t, box_d, box_h),
        _box("דופן מגירה", "board", bx + bw - t, by, bz, t, box_d, box_h),
        _box("גב מגירה", "board", bx + t, by + box_d - t, bz, bw - 2 * t, t, box_h),
        _box("תחתית מגירה", "back", bx + t, by, bz, bw - 2 * t, box_d - t, bt),
    ]


def _item_parts(item, x, w, t, bt, inner_d):
    z0 = t + item["z"]
    if item["type"] == "shelf":
        return [_box("מדף", "board", x, 0, z0, w, inner_d, t)]
    if item["type"] == "rod":
        return [_box("מוט תלייה", "rod", x, inner_d / 2 - ROD_SIZE / 2, z0, w, ROD_SIZE, ROD_SIZE)]
    return _drawer_parts(item, x, w, t, bt, inner_d)


def _door_parts(design):
    W, H, t = design["width"], design["height"], design["thickness"]
    starts, widths = column_starts(design), column_widths(design)
    # overlay doors meet at the middle of each partition
    edges = [0] + [x + w + t / 2 for x, w in zip(starts[:-1], widths[:-1])] + [W]
    return [
        _box("דלת", "door", a + DOOR_GAP / 2, -t, DOOR_GAP / 2, b - a - DOOR_GAP, t, H - DOOR_GAP)
        for a, b in zip(edges, edges[1:])
    ]


def build_parts(design):
    W, H, D = design["width"], design["height"], design["depth"]
    t, bt = design["thickness"], design["back_thickness"]
    inner_h, inner_d = H - 2 * t, D - bt
    carcass = [
        _box("דופן", "board", 0, 0, 0, t, inner_d, H),
        _box("דופן", "board", W - t, 0, 0, t, inner_d, H),
        _box("תקרה", "board", t, 0, H - t, W - 2 * t, inner_d, t),
        _box("תחתית", "board", t, 0, 0, W - 2 * t, inner_d, t),
        _box("גב", "back", 0, inner_d, 0, W, bt, H),
    ]
    cols = list(zip(column_starts(design), column_widths(design), design["columns"]))
    partitions = [_box("מחיצה", "board", x + w, 0, t, t, inner_d, inner_h) for x, w, _ in cols[:-1]]
    items = [p for x, w, c in cols for it in c["items"] for p in _item_parts(it, x, w, t, bt, inner_d)]
    doors = _door_parts(design) if design["doors"] else []
    return carcass + partitions + items + doors


def _validate(design):
    W, H, D = design["width"], design["height"], design["depth"]
    t, bt = design["thickness"], design["back_thickness"]
    if min(W, H, D, t, bt) <= 0:
        return ["כל המידות והעוביים חייבים להיות חיוביים"]
    if bt >= D or 4 * t >= min(W, H):
        return ["העובי גדול מדי ביחס למידות הארון"]
    if not design["columns"]:
        return ["צריך לפחות עמודה אחת"]
    errors = []
    inner_h = H - 2 * t
    for n, (w, col) in enumerate(zip(column_widths(design), design["columns"]), start=1):
        if w <= 0:
            errors.append(f"עמודה {n}: הרוחב יוצא {w} מ\"מ – הקטינו את רוחב העמודות האחרות")
        spans = []
        for it in col["items"]:
            if it["type"] not in ITEM_LABELS:
                errors.append(f"עמודה {n}: סוג רכיב לא מוכר '{it['type']}'")
                continue
            label = ITEM_LABELS[it["type"]]
            if it["type"] == "drawer" and it["h"] < DRAWER_MIN_H:
                errors.append(f"עמודה {n}: גובה מגירה מינימלי הוא {DRAWER_MIN_H} מ\"מ")
            lo, hi = item_extent(it, t)
            if lo < 0 or hi > inner_h:
                errors.append(f"עמודה {n}: {label} בגובה {lo} חורג מגובה הפנים ({inner_h} מ\"מ)")
            spans.append((lo, hi, label))
        spans.sort()
        for (_, hi1, l1), (lo2, _, l2) in zip(spans, spans[1:]):
            if lo2 < hi1:
                errors.append(f"עמודה {n}: {l1} ו{l2} חופפים (גובה {lo2})")
    return errors


def validate(design):
    """Hebrew error messages; empty list means the design is buildable."""
    try:
        return _validate(design)
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["קובץ התכנון אינו תקין"]


def _board_dims(p):
    th, wd, ln = sorted((p["w"], p["d"], p["h"]))
    return round(ln), round(wd), round(th)


def cut_list(parts):
    rows = [
        dict(zip(["חלק", "חומר", "אורך", "רוחב", "עובי"], [p["name"], MATERIAL_LABELS[p["material"]], *_board_dims(p)]))
        for p in parts if p["material"] != "rod"
    ]
    keys = ["חלק", "חומר", "אורך", "רוחב", "עובי"]
    return pd.DataFrame(rows).groupby(keys, as_index=False, sort=False).size().rename(columns={"size": "כמות"})


def _area_m2(parts, materials):
    return sum(ln * wd for ln, wd, _ in (_board_dims(p) for p in parts if p["material"] in materials)) / 1e6


def hinges_for(door_h):
    return max(2, math.ceil(door_h / 800))


def estimate_price(parts, design):
    pr = design["prices"]
    items = [it["type"] for c in design["columns"] for it in c["items"]]
    hinges = sum(hinges_for(p["h"]) for p in parts if p["material"] == "door")
    lines = [
        ("לוחות (מ\"ר)", round(_area_m2(parts, {"board", "door"}), 2), pr["board_m2"]),
        ("לוח דק (מ\"ר)", round(_area_m2(parts, {"back"}), 2), pr["back_m2"]),
        ("מסילות מגירה (זוג)", items.count("drawer"), pr["drawer_unit"]),
        ("מוטות תלייה", items.count("rod"), pr["rod_unit"]),
        ("צירים", hinges, pr["hinge_unit"]),
    ]
    rows = [{"פריט": name, "כמות": qty, "מחיר ליחידה": unit, "סה\"כ": round(qty * unit, 2)} for name, qty, unit in lines]
    return {"lines": rows, "total": round(sum(r["סה\"כ"] for r in rows), 2)}
