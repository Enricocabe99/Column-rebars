# pdf_export.py
"""Report PDF tecnico per le armature del pilastro, in stile disegno tecnico."""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Patch, Polygon, Arc
import matplotlib.patches as mpatches
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                 Table, TableStyle, PageBreak)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import datetime

# Palette
C_CORNER = "#8B0000"
C_INTER  = "#D22B2B"
C_EXTRA  = "#FF8C00"
C_STIRR  = "#1E5ABE"
C_HOOK   = "#7B2FBE"
C_FORK   = "#00884A"
C_TIE    = "#C89600"
C_MEN_TIR = "#E60082"
C_DENSE  = "#E6781E"


# ============================================================
# UTILITY
# ============================================================
def _bar_color(d_mm, model):
    if abs(d_mm - model.longitudinal.corner.diameter_mm) < 0.5:
        return C_CORNER
    if abs(d_mm - model.longitudinal.intermediate.diameter_mm) < 0.5:
        return C_INTER
    return C_EXTRA


def _fit_image_aspect(nat_w, nat_h, max_w, max_h):
    if nat_w <= 0 or nat_h <= 0:
        return max_w, max_h
    aspect = nat_w / nat_h
    w, h = max_w, max_w / aspect
    if h > max_h:
        h = max_h
        w = max_h * aspect
    return w, h


def _simple_table(data, col_widths, header_bg=colors.HexColor("#1E5ABE")):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    return t


def _styles():
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                        fontSize=16, alignment=TA_CENTER, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                        fontSize=12, spaceBefore=10, spaceAfter=6,
                        textColor=colors.HexColor("#1E5ABE"))
    h3 = ParagraphStyle("h3", parent=styles["Heading3"],
                        fontSize=10, spaceBefore=6, spaceAfter=4)
    body = styles["BodyText"]
    body.fontSize = 9
    return h1, h2, h3, body


# ============================================================
# FIGURA 3D → PNG (esportazione Plotly)
# ============================================================
def fig_to_png(fig, width=800, height=800):
    """Esporta una figura Plotly in PNG. Ritorna BytesIO o None se fallisce."""
    try:
        img_bytes = fig.to_image(format="png", width=width, height=height,
                                  scale=2)
        buf = io.BytesIO(img_bytes)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Errore export 3D (kaleido?): {e}")
        return None


# ============================================================
# SEZIONE TRASVERSALE NUMERATA
# ============================================================
def draw_section_numbered(model, bars):
    """Sezione trasversale con ferri numerati per gruppo."""
    b, h, cover = model.b_cm, model.h_cm, model.cover_cm
    fig, ax = plt.subplots(figsize=(5.5, 5.5), dpi=150)

    ax.add_patch(Rectangle((0, 0), b, h, facecolor="#F0F0F0",
                            edgecolor="black", linewidth=1.0))

    ds = max(
        model.stirrups.ductile.diameter_mm,
        model.stirrups.head.diameter_mm,
        model.stirrups.minimum.diameter_mm,
        model.stirrups.embedded.diameter_mm,
    ) / 10.0
    sx0, sy0 = cover + ds / 2, cover + ds / 2
    sx1, sy1 = b - cover - ds / 2, h - cover - ds / 2
    ax.add_patch(Rectangle((sx0, sy0), sx1 - sx0, sy1 - sy0,
                            fill=False, edgecolor=C_STIRR, linewidth=2.0,
                            zorder=3))

    groups = {}
    for (p1, p2, d_cm) in bars:
        x, y = p1[0], p1[1]
        d_mm = int(round(d_cm * 10))
        groups.setdefault(d_mm, []).append((x, y))

    group_ids = {}
    gi = 1
    for d_mm in sorted(groups.keys()):
        group_ids[d_mm] = gi
        gi += 1

    for d_mm, positions in groups.items():
        col = _bar_color(d_mm, model)
        num = group_ids[d_mm]
        for (x, y) in positions:
            ax.add_patch(Circle((x, y), d_mm / 20.0,
                                 facecolor=col, edgecolor="black",
                                 linewidth=0.5, zorder=5))
            ax.annotate(f"{num}",
                        xy=(x, y),
                        xytext=(x + 4, y + 4),
                        fontsize=7, fontweight="bold",
                        color="black",
                        bbox=dict(boxstyle="circle,pad=0.15",
                                  facecolor="white", edgecolor="black",
                                  linewidth=0.5),
                        arrowprops=dict(arrowstyle="-", color="black",
                                        lw=0.4),
                        zorder=8)

    ax.annotate("", xy=(0, -5), xytext=(b, -5),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.7))
    ax.text(b / 2, -7, f"{b:.0f}", ha="center", va="top", fontsize=8)
    ax.annotate("", xy=(-5, 0), xytext=(-5, h),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.7))
    ax.text(-7, h / 2, f"{h:.0f}", ha="right", va="center",
            fontsize=8, rotation=90)

    legend_items = []
    for d_mm in sorted(groups.keys()):
        n = len(groups[d_mm])
        legend_items.append(
            f"{group_ids[d_mm]}) {n}Ø{d_mm}"
        )
    legend_txt = "  ".join(legend_items)
    if legend_txt:
        ax.text(b / 2, h + 5, legend_txt, ha="center", va="bottom",
                fontsize=7, wrap=True)

    ax.set_xlim(-12, b + 12)
    ax.set_ylim(-12, h + 15)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Sezione trasversale", fontsize=10, fontweight="bold", pad=15)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# PROSPETTO LONGITUDINALE TECNICO
