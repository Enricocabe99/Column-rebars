import streamlit as st
import plotly.graph_objects as go
import numpy as np
from dataclasses import dataclass, field, asdict
import datetime
import json
from collections import Counter

from pdf_export import generate_pdf

st.set_page_config(page_title="Armature Pilastro 3D",
                   layout="wide", initial_sidebar_state="collapsed")
st.title("🏗️ Visualizzatore 3D — Armature di un Pilastro in c.a.")

# ============================================================
# COSTANTI MATERIALI
# ============================================================
CLS_KN_M3 = 24.0
CLS_KG_M3 = 2400.0
STEEL_KN_M3 = 78.5
STEEL_KG_M3 = 7850.0

# ============================================================
# 1) MODELLO DATI
# ============================================================
@dataclass
class CornerBars:
    diameter_mm: float = 26.0
    coupled: bool = False

@dataclass
class IntermediateBars:
    n_bars: int = 2
    diameter_mm: float = 24.0
    coupled: bool = False
    spacing_mode: str = "uniform"
    custom_spacings: tuple = ()

@dataclass
class ExtraBar:
    distance_cm: float = 5.0
    diameter_mm: float = 20.0
    mirror: bool = True

@dataclass
class LongitudinalLayout:
    corner: CornerBars = field(default_factory=CornerBars)
    intermediate: IntermediateBars = field(default_factory=IntermediateBars)
    extras: list = field(default_factory=list)

@dataclass
class Foundation:
    tipo: str = "nessuna"
    anchorage_length_cm: float = 40.0
    bicchiere_depth_cm: float = 120.0

@dataclass
class Hooks:
    enabled: bool = False
    diameter_mm: float = 8.0

@dataclass
class Forks:
    enabled: bool = False
    n_per_side: int = 2
    diameter_mm: float = 16.0
    length_cm: float = 80.0

@dataclass
class TieRod:
    enabled: bool = False
    diameter_mm: float = 24.0
    protrusion_cm: float = 30.0
    embedment_cm: float = 90.0
    offset_cm: float = 12.0

@dataclass
class MensolaRebar:
    cover_cm: float = 3.0
    n_top_bars: int = 3
    d_top_mm: float = 16.0
    vertical_anchorage_enabled: bool = False
    vertical_anchorage_cm: float = 50.0
    return_enabled: bool = False
    stirrup_h_pitch_cm: float = 15.0
    stirrup_h_d_mm: float = 8.0
    stirrup_v_pitch_cm: float = 15.0
    stirrup_v_d_mm: float = 8.0
    tirafondi_enabled: bool = False
    n_tirafondi: int = 2
    d_tirafondi_mm: float = 24.0
    tir_dist_testa_cm: float = 10.0
    tir_dist_bordo_cm: float = 12.0
    tir_prof_dado_cm: float = 15.0
    tir_sporgenza_cm: float = 50.0

@dataclass
class Mensola:
    lato: str = "x+"
    sporgenza_cm: float = 40.0
    larghezza_cm: float = 40.0
    quota_cm: float = 100.0
    altezza_cm: float = 30.0
    rastremata: bool = False
    altezza_base_cm: float = 50.0
    doppia: bool = False
    rebar: MensolaRebar = field(default_factory=MensolaRebar)

@dataclass
class StirrupZone:
    diameter_mm: float = 8.0
    pitch_cm: float = 15.0

@dataclass
class DenseZone:
    enabled: bool = False
    diameter_mm: float = 8.0
    pitch_cm: float = 10.0
    length_cm: float = 0.0

@dataclass
class Stirrups:
    hooks: Hooks = field(default_factory=Hooks)
    ductile_zone_length_cm: float = 60.0
    head_zone_length_cm: float = 60.0
    ductile: StirrupZone = field(default_factory=lambda: StirrupZone(8.0, 10.0))
    head: StirrupZone = field(default_factory=lambda: StirrupZone(8.0, 10.0))
    minimum: StirrupZone = field(default_factory=lambda: StirrupZone(8.0, 15.0))
    embedded: StirrupZone = field(default_factory=lambda: StirrupZone(8.0, 10.0))
    dense_zones: DenseZone = field(default_factory=DenseZone)

@dataclass
class ColumnModel:
    b_cm: float = 40.0
    h_cm: float = 40.0
    H_cm: float = 300.0
    cover_cm: float = 3.0
    longitudinal: LongitudinalLayout = field(default_factory=LongitudinalLayout)
    stirrups: Stirrups = field(default_factory=Stirrups)
    foundation: Foundation = field(default_factory=Foundation)
    forks: Forks = field(default_factory=Forks)
    tie_rods: TieRod = field(default_factory=TieRod)
    mensole: list = field(default_factory=list)

# ============================================================
# GESTIONE SESSIONE / SALVATAGGIO
# ============================================================
DEFAULT_PARAMS = {
    "nome_progetto": "", "descrizione_progetto": "",
    "b_cm": 70.0, "h_cm": 70.0, "H_cm": 400.0, "cover": 3.0,
    "tipo_fond": "nessuna", "anchorage": 40.0, "bicchiere_depth": 120.0,
    "d_corner": 26.0, "coupled_corner": False,
    "n_int": 2, "d_int": 24.0, "coupled_int": False,
    "spacing_mode_ui": "Uniforme", "custom_txt": "",
    "duct_len": 60.0, "duct_d": 8.0, "duct_p": 10.0,
    "head_len": 60.0, "head_d": 8.0, "head_p": 10.0,
    "min_d": 8.0, "min_p": 15.0,
    "emb_d": 8.0, "emb_p": 10.0,
    "hooks_enabled": False, "hook_dia": 8.0,
    "forks_enabled": False, "n_forks": 2, "fork_dia": 16.0, "fork_length": 80.0,
    "tie_enabled": False, "tie_d": 24.0, "tie_off": 12.0,
    "tie_prot": 30.0, "tie_emb": 90.0,
    "dense_enabled": False, "dense_d": 8.0, "dense_p": 10.0, "dense_len": 0.0,
    "pdf_show_3d": True, "pdf_3d_opacity": 0.08,
    "show_concrete": True, "opacity_cls": 0.15, "show_foundation": True,
    "show_mensole": True, "mensole_opacity": 0.55,
    "show_column_edges": False, "column_edges_width": 3,
    "show_mensole_edges": False, "mensole_edges_width": 3,
    "show_bars": True, "show_stirrups": True, "show_hooks_3d": True,
    "show_forks_3d": True, "show_ties_3d": True,
    "show_men_top": True, "show_men_sh": True, "show_men_sv": True,
    "show_men_tir": True, "show_dense": True,
    "real_prop": True, "grid_on": True, "auto_fit": True, "zoom_factor": 1.0,
}

if "load_token" not in st.session_state:
    st.session_state.load_token = 0
if "loaded_params" not in st.session_state:
    st.session_state.loaded_params = {}
if "extras" not in st.session_state:
    st.session_state.extras = []
if "extras_next_id" not in st.session_state:
    st.session_state.extras_next_id = 0
if "mensole" not in st.session_state:
    st.session_state.mensole = []
if "mensole_next_id" not in st.session_state:
    st.session_state.mensole_next_id = 0
if "view_preset" not in st.session_state:
    st.session_state.view_preset = "3d"


def get_param(key, default=None):
    lp = st.session_state.loaded_params
    if key in lp:
        return lp[key]
    if default is not None:
        return default
    return DEFAULT_PARAMS.get(key)


def widget_key(base):
    return f"{base}__tok{st.session_state.load_token}"


def _apply_loaded_params(params):
    st.session_state.loaded_params = dict(params)
    st.session_state.load_token += 1


def _reset_extras_from_list(extras_data):
    new_extras = []
    next_id = 0
    for ex in extras_data:
        new_extras.append({
            "id": next_id,
            "distance_cm": float(ex.get("distance_cm", 5.0)),
            "diameter_mm": float(ex.get("diameter_mm", 20.0)),
            "mirror": bool(ex.get("mirror", True)),
        })
        next_id += 1
    st.session_state.extras = new_extras
    st.session_state.extras_next_id = next_id


def _reset_mensole_from_list(mensole_data):
    new_mensole = []
    next_id = 0
    for men in mensole_data:
        rb = men.get("rebar", {}) or {}
        new_mensole.append({
            "id": next_id,
            "lato": men.get("lato", "x+"),
            "sporgenza_cm": float(men.get("sporgenza_cm", 40.0)),
            "larghezza_cm": float(men.get("larghezza_cm", 40.0)),
            "quota_cm": float(men.get("quota_cm", 100.0)),
            "altezza_cm": float(men.get("altezza_cm", 30.0)),
            "rastremata": bool(men.get("rastremata", False)),
            "altezza_base_cm": float(men.get("altezza_base_cm", 50.0)),
            "doppia": bool(men.get("doppia", False)),
            "rebar": {
                "cover_cm": float(rb.get("cover_cm", 3.0)),
                "n_top_bars": int(rb.get("n_top_bars", 3)),
                "d_top_mm": float(rb.get("d_top_mm", 16.0)),
                "vertical_anchorage_enabled": bool(rb.get("vertical_anchorage_enabled", False)),
                "vertical_anchorage_cm": float(rb.get("vertical_anchorage_cm", 50.0)),
                "return_enabled": bool(rb.get("return_enabled", False)),
                "stirrup_h_pitch_cm": float(rb.get("stirrup_h_pitch_cm", 15.0)),
                "stirrup_h_d_mm": float(rb.get("stirrup_h_d_mm", 8.0)),
                "stirrup_v_pitch_cm": float(rb.get("stirrup_v_pitch_cm", 15.0)),
                "stirrup_v_d_mm": float(rb.get("stirrup_v_d_mm", 8.0)),
                "tirafondi_enabled": bool(rb.get("tirafondi_enabled", False)),
                "n_tirafondi": int(rb.get("n_tirafondi", 2)),
                "d_tirafondi_mm": float(rb.get("d_tirafondi_mm", 24.0)),
                "tir_dist_testa_cm": float(rb.get("tir_dist_testa_cm", 10.0)),
                "tir_dist_bordo_cm": float(rb.get("tir_dist_bordo_cm", 12.0)),
                "tir_prof_dado_cm": float(rb.get("tir_prof_dado_cm", 15.0)),
                "tir_sporgenza_cm": float(rb.get("tir_sporgenza_cm", 50.0)),
            },
        })
        next_id += 1
    st.session_state.mensole = new_mensole
    st.session_state.mensole_next_id = next_id


# ============================================================
# 2) GEOMETRIA DI BASE
# ============================================================
def cylinder_geometry(p1, p2, radius, n_seg=10):
    p1 = np.asarray(p1, float); p2 = np.asarray(p2, float)
    v = p2 - p1; L = np.linalg.norm(v)
    if L < 1e-9:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=int)
    v /= L
    ref = np.array([1., 0., 0.]) if abs(v[0]) < 0.9 else np.array([0., 1., 0.])
    u = np.cross(v, ref); u /= np.linalg.norm(u)
    w = np.cross(v, u)
    theta = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
    c, s = np.cos(theta), np.sin(theta)
    r1 = p1 + radius * (c[:, None] * u + s[:, None] * w)
    r2 = p2 + radius * (c[:, None] * u + s[:, None] * w)
    verts = np.vstack([r1, r2, p1[None, :], p2[None, :]])
    faces = []
    for i in range(n_seg):
        n = (i + 1) % n_seg
        faces += [[i, n, n_seg + i], [n, n_seg + n, n_seg + i]]
    c1, c2 = 2 * n_seg, 2 * n_seg + 1
    for i in range(n_seg):
        n = (i + 1) % n_seg
        faces += [[c1, n, i], [c2, n_seg + i, n_seg + n]]
    return verts, np.array(faces, dtype=int)

def merge_geometries(geoms):
    vs, fs, off = [], [], 0
    for v, f in geoms:
        if len(v) == 0:
            continue
        vs.append(v); fs.append(f + off); off += len(v)
    if not vs:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=int)
    return np.vstack(vs), np.vstack(fs)

def make_mesh_trace(geoms, color, name=None, opacity=1.0, showlegend=True):
    v, f = merge_geometries(geoms)
    if len(v) == 0:
        return None
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=f[:, 0], j=f[:, 1], k=f[:, 2],
        color=color, opacity=opacity, flatshading=True,
        showlegend=showlegend and (name is not None), name=name or "",
        hoverinfo='name' if name else 'skip',
        lighting=dict(ambient=0.55, diffuse=0.9, specular=0.3, roughness=0.5))

def make_edges_trace(segments, color="black", name=None, line_width=3):
    if not segments:
        return None
    xs, ys, zs = [], [], []
    for (p1, p2) in segments:
        xs.extend([p1[0], p2[0], None])
        ys.extend([p1[1], p2[1], None])
        zs.extend([p1[2], p2[2], None])
    return go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='lines',
        line=dict(color=color, width=line_width),
        name=name or "",
        showlegend=(name is not None),
        hoverinfo='skip',
    )

def box_geometry(x0, y0, z0, dx, dy, dz):
    v = np.array([
        [x0, y0, z0], [x0 + dx, y0, z0], [x0 + dx, y0 + dy, z0], [x0, y0 + dy, z0],
        [x0, y0, z0 + dz], [x0 + dx, y0, z0 + dz],
        [x0 + dx, y0 + dy, z0 + dz], [x0, y0 + dy, z0 + dz]])
    f = np.array([
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [3, 2, 6], [3, 6, 7],
        [0, 3, 7], [0, 7, 4], [1, 2, 6], [1, 6, 5]])
    return v, f

def build_box_edges(x0, y0, z0, dx, dy, dz):
    v = [
        (x0, y0, z0), (x0 + dx, y0, z0),
        (x0 + dx, y0 + dy, z0), (x0, y0 + dy, z0),
        (x0, y0, z0 + dz), (x0 + dx, y0, z0 + dz),
        (x0 + dx, y0 + dy, z0 + dz), (x0, y0 + dy, z0 + dz),
    ]
    edges_idx = [
        (0,1),(1,2),(2,3),(3,0),
        (4,5),(5,6),(6,7),(7,4),
        (0,4),(1,5),(2,6),(3,7),
    ]
    return [(v[i], v[j]) for (i, j) in edges_idx]

def _max_stirrup_d_cm(m):
    return max(
        m.stirrups.ductile.diameter_mm,
        m.stirrups.head.diameter_mm,
        m.stirrups.minimum.diameter_mm,
        m.stirrups.embedded.diameter_mm,
        m.stirrups.dense_zones.diameter_mm,
    ) / 10.0

# ============================================================
# 3) FERRI LONGITUDINALI
# ============================================================
def _custom_offsets(spacings, n, span):
    spacings = list(spacings)[:n]
    cum, acc = [], 0.0
    for s in spacings:
        acc += s
        cum.append(acc)
    if len(cum) < n:
        start = cum[-1] if cum else 0.0
        remaining = span - start
        m = n - len(cum)
        step = remaining / (m + 1)
        for _ in range(m):
            start += step
            cum.append(start)
    return cum

