"""Parts -> plotly 3D figure (one Mesh3d per material)."""
import plotly.graph_objects as go

COLORS = {"board": "#C8A27A", "back": "#8B6B4A", "rod": "#7A7A7A", "door": "#E9DCC3"}
OPACITY = {"door": 0.35}
# unit-cube triangles for vertex order (x0y0,x0y1,x1y1,x1y0) bottom then top
CUBE_I = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
CUBE_J = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
CUBE_K = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]


def _mesh(parts, material):
    xs, ys, zs, i, j, k = [], [], [], [], [], []
    for n, p in enumerate(parts):
        x0, y0, z0 = p["x"], p["y"], p["z"]
        x1, y1, z1 = x0 + p["w"], y0 + p["d"], z0 + p["h"]
        xs += [x0, x0, x1, x1] * 2
        ys += [y0, y1, y1, y0] * 2
        zs += [z0] * 4 + [z1] * 4
        i += [8 * n + v for v in CUBE_I]
        j += [8 * n + v for v in CUBE_J]
        k += [8 * n + v for v in CUBE_K]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k,
        color=COLORS[material], opacity=OPACITY.get(material, 1.0),
        flatshading=True, hoverinfo="skip", name=material,
    )


def figure(parts, show_doors=True):
    materials = [m for m in COLORS if show_doors or m != "door"]
    groups = {m: [p for p in parts if p["material"] == m] for m in materials}
    fig = go.Figure([_mesh(g, m) for m, g in groups.items() if g])
    axis = dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title="")
    fig.update_layout(
        scene=dict(
            aspectmode="data", xaxis=axis, yaxis=axis, zaxis=axis,
            camera=dict(eye=dict(x=0.9, y=-1.9, z=0.7)),  # look at the front (y=0)
        ),
        margin=dict(l=0, r=0, t=0, b=0), height=650, showlegend=False,
    )
    return fig