# ============================================================
def draw_elevation_technical(model, bars, stirrup_segments,
                              dense_segments=None, hook_segments=None,
                              fork_segments=None, tie_segments=None):
    b, h, H, cover = model.b_cm, model.h_cm, model.H_cm, model.cover_cm

    z_min = 0.0
    z_max = H
    if model.foundation.tipo == "armatubo":
        z_min = -model.foundation.anchorage_length_cm
    if model.tie_rods.enabled:
        z_max = max(z_max, H + model.tie_rods.protrusion_cm)
    if model.forks.enabled:
        z_max = max(z_max, H + model.forks.diameter_mm / 10.0)
    z_span = z_max - z_min

    fig_h = 11.0
    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)

    ax.add_patch(Rectangle((0, 0), b, H, facecolor="white",
                            edgecolor="black", linewidth=1.0, zorder=1))

    if model.foundation.tipo == "armatubo":
        ax.add_patch(Rectangle((-8, z_min), b + 16, -z_min,
                                facecolor="#E8E8E8", edgecolor="grey",
                                linewidth=0.6, zorder=0))
        ax.text(b / 2, z_min - 3, "ARMATUBO", ha="center", va="top",
                fontsize=7, style="italic")

    if model.foundation.tipo == "bicchiere":
        d_bic = model.foundation.bicchiere_depth_cm
        ax.add_patch(Rectangle((-8, 0), b + 16, d_bic,
                                facecolor="#E8E8E8", edgecolor="grey",
                                linewidth=0.6, zorder=0))
        ax.text(b / 2, d_bic + 3, "BICCHIERE", ha="center", va="bottom",
                fontsize=7, style="italic")

    seen = set()
    for (p1, p2, d_cm) in bars:
        x, y = p1[0], p1[1]
        key = (round(x, 1), round(y, 1))
        if key in seen:
            continue
        seen.add(key)
        d_mm = int(round(d_cm * 10))
        col = _bar_color(d_mm, model)
        ax.plot([x, x], [p1[2], p2[2]], color=col,
                linewidth=max(1.0, d_cm * 1.0), solid_capstyle="butt",
                zorder=2)

    z_levels_base = sorted(set(round(s[0][2], 3) for s in stirrup_segments))
    for z in z_levels_base:
        ax.plot([cover, b - cover], [z, z],
                color=C_STIRR, linewidth=0.8, zorder=3)

    if dense_segments:
        z_levels_dense = sorted(set(round(s[0][2], 3) for s in dense_segments))
        for z in z_levels_dense:
            ax.plot([cover, b - cover], [z, z],
                    color=C_DENSE, linewidth=0.8, zorder=3)

    if hook_segments:
        z_hooks = sorted(set(round(s[0][2], 3) for s in hook_segments))
        for z in z_hooks:
            ax.plot([cover + 2, b - cover - 2], [z, z],
                    color=C_HOOK, linewidth=0.6, linestyle="--",
                    zorder=4)

    if fork_segments and model.forks.enabled:
        fork_d = model.forks.diameter_mm / 10.0
        z_fork_top = (H - cover) + fork_d / 2
        ax.plot([cover + 3, b - cover - 3], [z_fork_top, z_fork_top],
                color=C_FORK, linewidth=1.2, zorder=5)

    if tie_segments and model.tie_rods.enabled:
        for (p1, p2, d_cm) in tie_segments:
            x, y = p1[0], p1[1]
            if abs(x - y) < 0.1:
                continue
            if abs(x - p1[0]) < 1.0:
                ax.plot([x, x], [p1[2], p2[2]], color=C_TIE,
                        linewidth=1.2, zorder=6)

    def draw_quote(x_pos, z1, z2, label):
        ax.annotate("", xy=(x_pos, z1), xytext=(x_pos, z2),
                    arrowprops=dict(arrowstyle="<->", color="black", lw=0.6),
                    zorder=10)
        ax.text(x_pos - 1.5, (z1 + z2) / 2, label, ha="right", va="center",
                fontsize=6.5, rotation=90, zorder=10)

    draw_quote(-8, 0, H, f"H={H:.0f}")

    Ld = model.stirrups.ductile_zone_length_cm
    if model.foundation.tipo == "bicchiere":
        z_d0 = model.foundation.bicchiere_depth_cm
        z_d1 = z_d0 + Ld
    else:
        z_d0 = cover
        z_d1 = z_d0 + Ld
    draw_quote(-14, z_d0, z_d1, f"duttile={Ld:.0f}")

    Lt = model.stirrups.head_zone_length_cm
    draw_quote(-20, H - cover - Lt, H - cover, f"testa={Lt:.0f}")

    if model.foundation.tipo == "armatubo":
        a = model.foundation.anchorage_length_cm
        draw_quote(-8, z_min, 0, f"anc={a:.0f}")

    if model.mensole and model.stirrups.dense_zones.enabled:
        dz = model.stirrups.dense_zones
        default_len = max(b, h)
        L = dz.length_cm if dz.length_cm > 0 else default_len
        for men in model.mensole:
            z_top_men = H - men.quota_cm
            ax.annotate("", xy=(b + 6, z_top_men),
                        xytext=(b + 6, z_top_men + L),
                        arrowprops=dict(arrowstyle="<->", color=C_DENSE,
                                        lw=0.6))
            ax.text(b + 8, z_top_men + L / 2, f"infittita={L:.0f}",
                    ha="left", va="center", fontsize=6, color=C_DENSE,
                    rotation=90)

    ax.text(b + 15, H / 2, "Ferri long.", ha="left", va="center",
            fontsize=7, color=C_CORNER, rotation=90)
    ax.text(b + 25, H * 0.3, "Staffe", ha="left", va="center",
            fontsize=7, color=C_STIRR, rotation=90)

    ax.set_xlim(-25, b + 35)
    ax.set_ylim(z_min - 10, z_max + 10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Prospetto longitudinale", fontsize=10,
                 fontweight="bold", pad=10)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# SAGOMA STAFFA RETTANGOLARE
