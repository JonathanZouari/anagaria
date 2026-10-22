# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Streamlit app for a carpentry shop to design wardrobes (columns with shelves / drawers / hanging rods) in 3D, with a cut list, price estimate and JSON save/load. UI text is Hebrew (RTL).

## Commands

```
pip install -r requirements.txt
streamlit run app.py                                  # http://localhost:8501
python -m pytest test_model.py                        # all tests
python -m pytest test_model.py -k overlap             # single test
```

`test_app_runs_without_errors` uses `streamlit.testing.v1.AppTest` to execute `app.py` headlessly, so UI regressions that raise show up in pytest.

## Workflow

1. Plan with Opus 5.5 (`claude-opus-5-5`); execute the plan with Sonnet 5.5 (`claude-sonnet-5-5`).
2. After executing, run the full test suite (`python -m pytest test_model.py`) and check for regressions — all previously passing tests must still pass.
3. Run the security review skill (`/security-review`) on the updated code.

## Architecture

Data flows one way: **design dict → parts → (figure | cut list | price)**.

- **design** is a plain JSON-serializable dict (see `DEFAULT_DESIGN` in `model.py`). It is the save/load file format, so changing its keys breaks saved files. All sizes are mm.
- **`model.py`** is pure logic with no Streamlit import:
  - `build_parts(design)` turns the design into axis-aligned boxes `{name, material, x, y, z, w, d, h}`.
  - Axes: x is width, y is depth with front = 0, z is height. Doors sit at y = -thickness.
  - Item `z` is measured from the inner bottom, which is the top of the bottom panel.
  - `name` is the Hebrew part label shown in the cut list.
  - `material` is one of `board | back | door | rod`. It drives the 3D color, the cut list (rods are excluded as hardware) and pricing.
- **The last column's width is never trusted from input.** `column_widths()` recomputes it from the outer width minus the other columns and the partitions. `app.py` mirrors this calculation to display it.
- **`validate(design)`** returns a list of Hebrew error strings and doubles as the guard for uploaded JSON: it catches malformed-structure exceptions and returns a generic error. `app.py` only builds parts and renders when this list is empty.
- **`render.py`** merges all parts of a material into one `Mesh3d` built from the unit-cube triangle indices. The vertex order must match `CUBE_I/J/K`. The camera faces the front (negative y).
- **`app.py` state pattern:**
  - `st.session_state.base` is the design the widgets are seeded from.
  - Every widget key is suffixed with `st.session_state.ver`. Loading a JSON file replaces `base` and bumps `ver`, which recreates all widgets.
  - The current design is rebuilt from widget return values on every run.
  - Widget `value`/`data` arguments come only from `base`, never from live values, so that Streamlit doesn't reset widgets mid-edit.
- The cut list CSV is encoded `utf-8-sig` so Hebrew opens correctly in Excel.
