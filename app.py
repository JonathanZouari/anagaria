"""Streamlit UI for planning a wardrobe in 3D. Run: streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

from model import DEFAULT_DESIGN, ITEM_LABELS, build_parts, cut_list, estimate_price, validate
from render import figure

LABEL_TO_TYPE = {v: k for k, v in ITEM_LABELS.items()}
ITEM_COLS = ["סוג", "גובה מהתחתית", "גובה מגירה"]
DRAWER_DEFAULT_H = 200

st.set_page_config(page_title="תכנון ארון בגדים", page_icon="🪚", layout="wide")
st.markdown("<style>.stApp{direction:rtl;text-align:right}</style>", unsafe_allow_html=True)

# "base" is the design the widgets start from; bumping "ver" re-creates all widgets after a load
if "base" not in st.session_state:
    st.session_state.base, st.session_state.ver = DEFAULT_DESIGN, 0
base, v = st.session_state.base, st.session_state.ver


def load_from_upload():
    up = st.sidebar.file_uploader("טעינת תכנון (JSON)", type="json")
    if up is None:
        return
    try:
        loaded = json.loads(up.getvalue())
    except (json.JSONDecodeError, UnicodeDecodeError):
        loaded = None
    errors = validate(loaded)
    if errors:
        st.sidebar.error("לא ניתן לטעון: " + "; ".join(errors))
    elif up.file_id != st.session_state.get("loaded_id"):
        st.session_state.loaded_id = up.file_id
        st.session_state.base, st.session_state.ver = loaded, v + 1
        st.rerun()


def sidebar_inputs():
    sb = st.sidebar
    sb.header("מידות הארון (מ\"מ)")
    dims = {
        "width": sb.number_input("רוחב", 300, 6000, int(base["width"]), 10, key=f"W{v}"),
        "height": sb.number_input("גובה", 300, 3000, int(base["height"]), 10, key=f"H{v}"),
        "depth": sb.number_input("עומק", 200, 1000, int(base["depth"]), 10, key=f"D{v}"),
        "thickness": sb.number_input("עובי לוח", 6, 40, int(base["thickness"]), 1, key=f"T{v}"),
        "back_thickness": sb.number_input("עובי גב", 3, 20, int(base["back_thickness"]), 1, key=f"B{v}"),
        "doors": sb.checkbox("לארון יש דלתות", bool(base["doors"]), key=f"doors{v}"),
    }
    with sb.expander("מחירון (₪)"):
        labels = {"board_m2": "לוח למ\"ר", "back_m2": "לוח דק למ\"ר", "drawer_unit": "זוג מסילות",
                  "rod_unit": "מוט תלייה", "hinge_unit": "ציר"}
        prices = {k: st.number_input(lbl, 0.0, 10000.0, float(base["prices"][k]), key=f"p_{k}{v}")
                  for k, lbl in labels.items()}
    n_cols = sb.number_input("מספר עמודות", 1, 8, len(base["columns"]), key=f"n{v}")
    return dims, prices, n_cols


def items_editor(items, key):
    df = pd.DataFrame(
        [[ITEM_LABELS[it["type"]], it["z"], it.get("h")] for it in items], columns=ITEM_COLS
    ).astype({ITEM_COLS[1]: "float", ITEM_COLS[2]: "float"})
    edited = st.data_editor(
        df, key=key, num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            ITEM_COLS[0]: st.column_config.SelectboxColumn(options=list(LABEL_TO_TYPE), required=True),
            ITEM_COLS[1]: st.column_config.NumberColumn(min_value=0, step=10, format="%d"),
            ITEM_COLS[2]: st.column_config.NumberColumn("גובה מגירה (רק למגירה)", min_value=0, step=10, format="%d"),
        },
    )
    rows = edited.dropna(subset=ITEM_COLS[:2]).to_dict("records")
    return [_row_to_item(r) for r in rows]


def _row_to_item(r):
    kind = LABEL_TO_TYPE[r[ITEM_COLS[0]]]
    item = {"type": kind, "z": int(r[ITEM_COLS[1]])}
    if kind != "drawer":
        return item
    h = r[ITEM_COLS[2]]
    return {**item, "h": int(h) if pd.notna(h) else DRAWER_DEFAULT_H}


def columns_inputs(dims, n_cols):
    t = dims["thickness"]
    free = dims["width"] - 2 * t - (n_cols - 1) * t
    cols = []
    for i in range(n_cols):
        bc = base["columns"][i] if i < len(base["columns"]) else {"width": 600, "items": []}
        with st.expander(f"עמודה {i + 1}", expanded=(i == 0)):
            if i < n_cols - 1:
                w = st.number_input("רוחב (מ\"מ)", 1, 5000, int(bc["width"]), 10, key=f"cw{i}_{v}")
            else:
                w = free - sum(c["width"] for c in cols)
                st.caption(f"רוחב מחושב אוטומטית: {w} מ\"מ")
            cols.append({"width": w, "items": items_editor(bc["items"], f"items{i}_{v}")})
    return cols


def show_results(design, show_doors):
    parts = build_parts(design)
    st.plotly_chart(figure(parts, show_doors), use_container_width=True)
    tab_cut, tab_price = st.tabs(["רשימת חיתוך", "הערכת מחיר"])
    with tab_cut:
        cl = cut_list(parts)
        st.dataframe(cl, hide_index=True, use_container_width=True)
        st.download_button("הורדת רשימת חיתוך (CSV)", cl.to_csv(index=False).encode("utf-8-sig"),
                           "cut_list.csv", "text/csv")
    with tab_price:
        price = estimate_price(parts, design)
        st.dataframe(pd.DataFrame(price["lines"]), hide_index=True, use_container_width=True)
        st.metric("סה\"כ משוער", f"₪{price['total']:,.0f}")


st.title("🪚 תכנון ארון בגדים")
load_from_upload()
dims, prices, n_cols = sidebar_inputs()
show_doors = st.sidebar.checkbox("הצג דלתות בתצוגה", True, disabled=not dims["doors"])

edit_area, view_area = st.columns([1, 2])
with edit_area:
    st.subheader("פנים הארון")
    st.caption("הגובה נמדד מתחתית הפנים של הארון, במ\"מ")
    design = {**dims, "columns": columns_inputs(dims, n_cols), "prices": prices}

errors = validate(design)
with view_area:
    if errors:
        for e in errors:
            st.error(e)
    else:
        show_results(design, show_doors)
        st.sidebar.download_button("שמירת תכנון (JSON)", json.dumps(design, ensure_ascii=False, indent=2),
                                   "wardrobe.json", "application/json")