# ============================================================
def draw_stirrup_shape(b, h, cover, d_mm, label):
    fig, ax = plt.subplots(figsize=(3.2, 3.2), dpi=150)

    x0, y0 = 0, 0
    x1, y1 = b - 2 * cover, h - 2 * cover
    lw = 2.5
    ax.plot([x0, x1], [y0, y0], color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x1], [y0, y1], color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x0], [y1, y1], color="black", linewidth=lw, zorder=2)
    ax.plot([x0, x0], [y1, y0], color="black", linewidth=lw, zorder=2)

    ganc = min(10, (x1 - x0) * 0.15, (y1 - y0) * 0.15)
    ax.plot([x0, x0 + ganc * np.cos(np.radians(45))],
            [y1, y1 - ganc * np.sin(np.radians(45))],
            color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x1 - ganc * np.cos(np.radians(45))],
            [y1, y1 - ganc * np.sin(np.radians(45))],
            color="black", linewidth=lw, zorder=2)

    L_tot = 2 * (x1 - x0) + 2 * (y1 - y0) + 2 * ganc
    ax.text((x0 + x1) / 2, -8, f"b' = {b - 2 * cover:.0f}",
            ha="center", va="top", fontsize=7)
    ax.text(-8, (y0 + y1) / 2, f"h' = {h - 2 * cover:.0f}",
            ha="right", va="center", fontsize=7, rotation=90)

    ax.text((x0 + x1) / 2, y1 + 8, f"{label}",
            ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax.text((x0 + x1) / 2, y1 + 3, f"Ø{d_mm} mm",
            ha="center", va="bottom", fontsize=7)

    ax.set_xlim(-15, x1 + 8)
    ax.set_ylim(-15, y1 + 15)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# SAGOMA GANCIO
# ============================================================
def draw_hook_shape(b_inner, d_mm, label):
    fig, ax = plt.subplots(figsize=(3.0, 2.5), dpi=150)

    L = b_inner
    lw = 2.0

    x0, x1 = 0, L
    y0, y1 = -10, 0

    ax.plot([x0, x1], [0, 0], color="black", linewidth=lw, zorder=2)
    ax.plot([x0, x0], [0, -10], color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x1], [0, -10], color="black", linewidth=lw, zorder=2)
    ax.plot([x0, x0 + 2], [-10, -10], color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x1 - 2], [-10, -10], color="black", linewidth=lw, zorder=2)

    ax.text((x0 + x1) / 2, 6, label, ha="center", va="bottom",
            fontsize=8, fontweight="bold")
    ax.text((x0 + x1) / 2, 2, f"Ø{d_mm} mm", ha="center", va="bottom",
            fontsize=7)
    ax.text((x0 + x1) / 2, -14, f"L = {L:.0f} cm", ha="center", va="top",
            fontsize=7)

    ax.set_xlim(-5, x1 + 5)
    ax.set_ylim(-20, 12)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# SAGOMA FORCA (U INVERSA)