def _get_bar_z_range(model):
    if model.foundation.tipo == "armatubo":
        z_bot = -model.foundation.anchorage_length_cm
    else:
        z_bot = model.cover_cm
    z_top = model.H_cm - model.cover_cm
    return z_bot, z_top

def build_longitudinal_bars(m: ColumnModel):
    b, h, H, cover = m.b_cm, m.h_cm, m.H_cm, m.cover_cm
    lon = m.longitudinal
    ds = _max_stirrup_d_cm(m)
    z0, z1 = _get_bar_z_range(m)
    bars = []

    dc = lon.corner.diameter_mm / 10.0
    off_c = cover + ds + dc / 2
    corner_xy = [(off_c, off_c), (b - off_c, off_c),
                 (b - off_c, h - off_c), (off_c, h - off_c)]
    face_dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    for (cx, cy), (dx, dy) in zip(corner_xy, face_dirs):
        if lon.corner.coupled:
            for s in (-0.5, 0.5):
                px = cx + s * dc * dx
                py = cy + s * dc * dy
                bars.append(((px, py, z0), (px, py, z1), dc))
        else:
            bars.append(((cx, cy, z0), (cx, cy, z1), dc))

    di = lon.intermediate.diameter_mm / 10.0
    off_i = cover + ds + di / 2
    span_b = b - 2 * off_c
    span_h = h - 2 * off_c

    faces = [
        ("bottom", 1, off_i,         off_c,     +1, span_b),
        ("right",  0, b - off_i,     off_c,     +1, span_h),
        ("top",    1, h - off_i,     b - off_c, -1, span_b),
        ("left",   0, off_i,         h - off_c, -1, span_h),
    ]

    if lon.intermediate.n_bars > 0:
        if lon.intermediate.spacing_mode == "uniform":
            offs_b = list(np.linspace(0, span_b, lon.intermediate.n_bars + 2)[1:-1])
            offs_h = list(np.linspace(0, span_h, lon.intermediate.n_bars + 2)[1:-1])
        else:
            offs_b = _custom_offsets(lon.intermediate.custom_spacings,
                                     lon.intermediate.n_bars, span_b)
            offs_h = _custom_offsets(lon.intermediate.custom_spacings,
                                     lon.intermediate.n_bars, span_h)

        for name, fixed_axis, perp, ref, dir_sign, span in faces:
            offs = offs_b if name in ("bottom", "top") else offs_h
            for off in offs:
                pa = ref + dir_sign * off
                if fixed_axis == 1:
                    px, py = pa, perp
                else:
                    px, py = perp, pa
                if lon.intermediate.coupled:
                    half = di / 2
                    if fixed_axis == 1:
                        bars.append(((px - half, py, z0), (px - half, py, z1), di))
                        bars.append(((px + half, py, z0), (px + half, py, z1), di))
                    else:
                        bars.append(((px, py - half, z0), (px, py - half, z1), di))
                        bars.append(((px, py + half, z0), (px, py + half, z1), di))
                else:
                    bars.append(((px, py, z0), (px, py, z1), di))

    for extra in lon.extras:
        de = extra.diameter_mm / 10.0
        off_e = cover + ds + de / 2
        d = extra.distance_cm
        faces_e = [
            ("bottom", 1, off_e,         off_c,     +1, span_b),
            ("right",  0, b - off_e,     off_c,     +1, span_h),
            ("top",    1, h - off_e,     b - off_c, -1, span_b),
            ("left",   0, off_e,         h - off_c, -1, span_h),
        ]
        if d <= 0 or d > span_b or d > span_h:
            continue
        if extra.mirror:
            for name, fixed_axis, perp, ref, dir_sign, span in faces_e:
                for along in (d, span - d):
                    pa = ref + dir_sign * along
                    if fixed_axis == 1:
                        px, py = pa, perp
                    else:
                        px, py = perp, pa
                    bars.append(((px, py, z0), (px, py, z1), de))
        else:
            name, fixed_axis, perp, ref, dir_sign, span = faces_e[0]
            pa = ref + dir_sign * d
            if fixed_axis == 1:
                px, py = pa, perp
            else:
                px, py = perp, pa
            bars.append(((px, py, z0), (px, py, z1), de))

    return bars

# ============================================================
# 4) FASCE DI STAFFATURA
# ============================================================
def get_stirrup_zones(model):
    cover = model.cover_cm
    H = model.H_cm
    Ld = model.stirrups.ductile_zone_length_cm
    Lt = model.stirrups.head_zone_length_cm
    z_top_phys = H - cover

    zones = []
    if model.foundation.tipo == "bicchiere":
        d_bic = model.foundation.bicchiere_depth_cm
        zones.append(("embedded", cover, d_bic))
        zones.append(("ductile",  d_bic, d_bic + Ld))
        z_min_end = z_top_phys - Lt
        if z_min_end > d_bic + Ld:
            zones.append(("minimum", d_bic + Ld, z_min_end))
        zones.append(("head", z_min_end, z_top_phys))
    else:
        zones.append(("ductile", cover, cover + Ld))
        z_min_end = z_top_phys - Lt
        if z_min_end > cover + Ld:
            zones.append(("minimum", cover + Ld, z_min_end))
        zones.append(("head", z_min_end, z_top_phys))

    return [(n, z0, z1) for (n, z0, z1) in zones if z1 > z0]

def build_stirrups(m: ColumnModel):
    b, h, H, cover = m.b_cm, m.h_cm, m.H_cm, m.cover_cm
    zones = get_stirrup_zones(m)
    zone_cfgs = {
        "ductile":  m.stirrups.ductile,
        "head":     m.stirrups.head,
        "minimum":  m.stirrups.minimum,
        "embedded": m.stirrups.embedded,
    }

    segs = []
    seen_z = set()

    for name, z0, z1 in zones:
        cfg = zone_cfgs[name]
        ds = cfg.diameter_mm / 10.0
        r = ds / 2
        x0, x1 = cover + r, b - cover - r
        y0, y1 = cover + r, h - cover - r

        z_start_eff = max(z0, cover + r)
        z_end_eff = min(z1, H - cover - r)
        if z_end_eff - z_start_eff < 1e-3:
            continue

        pitch = cfg.pitch_cm
        n = max(1, int(round((z_end_eff - z_start_eff) / pitch)))
        z_levels = np.linspace(z_start_eff, z_end_eff, n + 1)

        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for z in z_levels:
            key = round(float(z), 3)
            if key in seen_z:
                continue
            seen_z.add(key)
            for i in range(4):
                a = corners[i]; b_ = corners[(i + 1) % 4]
                segs.append(((a[0], a[1], z), (b_[0], b_[1], z), ds))

    return segs

def build_dense_stirrups(m: ColumnModel, base_stirrups):
    dz = m.stirrups.dense_zones
    if not dz.enabled or not m.mensole:
        return []

    z_existing = sorted(set(round(s[0][2], 3) for s in base_stirrups))
    if len(z_existing) < 2:
        return []

    z_tops = []
    for men in m.mensole:
        g = _setup_side(m, men)
        z_tops.append(round(g['z_top'], 3))
    z_tops = sorted(set(z_tops))

    default_len = max(m.b_cm, m.h_cm)
    zone_len = dz.length_cm if dz.length_cm > 0 else default_len

    ds = dz.diameter_mm / 10.0
    r = ds / 2
    x0, x1 = m.cover_cm + r, m.b_cm - m.cover_cm - r
    y0, y1 = m.cover_cm + r, m.h_cm - m.cover_cm - r
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    segs = []
    seen = set()

    for z_top in z_tops:
        z_low = z_top
        z_high = min(z_top + zone_len, m.H_cm - m.cover_cm)
        if z_high <= z_low:
            continue

        z_in_zone = [z for z in z_existing if z >= z_low - 0.01 and z <= z_high + 0.01]
        if len(z_in_zone) < 2:
            below = [z for z in z_existing if z < z_low]
            above = [z for z in z_existing if z > z_high]
            z_a = below[-1] if below else None
            z_b = above[0] if above else None
            if z_a is not None and z_b is not None:
                z_in_zone = [z_a, z_b]
            else:
                continue

        for i in range(len(z_in_zone) - 1):
            z_a = z_in_zone[i]
            z_b = z_in_zone[i + 1]
            span = z_b - z_a
            if span <= 0.1:
                continue

            n = max(1, int(round(span / dz.pitch_cm)))
            for k in range(1, n):
                z_new = z_a + k * span / n
                key = round(z_new, 3)
                if key in seen:
                    continue
                if not (z_low - 0.01 <= z_new <= z_high + 0.01):
                    continue
                seen.add(key)
                for j in range(4):
                    a = corners[j]; b_ = corners[(j + 1) % 4]
                    segs.append(((a[0], a[1], z_new), (b_[0], b_[1], z_new), ds))

    return segs

def build_all_stirrups(m: ColumnModel):
    base = build_stirrups(m)
    dense = build_dense_stirrups(m, base)
    return base, dense

# ============================================================
# 5) GANCI
# ============================================================
def _get_ductile_zone(model):
    Ld = model.stirrups.ductile_zone_length_cm
    if model.foundation.tipo == "bicchiere":
        z_low = model.foundation.bicchiere_depth_cm
        z_high = z_low + Ld
    else:
        z_low = model.cover_cm
        z_high = z_low + Ld
    return z_low, z_high

def build_hooks(m: ColumnModel, stirrup_segments):
    if not m.stirrups.hooks.enabled:
        return []
    if m.longitudinal.intermediate.n_bars == 0:
        return []

    b, h, cover = m.b_cm, m.h_cm, m.cover_cm
    ds = _max_stirrup_d_cm(m)
    dh = m.stirrups.hooks.diameter_mm / 10.0
    di = m.longitudinal.intermediate.diameter_mm / 10.0
    dc = m.longitudinal.corner.diameter_mm / 10.0

    off_c = cover + ds + dc / 2
    off_i = cover + ds + di / 2
    span_b = b - 2 * off_c
    span_h = h - 2 * off_c

    n = m.longitudinal.intermediate.n_bars
    if m.longitudinal.intermediate.spacing_mode == "uniform":
        offsets_b = list(np.linspace(0, span_b, n + 2)[1:-1])
        offsets_h = list(np.linspace(0, span_h, n + 2)[1:-1])
    else:
        offsets_b = _custom_offsets(m.longitudinal.intermediate.custom_spacings, n, span_b)
        offsets_h = _custom_offsets(m.longitudinal.intermediate.custom_spacings, n, span_h)

    z_low, z_high = _get_ductile_zone(m)
    z_all = sorted(set(round(s[0][2], 4) for s in stirrup_segments))
    z_ductile = [z for z in z_all if z_low <= z <= z_high]

    segs = []
    for z in z_ductile:
        for x_off in offsets_b:
            x = off_c + x_off
            segs.append(((x, off_i, z), (x, h - off_i, z), dh))
        for y_off in offsets_h:
            y = off_c + y_off
            segs.append(((off_i, y, z), (b - off_i, y, z), dh))
    return segs

# ============================================================
# 6) FORCHE
# ============================================================
def build_forks(m: ColumnModel):
    f = m.forks
    if not f.enabled or f.n_per_side <= 0:
        return []

    b, h, H, cover = m.b_cm, m.h_cm, m.H_cm, m.cover_cm
    ds = _max_stirrup_d_cm(m)
    df = f.diameter_mm / 10.0
    dc = m.longitudinal.corner.diameter_mm / 10.0
    L = f.length_cm

    z_top = (H - cover) + df / 2
    z_bot = max(z_top - L, cover + df / 2)

    R_piega = max(2.5 * df, 3.0)
    R_piega = min(R_piega, max((b - 2 * cover - ds) / 4, 1.0),
                          max((h - 2 * cover - ds) / 4, 1.0))

    off_x = cover + ds + df / 2
    off_y = cover + ds + df / 2
    corner_off_along = cover + ds + dc + df

    n = f.n_per_side
    if n == 1:
        y_centers = [(corner_off_along + (h - corner_off_along)) / 2]
        x_centers = [(corner_off_along + (b - corner_off_along)) / 2]
    else:
        y_centers = list(np.linspace(corner_off_along, h - corner_off_along, n))
        x_centers = list(np.linspace(corner_off_along, b - corner_off_along, n))

    segs = []
    n_arc = 4

    def add_fork_x_normal(y_fixed, x1, x2):
        segs.append(((x1, y_fixed, z_bot), (x1, y_fixed, z_top - R_piega), df))
        segs.append(((x2, y_fixed, z_bot), (x2, y_fixed, z_top - R_piega), df))
        for i in range(n_arc):
            t1 = np.pi / 2 * i / n_arc
            t2 = np.pi / 2 * (i + 1) / n_arc
            p1 = (x1 + R_piega * (1 - np.cos(t1)), y_fixed,
                  z_top - R_piega + R_piega * np.sin(t1))
            p2 = (x1 + R_piega * (1 - np.cos(t2)), y_fixed,
                  z_top - R_piega + R_piega * np.sin(t2))
            segs.append((p1, p2, df))
        segs.append(((x1 + R_piega, y_fixed, z_top),
                     (x2 - R_piega, y_fixed, z_top), df))
        for i in range(n_arc):
            t1 = np.pi / 2 * i / n_arc
            t2 = np.pi / 2 * (i + 1) / n_arc
            p1 = (x2 - R_piega * (1 - np.cos(t1)), y_fixed,
                  z_top - R_piega + R_piega * np.sin(t1))
            p2 = (x2 - R_piega * (1 - np.cos(t2)), y_fixed,
                  z_top - R_piega + R_piega * np.sin(t2))
            segs.append((p1, p2, df))

    def add_fork_y_normal(x_fixed, y1, y2):
        segs.append(((x_fixed, y1, z_bot), (x_fixed, y1, z_top - R_piega), df))
        segs.append(((x_fixed, y2, z_bot), (x_fixed, y2, z_top - R_piega), df))
        for i in range(n_arc):
            t1 = np.pi / 2 * i / n_arc
            t2 = np.pi / 2 * (i + 1) / n_arc
            p1 = (x_fixed, y1 + R_piega * (1 - np.cos(t1)),
                  z_top - R_piega + R_piega * np.sin(t1))
            p2 = (x_fixed, y1 + R_piega * (1 - np.cos(t2)),
                  z_top - R_piega + R_piega * np.sin(t2))
            segs.append((p1, p2, df))
        segs.append(((x_fixed, y1 + R_piega, z_top),
                     (x_fixed, y2 - R_piega, z_top), df))
        for i in range(n_arc):
            t1 = np.pi / 2 * i / n_arc
            t2 = np.pi / 2 * (i + 1) / n_arc
            p1 = (x_fixed, y2 - R_piega * (1 - np.cos(t1)),
                  z_top - R_piega + R_piega * np.sin(t1))
            p2 = (x_fixed, y2 - R_piega * (1 - np.cos(t2)),
                  z_top - R_piega + R_piega * np.sin(t2))
            segs.append((p1, p2, df))

    for y in y_centers:
        add_fork_x_normal(y, off_x, b - off_x)
    for x in x_centers:
        add_fork_y_normal(x, off_y, h - off_y)

    return segs

