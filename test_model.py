import json

from streamlit.testing.v1 import AppTest

from model import DEFAULT_DESIGN, build_parts, column_widths, cut_list, estimate_price, validate
from render import figure


def simple(**over):
    base = {
        "width": 1000, "height": 2000, "depth": 600, "thickness": 20, "back_thickness": 4,
        "doors": False, "columns": [{"width": 0, "items": []}],
        "prices": {"board_m2": 100, "back_m2": 10, "drawer_unit": 50, "rod_unit": 20, "hinge_unit": 5},
    }
    return {**base, **over}


def test_three_columns_fill_inner_width():
    d = DEFAULT_DESIGN
    widths = column_widths(d)
    assert sum(widths) + (len(widths) + 1) * d["thickness"] == d["width"]
    names = [p["name"] for p in build_parts(d)]
    assert names.count("דופן") == 2
    assert names.count("מחיצה") == 2
    assert names.count("דלת") == 3


def test_default_design_is_valid():
    assert validate(DEFAULT_DESIGN) == []


def test_item_above_height_is_error():
    d = simple(columns=[{"width": 0, "items": [{"type": "shelf", "z": 1970}]}])
    assert any("חורג" in e for e in validate(d))


def test_overlap_is_error():
    items = [{"type": "drawer", "z": 0, "h": 200}, {"type": "shelf", "z": 150}]
    assert any("חופפים" in e for e in validate(simple(columns=[{"width": 0, "items": items}])))


def test_negative_last_column_is_error():
    d = simple(columns=[{"width": 2000, "items": []}, {"width": 0, "items": []}])
    assert any("רוחב" in e for e in validate(d))


def test_garbage_is_rejected():
    assert validate(None) == ["קובץ התכנון אינו תקין"]
    assert validate({"width": 1}) == ["קובץ התכנון אינו תקין"]


def test_cut_list_groups_identical_boards():
    cl = cut_list(build_parts(simple()))
    sides = cl[cl["חלק"] == "דופן"]
    assert len(sides) == 1 and sides["כמות"].iloc[0] == 2
    assert tuple(sides[["אורך", "רוחב", "עובי"]].iloc[0]) == (2000, 596, 20)


def test_price_of_minimal_wardrobe():
    d = simple(doors=True)
    price = estimate_price(build_parts(d), d)
    sides = 2 * 2.0 * 0.596
    top_bottom = 2 * 0.96 * 0.596
    door = 0.997 * 1.997
    back = 1.0 * 2.0
    expected = round(round(sides + top_bottom + door, 2) * 100, 2) + round(back, 2) * 10 + 3 * 5
    assert price["total"] == round(expected, 2)


def test_json_roundtrip():
    assert json.loads(json.dumps(DEFAULT_DESIGN, ensure_ascii=False)) == DEFAULT_DESIGN


def test_figure_hides_doors():
    parts = build_parts(DEFAULT_DESIGN)
    assert "door" in [t.name for t in figure(parts, True).data]
    assert "door" not in [t.name for t in figure(parts, False).data]


def test_app_runs_without_errors():
    at = AppTest.from_file("app.py").run(timeout=30)
    assert not at.exception
    assert not at.error