# ============================================================
def draw_fork_shape(b_width, h_fork, d_mm, label):
    fig, ax = plt.subplots(figsize=(2.8, 3.5), dpi=150)

    lw = 2.5
    x0 = 0
    x1 = b_width
    y_top = 0
    y_bot = -h_fork

    ax.plot([x0, x0], [y_top, y_bot], color="black", linewidth=lw, zorder=2)
    ax.plot([x1, x1], [y_top, y_bot], color="black", linewidth=lw, zorder=2)
    r = min(2.5, b_width / 4)
    ax.plot([x0, x0], [y_top, y_top], color="black", linewidth=lw, zorder=2)
    ax.plot([x0 + r, x1 - r], [y_top, y_top],
            color="black", linewidth=lw, zorder=2)
    arc1 = Arc((x0 + r, y_top - r), 2 * r, 2 * r, angle=0,
                theta1=90, theta2=180, color="black", linewidth=lw,
                zorder=2)
    ax.add_patch(arc1)
    arc2 = Arc((x1 - r, y_top - r), 2 * r, 2 * r, angle=0,
                theta1=0, theta2=90, color="black", linewidth=lw,
                zorder=2)
    ax.add_patch(arc2)

    ax.text((x0 + x1) / 2, 8, label, ha="center", va="bottom",
            fontsize=8, fontweight="bold")
    ax.text((x0 + x1) / 2, 3, f"Ø{d_mm} mm", ha="center", va="bottom",
            fontsize=7)
    ax.text((x0 + x1) / 2, y_bot - 4, f"L = {h_fork:.0f} cm",
            ha="center", va="top", fontsize=7)
    ax.text(-3, y_bot / 2, f"larg. = {b_width:.0f}",
            ha="right", va="center", fontsize=6.5, rotation=90)

    ax.set_xlim(-10, x1 + 5)
    ax.set_ylim(y_bot - 12, 15)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# SAGOMA TIRAFONDO
# ============================================================
def draw_tied_rod(prof_dado, sporgenza, d_mm, label):
    fig, ax = plt.subplots(figsize=(2.2, 3.5), dpi=150)

    lw = 2.5
    x = 0
    dado_h = 1.5
    dado_w = d_mm / 10.0 * 1.8
    ax.add_patch(Rectangle((x - dado_w / 2, -prof_dado),
                            dado_w, dado_h,
                            facecolor="#888888", edgecolor="black",
                            linewidth=1.0))
    ax.plot([x, x], [0, sporgenza], color="black", linewidth=lw, zorder=2)
    ax.plot([x, x], [-prof_dado, 0], color="black", linewidth=lw, zorder=2)

    for z in np.linspace(sporgenza * 0.2, sporgenza * 0.9, 5):
        ax.plot([x - 0.6, x + 0.6], [z, z], color="black", linewidth=0.4)

    ax.text(3, sporgenza / 2, f"sporg.={sporgenza:.0f}",
            ha="left", va="center", fontsize=7, rotation=90)
    ax.text(3, -prof_dado / 2, f"prof.={prof_dado:.0f}",
            ha="left", va="center", fontsize=7, rotation=90)

    ax.text(0, sporgenza + 3, label, ha="center", va="bottom",
            fontsize=8, fontweight="bold")
    ax.text(0, sporgenza + 1, f"Ø{d_mm}", ha="center", va="bottom",
            fontsize=7)

    ax.set_xlim(-8, 12)
    ax.set_ylim(-prof_dado - 5, sporgenza + 10)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# CONTEGGIO E DISTINTE
# ============================================================
def count_longitudinal_bars(bars):
    counts = {}
    for (_, _, d_cm) in bars:
        d_mm = int(round(d_cm * 10))
        counts[d_mm] = counts.get(d_mm, 0) + 1
    return dict(sorted(counts.items()))


def _segment_length_cm(p1, p2):
    return float(np.linalg.norm(np.asarray(p2, float) - np.asarray(p1, float)))


def _bill_of_materials_long(bars):
    by_d = {}
    for (p1, p2, d_cm) in bars:
        d_mm = int(round(d_cm * 10))
        L = _segment_length_cm(p1, p2)
        by_d.setdefault(d_mm, {"qty": 0, "L": L, "Ltot": 0.0})
        by_d[d_mm]["qty"] += 1
        by_d[d_mm]["L"] = L
        by_d[d_mm]["Ltot"] += L
    rows = []
    for d_mm in sorted(by_d.keys()):
        v = by_d[d_mm]
        rows.append((d_mm, v["L"], v["qty"], v["Ltot"] / 100.0))
    return rows