# ============================================================
# 7) TIRAFONDI (nel pilastro)
# ============================================================
def build_tie_rods(m: ColumnModel):
    tr = m.tie_rods
    if not tr.enabled:
        return []

    b, h, H = m.b_cm, m.h_cm, m.H_cm
    dt = tr.diameter_mm / 10.0
    off = tr.offset_cm

    z_bot = max(H - tr.embedment_cm, 0.0)
    z_top = H + tr.protrusion_cm

    positions = [
        (off, off), (b - off, off),
        (b - off, h - off), (off, h - off),
    ]

    segs = []
    for (x, y) in positions:
        segs.append(((x, y, z_bot), (x, y, z_top), dt))
    return segs

# ============================================================
# 8) MENSOLE — MESH SOLIDA
# ============================================================
def _mensola_vertices(b, h, H, m_dict):
    S = m_dict["sporgenza_cm"]
    W = m_dict["larghezza_cm"]
    quota = m_dict["quota_cm"]
    h_tip = m_dict["altezza_cm"]
    h_base = m_dict["altezza_base_cm"] if m_dict["rastremata"] else h_tip
    z_top = H - quota
    z_bot_base = z_top - h_base
    z_bot_tip = z_top - h_tip
    lato = m_dict["lato"]

    if lato == "x+":
        x_face = b; x_tip = b + S
        y0 = (h - W) / 2; y1 = (h + W) / 2
        T1 = (x_face, y0, z_top); T2 = (x_tip, y0, z_top)
        T3 = (x_tip, y1, z_top);  T4 = (x_face, y1, z_top)
        B1 = (x_face, y0, z_bot_base); B2 = (x_face, y1, z_bot_base)
        C1 = (x_tip, y0, z_bot_tip);   C2 = (x_tip, y1, z_bot_tip)
    elif lato == "x-":
        x_face = 0.0; x_tip = -S
        y0 = (h - W) / 2; y1 = (h + W) / 2
        T1 = (x_face, y0, z_top); T2 = (x_tip, y0, z_top)
        T3 = (x_tip, y1, z_top);  T4 = (x_face, y1, z_top)
        B1 = (x_face, y0, z_bot_base); B2 = (x_face, y1, z_bot_base)
        C1 = (x_tip, y0, z_bot_tip);   C2 = (x_tip, y1, z_bot_tip)
    elif lato == "y+":
        y_face = h; y_tip = h + S
        x0 = (b - W) / 2; x1 = (b + W) / 2
        T1 = (x0, y_face, z_top); T2 = (x0, y_tip, z_top)
        T3 = (x1, y_tip, z_top);  T4 = (x1, y_face, z_top)
        B1 = (x0, y_face, z_bot_base); B2 = (x1, y_face, z_bot_base)
        C1 = (x0, y_tip, z_bot_tip);   C2 = (x1, y_tip, z_bot_tip)
    else:
        y_face = 0.0; y_tip = -S
        x0 = (b - W) / 2; x1 = (b + W) / 2
        T1 = (x0, y_face, z_top); T2 = (x0, y_tip, z_top)
        T3 = (x1, y_tip, z_top);  T4 = (x1, y_face, z_top)
        B1 = (x0, y_face, z_bot_base); B2 = (x1, y_face, z_bot_base)
        C1 = (x0, y_tip, z_bot_tip);   C2 = (x1, y_tip, z_bot_tip)

    return T1, T2, T3, T4, B1, B2, C1, C2

def _mensola_geometry(b, h, H, m_dict):
    T1, T2, T3, T4, B1, B2, C1, C2 = _mensola_vertices(b, h, H, m_dict)
    verts = np.array([T1, T2, T3, T4, B1, B2, C1, C2], dtype=float)
    faces = [
        [0, 1, 2], [0, 2, 3],
        [4, 5, 7], [4, 7, 6],
        [0, 3, 5], [0, 5, 4],
        [1, 6, 7], [1, 7, 2],
        [0, 1, 6], [0, 6, 4],
        [3, 5, 7], [3, 7, 2],
    ]
    return verts, np.array(faces, dtype=int)

def _mensola_edges(b, h, H, m_dict):
    T1, T2, T3, T4, B1, B2, C1, C2 = _mensola_vertices(b, h, H, m_dict)
    edges = [
        (T1, T2), (T2, T3), (T3, T4), (T4, T1),
        (B1, C1), (C1, C2), (C2, B2), (B2, B1),
        (T1, B1), (T4, B2),
        (T2, C1), (T3, C2),
    ]
    return edges

def build_mensole_geometry(m: ColumnModel):
    geoms = []
    for men in m.mensole:
        d = {
            "lato": men.lato,
            "sporgenza_cm": men.sporgenza_cm,
            "larghezza_cm": men.larghezza_cm,
            "quota_cm": men.quota_cm,
            "altezza_cm": men.altezza_cm,
            "rastremata": men.rastremata,
            "altezza_base_cm": men.altezza_base_cm,
        }
        geoms.append(_mensola_geometry(m.b_cm, m.h_cm, m.H_cm, d))
        if men.doppia:
            mirror_map = {"x+": "x-", "x-": "x+", "y+": "y-", "y-": "y+"}
            d2 = dict(d)
            d2["lato"] = mirror_map[men.lato]
            geoms.append(_mensola_geometry(m.b_cm, m.h_cm, m.H_cm, d2))
    return geoms

def build_mensole_edges(m: ColumnModel):
    edges = []
    for men in m.mensole:
        d = {
            "lato": men.lato,
            "sporgenza_cm": men.sporgenza_cm,
            "larghezza_cm": men.larghezza_cm,
            "quota_cm": men.quota_cm,
            "altezza_cm": men.altezza_cm,
            "rastremata": men.rastremata,
            "altezza_base_cm": men.altezza_base_cm,
        }
        edges.extend(_mensola_edges(m.b_cm, m.h_cm, m.H_cm, d))
        if men.doppia:
            mirror_map = {"x+": "x-", "x-": "x+", "y+": "y-", "y-": "y+"}
            d2 = dict(d)
            d2["lato"] = mirror_map[men.lato]
            edges.extend(_mensola_edges(m.b_cm, m.h_cm, m.H_cm, d2))
    return edges

# ============================================================
# 9) ARMATURA MENSOLE
# ============================================================
def _setup_side(m, men):
    S = men.sporgenza_cm
    W = men.larghezza_cm
    quota = men.quota_cm
    H = m.H_cm
    h_tip = men.altezza_cm
    h_base = men.altezza_base_cm if men.rastremata else h_tip
    z_top = H - quota
    z_bot_base = z_top - h_base
    z_bot_tip = z_top - h_tip

    if men.lato == "x+":
        axis = 'x'; face = m.b_cm; tip = m.b_cm + S; opp = 0.0
        perp_min = (m.h_cm - W) / 2; perp_max = (m.h_cm + W) / 2
        sign = +1; center = m.b_cm / 2
    elif men.lato == "x-":
        axis = 'x'; face = 0.0; tip = -S; opp = m.b_cm
        perp_min = (m.h_cm - W) / 2; perp_max = (m.h_cm + W) / 2
        sign = -1; center = m.b_cm / 2
    elif men.lato == "y+":
        axis = 'y'; face = m.h_cm; tip = m.h_cm + S; opp = 0.0
        perp_min = (m.b_cm - W) / 2; perp_max = (m.b_cm + W) / 2
        sign = +1; center = m.h_cm / 2
    else:
        axis = 'y'; face = 0.0; tip = -S; opp = m.h_cm
        perp_min = (m.b_cm - W) / 2; perp_max = (m.b_cm + W) / 2
        sign = -1; center = m.h_cm / 2

    return dict(
        S=S, W=W, quota=quota, H=H, h_tip=h_tip, h_base=h_base,
        z_top=z_top, z_bot_base=z_bot_base, z_bot_tip=z_bot_tip,
        axis=axis, face=face, tip=tip, opp=opp,
        perp_min=perp_min, perp_max=perp_max,
        sign=sign, center=center,
    )

def _pt(axis, main, perp, z):
    if axis == 'x':
        return (main, perp, z)
    return (perp, main, z)

def _mensola_stirrups(m, men):
    g = _setup_side(m, men)
    r = men.rebar
    cover = r.cover_cm
    d_st_h = r.stirrup_h_d_mm / 10.0
    d_st_v = r.stirrup_v_d_mm / 10.0

    axis = g['axis']; sign = g['sign']
    face = g['face']; tip = g['tip']; opp = g['opp']
    perp_min = g['perp_min']; perp_max = g['perp_max']
    z_top = g['z_top']; z_bot_base = g['z_bot_base']; z_bot_tip = g['z_bot_tip']
    S = g['S']; rastremata = men.rastremata

    stirrups_h = []
    stirrups_v = []

    if r.stirrup_h_pitch_cm > 0:
        if sign > 0:
            main_back = opp + cover + d_st_h / 2
        else:
            main_back = opp - cover - d_st_h / 2

        w_min_st = perp_min + cover + d_st_h / 2
        w_max_st = perp_max - cover - d_st_h / 2

        z_lo_global = z_bot_base + cover + d_st_h / 2
        z_hi_global = z_top - cover - d_st_h / 2

        if z_hi_global > z_lo_global:
            n_h = max(1, int(round((z_hi_global - z_lo_global) /
                                    r.stirrup_h_pitch_cm)))
            z_levels = np.linspace(z_lo_global, z_hi_global, n_h + 1)

            for z in z_levels:
                if rastremata:
                    if z <= z_bot_base + 1e-6:
                        main_front = face
                    elif z >= z_bot_tip - 1e-6:
                        main_front = tip - sign * (cover + d_st_h / 2)
                    else:
                        slope = (z_bot_tip - z_bot_base) / S
                        delta = (z - z_bot_base) / slope
                        main_at_z = face + sign * delta
                        main_front = main_at_z - sign * (cover + d_st_h / 2)
                else:
                    main_front = tip - sign * (cover + d_st_h / 2)

                m1, m2 = main_back, main_front
                m_min, m_max = (m1, m2) if m1 < m2 else (m2, m1)
                if m_max - m_min < 0.2:
                    continue

                p1 = _pt(axis, m_min, w_min_st, z)
                p2 = _pt(axis, m_max, w_min_st, z)
                p3 = _pt(axis, m_max, w_max_st, z)
                p4 = _pt(axis, m_min, w_max_st, z)
                stirrups_h.append((p1, p2, d_st_h))
                stirrups_h.append((p2, p3, d_st_h))
                stirrups_h.append((p3, p4, d_st_h))
                stirrups_h.append((p4, p1, d_st_h))

    if r.stirrup_v_pitch_cm > 0:
        main_start = face
        main_end = tip - sign * (cover + d_st_v / 2)
        m1, m2 = main_start, main_end
        m_min, m_max = (m1, m2) if m1 < m2 else (m2, m1)

        if m_max - m_min > 0.2:
            n_v = max(1, int(round((m_max - m_min) / r.stirrup_v_pitch_cm)))
            main_levels = np.linspace(m_min, m_max, n_v + 1)

            w_min_st_v = perp_min + cover + d_st_v / 2
            w_max_st_v = perp_max - cover - d_st_v / 2

            for mv in main_levels:
                if rastremata:
                    if sign > 0:
                        t = (mv - face) / S
                    else:
                        t = (face - mv) / S
                    t = max(0.0, min(1.0, t))
                    z_bot_local = z_bot_base + (z_bot_tip - z_bot_base) * t
                else:
                    z_bot_local = z_bot_tip

                z_lo_local = z_bot_local + cover + d_st_v / 2
                z_hi_local = z_top - cover - d_st_v / 2
                if z_hi_local <= z_lo_local:
                    continue

                p1 = _pt(axis, mv, w_min_st_v, z_lo_local)
                p2 = _pt(axis, mv, w_max_st_v, z_lo_local)
                p3 = _pt(axis, mv, w_max_st_v, z_hi_local)
                p4 = _pt(axis, mv, w_min_st_v, z_hi_local)
                stirrups_v.append((p1, p2, d_st_v))
                stirrups_v.append((p2, p3, d_st_v))
                stirrups_v.append((p3, p4, d_st_v))
                stirrups_v.append((p4, p1, d_st_v))

    return stirrups_h, stirrups_v

def _mensola_top_bars_single(m, men):
    g = _setup_side(m, men)
    r = men.rebar
    cover = r.cover_cm
    d_top = r.d_top_mm / 10.0
    n_top = r.n_top_bars

    axis = g['axis']; sign = g['sign']
    face = g['face']; tip = g['tip']; opp = g['opp']
    perp_min = g['perp_min']; perp_max = g['perp_max']
    z_top = g['z_top']; z_bot_base = g['z_bot_base']; z_bot_tip = g['z_bot_tip']
    S = g['S']; center = g['center']

    z_top_bar = z_top - cover - d_top / 2
    z_bot_base_inner = z_bot_base + cover + d_top / 2
    z_bot_tip_inner = z_bot_tip + cover + d_top / 2

    w_min = perp_min + cover + d_top / 2
    w_max = perp_max - cover - d_top / 2
    if n_top == 1:
        w_positions = [(w_min + w_max) / 2]
    else:
        w_positions = list(np.linspace(w_min, w_max, n_top))

    if sign > 0:
        main_start_horiz = opp + cover + d_top / 2
        main_tip_inner = tip - cover - d_top / 2
    else:
        main_start_horiz = opp - cover - d_top / 2
        main_tip_inner = tip + cover + d_top / 2

    top_bars = []
    for w in w_positions:
        path = []
        if r.vertical_anchorage_enabled:
            z_anchor_bot = z_top_bar - r.vertical_anchorage_cm
            path.append(_pt(axis, main_start_horiz, w, z_anchor_bot))
        path.append(_pt(axis, main_start_horiz, w, z_top_bar))
        path.append(_pt(axis, main_tip_inner, w, z_top_bar))
        path.append(_pt(axis, main_tip_inner, w, z_bot_tip_inner))
        if r.return_enabled:
            dist_from_face_max = abs(center - face)
            dist_from_face = max(0.0, dist_from_face_max - 3 * d_top)
            main_ret_pos = face - sign * dist_from_face

            if men.rastremata:
                slope = (z_bot_tip - z_bot_base) / S
                z_end = z_bot_base_inner - slope * dist_from_face
            else:
                z_end = z_bot_tip_inner
            path.append(_pt(axis, main_ret_pos, w, z_end))

        for i in range(len(path) - 1):
            top_bars.append((path[i], path[i + 1], d_top))

    return top_bars