def _bill_of_materials_stirrups(segments, axis_perimeter_fn=None):
    by_d = {}
    for (p1, p2, d_cm) in segments:
        d_mm = int(round(d_cm * 10))
        L = _segment_length_cm(p1, p2)
        by_d.setdefault(d_mm, {"Ltot": 0.0, "n_seg": 0})
        by_d[d_mm]["Ltot"] += L
        by_d[d_mm]["n_seg"] += 1
    rows = []
    for d_mm in sorted(by_d.keys()):
        v = by_d[d_mm]
        n_st = v["n_seg"] / 4.0
        rows.append((d_mm, v["Ltot"] / 100.0, n_st))
    return rows


# ============================================================
# LETTURA NOME/DESCRIZIONE PROGETTO
# ============================================================
def _read_project_meta():
    """Legge nome e descrizione progetto da Streamlit se disponibile."""
    try:
        import streamlit as st
        params = st.session_state.get("_current_params", {})
        return (params.get("nome_progetto", "") or "",
                params.get("descrizione_progetto", "") or "")
    except Exception:
        return "", ""


# ============================================================
# GENERAZIONE PDF COMPLETO
# ============================================================
def generate_pdf(model, bars, stirrup_segments, hook_segments=None,
                 fig_3d=None, dense_segments=None, fork_segments=None,
                 tie_segments=None, qty=None):
    """Genera il PDF completo. Ritorna un BytesIO."""
    h1, h2, h3, body = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="Relazione armature pilastro",
    )

    story = []

    # =========================================================
    # PAGINA 1
    # =========================================================
    story.append(Paragraph("Relazione armature — Pilastro in c.a.", h1))
    story.append(Spacer(1, 2 * mm))
    ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Documento generato automaticamente il {ts}. "
        f"Le dimensioni sono espresse in centimetri.", body))
    story.append(Spacer(1, 4 * mm))

    nome_p, descr_p = _read_project_meta()
    if nome_p or descr_p:
        proj_rows = [["Progetto", nome_p or "—"]]
        if descr_p:
            proj_rows.append(["Descrizione", descr_p])
        story.append(_simple_table(proj_rows, [35 * mm, 130 * mm]))
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Dati generali", h2))
    data = [
        ["Larghezza b", f"{model.b_cm:.0f} cm", "Altezza H", f"{model.H_cm:.0f} cm"],
        ["Profondità h", f"{model.h_cm:.0f} cm", "Copriferro", f"{model.cover_cm:.1f} cm"],
    ]
    if model.foundation.tipo == "armatubo":
        data.append(["Fondazione", "Armatubo", "Ancoraggio",
                     f"{model.foundation.anchorage_length_cm:.0f} cm"])
    elif model.foundation.tipo == "bicchiere":
        data.append(["Fondazione", "Bicchiere", "Profondità",
                     f"{model.foundation.bicchiere_depth_cm:.0f} cm"])
    else:
        data.append(["Fondazione", "—", "", ""])
    t = Table(data, colWidths=[35 * mm, 40 * mm, 35 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("2. Vista 3D del pilastro armato", h2))
    story.append(Paragraph(
        "Il calcestruzzo e le mensole sono rappresentati con opacità ridotta "
        "per mettere in evidenza l'armatura interna.", body))
    story.append(Spacer(1, 2 * mm))

    if fig_3d is not None:
        img3d = fig_to_png(fig_3d, width=900, height=900)
        if img3d is not None:
            sec_w, sec_h = _fit_image_aspect(1.0, 1.0, 150, 150)
            story.append(Image(img3d, width=sec_w * mm, height=sec_h * mm,
                                hAlign="CENTER"))
        else:
            story.append(Paragraph(
                "<i>⚠️ Impossibile generare l'immagine 3D. Verifica che la "
                "libreria kaleido sia installata.</i>", body))
    else:
        story.append(Paragraph("<i>Figura 3D non disponibile.</i>", body))

    story.append(PageBreak())

    # =========================================================
    # PAGINA 2
    # =========================================================
    story.append(Paragraph("3. Prospetto longitudinale — Staffatura", h2))
    elev_img = draw_elevation_technical(
        model, bars, stirrup_segments,
        dense_segments=dense_segments,
        hook_segments=hook_segments,
        fork_segments=fork_segments,
        tie_segments=tie_segments,
    )
    elev_w, elev_h = _fit_image_aspect(model.b_cm, model.H_cm, 80, 200)
    story.append(Image(elev_img, width=elev_w * mm, height=elev_h * mm,
                       hAlign="CENTER"))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("3.1 Fasce di staffatura", h3))
    rows = [["Fascia", "Ø [mm]", "Passo [cm]", "Lunghezza [cm]"]]
    Ld = model.stirrups.ductile_zone_length_cm
    Lt = model.stirrups.head_zone_length_cm
    if model.foundation.tipo == "bicchiere":
        d_bic = model.foundation.bicchiere_depth_cm
        rows.append(["Bicchiere", f"Ø{model.stirrups.embedded.diameter_mm:.0f}",
                     f"{model.stirrups.embedded.pitch_cm:.0f}",
                     f"{max(0, d_bic - model.cover_cm):.0f}"])
        rows.append(["Duttile", f"Ø{model.stirrups.ductile.diameter_mm:.0f}",
                     f"{model.stirrups.ductile.pitch_cm:.0f}", f"{Ld:.0f}"])
    else:
        rows.append(["Duttile", f"Ø{model.stirrups.ductile.diameter_mm:.0f}",
                     f"{model.stirrups.ductile.pitch_cm:.0f}", f"{Ld:.0f}"])
    if model.foundation.tipo == "bicchiere":
        zmin_s = d_bic + Ld
    else:
        zmin_s = model.cover_cm + Ld
    zmin_e = model.H_cm - model.cover_cm - Lt
    rows.append(["Minima", f"Ø{model.stirrups.minimum.diameter_mm:.0f}",
                 f"{model.stirrups.minimum.pitch_cm:.0f}",
                 f"{max(0, zmin_e - zmin_s):.0f}"])
    rows.append(["Testa", f"Ø{model.stirrups.head.diameter_mm:.0f}",
                 f"{model.stirrups.head.pitch_cm:.0f}", f"{Lt:.0f}"])
    if model.stirrups.dense_zones.enabled:
        dz = model.stirrups.dense_zones
        default_len = max(model.b_cm, model.h_cm)
        eff_len = dz.length_cm if dz.length_cm > 0 else default_len
        rows.append(["Infittita sopra mensole",
                     f"Ø{dz.diameter_mm:.0f}",
                     f"{dz.pitch_cm:.0f}",
                     f"{eff_len:.0f}"])
    story.append(_simple_table(rows, [45 * mm, 25 * mm, 30 * mm, 35 * mm]))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("3.2 Riepilogo staffe per diametro", h3))
    st_rows = [["Ø [mm]", "Lunghezza totale [m]"]]
    all_stirrup_segs = list(stirrup_segments or [])
    if dense_segments:
        all_stirrup_segs.extend(dense_segments)
    stir_bom = _bill_of_materials_stirrups(all_stirrup_segs)
    for d_mm, L_tot, n_st in stir_bom:
        st_rows.append([f"Ø{d_mm}", f"{L_tot:.2f}"])
    story.append(_simple_table(st_rows, [35 * mm, 60 * mm]))

    story.append(PageBreak())

    # =========================================================
    # PAGINA 3
    # =========================================================
    story.append(Paragraph("4. Sezione trasversale — Ferri longitudinali", h2))
    sec_img = draw_section_numbered(model, bars)
    sec_w, sec_h = _fit_image_aspect(model.b_cm, model.h_cm, 110, 130)
    story.append(Image(sec_img, width=sec_w * mm, height=sec_h * mm,
                       hAlign="CENTER"))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("4.1 Distinta ferri longitudinali", h3))
    long_bom = _bill_of_materials_long(bars)
    rows = [["Gruppo", "Ø [mm]", "Quantità", "Lungh. singola [cm]",
             "Lungh. totale [m]"]]
    counts = count_longitudinal_bars(bars)
    for d_mm in sorted(counts.keys()):
        matching = [r for r in long_bom if r[0] == d_mm]
        if not matching:
            continue
        _, L, n_bar, Ltot = matching[0]
        role = []
        if abs(d_mm - model.longitudinal.corner.diameter_mm) < 0.5:
            role.append("angolo")
        if (model.longitudinal.intermediate.n_bars > 0
                and abs(d_mm - model.longitudinal.intermediate.diameter_mm) < 0.5):
            role.append("intermedio")
        if not role:
            role.append("extra")
        rows.append([", ".join(role), f"Ø{d_mm}", str(n_bar),
                     f"{L:.0f}", f"{Ltot:.2f}"])
    story.append(_simple_table(rows, [35 * mm, 20 * mm, 22 * mm, 33 * mm,
                                      35 * mm]))
    story.append(Spacer(1, 3 * mm))

    n_long = sum(counts.values())
    A_long_mm2 = sum(n * np.pi * (d / 2.0) ** 2 for d, n in counts.items())
    A_cls_mm2 = model.b_cm * model.h_cm * 100
    perc = A_long_mm2 / A_cls_mm2 * 100 if A_cls_mm2 > 0 else 0
    story.append(Paragraph(
        f"Numero di barre longitudinali: <b>{n_long}</b> — "
        f"Area totale: <b>{A_long_mm2 / 100:.2f} cm²</b> — "
        f"Percentuale geometrica: <b>{perc:.2f}%</b>", body))

    story.append(PageBreak())

    # =========================================================
    # PAGINA 4 — Sagome
    # =========================================================
    story.append(Paragraph("5. Sagome armatura trasversale", h2))

    story.append(Paragraph("5.1 Staffe rettangolari", h3))
    stirrup_imgs = []
    seen_d = set()
    for d in [model.stirrups.ductile.diameter_mm,
              model.stirrups.head.diameter_mm,
              model.stirrups.minimum.diameter_mm,
              model.stirrups.embedded.diameter_mm]:
        d_int = int(round(d))
        if d_int in seen_d:
            continue
        seen_d.add(d_int)
        label = f"Staffa Ø{d_int}"
        buf_img = draw_stirrup_shape(model.b_cm, model.h_cm, model.cover_cm,
                                     d_int, label)
        stirrup_imgs.append(buf_img)

    if stirrup_imgs:
        img_cells = []
        row_cells = []
        for i, img_buf in enumerate(stirrup_imgs):
            img = Image(img_buf, width=55 * mm, height=55 * mm)
            row_cells.append(img)
            if len(row_cells) == 2:
                img_cells.append(row_cells)
                row_cells = []
        if row_cells:
            img_cells.append(row_cells)
        for row in img_cells:
            while len(row) < 2:
                row.append("")
            t = Table([row], colWidths=[80 * mm, 80 * mm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)

    story.append(Spacer(1, 5 * mm))

    if model.stirrups.hooks.enabled:
        story.append(Paragraph("5.2 Ganci (zona duttile)", h3))
        b_inner = model.h_cm - 2 * model.cover_cm
        hook_img = draw_hook_shape(b_inner,
                                    int(model.stirrups.hooks.diameter_mm),
                                    f"Gancio Ø{int(model.stirrups.hooks.diameter_mm)}")
        story.append(Image(hook_img, width=80 * mm, height=50 * mm,
                            hAlign="CENTER"))
        story.append(Spacer(1, 4 * mm))

    if model.forks.enabled:
        story.append(Paragraph("5.3 Forche in testa", h3))
        b_fork = model.b_cm - 2 * model.cover_cm
        fork_img = draw_fork_shape(b_fork, model.forks.length_cm,
                                    int(model.forks.diameter_mm),
                                    f"Forca Ø{int(model.forks.diameter_mm)}")
        story.append(Image(fork_img, width=50 * mm, height=70 * mm,
                            hAlign="CENTER"))
        story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())

    # =========================================================
    # PAGINA 5 — Tirafondi
    # =========================================================
    story.append(Paragraph("6. Tirafondi", h2))

    if model.tie_rods.enabled:
        story.append(Paragraph("6.1 Tirafondi in testa al pilastro", h3))
        tie_img = draw_tied_rod(model.tie_rods.embedment_cm,
                                 model.tie_rods.protrusion_cm,
                                 int(model.tie_rods.diameter_mm),
                                 f"Tirafondo Ø{int(model.tie_rods.diameter_mm)}")
        story.append(Image(tie_img, width=50 * mm, height=90 * mm,
                            hAlign="CENTER"))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Disposti a {model.tie_rods.offset_cm:.0f} cm dai lati. "
            f"4 tirafondi in totale.", body))
        story.append(Spacer(1, 4 * mm))

    tir_mens_data = []
    for i, men in enumerate(model.mensole or []):
        rb = men.rebar
        if rb.tirafondi_enabled:
            n = rb.n_tirafondi * (2 if men.doppia else 1)
            tir_mens_data.append(
                (i + 1, men.lato, rb.n_tirafondi, n,
                 rb.d_tirafondi_mm, rb.tir_dist_testa_cm,
                 rb.tir_prof_dado_cm))
    if tir_mens_data:
        story.append(Paragraph("6.2 Tirafondi nelle mensole", h3))
        rows = [["Mensola", "Lato", "N° per lato", "N° tot",
                 "Ø [mm]", "Dist. testa [cm]", "Prof. dado [cm]"]]
        for (idx, lato, n_l, n_tot, d_mm, dist, prof) in tir_mens_data:
            rows.append([f"#{idx}", lato, str(n_l), str(n_tot),
                         f"Ø{int(d_mm)}", f"{dist:.0f}", f"{prof:.0f}"])
        story.append(_simple_table(rows,
            [20 * mm, 18 * mm, 22 * mm, 18 * mm, 18 * mm, 25 * mm, 25 * mm]))
        story.append(Spacer(1, 3 * mm))
        first_rb = next((m.rebar for m in model.mensole
                          if m.rebar.tirafondi_enabled), None)
        if first_rb:
            tir_img = draw_tied_rod(first_rb.tir_prof_dado_cm,
                                     first_rb.tir_sporgenza_cm,
                                     int(first_rb.d_tirafondi_mm),
                                     f"Tirafondo mensola Ø{int(first_rb.d_tirafondi_mm)}")
            story.append(Image(tir_img, width=50 * mm, height=90 * mm,
                                hAlign="CENTER"))
    elif not model.tie_rods.enabled:
        story.append(Paragraph("Nessun tirafondo presente.", body))

    story.append(PageBreak())

    # =========================================================
    # PAGINA 6 — Riepilogo materiali
    # =========================================================
    story.append(Paragraph("7. Riepilogo materiali", h2))

    if qty is None or not isinstance(qty, dict):
        story.append(Paragraph(
            "Dati quantitativi non disponibili.", body))
    else:
        story.append(Paragraph("7.1 Calcestruzzo", h3))
        rows = [["Voce", "Valore"]]
        rows.append(["Volume pilastro", f"{qty['V_pilastro_m3']:.3f} m³"])
        rows.append(["Volume mensole", f"{qty['V_mensole_m3']:.3f} m³"])
        rows.append(["Volume totale cls", f"{qty['V_cls_m3']:.3f} m³"])
        rows.append(["Peso cls", f"{qty['peso_cls_kN']:.2f} kN "
                                 f"({qty['peso_cls_kg']:.0f} kg)"])
        story.append(_simple_table(rows, [80 * mm, 60 * mm]))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("7.2 Acciaio d'armatura", h3))
        rows = [["Gruppo", "Volume [cm³]"]]
        rows.append(["Ferri longitudinali", f"{qty['V_long_cm3']:.0f}"])
        rows.append(["Staffe base", f"{qty['V_stirrups_cm3']:.0f}"])
        if model.stirrups.dense_zones.enabled:
            rows.append(["Staffe infittite sopra mensole",
                         f"{qty.get('V_dense_cm3', 0):.0f}"])
        if model.stirrups.hooks.enabled:
            rows.append(["Ganci", f"{qty['V_hooks_cm3']:.0f}"])
        if model.forks.enabled:
            rows.append(["Forche", f"{qty['V_forks_cm3']:.0f}"])
        if model.tie_rods.enabled:
            rows.append(["Tirafondi pilastro", f"{qty['V_ties_cm3']:.0f}"])
        if model.mensole:
            rows.append(["Ferri sup. mensole", f"{qty['V_men_top_cm3']:.0f}"])
            rows.append(["Staffe orizz. mensole", f"{qty['V_men_sh_cm3']:.0f}"])
            rows.append(["Staffe vert. mensole", f"{qty['V_men_sv_cm3']:.0f}"])
            rows.append(["Tirafondi mensole",
                         f"{qty.get('V_men_tir_cm3', 0):.0f}"])
        rows.append(["Volume acciaio totale", f"{qty['V_steel_m3'] * 1000:.2f} dm³"])
        rows.append(["Peso acciaio", f"{qty['peso_steel_kN']:.2f} kN "
                                     f"({qty['peso_steel_kg']:.1f} kg)"])
        story.append(_simple_table(rows, [80 * mm, 60 * mm]))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("7.3 Riepilogo totale", h3))
        peso_tot_kN = qty['peso_cls_kN'] + qty['peso_steel_kN']
        peso_tot_kg = qty['peso_cls_kg'] + qty['peso_steel_kg']
        rows = [["Voce", "Valore"]]
        rows.append(["Peso totale", f"{peso_tot_kN:.2f} kN "
                                     f"({peso_tot_kg:.0f} kg)"])
        if qty['V_cls_m3'] > 0:
            rapp = qty['V_steel_m3'] / qty['V_cls_m3'] * 100
            rows.append(["Rapporto volumetrico acciaio/cls", f"{rapp:.2f}%"])
        rows.append(["Percentuale geometrica armatura long.",
                     f"{qty['perc_arm']:.2f}%"])
        story.append(_simple_table(rows, [80 * mm, 60 * mm]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "<i>Nota: il presente documento ha valore indicativo per la "
        "visualizzazione delle armature. Per il dimensionamento strutturale "
        "fare riferimento ai calcoli redatti dal progettista.</i>", body))

    doc.build(story)
    buf.seek(0)
    return buf