def _mensola_top_bars_double(m, men_a, men_b):
    if men_a.lato.endswith('+'):
        men_pos, men_neg = men_a, men_b
    else:
        men_pos, men_neg = men_b, men_a

    g_pos = _setup_side(m, men_pos)
    axis = g_pos['axis']
    r = men_pos.rebar
    cover = r.cover_cm
    d_top = r.d_top_mm / 10.0
    n_top = r.n_top_bars

    S = g_pos['S']
    perp_min = g_pos['perp_min']; perp_max = g_pos['perp_max']
    z_top = g_pos['z_top']
    z_bot_base = g_pos['z_bot_base']
    z_bot_tip = g_pos['z_bot_tip']
    center = g_pos['center']

    z_top_bar = z_top - cover - d_top / 2
    z_bot_tip_inner = z_bot_tip + cover + d_top / 2
    z_bot_base_inner = z_bot_base + cover + d_top / 2

    w_min = perp_min + cover + d_top / 2
    w_max = perp_max - cover - d_top / 2
    if n_top == 1:
        w_positions = [(w_min + w_max) / 2]
    else:
        w_positions = list(np.linspace(w_min, w_max, n_top))

    if axis == 'x':
        face_pos = m.b_cm; face_neg = 0.0
    else:
        face_pos = m.h_cm; face_neg = 0.0

    tip_pos = face_pos + S
    tip_neg = face_neg - S

    main_pos_tip_inner = tip_pos - cover - d_top / 2
    main_neg_tip_inner = tip_neg + cover + d_top / 2

    dist_eff = max(0.0, abs(center - face_pos) - 3 * d_top)
    main_neg_ret = face_neg + dist_eff
    main_pos_ret = face_pos - dist_eff

    top_bars = []
    for w in w_positions:
        path = []
        if r.return_enabled:
            if men_pos.rastremata:
                slope = (z_bot_tip - z_bot_base) / S
                z_neg_ret = z_bot_base_inner - slope * dist_eff
            else:
                z_neg_ret = z_bot_tip_inner
            path.append(_pt(axis, main_neg_ret, w, z_neg_ret))

        path.append(_pt(axis, main_neg_tip_inner, w, z_bot_tip_inner))
        path.append(_pt(axis, main_neg_tip_inner, w, z_top_bar))
        path.append(_pt(axis, main_pos_tip_inner, w, z_top_bar))
        path.append(_pt(axis, main_pos_tip_inner, w, z_bot_tip_inner))

        if r.return_enabled:
            if men_pos.rastremata:
                slope = (z_bot_tip - z_bot_base) / S
                z_pos_ret = z_bot_base_inner - slope * dist_eff
            else:
                z_pos_ret = z_bot_tip_inner
            path.append(_pt(axis, main_pos_ret, w, z_pos_ret))

        for i in range(len(path) - 1):
            top_bars.append((path[i], path[i + 1], d_top))

    return top_bars

def _mensola_tirafondi(m, men):
    r = men.rebar
    if not r.tirafondi_enabled or r.n_tirafondi <= 0:
        return []

    g = _setup_side(m, men)
    axis = g['axis']; sign = g['sign']
    tip = g['tip']
    perp_min = g['perp_min']; perp_max = g['perp_max']
    z_top = g['z_top']; z_bot_tip = g['z_bot_tip']

    if sign > 0:
        main_pos = tip - r.tir_dist_testa_cm
    else:
        main_pos = tip + r.tir_dist_testa_cm

    bordo = r.tir_dist_bordo_cm
    w_min_ok = perp_min + bordo
    w_max_ok = perp_max - bordo

    if w_min_ok > w_max_ok:
        return []

    if r.n_tirafondi == 1:
        w_positions = [(perp_min + perp_max) / 2]
    else:
        w_positions = list(np.linspace(w_min_ok, w_max_ok, r.n_tirafondi))

    d_cm = r.d_tirafondi_mm / 10.0
    d_dado_cm = d_cm * 1.8

    z_sup = z_top + r.tir_sporgenza_cm
    z_dado_bot = z_top - r.tir_prof_dado_cm
    if z_dado_bot < z_bot_tip + 0.5:
        z_dado_bot = z_bot_tip + 0.5

    segs = []
    for w in w_positions:
        if axis == 'x':
            p1 = (main_pos, w, z_dado_bot)
            p2 = (main_pos, w, z_sup)
        else:
            p1 = (w, main_pos, z_dado_bot)
            p2 = (w, main_pos, z_sup)
        segs.append((p1, p2, d_cm))

        dado_h = 1.5
        if axis == 'x':
            dp1 = (main_pos, w, z_dado_bot)
            dp2 = (main_pos, w, z_dado_bot + dado_h)
        else:
            dp1 = (w, main_pos, z_dado_bot)
            dp2 = (w, main_pos, z_dado_bot + dado_h)
        segs.append((dp1, dp2, d_dado_cm))

    return segs

def _make_virtual_partner(m, men):
    mirror_map = {"x+": "x-", "x-": "x+", "y+": "y-", "y-": "y+"}
    return Mensola(
        lato=mirror_map[men.lato],
        sporgenza_cm=men.sporgenza_cm,
        larghezza_cm=men.larghezza_cm,
        quota_cm=men.quota_cm,
        altezza_cm=men.altezza_cm,
        rastremata=men.rastremata,
        altezza_base_cm=men.altezza_base_cm,
        doppia=False,
        rebar=men.rebar,
    )

def build_mensole_rebar(m: ColumnModel):
    all_top = []
    all_sh = []
    all_sv = []
    all_tir = []

    for men in m.mensole:
        if men.doppia:
            partner = _make_virtual_partner(m, men)
            top = _mensola_top_bars_double(m, men, partner)
            sh1, sv1 = _mensola_stirrups(m, men)
            sh2, sv2 = _mensola_stirrups(m, partner)
            tir1 = _mensola_tirafondi(m, men)
            tir2 = _mensola_tirafondi(m, partner)
            all_top.extend(top)
            all_sh.extend(sh1); all_sv.extend(sv1)
            all_sh.extend(sh2); all_sv.extend(sv2)
            all_tir.extend(tir1); all_tir.extend(tir2)
        else:
            top = _mensola_top_bars_single(m, men)
            sh, sv = _mensola_stirrups(m, men)
            tir = _mensola_tirafondi(m, men)
            all_top.extend(top)
            all_sh.extend(sh); all_sv.extend(sv)
            all_tir.extend(tir)

    return all_top, all_sh, all_sv, all_tir

# ============================================================
# 10) VISTE PREIMPOSTATE
# ============================================================
def compute_camera(preset, b, h, H_eff, zoom_factor=1.0):
    max_span = max(b, h, H_eff)
    nb, nh, nH = b / max_span, h / max_span, H_eff / max_span
    dirs = {
        "3d": np.array([1.0, 0.85, 0.55]),
        "xz": np.array([0.0, -1.0, 0.0]),
        "yz": np.array([1.0, 0.0, 0.0]),
        "xy": np.array([0.0, 0.0, 1.0]),
    }
    d = dirs[preset]; d = d / np.linalg.norm(d)
    half_x, half_y, half_z = nb, nh, nH
    if preset == "3d":
        R = np.sqrt(half_x ** 2 + half_y ** 2 + half_z ** 2)
        dist = 2.8 * R + 1.0
    elif preset == "xz":
        dist = 2.8 * max(half_x, half_z) + 1.0
    elif preset == "yz":
        dist = 2.8 * max(half_y, half_z) + 1.0
    else:
        dist = 2.8 * max(half_x, half_y) + 1.0
    dist *= zoom_factor
    eye = d * dist
    up = {"3d": (0, 0, 1), "xz": (0, 0, 1),
          "yz": (0, 0, 1), "xy": (0, 1, 0)}[preset]
    proj = "orthographic" if preset != "3d" else "perspective"
    return dict(
        eye=dict(x=float(eye[0]), y=float(eye[1]), z=float(eye[2])),
        up=dict(x=up[0], y=up[1], z=up[2]),
        projection=dict(type=proj),
    )

# ============================================================
# 11) CALCOLO MATERIALI
# ============================================================
def _cyl_volume_cm3(p1, p2, d_cm):
    p1 = np.asarray(p1, float)
    p2 = np.asarray(p2, float)
    L = float(np.linalg.norm(p2 - p1))
    return float(np.pi * (d_cm / 2.0) ** 2 * L)

def _total_steel_volume_cm3(segments):
    return sum(_cyl_volume_cm3(p1, p2, d) for (p1, p2, d) in segments)

def _mensola_volume_cm3(men: Mensola):
    S = men.sporgenza_cm
    W = men.larghezza_cm
    h_tip = men.altezza_cm
    if men.rastremata:
        h_base = men.altezza_base_cm
        return S * W * (h_tip + h_base) / 2.0
    return S * W * h_tip

def compute_material_quantities(model: ColumnModel):
    b, h, H = model.b_cm, model.h_cm, model.H_cm

    V_pilastro_cm3 = b * h * H
    V_mensole_cm3 = 0.0
    for men in model.mensole:
        v_men = _mensola_volume_cm3(men)
        if men.doppia:
            v_men *= 2
        V_mensole_cm3 += v_men

    V_cls_cm3 = V_pilastro_cm3 + V_mensole_cm3
    V_cls_m3 = V_cls_cm3 / 1e6

    long_bars = build_longitudinal_bars(model)
    base_stirrups, dense_stirrups = build_all_stirrups(model)
    hooks_3d = build_hooks(model, base_stirrups)
    forks_3d = build_forks(model)
    ties_3d = build_tie_rods(model)
    top_bars, sh_segs, sv_segs, tir_segs = build_mensole_rebar(model)

    V_long_cm3 = _total_steel_volume_cm3(long_bars)
    V_stirrups_cm3 = _total_steel_volume_cm3(base_stirrups)
    V_dense_cm3 = _total_steel_volume_cm3(dense_stirrups)
    V_hooks_cm3 = _total_steel_volume_cm3(hooks_3d)
    V_forks_cm3 = _total_steel_volume_cm3(forks_3d)
    V_ties_cm3 = _total_steel_volume_cm3(ties_3d)
    V_men_top_cm3 = _total_steel_volume_cm3(top_bars)
    V_men_sh_cm3 = _total_steel_volume_cm3(sh_segs)
    V_men_sv_cm3 = _total_steel_volume_cm3(sv_segs)
    V_men_tir_cm3 = _total_steel_volume_cm3(tir_segs)

    V_steel_cm3 = (V_long_cm3 + V_stirrups_cm3 + V_dense_cm3 + V_hooks_cm3
                   + V_forks_cm3 + V_ties_cm3
                   + V_men_top_cm3 + V_men_sh_cm3 + V_men_sv_cm3
                   + V_men_tir_cm3)
    V_steel_m3 = V_steel_cm3 / 1e6

    peso_cls_kN = V_cls_m3 * CLS_KN_M3
    peso_cls_kg = V_cls_m3 * CLS_KG_M3
    peso_steel_kN = V_steel_m3 * STEEL_KN_M3
    peso_steel_kg = V_steel_m3 * STEEL_KG_M3

    A_cls_cm2 = b * h
    A_cls_mm2 = A_cls_cm2 * 100.0

    bar_counts = Counter()
    for (_, _, d_cm) in long_bars:
        d_mm = int(round(d_cm * 10))
        bar_counts[d_mm] += 1

    A_long_mm2 = sum(n * np.pi * (d / 2.0) ** 2
                     for d, n in bar_counts.items())
    A_long_cm2 = A_long_mm2 / 100.0
    perc_arm = (A_long_mm2 / A_cls_mm2 * 100.0) if A_cls_mm2 > 0 else 0.0

    return {
        'V_pilastro_m3': V_pilastro_cm3 / 1e6,
        'V_mensole_m3': V_mensole_cm3 / 1e6,
        'V_cls_m3': V_cls_m3,
        'V_long_cm3': V_long_cm3,
        'V_stirrups_cm3': V_stirrups_cm3,
        'V_dense_cm3': V_dense_cm3,
        'V_hooks_cm3': V_hooks_cm3,
        'V_forks_cm3': V_forks_cm3,
        'V_ties_cm3': V_ties_cm3,
        'V_men_top_cm3': V_men_top_cm3,
        'V_men_sh_cm3': V_men_sh_cm3,
        'V_men_sv_cm3': V_men_sv_cm3,
        'V_men_tir_cm3': V_men_tir_cm3,
        'V_steel_m3': V_steel_m3,
        'peso_cls_kN': peso_cls_kN,
        'peso_cls_kg': peso_cls_kg,
        'peso_steel_kN': peso_steel_kN,
        'peso_steel_kg': peso_steel_kg,
        'A_cls_cm2': A_cls_cm2,
        'A_long_mm2': A_long_mm2,
        'A_long_cm2': A_long_cm2,
        'perc_arm': perc_arm,
        'bar_counts': dict(bar_counts),
        'n_long_bars': len(long_bars),
    }

# ============================================================
# 12) SERIALIZZAZIONE / SALVATAGGIO
# ============================================================
def build_export_dict():
    params = st.session_state.get("_current_params", {})
    safe_params = {}
    for k, v in params.items():
        if isinstance(v, tuple):
            v = list(v)
        safe_params[k] = v

    data = {
        "version": 1,
        "timestamp": datetime.datetime.now().isoformat(),
        "project_name": safe_params.get("nome_progetto", ""),
        "project_description": safe_params.get("descrizione_progetto", ""),
        "params": safe_params,
        "extras": [
            {
                "distance_cm": e["distance_cm"],
                "diameter_mm": e["diameter_mm"],
                "mirror": e["mirror"],
            }
            for e in st.session_state.extras
        ],
        "mensole": [
            {
                "lato": m["lato"],
                "sporgenza_cm": m["sporgenza_cm"],
                "larghezza_cm": m["larghezza_cm"],
                "quota_cm": m["quota_cm"],
                "altezza_cm": m["altezza_cm"],
                "rastremata": m["rastremata"],
                "altezza_base_cm": m["altezza_base_cm"],
                "doppia": m["doppia"],
                "rebar": dict(m["rebar"]),
            }
            for m in st.session_state.mensole
        ],
    }
    return data

# ============================================================
# 13) LAYOUT
# ============================================================
col_left, col_right = st.columns([1, 1.6], gap="medium")

with col_left:
    st.subheader("⚙️ Parametri")

    (tab_prog, tab_geom, tab_long, tab_st, tab_fork, tab_men,
     tab_arm_men, tab_riep, tab_vis) = st.tabs(
        ["📁 Progetto", "📐 Geometria", "🟥 Ferri", "🟦 Staffe",
         "🟩 Testa pilastro", "🏗️ Mensole", "🟫 Armatura mensole",
         "📊 Riepilogo", "👁️ Vista"])

    # ------------------------------------------------------------
    # TAB PROGETTO
    # ------------------------------------------------------------
    with tab_prog:
        st.markdown("#### 📁 Informazioni del progetto")
        nome_progetto = st.text_input(
            "Nome del progetto",
            value=str(get_param("nome_progetto", "")),
            placeholder="Es. Pilastro P1 — Edificio A",
            key=widget_key("nome_progetto"))
        descrizione_progetto = st.text_area(
            "Breve descrizione",
            value=str(get_param("descrizione_progetto", "")),
            placeholder="Es. Pilastro di bordo piano terra, sezione 70x70...",
            height=120, key=widget_key("descrizione_progetto"))

        st.markdown("---")
        st.markdown("#### 💾 Gestione del lavoro")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            if st.button("📂 Carica", width='stretch',
                         key=widget_key("btn_load")):
                st.session_state["show_uploader"] = True
        with sc2:
            if st.button("💾 Salva", width='stretch',
                         key=widget_key("btn_save")):
                st.session_state["do_save"] = True
        with sc3:
            if st.button("🆕 Nuovo", width='stretch',
                         key=widget_key("btn_new")):
                st.session_state.loaded_params = {}
                st.session_state.load_token += 1
                _reset_extras_from_list([])
                _reset_mensole_from_list([])
                st.session_state.view_preset = "3d"
                for k in ["pdf_bytes", "_last_json", "_last_json_name", "_download_ready"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if st.session_state.get("show_uploader", False):
            uploaded = st.file_uploader(
                "Seleziona un file .json di lavoro",
                type=["json"], key=widget_key("uploader"))
            if uploaded is not None:
                try:
                    loaded = json.loads(uploaded.read().decode("utf-8"))
                    params = loaded.get("params", {})
                    if "nome_progetto" not in params:
                        params["nome_progetto"] = loaded.get("project_name", "")
                    if "descrizione_progetto" not in params:
                        params["descrizione_progetto"] = loaded.get("project_description", "")
                    _apply_loaded_params(params)
                    _reset_extras_from_list(loaded.get("extras", []))
                    _reset_mensole_from_list(loaded.get("mensole", []))
                    st.session_state["show_uploader"] = False
                    for k in ["pdf_bytes", "_last_json", "_last_json_name", "_download_ready"]:
                        st.session_state.pop(k, None)
                    st.success("✅ Lavoro caricato correttamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel caricamento: {e}")

        if st.session_state.get("_download_ready", False):
            st.success("✅ File JSON pronto. Clicca per scaricarlo.")
            st.download_button(
                "📥 Scarica file .json",
                data=st.session_state["_last_json"],
                file_name=st.session_state["_last_json_name"],
                mime="application/json",
                width='stretch', key=widget_key("dl_json"))
            if st.button("❌ Chiudi", key=widget_key("close_dl")):
                st.session_state["_download_ready"] = False
                st.session_state.pop("_last_json", None)
                st.session_state.pop("_last_json_name", None)
                st.rerun()

    # ------------------------------------------------------------
    # TAB GEOMETRIA
    # ------------------------------------------------------------
    with tab_geom:
        b_cm = st.number_input("Larghezza b [cm]", 20.0, 300.0,
                               float(get_param("b_cm", 70.0)), 5.0,
                               key=widget_key("b_cm"))
        h_cm = st.number_input("Profondità h [cm]", 20.0, 300.0,
                               float(get_param("h_cm", 70.0)), 5.0,
                               key=widget_key("h_cm"))
        H_cm = st.number_input("Altezza H [cm]", 50.0, 2000.0,
                               float(get_param("H_cm", 400.0)), 10.0,
                               key=widget_key("H_cm"))
        cover = st.number_input("Copriferro [cm]", 1.0, 10.0,
                                float(get_param("cover", 3.0)), 0.5,
                                key=widget_key("cover"))

        st.markdown("---")
        st.markdown("#### 🏛️ Fondazione")
        tipo_fond = st.selectbox(
            "Tipo di fondazione",
            ["nessuna", "armatubo", "bicchiere"],
            index=["nessuna", "armatubo", "bicchiere"].index(
                get_param("tipo_fond", "nessuna")),
            format_func=lambda x: {
                "nessuna": "Nessuna / non specificata",
                "armatubo": "Armatubo (ferri sporgenti)",
                "bicchiere": "Plinto a bicchiere (ferri non sporgenti)",
            }[x],
            key=widget_key("tipo_fond"))

        if tipo_fond == "armatubo":
            anchorage = st.number_input(
                "Lunghezza di ancoraggio [cm]", 10.0, 300.0,
                float(get_param("anchorage", 40.0)), 5.0,
                key=widget_key("anchorage"))
            bicchiere_depth = float(get_param("bicchiere_depth", 120.0))
        elif tipo_fond == "bicchiere":
            bicchiere_depth = st.number_input(
                "Profondità bicchiere [cm]", 40.0, 250.0,
                float(get_param("bicchiere_depth", 120.0)), 5.0,
                key=widget_key("bicchiere_depth"))
            anchorage = float(get_param("anchorage", 40.0))
        else:
            anchorage = float(get_param("anchorage", 40.0))
            bicchiere_depth = float(get_param("bicchiere_depth", 120.0))

    # ------------------------------------------------------------
    # TAB FERRI
    # ------------------------------------------------------------
    with tab_long:
        st.markdown("#### 🔺 Ferri d'angolo")
        ca1, ca2 = st.columns(2)
        d_corner = ca1.number_input(
            "Ø angolari [mm]", 6, 40,
            int(get_param("d_corner", 26.0)), 2,
            key=widget_key("d_corner"))
        coupled_corner = ca2.checkbox(
            "Accoppiati", value=bool(get_param("coupled_corner", False)),
            key=widget_key("coupled_corner"))

        st.markdown("---")
        st.markdown("#### ➖ Ferri intermedi (uguali sui 4 lati)")
        cb1, cb2 = st.columns(2)
        n_int = int(cb1.number_input(
            "N° per lato", 0, 20, int(get_param("n_int", 2)), 1,
            key=widget_key("n_int")))
        d_int = cb2.number_input(
            "Ø intermedi [mm]", 6, 40, int(get_param("d_int", 24.0)), 2,
            disabled=(n_int == 0), key=widget_key("d_int"))
        coupled_int = st.checkbox(
            "Accoppiati (affiancati lungo il bordo)",
            value=bool(get_param("coupled_int", False)),
            disabled=(n_int == 0), key=widget_key("coupled_int"))

        spacing_mode_ui = st.radio(
            "Distanziamento", ["Uniforme", "Personalizzato"],
            index=0 if get_param("spacing_mode_ui", "Uniforme") == "Uniforme" else 1,
            horizontal=True, disabled=(n_int == 0),
            key=widget_key("spacing_mode_ui"))

        custom_spacings = ()
        if spacing_mode_ui == "Personalizzato" and n_int > 0:
            default_vals = [15.0] + [20.0] * (n_int - 1)
            default_txt = get_param("custom_txt", "") or ", ".join(f"{v:.0f}" for v in default_vals)
            txt = st.text_input(
                f"Inserisci {n_int} distanze [cm] separate da virgola",
                value=default_txt, key=widget_key("custom_txt"))
            try:
                vals = [float(x.strip()) for x in txt.split(",") if x.strip()]
                custom_spacings = tuple(vals)
                if len(vals) != n_int:
                    st.warning(f"⚠️ Inserite {len(vals)} distanze, servono {n_int}.")
            except ValueError:
                st.error("Formato non valido.")

        st.markdown("---")
        st.markdown("#### ➕ Ferri aggiuntivi liberi")

        to_remove_id = None
        for ex in st.session_state.extras:
            uid = ex["id"]
            with st.container(border=True):
                ec1, ec2, ec3, ec4 = st.columns([2, 1, 1.2, 0.5])
                ex["distance_cm"] = ec1.number_input(
                    "Dist. dal ferro d'angolo [cm]", 1.0, 200.0,
                    float(ex["distance_cm"]), 0.5, key=widget_key(f"ex_d_{uid}"))
                ex["diameter_mm"] = ec2.number_input(
                    "Ø [mm]", 6, 40, int(ex["diameter_mm"]), 2,
                    key=widget_key(f"ex_dia_{uid}"))
                ex["mirror"] = ec3.checkbox(
                    "Specchia", value=ex["mirror"], key=widget_key(f"ex_m_{uid}"))
                if ec4.button("🗑️", key=widget_key(f"ex_rm_{uid}")):
                    to_remove_id = uid

        if to_remove_id is not None:
            st.session_state.extras = [
                e for e in st.session_state.extras if e["id"] != to_remove_id]
            st.rerun()

        if st.button("➕ Aggiungi ferro aggiuntivo", key=widget_key("add_ex")):
            st.session_state.extras.append({
                "id": st.session_state.extras_next_id,
                "distance_cm": 5.0, "diameter_mm": 20.0, "mirror": True,
            })
            st.session_state.extras_next_id += 1
            st.rerun()

    # ------------------------------------------------------------
    # TAB STAFFE
    # ------------------------------------------------------------
    with tab_st:
        st.markdown("#### 🔷 Fascia zona duttile")
        du_c1, du_c2, du_c3 = st.columns(3)
        duct_len = du_c1.number_input(
            "Lunghezza [cm]", 20.0, 500.0,
            float(get_param("duct_len", 60.0)), 5.0,
            key=widget_key("duct_len"))
        duct_d = du_c2.number_input(
            "Ø staffe [mm]", 6, 20, int(get_param("duct_d", 8.0)), 2,
            key=widget_key("duct_d"))
        duct_p = du_c3.number_input(
            "Passo [cm]", 5.0, 50.0, float(get_param("duct_p", 10.0)), 1.0,
            key=widget_key("duct_p"))

        st.markdown("---")
        st.markdown("#### 🟩 Fascia testa pilastro")
        he_c1, he_c2, he_c3 = st.columns(3)
        head_len = he_c1.number_input(
            "Lunghezza [cm]", 20.0, 300.0,
            float(get_param("head_len", 60.0)), 5.0,
            key=widget_key("head_len"))
        head_d = he_c2.number_input(
            "Ø staffe [mm]", 6, 20, int(get_param("head_d", 8.0)), 2,
            key=widget_key("head_d"))
        head_p = he_c3.number_input(
            "Passo [cm]", 5.0, 50.0, float(get_param("head_p", 10.0)), 1.0,
            key=widget_key("head_p"))

        st.markdown("---")
        st.markdown("#### ⬜ Fascia armatura minima")
        if tipo_fond == "bicchiere":
            z_min_start = bicchiere_depth + duct_len
        else:
            z_min_start = cover + duct_len
        z_min_end = H_cm - head_len
        auto_min_len = max(0.0, z_min_end - z_min_start)
        st.caption(f"Lunghezza automatica: {auto_min_len:.0f} cm")
        if auto_min_len <= 0:
            st.warning("⚠️ Fascia minima nulla.")
        mi_c1, mi_c2 = st.columns(2)
        min_d = mi_c1.number_input(
            "Ø staffe [mm]", 6, 20, int(get_param("min_d", 8.0)), 2,
            key=widget_key("min_d"))
        min_p = mi_c2.number_input(
            "Passo [cm]", 5.0, 50.0, float(get_param("min_p", 15.0)), 1.0,
            key=widget_key("min_p"))

        if tipo_fond == "bicchiere":
            st.markdown("---")
            st.markdown("#### 🏛️ Fascia nel bicchiere")
            emb_len = max(0.0, bicchiere_depth - cover)
            st.caption(f"Lunghezza automatica: {emb_len:.0f} cm")
            em_c1, em_c2 = st.columns(2)
            emb_d = em_c1.number_input(
                "Ø staffe [mm]", 6, 20, int(get_param("emb_d", 8.0)), 2,
                key=widget_key("emb_d"))
            emb_p = em_c2.number_input(
                "Passo [cm]", 5.0, 50.0, float(get_param("emb_p", 10.0)), 1.0,
                key=widget_key("emb_p"))
        else:
            emb_d = 8.0
            emb_p = 10.0

        st.markdown("---")
        st.markdown("#### 🔗 Ganci (zona duttile)")
        hooks_enabled = st.checkbox(
            "Abilita ganci", value=bool(get_param("hooks_enabled", False)),
            key=widget_key("hooks_enabled"))
        if hooks_enabled:
            hook_dia = st.number_input(
                "Ø ganci [mm]", 6, 20,
                int(get_param("hook_dia", 8.0)), 2,
                key=widget_key("hook_dia"))
            if tipo_fond == "bicchiere":
                st.info(f"ℹ️ Zona duttile: da z = {bicchiere_depth:.0f} cm "
                        f"a z = {bicchiere_depth + duct_len:.0f} cm.")
            else:
                st.info(f"ℹ️ Zona duttile: da z = {cover:.0f} cm "
                        f"a z = {cover + duct_len:.0f} cm.")
        else:
            hook_dia = 8.0

        st.markdown("---")
        st.markdown("#### 🔶 Fasce infittite sopra le mensole")
        st.caption("Infittisce la staffatura al di sopra di ogni mensola.")
        dense_enabled = st.checkbox(
            "Abilita fasce infittite",
            value=bool(get_param("dense_enabled", False)),
            key=widget_key("dense_enabled"))
        if dense_enabled:
            dd_c1, dd_c2, dd_c3 = st.columns(3)
            dense_d = dd_c1.number_input(
                "Ø staffe infittite [mm]", 6, 20,
                int(get_param("dense_d", 8.0)), 2,
                key=widget_key("dense_d"))
            dense_p = dd_c2.number_input(
                "Passo infittito [cm]", 2.0, 50.0,
                float(get_param("dense_p", 10.0)), 1.0,
                key=widget_key("dense_p"))
            dense_len = dd_c3.number_input(
                "Lunghezza fascia [cm] (0 = auto)", 0.0, 500.0,
                float(get_param("dense_len", 0.0)), 5.0,
                key=widget_key("dense_len"),
                help="0 = lunghezza automatica (max(b,h) del pilastro)")
            auto_len = max(b_cm, h_cm)
            eff_len = dense_len if dense_len > 0 else auto_len
            st.caption(f"ℹ️ Lunghezza effettiva: **{eff_len:.0f} cm** "
                       f"(default = max(b,h) = {auto_len:.0f} cm).")
        else:
            dense_d = float(get_param("dense_d", 8.0))
            dense_p = float(get_param("dense_p", 10.0))
            dense_len = float(get_param("dense_len", 0.0))

    # ------------------------------------------------------------
    # TAB TESTA PILASTRO
    # ------------------------------------------------------------
    with tab_fork:
        st.markdown("#### 🟩 Testa pilastro")
        forks_enabled = st.checkbox(
            "Abilita forche", value=bool(get_param("forks_enabled", False)),
            key=widget_key("forks_enabled"))
        if forks_enabled:
            fc1, fc2 = st.columns(2)
            n_forks = int(fc1.number_input(
                "N° per lato", 1, 12, int(get_param("n_forks", 2)), 1,
                key=widget_key("n_forks")))
            fork_dia = fc2.number_input(
                "Ø forche [mm]", 8, 32, int(get_param("fork_dia", 16.0)), 2,
                key=widget_key("fork_dia"))
            fork_length = st.number_input(
                "Lunghezza di ancoraggio [cm]", 20.0, 400.0,
                float(get_param("fork_length", 80.0)), 5.0,
                key=widget_key("fork_length"))
        else:
            n_forks = 2; fork_dia = 16.0; fork_length = 80.0

        st.markdown("---")
        st.markdown("#### 🟨 Tirafondi (nel pilastro)")
        tie_enabled = st.checkbox(
            "Abilita tirafondi", value=bool(get_param("tie_enabled", False)),
            key=widget_key("tie_enabled"))
        if tie_enabled:
            tc1, tc2 = st.columns(2)
            tie_d = tc1.number_input(
                "Ø tirafondi [mm]", 8, 60, int(get_param("tie_d", 24.0)), 2,
                key=widget_key("tie_d"))
            tie_off = tc2.number_input(
                "Offset dai lati [cm]", 3.0, 50.0,
                float(get_param("tie_off", 12.0)), 0.5,
                key=widget_key("tie_off"))
            tc3, tc4 = st.columns(2)
            tie_prot = tc3.number_input(
                "Sporgenza sopra la testa [cm]", 5.0, 200.0,
                float(get_param("tie_prot", 30.0)), 5.0,
                key=widget_key("tie_prot"))
            tie_emb = tc4.number_input(
                "Lunghezza di ancoraggio [cm]", 20.0, 500.0,
                float(get_param("tie_emb", 90.0)), 5.0,
                key=widget_key("tie_emb"))
        else:
            tie_d = 24.0; tie_off = 12.0; tie_prot = 30.0; tie_emb = 90.0

    # ------------------------------------------------------------
    # TAB MENSOLE
    # ------------------------------------------------------------
    with tab_men:
        st.markdown("#### 🏗️ Mensole")
        lato_opts = {
            "x+": "Destra (+X)", "x-": "Sinistra (−X)",
            "y+": "Alto (+Y)", "y-": "Basso (−Y)",
        }
        to_remove_men_id = None
        for men in st.session_state.mensole:
            uid = men["id"]
            with st.container(border=True):
                r1 = st.columns([2, 1, 1, 0.5])
                men["lato"] = r1[0].selectbox(
                    "Lato", options=list(lato_opts.keys()),
                    index=list(lato_opts.keys()).index(men["lato"]),
                    format_func=lambda k: lato_opts[k],
                    key=widget_key(f"men_lato_{uid}"))
                men["doppia"] = r1[1].checkbox(
                    "Doppia", value=men["doppia"],
                    key=widget_key(f"men_dop_{uid}"))
                men["rastremata"] = r1[2].checkbox(
                    "Rastremata", value=men["rastremata"],
                    key=widget_key(f"men_ras_{uid}"))
                if r1[3].button("🗑️", key=widget_key(f"men_rm_{uid}")):
                    to_remove_men_id = uid

                r2 = st.columns(3)
                men["sporgenza_cm"] = r2[0].number_input(
                    "Sporgenza [cm]", 5.0, 300.0,
                    float(men["sporgenza_cm"]), 5.0,
                    key=widget_key(f"men_s_{uid}"))
                men["larghezza_cm"] = r2[1].number_input(
                    "Larghezza [cm]", 5.0, 300.0,
                    float(men["larghezza_cm"]), 5.0,
                    key=widget_key(f"men_w_{uid}"))
                men["quota_cm"] = r2[2].number_input(
                    "Quota top dalla testa [cm]", 0.0, 2000.0,
                    float(men["quota_cm"]), 5.0,
                    key=widget_key(f"men_q_{uid}"))

                r3 = st.columns(3)
                men["altezza_cm"] = r3[0].number_input(
                    "Altezza in punta [cm]", 5.0, 300.0,
                    float(men["altezza_cm"]), 5.0,
                    key=widget_key(f"men_h_{uid}"))
                men["altezza_base_cm"] = r3[1].number_input(
                    "Altezza all'attacco [cm]", 5.0, 300.0,
                    float(men["altezza_base_cm"]), 5.0,
                    key=widget_key(f"men_hb_{uid}"),
                    disabled=not men["rastremata"])

                face_dim = b_cm if men["lato"] in ("x+", "x-") else h_cm
                if men["larghezza_cm"] > face_dim:
                    st.warning(f"⚠️ Larghezza > faccia {face_dim:.0f} cm.")

        if to_remove_men_id is not None:
            st.session_state.mensole = [
                e for e in st.session_state.mensole if e["id"] != to_remove_men_id]
            st.rerun()

        if st.button("➕ Aggiungi mensola", key=widget_key("add_men")):
            st.session_state.mensole.append({
                "id": st.session_state.mensole_next_id,
                "lato": "x+", "sporgenza_cm": 40.0, "larghezza_cm": 40.0,
                "quota_cm": 100.0, "altezza_cm": 30.0,
                "rastremata": False, "altezza_base_cm": 50.0, "doppia": False,
                "rebar": {
                    "cover_cm": 3.0, "n_top_bars": 3, "d_top_mm": 16.0,
                    "vertical_anchorage_enabled": False,
                    "vertical_anchorage_cm": 50.0, "return_enabled": False,
                    "stirrup_h_pitch_cm": 15.0, "stirrup_h_d_mm": 8.0,
                    "stirrup_v_pitch_cm": 15.0, "stirrup_v_d_mm": 8.0,
                    "tirafondi_enabled": False, "n_tirafondi": 2,
                    "d_tirafondi_mm": 24.0, "tir_dist_testa_cm": 10.0,
                    "tir_dist_bordo_cm": 12.0, "tir_prof_dado_cm": 15.0,
                    "tir_sporgenza_cm": 50.0,
                },
            })
            st.session_state.mensole_next_id += 1
            st.rerun()

    # ------------------------------------------------------------
    # TAB ARMATURA MENSOLE
    # ------------------------------------------------------------
    with tab_arm_men:
        st.markdown("#### 🟫 Armatura mensole")
        if not st.session_state.mensole:
            st.info("Aggiungi prima una mensola nella tab 🏗️ Mensole.")
        else:
            for men in st.session_state.mensole:
                uid = men["id"]
                rb = men["rebar"]
                defaults = {
                    "cover_cm": 3.0, "n_top_bars": 3, "d_top_mm": 16.0,
                    "vertical_anchorage_enabled": False,
                    "vertical_anchorage_cm": 50.0, "return_enabled": False,
                    "stirrup_h_pitch_cm": 15.0, "stirrup_h_d_mm": 8.0,
                    "stirrup_v_pitch_cm": 15.0, "stirrup_v_d_mm": 8.0,
                    "tirafondi_enabled": False, "n_tirafondi": 2,
                    "d_tirafondi_mm": 24.0, "tir_dist_testa_cm": 10.0,
                    "tir_dist_bordo_cm": 12.0, "tir_prof_dado_cm": 15.0,
                    "tir_sporgenza_cm": 50.0,
                }
                for k, v in defaults.items():
                    rb.setdefault(k, v)

                lato_txt = {"x+": "Destra (+X)", "x-": "Sinistra (−X)",
                            "y+": "Alto (+Y)", "y-": "Basso (−Y)"}.get(
                                men["lato"], men["lato"])
                header = (f"🏗️ Mensola #{uid} — {lato_txt}"
                          f"{' (doppia)' if men['doppia'] else ''}"
                          f"{' (rastremata)' if men['rastremata'] else ''}")

                with st.expander(header, expanded=False):
                    st.markdown("**Ferri superiori**")
                    c1, c2, c3 = st.columns(3)
                    rb["cover_cm"] = c1.number_input(
                        "Copriferro [cm]", 1.0, 10.0,
                        float(rb["cover_cm"]), 0.5,
                        key=widget_key(f"mr_cov_{uid}"))
                    rb["n_top_bars"] = c2.number_input(
                        "N° ferri", 1, 20, int(rb["n_top_bars"]), 1,
                        key=widget_key(f"mr_nt_{uid}"))
                    rb["d_top_mm"] = c3.number_input(
                        "Ø ferri [mm]", 6, 40, int(rb["d_top_mm"]), 2,
                        key=widget_key(f"mr_dt_{uid}"))

                    if men["doppia"]:
                        st.info("ℹ️ Mensola doppia: ferri superiori proseguono.")
                        rb["vertical_anchorage_enabled"] = False
                    else:
                        st.markdown("**Ancoraggio verticale** (opzionale)")
                        c4, c5 = st.columns(2)
                        rb["vertical_anchorage_enabled"] = c4.checkbox(
                            "Abilita ancoraggio verticale",
                            value=bool(rb["vertical_anchorage_enabled"]),
                            key=widget_key(f"mr_anc_en_{uid}"))
                        rb["vertical_anchorage_cm"] = c5.number_input(
                            "Lunghezza [cm]", 10.0, 300.0,
                            float(rb["vertical_anchorage_cm"]), 5.0,
                            key=widget_key(f"mr_anc_{uid}"),
                            disabled=not rb["vertical_anchorage_enabled"])

                    st.markdown("**Ripiego verso il pilastro** (opzionale)")
                    rb["return_enabled"] = st.checkbox(
                        "Abilita ripiego verso il pilastro",
                        value=bool(rb["return_enabled"]),
                        key=widget_key(f"mr_ret_{uid}"))

                    st.markdown("**Staffe orizzontali**")
                    c6, c7 = st.columns(2)
                    rb["stirrup_h_pitch_cm"] = c6.number_input(
                        "Passo verticale [cm]", 0.0, 100.0,
                        float(rb["stirrup_h_pitch_cm"]), 1.0,
                        key=widget_key(f"mr_shp_{uid}"), help="0 = disattivate")
                    rb["stirrup_h_d_mm"] = c7.number_input(
                        "Ø [mm]", 6, 20, int(rb["stirrup_h_d_mm"]), 2,
                        key=widget_key(f"mr_shd_{uid}"),
                        disabled=rb["stirrup_h_pitch_cm"] <= 0)

                    st.markdown("**Staffe verticali**")
                    c8, c9 = st.columns(2)
                    rb["stirrup_v_pitch_cm"] = c8.number_input(
                        "Passo [cm]", 0.0, 100.0,
                        float(rb["stirrup_v_pitch_cm"]), 1.0,
                        key=widget_key(f"mr_svp_{uid}"), help="0 = disattivate")
                    rb["stirrup_v_d_mm"] = c9.number_input(
                        "Ø [mm]", 6, 20, int(rb["stirrup_v_d_mm"]), 2,
                        key=widget_key(f"mr_svd_{uid}"),
                        disabled=rb["stirrup_v_pitch_cm"] <= 0)

                    st.markdown("---")
                    st.markdown("**🟪 Tirafondi verticali con dado**")
                    tc1, tc2 = st.columns(2)
                    rb["tirafondi_enabled"] = tc1.checkbox(
                        "Abilita tirafondi",
                        value=bool(rb["tirafondi_enabled"]),
                        key=widget_key(f"mr_tir_en_{uid}"))
                    rb["n_tirafondi"] = tc2.number_input(
                        "N° tirafondi", 1, 10, int(rb["n_tirafondi"]), 1,
                        key=widget_key(f"mr_tir_n_{uid}"),
                        disabled=not rb["tirafondi_enabled"])

                    tc3, tc4 = st.columns(2)
                    rb["d_tirafondi_mm"] = tc3.number_input(
                        "Ø tirafondo [mm]", 8, 40,
                        int(rb["d_tirafondi_mm"]), 2,
                        key=widget_key(f"mr_tir_d_{uid}"),
                        disabled=not rb["tirafondi_enabled"])
                    rb["tir_dist_testa_cm"] = tc4.number_input(
                        "Dist. dalla testa [cm]", 2.0, 200.0,
                        float(rb["tir_dist_testa_cm"]), 1.0,
                        key=widget_key(f"mr_tir_dt_{uid}"),
                        disabled=not rb["tirafondi_enabled"])

                    tc5, tc6, tc7 = st.columns(3)
                    rb["tir_dist_bordo_cm"] = tc5.number_input(
                        "Dist. dal bordo [cm]", 2.0, 100.0,
                        float(rb["tir_dist_bordo_cm"]), 0.5,
                        key=widget_key(f"mr_tir_db_{uid}"),
                        disabled=not rb["tirafondi_enabled"])
                    rb["tir_prof_dado_cm"] = tc6.number_input(
                        "Prof. dado [cm]", 3.0, 100.0,
                        float(rb["tir_prof_dado_cm"]), 1.0,
                        key=widget_key(f"mr_tir_pd_{uid}"),
                        disabled=not rb["tirafondi_enabled"])
                    rb["tir_sporgenza_cm"] = tc7.number_input(
                        "Sporgenza [cm]", 0.0, 100.0,
                        float(rb["tir_sporgenza_cm"]), 0.5,
                        key=widget_key(f"mr_tir_sp_{uid}"),
                        disabled=not rb["tirafondi_enabled"])

                    if rb["tirafondi_enabled"]:
                        face_dim = men["larghezza_cm"]
                        if 2 * rb["tir_dist_bordo_cm"] >= face_dim:
                            st.warning(
                                f"⚠️ Distanza dal bordo troppo grande per la "
                                f"larghezza ({face_dim:.0f} cm).")

    # ------------------------------------------------------------
    # TAB VISTA
    # ------------------------------------------------------------
    with tab_vis:
        st.markdown("#### 🎨 Calcestruzzo e solidi")
        show_concrete = st.checkbox(
            "Mostra calcestruzzo",
            value=bool(get_param("show_concrete", True)),
            key=widget_key("show_concrete"))
        opacity_cls = st.slider(
            "Opacità calcestruzzo", 0.0, 1.0,
            float(get_param("opacity_cls", 0.15)), 0.05,
            key=widget_key("opacity_cls"))
        show_foundation = st.checkbox(
            "Mostra fondazione",
            value=bool(get_param("show_foundation", True)),
            key=widget_key("show_foundation"))
        show_mensole = st.checkbox(
            "Mostra mensole",
            value=bool(get_param("show_mensole", True)),
            key=widget_key("show_mensole"))
        mensole_opacity = st.slider(
            "Opacità mensole", 0.0, 1.0,
            float(get_param("mensole_opacity", 0.55)), 0.05,
            disabled=not show_mensole, key=widget_key("mensole_opacity"))

        st.markdown("---")
        st.markdown("#### ✏️ Bordi")
        show_column_edges = st.checkbox(
            "Bordi pilastro",
            value=bool(get_param("show_column_edges", False)),
            key=widget_key("show_column_edges"))
        column_edges_width = st.slider(
            "Spessore bordi pilastro", 1, 8,
            int(get_param("column_edges_width", 3)), 1,
            disabled=not show_column_edges,
            key=widget_key("column_edges_width"))
        show_mensole_edges = st.checkbox(
            "Bordi mensole",
            value=bool(get_param("show_mensole_edges", False)),
            key=widget_key("show_mensole_edges"))
        mensole_edges_width = st.slider(
            "Spessore bordi mensole", 1, 8,
            int(get_param("mensole_edges_width", 3)), 1,
            disabled=not show_mensole_edges,
            key=widget_key("mensole_edges_width"))

        st.markdown("---")
        st.markdown("#### 🔩 Armatura pilastro")
        show_bars = st.checkbox(
            "Mostra ferri longitudinali",
            value=bool(get_param("show_bars", True)),
            key=widget_key("show_bars"))
        show_stirrups = st.checkbox(
            "Mostra staffe",
            value=bool(get_param("show_stirrups", True)),
            key=widget_key("show_stirrups"))
        show_dense = st.checkbox(
            "Mostra fasce infittite sopra mensole",
            value=bool(get_param("show_dense", True)),
            key=widget_key("show_dense"))
        show_hooks_3d = st.checkbox(
            "Mostra ganci",
            value=bool(get_param("show_hooks_3d", True)),
            key=widget_key("show_hooks_3d"))
        show_forks_3d = st.checkbox(
            "Mostra forche",
            value=bool(get_param("show_forks_3d", True)),
            key=widget_key("show_forks_3d"))
        show_ties_3d = st.checkbox(
            "Mostra tirafondi pilastro",
            value=bool(get_param("show_ties_3d", True)),
            key=widget_key("show_ties_3d"))

        st.markdown("---")
        st.markdown("#### 🟫 Armatura mensole")
        show_men_top = st.checkbox(
            "Ferri superiori mensole",
            value=bool(get_param("show_men_top", True)),
            key=widget_key("show_men_top"))
        show_men_sh = st.checkbox(
            "Staffe orizzontali mensole",
            value=bool(get_param("show_men_sh", True)),
            key=widget_key("show_men_sh"))
        show_men_sv = st.checkbox(
            "Staffe verticali mensole",
            value=bool(get_param("show_men_sv", True)),
            key=widget_key("show_men_sv"))
        show_men_tir = st.checkbox(
            "Tirafondi mensole",
            value=bool(get_param("show_men_tir", True)),
            key=widget_key("show_men_tir"))

        st.markdown("---")
        st.markdown("#### 📐 Inquadratura")
        real_prop = st.checkbox(
            "Proporzioni reali", value=bool(get_param("real_prop", True)),
            key=widget_key("real_prop"))
        grid_on = st.checkbox(
            "Griglia assi", value=bool(get_param("grid_on", True)),
            key=widget_key("grid_on"))
        auto_fit = st.checkbox(
            "Auto-fit", value=bool(get_param("auto_fit", True)),
            key=widget_key("auto_fit"))
        zoom_factor = st.slider(
            "Margine di inquadratura", 0.7, 2.5,
            float(get_param("zoom_factor", 1.0)), 0.05,
            disabled=not auto_fit, key=widget_key("zoom_factor"))

        st.markdown("---")
        st.markdown("#### 📄 Opzioni report PDF")
        pdf_show_3d = st.checkbox(
            "Includi vista 3D nel PDF",
            value=bool(get_param("pdf_show_3d", True)),
            key=widget_key("pdf_show_3d"))
        pdf_3d_opacity = st.slider(
            "Opacità cls/mensole nel 3D del PDF",
            0.0, 0.3,
            float(get_param("pdf_3d_opacity", 0.08)), 0.02,
            key=widget_key("pdf_3d_opacity"),
            help="Opacità ridotta = si vedono meglio le armature.")
        st.caption("ℹ️ La generazione del PDF con vista 3D richiede la libreria "
                   "**kaleido**. Se non è installata, il PDF verrà generato "
                   "senza la vista 3D.")

    # ------------------------------------------------------------
    # MODELLO
    # ------------------------------------------------------------
    extras_list = [
        ExtraBar(distance_cm=float(e["distance_cm"]),
                 diameter_mm=float(e["diameter_mm"]),
                 mirror=bool(e["mirror"]))
        for e in st.session_state.extras
    ]

    mensole_list = []
    for men in st.session_state.mensole:
        rb = men["rebar"]
        mensole_list.append(Mensola(
            lato=men["lato"],
            sporgenza_cm=float(men["sporgenza_cm"]),
            larghezza_cm=float(men["larghezza_cm"]),
            quota_cm=float(men["quota_cm"]),
            altezza_cm=float(men["altezza_cm"]),
            rastremata=bool(men["rastremata"]),
            altezza_base_cm=float(men["altezza_base_cm"]),
            doppia=bool(men["doppia"]),
            rebar=MensolaRebar(
                cover_cm=float(rb.get("cover_cm", 3.0)),
                n_top_bars=int(rb.get("n_top_bars", 3)),
                d_top_mm=float(rb.get("d_top_mm", 16.0)),
                vertical_anchorage_enabled=bool(rb.get("vertical_anchorage_enabled", False)),
                vertical_anchorage_cm=float(rb.get("vertical_anchorage_cm", 50.0)),
                return_enabled=bool(rb.get("return_enabled", False)),
                stirrup_h_pitch_cm=float(rb.get("stirrup_h_pitch_cm", 15.0)),
                stirrup_h_d_mm=float(rb.get("stirrup_h_d_mm", 8.0)),
                stirrup_v_pitch_cm=float(rb.get("stirrup_v_pitch_cm", 15.0)),
                stirrup_v_d_mm=float(rb.get("stirrup_v_d_mm", 8.0)),
                tirafondi_enabled=bool(rb.get("tirafondi_enabled", False)),
                n_tirafondi=int(rb.get("n_tirafondi", 2)),
                d_tirafondi_mm=float(rb.get("d_tirafondi_mm", 24.0)),
                tir_dist_testa_cm=float(rb.get("tir_dist_testa_cm", 10.0)),
                tir_dist_bordo_cm=float(rb.get("tir_dist_bordo_cm", 12.0)),
                tir_prof_dado_cm=float(rb.get("tir_prof_dado_cm", 15.0)),
                tir_sporgenza_cm=float(rb.get("tir_sporgenza_cm", 50.0)),
            ),
        ))

    model = ColumnModel(
        b_cm=b_cm, h_cm=h_cm, H_cm=H_cm, cover_cm=cover,
        longitudinal=LongitudinalLayout(
            corner=CornerBars(diameter_mm=float(d_corner),
                              coupled=bool(coupled_corner)),
            intermediate=IntermediateBars(
                n_bars=int(n_int),
                diameter_mm=float(d_int),
                coupled=bool(coupled_int),
                spacing_mode=("uniform" if spacing_mode_ui == "Uniforme" else "custom"),
                custom_spacings=custom_spacings,
            ),
            extras=extras_list,
        ),
        stirrups=Stirrups(
            hooks=Hooks(enabled=bool(hooks_enabled),
                        diameter_mm=float(hook_dia)),
            ductile_zone_length_cm=float(duct_len),
            head_zone_length_cm=float(head_len),
            ductile=StirrupZone(diameter_mm=float(duct_d), pitch_cm=float(duct_p)),
            head=StirrupZone(diameter_mm=float(head_d), pitch_cm=float(head_p)),
            minimum=StirrupZone(diameter_mm=float(min_d), pitch_cm=float(min_p)),
            embedded=StirrupZone(diameter_mm=float(emb_d), pitch_cm=float(emb_p)),
            dense_zones=DenseZone(
                enabled=bool(dense_enabled),
                diameter_mm=float(dense_d),
                pitch_cm=float(dense_p),
                length_cm=float(dense_len),
            ),
        ),
        foundation=Foundation(tipo=tipo_fond,
                              anchorage_length_cm=float(anchorage),
                              bicchiere_depth_cm=float(bicchiere_depth)),
        forks=Forks(enabled=bool(forks_enabled),
                    n_per_side=int(n_forks),
                    diameter_mm=float(fork_dia),
                    length_cm=float(fork_length)),
        tie_rods=TieRod(enabled=bool(tie_enabled),
                        diameter_mm=float(tie_d),
                        protrusion_cm=float(tie_prot),
                        embedment_cm=float(tie_emb),
                        offset_cm=float(tie_off)),
        mensole=mensole_list,
    )

    st.session_state["_current_params"] = {
        "nome_progetto": nome_progetto,
        "descrizione_progetto": descrizione_progetto,
        "b_cm": b_cm, "h_cm": h_cm, "H_cm": H_cm, "cover": cover,
        "tipo_fond": tipo_fond, "anchorage": anchorage,
        "bicchiere_depth": bicchiere_depth,
        "d_corner": d_corner, "coupled_corner": coupled_corner,
        "n_int": n_int, "d_int": d_int, "coupled_int": coupled_int,
        "spacing_mode_ui": spacing_mode_ui,
        "custom_txt": locals().get("txt", ""),
        "duct_len": duct_len, "duct_d": duct_d, "duct_p": duct_p,
        "head_len": head_len, "head_d": head_d, "head_p": head_p,
        "min_d": min_d, "min_p": min_p, "emb_d": emb_d, "emb_p": emb_p,
        "hooks_enabled": hooks_enabled, "hook_dia": hook_dia,
        "forks_enabled": forks_enabled, "n_forks": n_forks,
        "fork_dia": fork_dia, "fork_length": fork_length,
        "tie_enabled": tie_enabled, "tie_d": tie_d, "tie_off": tie_off,
        "tie_prot": tie_prot, "tie_emb": tie_emb,
        "dense_enabled": dense_enabled, "dense_d": dense_d,
        "dense_p": dense_p, "dense_len": dense_len,
        "pdf_show_3d": pdf_show_3d, "pdf_3d_opacity": pdf_3d_opacity,
        "show_concrete": show_concrete, "opacity_cls": opacity_cls,
        "show_foundation": show_foundation, "show_mensole": show_mensole,
        "mensole_opacity": mensole_opacity,
        "show_column_edges": show_column_edges,
        "column_edges_width": column_edges_width,
        "show_mensole_edges": show_mensole_edges,
        "mensole_edges_width": mensole_edges_width,
        "show_bars": show_bars, "show_stirrups": show_stirrups,
        "show_dense": show_dense,
        "show_hooks_3d": show_hooks_3d, "show_forks_3d": show_forks_3d,
        "show_ties_3d": show_ties_3d,
        "show_men_top": show_men_top, "show_men_sh": show_men_sh,
        "show_men_sv": show_men_sv, "show_men_tir": show_men_tir,
        "real_prop": real_prop, "grid_on": grid_on,
        "auto_fit": auto_fit, "zoom_factor": zoom_factor,
    }

    if st.session_state.get("do_save", False):
        try:
            data = build_export_dict()
            json_bytes = json.dumps(data, indent=2).encode("utf-8")
            nome_file = (data.get("project_name", "") or "pilastro").strip()
            nome_file = "".join(c for c in nome_file
                                if c.isalnum() or c in " -_").strip()
            if not nome_file:
                nome_file = "pilastro"
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
            st.session_state["_last_json"] = json_bytes
            st.session_state["_last_json_name"] = f"{nome_file}_{ts}.json"
            st.session_state["do_save"] = False
            st.session_state["_download_ready"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Errore nel salvataggio: {e}")
            st.session_state["do_save"] = False

    # ------------------------------------------------------------
    # TAB RIEPILOGO
    # ------------------------------------------------------------
    with tab_riep:
        st.markdown("#### 📊 Riepilogo del pilastro")
        if nome_progetto or descrizione_progetto:
            with st.container(border=True):
                if nome_progetto:
                    st.markdown(f"### 📌 {nome_progetto}")
                if descrizione_progetto:
                    st.markdown(descrizione_progetto)
            st.markdown("")

        q = compute_material_quantities(model)

        st.markdown("##### 📐 Geometria")
        g1, g2, g3 = st.columns(3)
        g1.metric("Larghezza b", f"{model.b_cm:.0f} cm")
        g2.metric("Profondità h", f"{model.h_cm:.0f} cm")
        g3.metric("Altezza H", f"{model.H_cm:.0f} cm")
        g1, g2, g3 = st.columns(3)
        g1.metric("Area sezione", f"{q['A_cls_cm2']:.0f} cm²")
        g2.metric("Rapporto H/b", f"{model.H_cm / model.b_cm:.2f}")
        g3.metric("Copriferro", f"{model.cover_cm:.1f} cm")

        st.markdown("---")
        st.markdown("##### 🏛️ Fondazione")
        if model.foundation.tipo == "nessuna":
            st.info("Nessuna fondazione specificata.")
        elif model.foundation.tipo == "armatubo":
            st.markdown(
                f"- **Tipo:** Armatubo\n"
                f"- **Lunghezza di ancoraggio:** {model.foundation.anchorage_length_cm:.0f} cm")
        else:
            st.markdown(
                f"- **Tipo:** Plinto a bicchiere\n"
                f"- **Profondità bicchiere:** {model.foundation.bicchiere_depth_cm:.0f} cm")

        st.markdown("---")
        st.markdown("##### 🧱 Calcestruzzo")
        c1, c2 = st.columns(2)
        c1.metric("Volume pilastro", f"{q['V_pilastro_m3']:.3f} m³")
        c2.metric("Volume mensole", f"{q['V_mensole_m3']:.3f} m³")
        c1, c2, c3 = st.columns(3)
        c1.metric("Volume totale cls", f"{q['V_cls_m3']:.3f} m³")
        c2.metric("Peso cls", f"{q['peso_cls_kN']:.2f} kN")
        c3.metric("Massa cls", f"{q['peso_cls_kg']:.0f} kg")

        st.markdown("---")
        st.markdown("##### 🔩 Acciaio d'armatura")
        with st.expander("Dettaglio volume acciaio per gruppo", expanded=False):
            st.markdown(f"- Ferri longitudinali: **{q['V_long_cm3']:.0f} cm³**")
            st.markdown(f"- Staffe (base): **{q['V_stirrups_cm3']:.0f} cm³**")
            if model.stirrups.dense_zones.enabled:
                st.markdown(f"- Staffe infittite sopra mensole: **{q['V_dense_cm3']:.0f} cm³**")
            if model.stirrups.hooks.enabled:
                st.markdown(f"- Ganci: **{q['V_hooks_cm3']:.0f} cm³**")
            if model.forks.enabled:
                st.markdown(f"- Forche: **{q['V_forks_cm3']:.0f} cm³**")
            if model.tie_rods.enabled:
                st.markdown(f"- Tirafondi pilastro: **{q['V_ties_cm3']:.0f} cm³**")
            if model.mensole:
                st.markdown(f"- Ferri superiori mensole: **{q['V_men_top_cm3']:.0f} cm³**")
                st.markdown(f"- Staffe orizzontali mensole: **{q['V_men_sh_cm3']:.0f} cm³**")
                st.markdown(f"- Staffe verticali mensole: **{q['V_men_sv_cm3']:.0f} cm³**")
                st.markdown(f"- Tirafondi mensole: **{q['V_men_tir_cm3']:.0f} cm³**")

        c1, c2, c3 = st.columns(3)
        c1.metric("Volume acciaio", f"{q['V_steel_m3'] * 1000:.2f} dm³")
        c2.metric("Peso acciaio", f"{q['peso_steel_kN']:.2f} kN")
        c3.metric("Massa acciaio", f"{q['peso_steel_kg']:.1f} kg")

        st.markdown("---")
        st.markdown("##### 🟥 Ferri longitudinali")
        c1, c2, c3 = st.columns(3)
        c1.metric("N° barre totali", f"{q['n_long_bars']}")
        c2.metric("Area totale", f"{q['A_long_cm2']:.2f} cm²")
        c3.metric("Perc. geometrica", f"{q['perc_arm']:.2f} %")
        if q['bar_counts']:
            st.markdown("**Distinta barre longitudinali:**")
            for d_mm, n in sorted(q['bar_counts'].items()):
                st.markdown(f"- Ø{d_mm} mm — **{n} barre**")

        st.markdown("---")
        st.markdown("##### ⚖️ Riepilogo totale")
        peso_tot_kN = q['peso_cls_kN'] + q['peso_steel_kN']
        peso_tot_kg = q['peso_cls_kg'] + q['peso_steel_kg']
        c1, c2, c3 = st.columns(3)
        c1.metric("Peso totale", f"{peso_tot_kN:.2f} kN")
        c2.metric("Massa totale", f"{peso_tot_kg:.0f} kg")
        if q['V_cls_m3'] > 0:
            rapp = q['V_steel_m3'] / q['V_cls_m3'] * 100
            c3.metric("Rapporto acciaio/cls", f"{rapp:.2f} %")
        else:
            c3.metric("Rapporto acciaio/cls", "—")
        st.caption(
            f"Peso specifico cls: {CLS_KN_M3:.1f} kN/m³ — "
            f"Peso specifico acciaio: {STEEL_KN_M3:.1f} kN/m³")

    # ------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------
    st.markdown("---")
    st.subheader("📄 Report PDF")
    if st.button("🔧 Genera PDF", width='stretch', type="primary",
                 key=widget_key("gen_pdf")):
        with st.spinner("Generazione del PDF in corso (con export 3D)..."):
            bars_ = build_longitudinal_bars(model)
            stirrups_base, stirrups_dense = build_all_stirrups(model)
            hooks_ = build_hooks(model, stirrups_base)
            forks_ = build_forks(model)
            ties_ = build_tie_rods(model)
            top_bars_, sh_segs_, sv_segs_, tir_segs_ = build_mensole_rebar(model)
            q_ = compute_material_quantities(model)

            fig_pdf = go.Figure()
            op = pdf_3d_opacity

            v, f = box_geometry(0, 0, 0, model.b_cm, model.h_cm, model.H_cm)
            fig_pdf.add_trace(go.Mesh3d(
                x=v[:, 0], y=v[:, 1], z=v[:, 2],
                i=f[:, 0], j=f[:, 1], k=f[:, 2],
                color="rgb(210,210,215)", opacity=op,
                name="Calcestruzzo", showlegend=False, hoverinfo='skip',
                flatshading=True,
                lighting=dict(ambient=0.9, diffuse=0.3)))

            if model.foundation.tipo == "armatubo":
                a = model.foundation.anchorage_length_cm
                margin = 10
                v, f = box_geometry(-margin, -margin, -a,
                                     model.b_cm + 2 * margin,
                                     model.h_cm + 2 * margin, a)
                fig_pdf.add_trace(go.Mesh3d(
                    x=v[:, 0], y=v[:, 1], z=v[:, 2],
                    i=f[:, 0], j=f[:, 1], k=f[:, 2],
                    color="rgb(160,140,90)", opacity=op * 1.5,
                    showlegend=False, hoverinfo='skip',
                    flatshading=True,
                    lighting=dict(ambient=0.9, diffuse=0.3)))
            elif model.foundation.tipo == "bicchiere":
                d = model.foundation.bicchiere_depth_cm
                margin = 15
                v, f = box_geometry(-margin, -margin, 0,
                                     model.b_cm + 2 * margin,
                                     model.h_cm + 2 * margin, d)
                fig_pdf.add_trace(go.Mesh3d(
                    x=v[:, 0], y=v[:, 1], z=v[:, 2],
                    i=f[:, 0], j=f[:, 1], k=f[:, 2],
                    color="rgb(160,140,90)", opacity=op * 1.5,
                    showlegend=False, hoverinfo='skip',
                    flatshading=True,
                    lighting=dict(ambient=0.9, diffuse=0.3)))

            if model.mensole:
                mg = build_mensole_geometry(model)
                v, f = merge_geometries(mg)
                if len(v) > 0:
                    fig_pdf.add_trace(go.Mesh3d(
                        x=v[:, 0], y=v[:, 1], z=v[:, 2],
                        i=f[:, 0], j=f[:, 1], k=f[:, 2],
                        color="rgb(190,185,180)", opacity=op * 1.5,
                        showlegend=False, hoverinfo='skip',
                        flatshading=True,
                        lighting=dict(ambient=0.9, diffuse=0.3)))

            def add_steel(segments, color):
                geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                         for (p1, p2, d) in segments]
                v, f = merge_geometries(geoms)
                if len(v) == 0:
                    return
                fig_pdf.add_trace(go.Mesh3d(
                    x=v[:, 0], y=v[:, 1], z=v[:, 2],
                    i=f[:, 0], j=f[:, 1], k=f[:, 2],
                    color=color, opacity=1.0, flatshading=True,
                    showlegend=False, hoverinfo='skip',
                    lighting=dict(ambient=0.55, diffuse=0.9,
                                  specular=0.3, roughness=0.5)))

            add_steel(bars_, "rgb(190,40,40)")
            add_steel(stirrups_base, "rgb(30,90,190)")
            if stirrups_dense:
                add_steel(stirrups_dense, "rgb(230,120,30)")
            if hooks_:
                add_steel(hooks_, "rgb(123,47,190)")
            if model.forks.enabled:
                add_steel(forks_, "rgb(0,140,90)")
            if model.tie_rods.enabled:
                add_steel(ties_, "rgb(200,150,0)")
            if model.mensole:
                if top_bars_:
                    add_steel(top_bars_, "rgb(220,120,0)")
                if sh_segs_:
                    add_steel(sh_segs_, "rgb(0,170,200)")
                if sv_segs_:
                    add_steel(sv_segs_, "rgb(150,60,200)")
                if tir_segs_:
                    add_steel(tir_segs_, "rgb(230,0,130)")

            H_eff = model.H_cm
            if model.foundation.tipo == "armatubo":
                H_eff += model.foundation.anchorage_length_cm
            cam_pdf = compute_camera("3d", model.b_cm, model.h_cm, H_eff,
                                      zoom_factor=1.15)

            fig_pdf.update_layout(
                scene=dict(
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                    zaxis=dict(visible=False),
                    aspectmode='data',
                    camera=cam_pdf,
                ),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
                showlegend=False,
            )

            pdf_buf = generate_pdf(
                model, bars_, stirrups_base,
                hook_segments=hooks_,
                fig_3d=fig_pdf if pdf_show_3d else None,
                dense_segments=stirrups_dense,
                fork_segments=forks_,
                tie_segments=ties_,
                qty=q_,
            )
            st.session_state["pdf_bytes"] = pdf_buf.getvalue()
        st.success("✅ PDF pronto per il download.")

    if "pdf_bytes" in st.session_state:
        st.download_button(
            "📥 Scarica PDF",
            data=st.session_state["pdf_bytes"],
            file_name=f"armature_pilastro_{datetime.date.today():%Y-%m-%d}.pdf",
            mime="application/pdf",
            width='stretch', key=widget_key("dl_pdf"))

# ------------------------------------------------------------
# COLONNA DESTRA
# ------------------------------------------------------------
with col_right:
    nome_show = st.session_state.get("_current_params", {}).get("nome_progetto", "")
    if nome_show:
        st.markdown(f"### 📌 {nome_show}")

    st.markdown("##### 🎛️ Viste preimpostate")
    vb1, vb2, vb3, vb4 = st.columns(4)
    if vb1.button("🌐  3D", width='stretch',
                  type=("primary" if st.session_state.view_preset == "3d" else "secondary"),
                  key=widget_key("vp_3d")):
        st.session_state.view_preset = "3d"; st.rerun()
    if vb2.button("⬛  X–Z", width='stretch',
                  type=("primary" if st.session_state.view_preset == "xz" else "secondary"),
                  key=widget_key("vp_xz")):
        st.session_state.view_preset = "xz"; st.rerun()
    if vb3.button("⬛  Y–Z", width='stretch',
                  type=("primary" if st.session_state.view_preset == "yz" else "secondary"),
                  key=widget_key("vp_yz")):
        st.session_state.view_preset = "yz"; st.rerun()
    if vb4.button("⬛  X–Y", width='stretch',
                  type=("primary" if st.session_state.view_preset == "xy" else "secondary"),
                  key=widget_key("vp_xy")):
        st.session_state.view_preset = "xy"; st.rerun()

    fig = go.Figure()

    if show_concrete:
        v, f = box_geometry(0, 0, 0, model.b_cm, model.h_cm, model.H_cm)
        fig.add_trace(go.Mesh3d(
            x=v[:, 0], y=v[:, 1], z=v[:, 2],
            i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color="rgb(210,210,215)", opacity=opacity_cls,
            name="Calcestruzzo", showlegend=True, hoverinfo='name',
            flatshading=True, lighting=dict(ambient=0.9, diffuse=0.3)))

    if show_foundation:
        if model.foundation.tipo == "armatubo":
            a = model.foundation.anchorage_length_cm
            margin = 10
            v, f = box_geometry(-margin, -margin, -a,
                                 model.b_cm + 2 * margin,
                                 model.h_cm + 2 * margin, a)
            fig.add_trace(go.Mesh3d(
                x=v[:, 0], y=v[:, 1], z=v[:, 2],
                i=f[:, 0], j=f[:, 1], k=f[:, 2],
                color="rgb(160,140,90)", opacity=0.25,
                name="Fondazione (armatubo)", showlegend=True, hoverinfo='name',
                flatshading=True, lighting=dict(ambient=0.9, diffuse=0.3)))
        elif model.foundation.tipo == "bicchiere":
            d = model.foundation.bicchiere_depth_cm
            margin = 15
            v, f = box_geometry(-margin, -margin, 0,
                                 model.b_cm + 2 * margin,
                                 model.h_cm + 2 * margin, d)
            fig.add_trace(go.Mesh3d(
                x=v[:, 0], y=v[:, 1], z=v[:, 2],
                i=f[:, 0], j=f[:, 1], k=f[:, 2],
                color="rgb(160,140,90)", opacity=0.22,
                name="Fondazione (bicchiere)", showlegend=True, hoverinfo='name',
                flatshading=True, lighting=dict(ambient=0.9, diffuse=0.3)))

    if show_mensole and model.mensole:
        mensole_geoms = build_mensole_geometry(model)
        if mensole_geoms:
            tr = make_mesh_trace(mensole_geoms, "rgb(190,185,180)",
                                  name="Mensole", opacity=mensole_opacity)
            if tr is not None:
                fig.add_trace(tr)

    if show_column_edges:
        col_edges = build_box_edges(0, 0, 0, model.b_cm, model.h_cm, model.H_cm)
        tr = make_edges_trace(col_edges, color="black",
                              name="Bordi pilastro",
                              line_width=column_edges_width)
        if tr is not None:
            fig.add_trace(tr)

    if show_mensole_edges and model.mensole:
        men_edges = build_mensole_edges(model)
        tr = make_edges_trace(men_edges, color="black",
                              name="Bordi mensole",
                              line_width=mensole_edges_width)
        if tr is not None:
            fig.add_trace(tr)

    if show_bars:
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=10)
                 for (p1, p2, d) in build_longitudinal_bars(model)]
        tr = make_mesh_trace(geoms, "rgb(190,40,40)", name="Ferri longitudinali")
        if tr is not None:
            fig.add_trace(tr)

    base_stirrups, dense_stirrups = build_all_stirrups(model)

    if show_stirrups:
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                 for (p1, p2, d) in base_stirrups]
        tr = make_mesh_trace(geoms, "rgb(30,90,190)", name="Staffe")
        if tr is not None:
            fig.add_trace(tr)

    if show_dense and dense_stirrups:
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                 for (p1, p2, d) in dense_stirrups]
        tr = make_mesh_trace(geoms, "rgb(230,120,30)",
                             name="Staffe infittite sopra mensole")
        if tr is not None:
            fig.add_trace(tr)

    if show_hooks_3d and model.stirrups.hooks.enabled:
        hooks_3d = build_hooks(model, base_stirrups)
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                 for (p1, p2, d) in hooks_3d]
        tr = make_mesh_trace(geoms, "rgb(123,47,190)", name="Ganci")
        if tr is not None:
            fig.add_trace(tr)

    if (show_forks_3d and model.forks.enabled
            and st.session_state.view_preset != "xy"):
        forks_3d = build_forks(model)
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                 for (p1, p2, d) in forks_3d]
        tr = make_mesh_trace(geoms, "rgb(0,140,90)", name="Forche (testa)")
        if tr is not None:
            fig.add_trace(tr)

    if show_ties_3d and model.tie_rods.enabled:
        ties_3d = build_tie_rods(model)
        geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=10)
                 for (p1, p2, d) in ties_3d]
        tr = make_mesh_trace(geoms, "rgb(200,150,0)", name="Tirafondi (pilastro)")
        if tr is not None:
            fig.add_trace(tr)

    if model.mensole and (show_men_top or show_men_sh or show_men_sv or show_men_tir):
        top_bars, sh_segs, sv_segs, tir_segs = build_mensole_rebar(model)
        if show_men_top and top_bars:
            geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=10)
                     for (p1, p2, d) in top_bars]
            tr = make_mesh_trace(geoms, "rgb(220,120,0)",
                                  name="Ferri superiori mensole")
            if tr is not None:
                fig.add_trace(tr)
        if show_men_sh and sh_segs:
            geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                     for (p1, p2, d) in sh_segs]
            tr = make_mesh_trace(geoms, "rgb(0,170,200)",
                                  name="Staffe orizzontali mensole")
            if tr is not None:
                fig.add_trace(tr)
        if show_men_sv and sv_segs:
            geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=8)
                     for (p1, p2, d) in sv_segs]
            tr = make_mesh_trace(geoms, "rgb(150,60,200)",
                                  name="Staffe verticali mensole")
            if tr is not None:
                fig.add_trace(tr)
        if show_men_tir and tir_segs:
            geoms = [cylinder_geometry(p1, p2, d / 2, n_seg=10)
                     for (p1, p2, d) in tir_segs]
            tr = make_mesh_trace(geoms, "rgb(230,0,130)",
                                  name="Tirafondi mensole")
            if tr is not None:
                fig.add_trace(tr)

    H_eff = model.H_cm
    if model.foundation.tipo == "armatubo":
        H_eff += model.foundation.anchorage_length_cm
    extra_top = 0.0
    if model.forks.enabled:
        extra_top = max(extra_top, model.forks.diameter_mm / 10.0)
    if model.tie_rods.enabled:
        extra_top = max(extra_top, model.tie_rods.protrusion_cm)
    H_eff += extra_top

    cam = compute_camera(st.session_state.view_preset,
                         model.b_cm, model.h_cm, H_eff,
                         zoom_factor=zoom_factor if auto_fit else 1.0)

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="x [cm]", visible=grid_on,
                       backgroundcolor="rgb(245,245,245)",
                       gridcolor="white", showbackground=grid_on),
            yaxis=dict(title="y [cm]", visible=grid_on,
                       backgroundcolor="rgb(245,245,245)",
                       gridcolor="white", showbackground=grid_on),
            zaxis=dict(title="z [cm]", visible=grid_on,
                       backgroundcolor="rgb(245,245,245)",
                       gridcolor="white", showbackground=grid_on),
            aspectmode='data' if real_prop else 'cube',
            camera=cam,
            uirevision=f"{st.session_state.view_preset}_{auto_fit}_{zoom_factor}",
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=820,
        showlegend=True,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.75)",
                    bordercolor="rgba(0,0,0,0.15)", borderwidth=1),
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, width='stretch',
                    config={"scrollZoom": True, "displaylogo": False,
                            "responsive": True})
    st.caption("💡 Ruota liberamente con il mouse. Le forche non sono mostrate "
               "nella vista X–Y (pianta).")