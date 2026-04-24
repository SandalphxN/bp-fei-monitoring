import plotly.graph_objects as go
import pandas as pd
from typing import Optional

AREA_ORDER = {"FEI": 0, "Elektrotechnika": 1, "Informatika": 2}

DEGREE_COLORS = {"Bc": "#636EFA", "Ing": "#EF553B", "PhD": "#00CC96"}

ROCNIK_COLORS = {
    "všetci": "#636EFA",
    "1r": "#EF553B",
    "2r": "#00CC96",
    "3r": "#AB63FA",
    "4r": "#FFA15A",
    "5r": "#19D3F3",
}

SUBTYPE_COLORS = {
    "spolu":                          "#636EFA",
    "vylúčenie":                      "#EF553B",
    "zanechanie":                     "#FFA15A",
    "zmena ŠP":                       "#00CC96",
    "akademické podvody spolu":       "#636EFA",
    "podvody":                        "#EF553B",
    "plagiáty spolu":                 "#AB63FA",
    "plagiáty - záverečné práce":     "#FF6692",
    "plagiáty - ZAP":                 "#B6E880",
    "plagiáty - Progr":               "#FF97FF",
    "plagiáty - OOP":                 "#FECB52",
}

def _fmt(val, is_pct: bool) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if is_pct:
        return f"{val * 100:.2f}%"
    return f"{val:.0f}"

def _fmt_ratio(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return f"{val:.2f}"

def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text="Žiadne údaje pre zobrazenie",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16),
    )
    fig.update_layout(title=title, height=500)
    return fig

def _area_rank(area: str) -> int:
    return AREA_ORDER.get(area, 99)

def _sort_areas(areas: list) -> list:
    return sorted(areas, key=_area_rank)

def _sort_year_labels(year_labels: list) -> list:
    return sorted(year_labels)

def _build_x_labels(year_labels: list, groups: list, show_years: bool) -> list:
    if show_years:
        yl_sorted = _sort_year_labels(year_labels)
        return [f"{g} ({yl})" for g in groups for yl in yl_sorted]
    return list(groups)

def _get_val(sub: pd.DataFrame, filters: dict) -> Optional[float]:
    mask = pd.Series([True] * len(sub), index=sub.index)
    for col, val in filters.items():
        mask &= (sub[col] == val)
    row = sub[mask]
    return row["value"].iloc[0] if not row.empty else None

def _tickangle(x_labels: list) -> int:
    return -45 if len(x_labels) > 6 else 0

def _apply_layout(fig, title, x_title, y_title, legend_title=None,
                  height=500, barmode="group", x_labels=None):
    angle = _tickangle(x_labels) if x_labels is not None else 0
    kwargs = dict(
        title=title,
        barmode=barmode,
        xaxis_title=x_title,
        yaxis_title=y_title,
        height=height,
        xaxis_tickangle=angle,
    )
    if legend_title:
        kwargs["legend_title"] = legend_title
    fig.update_layout(**kwargs)


# ── LINE CHART CONVERSION ─────────────────────────────────────────────────────

def convert_bar_to_line(fig: go.Figure) -> go.Figure:
    """
    Converts a bar chart figure to a line chart figure.
    Each Bar trace becomes a Scatter trace with lines+markers.
    Layout (title, axes, legend) is preserved.
    """
    new_fig = go.Figure()

    for trace in fig.data:
        if isinstance(trace, go.Bar):
            new_fig.add_trace(go.Scatter(
                x=trace.x,
                y=trace.y,
                name=trace.name,
                mode="lines+markers",
                line=dict(color=trace.marker.color if trace.marker.color else None, width=2),
                marker=dict(
                    color=trace.marker.color if trace.marker.color else None,
                    size=8,
                ),
                text=trace.text,
                hovertemplate=trace.hovertemplate,
            ))
        else:
            new_fig.add_trace(trace)

    new_fig.update_layout(fig.layout)
    # Line charts don't use barmode
    new_fig.update_layout(barmode=None)

    return new_fig


# ── INDICATOR COMPARISON ──────────────────────────────────────────────────────

def plot_indicator_comparison(
    df: pd.DataFrame,
    indicator_code: str,
    indicator_name: str,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[df["indicator_code"] == indicator_code].copy()
    if df_f.empty:
        return _empty_fig(f"{indicator_code}. {indicator_name}")

    is_pct = bool(df_f["is_percentage"].iloc[0])
    areas_sorted = _sort_areas(df_f["area"].unique().tolist())
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())

    if show_years:
        x_labels = _build_x_labels(year_labels, areas_sorted, True)
    else:
        x_labels = areas_sorted

    fig = go.Figure()
    for deg in ["Bc", "Ing", "PhD"]:
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    disp = (val * 100) if (val is not None and is_pct) else val
                    y_vals.append(disp)
                    texts.append(_fmt(val, is_pct))
        else:
            for area in areas_sorted:
                sub = df_f[(df_f["area"] == area) & (df_f["degree"] == deg)]
                val = sub["value"].sum() if not sub.empty else None
                disp = (val * 100) if (val is not None and is_pct) else val
                y_vals.append(disp)
                texts.append(_fmt(val, is_pct))

        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals, name=deg,
            text=texts, textposition="outside",
            marker_color=DEGREE_COLORS.get(deg),
        ))

    _apply_layout(fig,
        title=f"{indicator_code}. {indicator_name}",
        x_title="Odbor",
        y_title="Hodnota (%)" if is_pct else "Hodnota",
        legend_title="Stupeň",
        x_labels=x_labels,
    )

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_program_comparison(
    df: pd.DataFrame,
    indicator_code: str,
    indicator_name: str,
    selected_areas: list,
    selected_programs: list = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[(df["indicator_code"] == indicator_code) & (df["program"].notna())].copy()
    if selected_areas:
        df_f = df_f[df_f["area"].isin(selected_areas)]
    if selected_programs:
        df_f = df_f[df_f["program"].isin(selected_programs)]

    if df_f.empty:
        return _empty_fig(f"{indicator_code}. {indicator_name}")

    is_pct = bool(df_f["is_percentage"].iloc[0])
    df_f["area_rank"] = df_f["area"].map(_area_rank)

    if len(selected_areas) > 1:
        df_f["prog_label"] = df_f["area"] + ": " + df_f["program"]
    else:
        df_f["prog_label"] = df_f["program"]

    df_f = df_f.sort_values(["area_rank", "program"])
    prog_labels = list(dict.fromkeys(df_f["prog_label"].tolist()))
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, prog_labels, show_years)

    fig = go.Figure()
    for deg in ["Bc", "Ing", "PhD"]:
        y_vals, texts = [], []
        if show_years:
            for pl in prog_labels:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f["prog_label"] == pl) & (df_f["year_display"] == yl) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    disp = (val * 100) if (val is not None and is_pct) else val
                    y_vals.append(disp)
                    texts.append(_fmt(val, is_pct))
        else:
            for pl in prog_labels:
                sub = df_f[(df_f["prog_label"] == pl) & (df_f["degree"] == deg)]
                val = sub["value"].sum() if not sub.empty else None
                disp = (val * 100) if (val is not None and is_pct) else val
                y_vals.append(disp)
                texts.append(_fmt(val, is_pct))

        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals, name=deg,
            text=texts, textposition="outside",
            marker_color=DEGREE_COLORS.get(deg),
        ))

    chart_height = max(500, min(900, 400 + len(prog_labels) * 20))
    _apply_layout(fig,
        title=f"{indicator_code}. {indicator_name}",
        x_title="Študijný program",
        y_title="Hodnota (%)" if is_pct else "Hodnota",
        legend_title="Stupeň",
        height=chart_height,
        x_labels=x_labels,
    )
    fig.update_xaxes(tickfont=dict(size=10), automargin=True)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_a(
    df: pd.DataFrame,
    selected_areas: list,
    snapshot_type: str = "ZS",
    show_years: bool = False,
    selected_rocnik: str = "všetci",
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    study_year_val = "1r" if snapshot_type == "LS" else selected_rocnik
    df_f = df[
        (df["indicator_code"] == "IV_a") &
        (df["snapshot_type"] == snapshot_type) &
        (df["area"].isin(selected_areas)) &
        (df["program"].isna()) &
        (df["study_year"] == study_year_val)
    ].copy()

    snap_lbl = snapshot_type
    rocnik_lbl = f" ({selected_rocnik})" if snapshot_type == "ZS" and selected_rocnik != "všetci" else ""
    title = f"IV_a. počet študentov{rocnik_lbl} – {snap_lbl}"

    if df_f.empty:
        return _empty_fig(title)

    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)
    degrees = ["Bc", "Ing", "PhD"] if snapshot_type == "ZS" else ["Bc"]

    fig = go.Figure()
    for deg in degrees:
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
        else:
            for area in areas_sorted:
                sub = df_f[(df_f["area"] == area) & (df_f["degree"] == deg)]
                val = sub["value"].iloc[0] if not sub.empty else None
                y_vals.append(val)
                texts.append(_fmt(val, False))

        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals, name=deg,
            text=texts, textposition="outside",
            marker_color=DEGREE_COLORS.get(deg, "#999"),
        ))

    y_label = "Počet študentov" if snapshot_type == "ZS" else "Počet študentov (1. roč. k 31.3.)"
    _apply_layout(fig, title=title, x_title="Odbor", y_title=y_label, legend_title="Stupeň",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_a_programme(
    df: pd.DataFrame,
    selected_areas: list,
    snapshot_type: str = "ZS",
    selected_programs: list = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_a") &
        (df["snapshot_type"] == snapshot_type) &
        (df["area"].isin(selected_areas)) &
        (df["program"].notna())
    ].copy()

    if selected_programs:
        df_f = df_f[df_f["program"].isin(selected_programs)]

    snap_lbl = snapshot_type
    title = f"IV_a. počet študentov po programoch – {snap_lbl}"

    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)
    if len(selected_areas) > 1:
        df_f["prog_label"] = df_f["area"] + ": " + df_f["program"]
    else:
        df_f["prog_label"] = df_f["program"]

    df_f = df_f.sort_values(["area_rank", "program"])
    prog_labels = list(dict.fromkeys(df_f["prog_label"].tolist()))
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, prog_labels, show_years)

    fig = go.Figure()

    if snapshot_type == "ZS":
        df_total = df_f[df_f["study_year"] == "všetci"]
        if df_total.empty:
            df_total = (
                df_f[df_f["study_year"].str.match(r"\d+r", na=False)]
                .groupby(["prog_label", "degree", "year_display"], as_index=False)["value"].sum()
            )
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for pl in prog_labels:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_total[(df_total["prog_label"] == pl) & (df_total["year_display"] == yl) & (df_total["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, False))
            else:
                for pl in prog_labels:
                    sub = df_total[(df_total["prog_label"] == pl) & (df_total["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(
                x=x_labels, y=y_vals, name=deg,
                text=texts, textposition="outside",
                marker_color=DEGREE_COLORS.get(deg, "#999"),
            ))
        fig.update_layout(barmode="group", yaxis_title="Počet študentov", legend_title="Stupeň")
    else:
        df_spring = df_f[(df_f["degree"] == "Bc") & (df_f["study_year"] == "1r")]
        y_vals, texts = [], []
        if show_years:
            for pl in prog_labels:
                for yl in _sort_year_labels(year_labels):
                    sub = df_spring[(df_spring["prog_label"] == pl) & (df_spring["year_display"] == yl)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
        else:
            for pl in prog_labels:
                sub = df_spring[df_spring["prog_label"] == pl]
                val = sub["value"].iloc[0] if not sub.empty else None
                y_vals.append(val)
                texts.append(_fmt(val, False))
        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals, name="1r Bc – jar",
            text=texts, textposition="outside",
            marker_color=DEGREE_COLORS.get("Bc", "#636EFA"),
        ))
        fig.update_layout(yaxis_title="Počet študentov Bc (1. roč. k 31.3.)")

    fig.update_layout(
        title=title,
        barmode="group",
        height=max(500, 400 + len(prog_labels) * 20),
        xaxis_title="Študijný program",
        xaxis_tickangle=_tickangle(x_labels),
    )

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_bc(
    df: pd.DataFrame,
    indicator_code: str,
    indicator_name: str,
    selected_areas: list,
    snapshot_type: str = "ZS",
    selected_sub_types: Optional[list] = None,
    show_programmes: bool = False,
    selected_programmes: Optional[list] = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == indicator_code) &
        (df["snapshot_type"] == snapshot_type) &
        (df["area"].isin(selected_areas))
    ].copy()

    snap_lbl = snapshot_type
    title = f"{indicator_code}. {indicator_name} – {snap_lbl}"

    if df_f.empty:
        return _empty_fig(title)

    if show_programmes:
        df_f = df_f[df_f["program"].notna()]
        if selected_programmes:
            df_f = df_f[df_f["program"].isin(selected_programmes)]
        df_f["area_rank"] = df_f["area"].map(_area_rank)
        if len(selected_areas) > 1:
            df_f["x_label"] = df_f["area"] + ": " + df_f["program"]
        else:
            df_f["x_label"] = df_f["program"]
        df_f = df_f.sort_values(["area_rank", "program"])
        group_col = "x_label"
    else:
        df_f = df_f[df_f["program"].isna()]
        df_f["area_rank"] = df_f["area"].map(_area_rank)
        df_f = df_f.sort_values("area_rank")
        group_col = "area"

    subtypes = selected_sub_types or ["spolu", "vylúčenie", "zanechanie", "zmena ŠP"]
    subtypes = [s for s in subtypes if s in df_f["sub_type"].unique()]
    degrees = ["Bc"] if show_programmes else ["Bc", "Ing", "PhD"]

    groups = list(dict.fromkeys(df_f[group_col].tolist()))
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, groups, show_years)

    fig = go.Figure()
    for sub in subtypes:
        for deg in degrees:
            trace_name = sub if len(degrees) == 1 else f"{sub} / {deg}"
            color = SUBTYPE_COLORS.get(sub, "#999")
            y_vals, texts = [], []
            if show_years:
                for g in groups:
                    for yl in _sort_year_labels(year_labels):
                        row = df_f[(df_f[group_col] == g) & (df_f["year_display"] == yl) & (df_f["sub_type"] == sub) & (df_f["degree"] == deg)]
                        val = row["value"].iloc[0] if not row.empty else None
                        y_vals.append(val if val is not None else 0)
                        texts.append(_fmt(val, True) if val is not None else "")
            else:
                for g in groups:
                    row = df_f[(df_f[group_col] == g) & (df_f["sub_type"] == sub) & (df_f["degree"] == deg)]
                    val = row["value"].iloc[0] if not row.empty else None
                    y_vals.append(val if val is not None else 0)
                    texts.append(_fmt(val, True) if val is not None else "")

            fig.add_trace(go.Bar(
                x=x_labels, y=y_vals,
                name=trace_name,
                text=texts, textposition="outside",
                marker_color=color,
                opacity=0.9 if deg == "Bc" else 0.5,
            ))

    _apply_layout(fig,
        title=title,
        x_title="Študijný program" if show_programmes else "Odbor",
        y_title="Podiel (%)",
        legend_title="Typ ukončenia",
        height=max(500, 400 + len(groups) * 18),
        x_labels=x_labels,
    )

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_d(
    df: pd.DataFrame,
    selected_areas: list,
    snapshot_type: str = "ZS",
    show_years: bool = False,
    selected_rocnik: str = "všetci",
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_d") &
        (df["snapshot_type"] == snapshot_type) &
        (df["area"].isin(selected_areas)) &
        (df["program"].isna())
    ].copy()

    snap_lbl = snapshot_type
    rocnik_lbl = "" if selected_rocnik == "všetci" else f" – {selected_rocnik}"
    title = f"IV_d. podiel zahraničných študentov{rocnik_lbl} – {snap_lbl}"

    if df_f.empty:
        return _empty_fig(title)

    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)

    fig = go.Figure()

    if snapshot_type == "LS":
        for deg in ["Bc"]:
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["study_year"] == "1r") & (df_f["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, True))
            else:
                for area in areas_sorted:
                    sub = df_f[(df_f["area"] == area) & (df_f["study_year"] == "1r") & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, True))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name="Bc 1r – jar",
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get("Bc", "#636EFA")))
        fig.update_layout(yaxis_title="Podiel zahraničných Bc (1. roč. k 31.3.)")
    else:
        study_year = "1r" if selected_rocnik == "1r" else "všetci" if selected_rocnik == "všetci" else selected_rocnik
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["study_year"] == study_year) & (df_f["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, True))
            else:
                for area in areas_sorted:
                    sub = df_f[(df_f["area"] == area) & (df_f["study_year"] == study_year) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, True))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        fig.update_layout(barmode="group", yaxis_title="Podiel zahraničných študentov", legend_title="Stupeň")

    _apply_layout(fig, title=title, x_title="Odbor", y_title="Podiel (%)", x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_e(
    df: pd.DataFrame,
    selected_areas: list,
    snapshot_type: str = "ZS",
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_e") &
        (df["snapshot_type"] == snapshot_type) &
        (df["area"].isin(selected_areas)) &
        (df["program"].isna())
    ].copy()

    snap_lbl = snapshot_type
    title = f"IV_e. podiel cudzincov – {snap_lbl}"

    if df_f.empty:
        return _empty_fig(title)

    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)

    fig = go.Figure()
    if snapshot_type == "LS":
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["study_year"] == "1r") & (df_f["degree"] == "Bc")]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, True))
        else:
            for area in areas_sorted:
                sub = df_f[(df_f["area"] == area) & (df_f["study_year"] == "1r") & (df_f["degree"] == "Bc")]
                val = sub["value"].iloc[0] if not sub.empty else None
                y_vals.append(val)
                texts.append(_fmt(val, True))
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name="Bc 1r",
                             text=texts, textposition="outside",
                             marker_color=DEGREE_COLORS.get("Bc", "#636EFA")))
        fig.update_layout(yaxis_title="Podiel cudzincov Bc (1. roč. k 31.3.)")
    else:
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["study_year"] == "všetci") & (df_f["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, True))
            else:
                for area in areas_sorted:
                    sub = df_f[(df_f["area"] == area) & (df_f["study_year"] == "všetci") & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, True))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        fig.update_layout(barmode="group", yaxis_title="Podiel cudzincov", legend_title="Stupeň")

    _apply_layout(fig, title=title, x_title="Odbor", y_title="Podiel (%)", x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_f(
    df: pd.DataFrame,
    selected_areas: list,
    show_years: bool = False,
    selected_programs: list = None,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_f") &
        (df["area"].isin(selected_areas))
    ].copy()
    title = "IV_f. počet študentov prekračujúcich štandardnú dĺžku štúdia"
    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)

    if selected_programs:
        df_f = df_f[df_f["program"].isin(selected_programs)]
        if len(selected_areas) > 1:
            df_f["prog_label"] = df_f["area"] + ": " + df_f["program"]
        else:
            df_f["prog_label"] = df_f["program"]
        df_f = df_f.sort_values(["area_rank", "program"])
        groups = list(dict.fromkeys(df_f["prog_label"].tolist()))
        x_col = "prog_label"
        x_title = "Študijný program"
    else:
        df_f = df_f[df_f["program"].isna()].sort_values("area_rank")
        groups = list(dict.fromkeys(df_f["area"].tolist()))
        x_col = "area"
        x_title = "Odbor"

    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, groups, show_years)

    fig = go.Figure()
    for deg in ["Bc", "Ing", "PhD"]:
        y_vals, texts = [], []
        if show_years:
            for g in groups:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f[x_col] == g) & (df_f["year_display"] == yl) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
        else:
            for g in groups:
                sub = df_f[(df_f[x_col] == g) & (df_f["degree"] == deg)]
                val = sub["value"].iloc[0] if not sub.empty else None
                y_vals.append(val)
                texts.append(_fmt(val, False))
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                             text=texts, textposition="outside",
                             marker_color=DEGREE_COLORS.get(deg, "#999")))

    _apply_layout(fig, title=title, x_title=x_title, y_title="Počet študentov",
                  legend_title="Stupeň", height=max(500, 400 + len(groups) * 20),
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_g(
    df: pd.DataFrame,
    selected_areas: list,
    selected_sub_types: Optional[list] = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_g") &
        (df["area"].isin(selected_areas)) &
        (df["program"].isna()) &
        (df["degree"] == "Bc")
    ].copy()
    title = "IV_g. počet odhalených akademických podvodov / plagiátov"
    if df_f.empty:
        return _empty_fig(title)

    available_subtypes = [s for s in [
        "akademické podvody spolu", "podvody", "plagiáty spolu",
        "plagiáty - záverečné práce", "plagiáty - ZAP", "plagiáty - OOP",
    ] if s in df_f["sub_type"].dropna().unique()]
    subtypes = selected_sub_types or (available_subtypes[:1] if available_subtypes else [])
    subtypes = [s for s in subtypes if s in available_subtypes]
    if not subtypes:
        subtypes = available_subtypes[:1]

    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)

    fig = go.Figure()
    for sub in subtypes:
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    sub_df = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["sub_type"] == sub)]
                    val = sub_df["value"].iloc[0] if not sub_df.empty else None
                    y_vals.append(val if val is not None else 0)
                    texts.append(_fmt(val, False) if val is not None else "")
        else:
            for area in areas_sorted:
                row = df_f[(df_f["area"] == area) & (df_f["sub_type"] == sub)]
                val = row["value"].iloc[0] if not row.empty else None
                y_vals.append(val if val is not None else 0)
                texts.append(_fmt(val, False) if val is not None else "")
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                             text=texts, textposition="outside",
                             marker_color=SUBTYPE_COLORS.get(sub, "#999")))

    _apply_layout(fig, title=title, x_title="Odbor",
                  y_title="Počet prípadov (Bc)", legend_title="Typ podvodu",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_h(
    df: pd.DataFrame,
    selected_areas: list,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_h") &
        (df["area"].isin(selected_areas)) &
        (df["program"].isna())
    ].copy()
    title = "IV_h. počet disciplinárnych konaní"
    if df_f.empty:
        return _empty_fig(title)

    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)

    fig = go.Figure()
    for deg in ["Bc", "Ing", "PhD"]:
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    sub = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl) & (df_f["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
        else:
            for area in areas_sorted:
                sub = df_f[(df_f["area"] == area) & (df_f["degree"] == deg)]
                val = sub["value"].iloc[0] if not sub.empty else None
                y_vals.append(val)
                texts.append(_fmt(val, False))
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                             text=texts, textposition="outside",
                             marker_color=DEGREE_COLORS.get(deg, "#999")))

    _apply_layout(fig, title=title, x_title="Odbor", y_title="Počet konaní", legend_title="Stupeň",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv_i(
    df: pd.DataFrame,
    selected_areas: list,
    show_years: bool = False,
    selected_programs: Optional[list] = None,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    df_f = df[
        (df["indicator_code"] == "IV_i") &
        (df["area"].isin(selected_areas))
    ].copy()
    title = "IV_i. počet absolventov"
    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)

    if selected_programs:
        df_prog = df_f[df_f["program"].isin(selected_programs)].copy()
        if df_prog.empty:
            return _empty_fig(title)
        if len(selected_areas) > 1:
            df_prog["prog_label"] = df_prog["area"] + ": " + df_prog["program"]
        else:
            df_prog["prog_label"] = df_prog["program"]
        df_prog = df_prog.sort_values(["area_rank", "program"])
        prog_labels = list(dict.fromkeys(df_prog["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_prog["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, prog_labels, show_years)

        fig = go.Figure()
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for pl in prog_labels:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_prog[(df_prog["prog_label"] == pl) & (df_prog["year_display"] == yl) & (df_prog["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, False))
            else:
                for pl in prog_labels:
                    sub = df_prog[(df_prog["prog_label"] == pl) & (df_prog["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Počet absolventov", legend_title="Stupeň",
                      height=max(500, 400 + len(prog_labels) * 20),
                      x_labels=x_labels)
    else:
        df_area = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted = _sort_areas([a for a in selected_areas if a in df_area["area"].unique()])
        year_labels = _sort_year_labels(df_area["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, areas_sorted, show_years)

        fig = go.Figure()
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        sub = df_area[(df_area["area"] == area) & (df_area["year_display"] == yl) & (df_area["degree"] == deg)]
                        val = sub["value"].iloc[0] if not sub.empty else None
                        y_vals.append(val)
                        texts.append(_fmt(val, False))
            else:
                for area in areas_sorted:
                    sub = df_area[(df_area["area"] == area) & (df_area["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    y_vals.append(val)
                    texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Počet absolventov", legend_title="Stupeň",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

IV2_A_SUBTYPE_COLORS = {
    "Bc a Ing k 31.10": "#636EFA",
    "Bc 1.roč k 31.3":  "#EF553B",
}

def _iv2_base_areas_years(df_f, selected_areas, show_years):
    areas_sorted = _sort_areas([a for a in selected_areas if a in df_f["area"].unique()])
    year_labels = _sort_year_labels(df_f["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, areas_sorted, show_years)
    return areas_sorted, year_labels, x_labels

def _iv2_base_progs_years(df_p, selected_programs, show_years):
    prog_labels = selected_programs or list(dict.fromkeys(df_p["program"].tolist()))
    year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, prog_labels, show_years)
    return prog_labels, year_labels, x_labels

def plot_iv2_a(
    df: pd.DataFrame,
    selected_areas: list,
    selected_sub_types: Optional[list] = None,
    selected_programs: Optional[list] = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    title = "IV-2 a. pomer počtu študentov a učiteľov"
    df_f = df[(df["indicator_code"] == "IV2_a") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)
    available_subs = [s for s in ["Bc a Ing k 31.10", "Bc 1.roč k 31.3"]
                      if s in df_f["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs) if s in available_subs] or available_subs[:1]

    fig = go.Figure()
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        prog_labels, year_labels, x_labels = _iv2_base_progs_years(df_p, selected_programs, show_years)
        for sub in subtypes:
            color = IV2_A_SUBTYPE_COLORS.get(sub, "#636EFA")
            y_vals, texts = [], []
            sub_df = df_p[df_p["sub_type"] == sub]
            if show_years:
                for p in prog_labels:
                    for yl in _sort_year_labels(year_labels):
                        row = sub_df[(sub_df["program"] == p) & (sub_df["year_display"] == yl)]
                        val = row["value"].iloc[0] if not row.empty else None
                        y_vals.append(val); texts.append(_fmt_ratio(val))
            else:
                for p in prog_labels:
                    row = sub_df[sub_df["program"] == p]
                    val = row["value"].iloc[0] if not row.empty else None
                    y_vals.append(val); texts.append(_fmt_ratio(val))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside", marker_color=color))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Pomer (študenti / učitelia)", legend_title="Typ",
                      height=max(500, 400 + len(prog_labels) * 18),
                      x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        for sub in subtypes:
            color = IV2_A_SUBTYPE_COLORS.get(sub, "#636EFA")
            y_vals, texts = [], []
            sub_df = df_a[df_a["sub_type"] == sub]
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        row = sub_df[(sub_df["area"] == area) & (sub_df["year_display"] == yl)]
                        val = row["value"].iloc[0] if not row.empty else None
                        y_vals.append(val); texts.append(_fmt_ratio(val))
            else:
                for area in areas_sorted:
                    row = sub_df[sub_df["area"] == area]
                    val = row["value"].iloc[0] if not row.empty else None
                    y_vals.append(val); texts.append(_fmt_ratio(val))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside", marker_color=color))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Pomer (študenti / učitelia)", legend_title="Typ",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

IV2_B_SUBTYPE_COLORS = {
    "všetci učitelia": "#636EFA",
    "obsadení vedúci": "#EF553B",
    "len počty vrátane DzP": "#00CC96",
}

def plot_iv2_b(
    df: pd.DataFrame,
    selected_areas: list,
    selected_sub_types: Optional[list] = None,
    selected_programs: Optional[list] = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    title = "IV-2 b. počet záverečných prác vedených vedúcim záverečnej práce"
    COUNTS_SUB = "len počty vrátane DzP"
    df_f = df[(df["indicator_code"] == "IV2_b") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)
    available_subs = [s for s in ["všetci učitelia", "obsadení vedúci", COUNTS_SUB]
                      if s in df_f["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs[:1]) if s in available_subs] or available_subs[:1]
    is_counts = any(s == COUNTS_SUB for s in subtypes)

    fig = go.Figure()

    def _add_ratio_bars(data, x_vals, sub, get_fn):
        color = IV2_B_SUBTYPE_COLORS.get(sub, "#999")
        y_vals, texts = [], []
        for xl in x_vals:
            val = get_fn(data, xl)
            y_vals.append(val); texts.append(_fmt_ratio(val))
        fig.add_trace(go.Bar(x=x_vals, y=y_vals, name=sub,
                             text=texts, textposition="outside", marker_color=color))

    def _add_count_bars(data, x_vals, get_fn):
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            for xl in x_vals:
                val = get_fn(data, xl, deg)
                y_vals.append(val); texts.append(_fmt(val, False) if val else "")
            fig.add_trace(go.Bar(x=x_vals, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))

    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        prog_labels, year_labels, x_labels = _iv2_base_progs_years(df_p, selected_programs, show_years)
        for sub in subtypes:
            sub_df = df_p[df_p["sub_type"] == sub]
            if sub == COUNTS_SUB:
                if show_years:
                    def gfn(data, xl, deg):
                        parts = xl.rsplit(" (", 1)
                        p, yl = (parts[0], parts[1].rstrip(")")) if len(parts) == 2 else (xl, None)
                        r = data[(data["program"] == p) & (data["degree"] == deg)]
                        if yl: r = r[r["year_display"] == yl]
                        return round(r["value"].iloc[0]) if not r.empty and r["value"].iloc[0] is not None else None
                    _add_count_bars(sub_df, x_labels, gfn)
                else:
                    def gfn(data, xl, deg):
                        r = data[(data["program"] == xl) & (data["degree"] == deg)]
                        return round(r["value"].iloc[0]) if not r.empty and r["value"].iloc[0] is not None else None
                    _add_count_bars(sub_df, x_labels, gfn)
            else:
                if show_years:
                    def gfn(data, xl):
                        parts = xl.rsplit(" (", 1)
                        p, yl = (parts[0], parts[1].rstrip(")")) if len(parts) == 2 else (xl, None)
                        r = data[(data["program"] == p) & (data["degree"] == "ratio")]
                        if yl: r = r[r["year_display"] == yl]
                        return r["value"].iloc[0] if not r.empty else None
                    _add_ratio_bars(sub_df, x_labels, sub, gfn)
                else:
                    def gfn(data, xl):
                        r = data[(data["program"] == xl) & (data["degree"] == "ratio")]
                        return r["value"].iloc[0] if not r.empty else None
                    _add_ratio_bars(sub_df, x_labels, sub, gfn)
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Počet prác" if is_counts else "Prác na vedúceho",
                      legend_title="Typ / Stupeň",
                      height=max(500, 400 + len(prog_labels) * 20),
                      x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        for sub in subtypes:
            sub_df = df_a[df_a["sub_type"] == sub]
            if sub == COUNTS_SUB:
                for deg in ["Bc", "Ing", "PhD"]:
                    y_vals, texts = [], []
                    if show_years:
                        for area in areas_sorted:
                            for yl in _sort_year_labels(year_labels):
                                r = sub_df[(sub_df["area"] == area) & (sub_df["year_display"] == yl) & (sub_df["degree"] == deg)]
                                val = round(r["value"].iloc[0]) if not r.empty and r["value"].iloc[0] is not None else None
                                y_vals.append(val); texts.append(_fmt(val, False) if val else "")
                    else:
                        for area in areas_sorted:
                            r = sub_df[(sub_df["area"] == area) & (sub_df["degree"] == deg)]
                            val = round(r["value"].iloc[0]) if not r.empty and r["value"].iloc[0] is not None else None
                            y_vals.append(val); texts.append(_fmt(val, False) if val else "")
                    fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                         text=texts, textposition="outside",
                                         marker_color=DEGREE_COLORS.get(deg, "#999")))
            else:
                color = IV2_B_SUBTYPE_COLORS.get(sub, "#999")
                y_vals, texts = [], []
                if show_years:
                    for area in areas_sorted:
                        for yl in _sort_year_labels(year_labels):
                            r = sub_df[(sub_df["area"] == area) & (sub_df["year_display"] == yl) & (sub_df["degree"] == "ratio")]
                            val = r["value"].iloc[0] if not r.empty else None
                            y_vals.append(val); texts.append(_fmt_ratio(val))
                else:
                    for area in areas_sorted:
                        r = sub_df[(sub_df["area"] == area) & (sub_df["degree"] == "ratio")]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val); texts.append(_fmt_ratio(val))
                fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                      text=texts, textposition="outside", marker_color=color))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Počet prác" if is_counts else "Prác na vedúceho",
                      legend_title="Typ / Stupeň",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

_IV2_CDEF_LABEL_SKIP = {
    "vyslaní / všetci", "ŠP", "odhad",
    "FEI", "Elektrotechnika", "Informatika",
}


def _iv2_cdef_is_prog(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    if s in _IV2_CDEF_LABEL_SKIP:
        return False
    skip_frags = ["Zoznam", "odhadované", "poradenstvo", "zamestnancov so",
                  "štúdia", "kariérne", "všetkých"]
    return not any(k in s for k in skip_frags)


def _plot_iv2_simple(df, code, title, selected_areas, selected_programs,
                     show_years, is_pct=False, y_title="Hodnota", deg_list=None,
                     chart_type="Stĺpcový"):
    if deg_list is None:
        deg_list = ["Bc", "Ing", "PhD"]
    data = df[df["indicator_code"] == code].copy()
    if selected_programs:
        plot_data = data[data["program"].isin(selected_programs)].copy()
        plot_data["area_rank"] = plot_data["area"].map(_area_rank)
        plot_data = plot_data.sort_values(["area_rank", "program"])
        groups = list(dict.fromkeys(plot_data["program"].tolist()))
        x_col = "program"
        x_title = "Odbor / Program"
    else:
        plot_data = data[data["area"].isin(selected_areas) & data["program"].isna()].copy()
        plot_data["area_rank"] = plot_data["area"].map(_area_rank)
        plot_data = plot_data.sort_values("area_rank")
        groups = _sort_areas(list(dict.fromkeys(plot_data["area"].tolist())))
        x_col = "area"
        x_title = "Odbor"

    if plot_data.empty:
        return _empty_fig(title)

    year_labels = _sort_year_labels(plot_data["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, groups, show_years)

    fig = go.Figure()
    for deg in deg_list:
        y_vals, texts = [], []
        if show_years:
            for g in groups:
                for yl in _sort_year_labels(year_labels):
                    sub = plot_data[(plot_data[x_col] == g) & (plot_data["year_display"] == yl) & (plot_data["degree"] == deg)]
                    val = sub["value"].iloc[0] if not sub.empty else None
                    disp = val * 100 if (val is not None and is_pct) else val
                    y_vals.append(disp)
                    texts.append(f"{disp:.2f} %" if (disp is not None and is_pct) else _fmt(val, False))
        else:
            for g in groups:
                sub = plot_data[(plot_data[x_col] == g) & (plot_data["degree"] == deg)]
                val = sub["value"].iloc[0] if not sub.empty else None
                disp = val * 100 if (val is not None and is_pct) else val
                y_vals.append(disp)
                texts.append(f"{disp:.2f} %" if (disp is not None and is_pct) else _fmt(val, False))
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                             marker_color=DEGREE_COLORS[deg],
                             text=texts, textposition="outside"))
    _apply_layout(fig, title=title, x_title=x_title, y_title=y_title, legend_title="Stupeň",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv2_c(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv2_simple(df, "IV2_c",
        "IV-2 c. podiel vyslaných študentov na mobility do zahraničia",
        selected_areas, selected_programs, show_years,
        is_pct=True, y_title="Podiel (%)", chart_type=chart_type)

def plot_iv2_d(df, selected_areas, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv2_simple(df, "IV2_d",
        "IV-2 d. počet prijatých študentov na mobility zo zahraničia",
        selected_areas, None, show_years, y_title="Počet", chart_type=chart_type)

def plot_iv2_e(df, selected_areas, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv2_simple(df, "IV2_e",
        "IV-2 e. rozsah podpory kariérneho poradenstva (odhadované hodiny na študenta)",
        selected_areas, None, show_years, y_title="Hodiny / študent", chart_type=chart_type)

def plot_iv2_f(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv2_simple(df, "IV2_f",
        "IV-2 f. počet zamestnancov so zameraním na podporu študentov",
        selected_areas, selected_programs, show_years, y_title="Počet zamestnancov",
        chart_type=chart_type)

IV2_G_SUBTYPE_COLORS = {
    "reálne":    "#636EFA",
    "oficiálne": "#EF553B",
}

def plot_iv2_g(
    df: pd.DataFrame,
    selected_areas: list,
    selected_sub_types: Optional[list] = None,
    selected_snapshot: Optional[str] = None,
    selected_programs: Optional[list] = None,
    show_years: bool = False,
    chart_type: str = "Stĺpcový",
) -> go.Figure:
    title = "IV-2 g. podiel študentov zapojených do hodnotenia kvality vzdelávania"
    snapshot = selected_snapshot or "ak.rok"
    df_f = df[
        (df["indicator_code"] == "IV2_g") &
        (df["area"].isin(selected_areas)) &
        (df["snapshot_type"] == snapshot)
    ].copy()
    if df_f.empty:
        return _empty_fig(title)

    df_f["area_rank"] = df_f["area"].map(_area_rank)
    available_subs = [s for s in ["reálne", "oficiálne"] if s in df_f["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs) if s in available_subs] or available_subs[:1]

    fig = go.Figure()
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        prog_labels, year_labels, x_labels = _iv2_base_progs_years(df_p, selected_programs, show_years)
        for sub in subtypes:
            color = IV2_G_SUBTYPE_COLORS.get(sub, "#999")
            sub_df = df_p[df_p["sub_type"] == sub]
            y_vals, texts = [], []
            if show_years:
                for p in prog_labels:
                    for yl in _sort_year_labels(year_labels):
                        r = sub_df[(sub_df["program"] == p) & (sub_df["year_display"] == yl)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val * 100 if val is not None else None)
                        texts.append(f"{val*100:.2f}%" if val is not None else "")
            else:
                for p in prog_labels:
                    r = sub_df[sub_df["program"] == p]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside", marker_color=color))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Podiel zapojených študentov (%)", legend_title="Typ ankety",
                      height=max(500, 400 + len(prog_labels) * 18),
                      x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        for sub in subtypes:
            color = IV2_G_SUBTYPE_COLORS.get(sub, "#999")
            sub_df = df_a[df_a["sub_type"] == sub]
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        r = sub_df[(sub_df["area"] == area) & (sub_df["year_display"] == yl)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val * 100 if val is not None else None)
                        texts.append(f"{val*100:.2f}%" if val is not None else "")
            else:
                for area in areas_sorted:
                    r = sub_df[sub_df["area"] == area]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside", marker_color=color))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Podiel zapojených študentov (%)", legend_title="Typ ankety",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv2_h(df, selected_areas, selected_snapshot=None, show_years=False, chart_type="Stĺpcový"):
    title = "IV-2 h. miera spokojnosti študentov s kvalitou výučby a učiteľov"
    SNAP_COLORS = {"ak.rok": "#636EFA", "ZS": "#EF553B", "LS": "#00CC96"}
    snapshot = selected_snapshot or "ak.rok"
    df_f = df[(df["indicator_code"] == "IV2_h") & (df["area"].isin(selected_areas)) & (df["snapshot_type"] == snapshot)].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    df_f = df_f.sort_values("area_rank")
    areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_f, selected_areas, show_years)
    y_vals, texts = [], []
    if show_years:
        for area in areas_sorted:
            for yl in _sort_year_labels(year_labels):
                r = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl)]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val * 100 if val is not None else None)
                texts.append(f"{val*100:.2f}%" if val is not None else "")
    else:
        for area in areas_sorted:
            r = df_f[df_f["area"] == area]
            val = r["value"].iloc[0] if not r.empty else None
            y_vals.append(val * 100 if val is not None else None)
            texts.append(f"{val*100:.2f}%" if val is not None else "")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside",
                         marker_color=SNAP_COLORS.get(snapshot, "#636EFA"), name=snapshot))
    _apply_layout(fig, title=title, x_title="Odbor", y_title="Miera spokojnosti (%)",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv2_i(df, show_years=False, chart_type="Stĺpcový"):
    title = "IV-2 i. miera spokojnosti študentov so špecifickými potrebami"
    data = df[df["indicator_code"] == "IV2_i"].copy()
    if data.empty:
        return _empty_fig(title)
    if show_years:
        x_vals = _sort_year_labels(data["year_display"].unique().tolist())
        y_vals = [data[data["year_display"] == y]["value"].iloc[0] * 100
                  if not data[data["year_display"] == y].empty else None for y in x_vals]
        texts = [f"{v:.2f}%" if v is not None else "" for v in y_vals]
    else:
        val = data["value"].iloc[0]
        x_vals = ["FEI"]
        y_vals = [val * 100 if val is not None else None]
        texts = [f"{val*100:.2f}%" if val is not None else ""]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_vals, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
    _apply_layout(fig, title=title, x_title="Akademický rok" if show_years else "",
                  y_title="Miera spokojnosti (%)", x_labels=x_vals)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

IV2_J_SUBTYPE_COLORS = {
    "spolu":               "#636EFA",
    "študentský senát":    "#EF553B",
    "študijné oddelenie":  "#00CC96",
    "študijní poradcovia": "#AB63FA",
}

def plot_iv2_j(df, selected_sub_types=None, show_years=False, chart_type="Stĺpcový"):
    title = "IV-2 j. počet podaných podnetov študentov"
    data = df[df["indicator_code"] == "IV2_j"].copy()
    if data.empty:
        return _empty_fig(title)
    all_subs = ["spolu", "študentský senát", "študijné oddelenie", "študijní poradcovia"]
    available_subs = [s for s in all_subs if s in data["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs) if s in available_subs]
    if not subtypes:
        subtypes = available_subs
    year_labels = _sort_year_labels(data["year_display"].unique().tolist())
    x_labels = _build_x_labels(year_labels, subtypes, show_years)
    fig = go.Figure()
    for deg in ["Bc", "Ing", "PhD"]:
        y_vals, texts = [], []
        if show_years:
            for sub in subtypes:
                for yl in _sort_year_labels(year_labels):
                    r = data[(data["sub_type"] == sub) & (data["degree"] == deg) & (data["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val)
                    texts.append(f"{int(val)}" if (val is not None and not (isinstance(val, float) and pd.isna(val))) else "")
        else:
            for sub in subtypes:
                r = data[(data["sub_type"] == sub) & (data["degree"] == deg)]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val)
                texts.append(f"{int(val)}" if (val is not None and not (isinstance(val, float) and pd.isna(val))) else "")
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                             text=texts, textposition="outside",
                             marker_color=DEGREE_COLORS.get(deg, "#999")))
    _apply_layout(fig, title=title, x_title="Typ podnetu",
                  y_title="Počet podnetov", legend_title="Stupeň",
                  x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

IV3_A_SUBTYPE_COLORS = {"prof": "#636EFA", "doc": "#EF553B", "OA": "#00CC96", "spolu": "#AB63FA"}

def plot_iv3_a(df, selected_areas, selected_sub_types=None, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    title = "IV-3 a. počty učiteľov na ŠP podľa vedecko-pedagogických hodností"
    df_f = df[(df["indicator_code"] == "IV3_a") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    available_subs = [s for s in ["prof", "doc", "OA"] if s in df_f["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs) if s in available_subs] or available_subs
    fig = go.Figure()
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        prog_labels = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, prog_labels, show_years)
        for sub in subtypes:
            sub_df = df_p[df_p["sub_type"] == sub]
            y_vals, texts = [], []
            if show_years:
                for pl in prog_labels:
                    for yl in _sort_year_labels(year_labels):
                        r = sub_df[(sub_df["prog_label"] == pl) & (sub_df["year_display"] == yl)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val); texts.append(_fmt(val, False))
            else:
                for pl in prog_labels:
                    r = sub_df[sub_df["prog_label"] == pl]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside",
                                 marker_color=IV3_A_SUBTYPE_COLORS.get(sub, "#999")))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Počet učiteľov", legend_title="Hodnosť",
                      height=max(500, 400 + len(prog_labels) * 18),
                      x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    r = df_a[(df_a["area"] == area) & (df_a["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
        else:
            for area in areas_sorted:
                r = df_a[df_a["area"] == area]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val); texts.append(_fmt(val, False))
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, name="spolu",
                             text=texts, textposition="outside", marker_color="#636EFA"))
        _apply_layout(fig, title=title, x_title="Odbor", y_title="Počet učiteľov",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def _plot_iv3_simple_count(df, code, title, selected_areas, selected_programs, show_years, chart_type="Stĺpcový"):
    df_f = df[(df["indicator_code"] == code) & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        groups = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, groups, show_years)
        y_vals, texts = [], []
        if show_years:
            for pl in groups:
                for yl in _sort_year_labels(year_labels):
                    r = df_p[(df_p["prog_label"] == pl) & (df_p["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
        else:
            for pl in groups:
                r = df_p[df_p["prog_label"] == pl]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val); texts.append(_fmt(val, False))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA", name="počet"))
        _apply_layout(fig, title=title, x_title="Študijný program", y_title="Počet učiteľov",
                      height=max(500, 400 + len(groups) * 18), x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    r = df_a[(df_a["area"] == area) & (df_a["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
        else:
            for area in areas_sorted:
                r = df_a[df_a["area"] == area]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val); texts.append(_fmt(val, False))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA", name="počet"))
        _apply_layout(fig, title=title, x_title="Odbor", y_title="Počet učiteľov",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv3_b(df, selected_areas, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_simple_count(df, "IV3_b",
        "IV-3 b. počty samostatných výskumných pracovníkov na ŠP",
        selected_areas, None, show_years, chart_type=chart_type)

def plot_iv3_c(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_simple_count(df, "IV3_c",
        "IV-3 c. počet učiteľov s vedecko-pedagogickým titulom (prof., doc.)",
        selected_areas, selected_programs, show_years, chart_type=chart_type)

def plot_iv3_i(df, selected_areas, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_simple_count(df, "IV3_i",
        "IV-3 i. počet prijatých učiteľov zo zahraničia alebo iných VŠ",
        selected_areas, None, show_years, chart_type=chart_type)

def plot_iv3_d(df, selected_areas, show_years=False, chart_type="Stĺpcový"):
    title = "IV-3 d. podiel učiteľov s PhD./ArtD. (alebo ekvivalentom)"
    df_f = df[(df["indicator_code"] == "IV3_d") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    df_f = df_f.sort_values("area_rank")
    areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_f, selected_areas, show_years)
    y_vals, texts = [], []
    if show_years:
        for area in areas_sorted:
            for yl in _sort_year_labels(year_labels):
                r = df_f[(df_f["area"] == area) & (df_f["year_display"] == yl)]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val * 100 if val is not None else None)
                texts.append(f"{val*100:.0f}%" if val is not None else "")
    else:
        for area in areas_sorted:
            r = df_f[df_f["area"] == area]
            val = r["value"].iloc[0] if not r.empty else None
            y_vals.append(val * 100 if val is not None else None)
            texts.append(f"{val*100:.0f}%" if val is not None else "")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
    _apply_layout(fig, title=title, x_title="Odbor", y_title="Podiel (%)", x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

IV3_E_SUBTYPE_COLORS = {"priemer": "#636EFA", "od": "#00CC96", "do": "#EF553B"}

def plot_iv3_e(df, selected_areas, selected_sub_types=None, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    title = "IV-3 e. vek učiteľov ŠP zabezpečujúcich profilové predmety"
    df_f = df[(df["indicator_code"] == "IV3_e") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    available_subs = [s for s in ["priemer", "od", "do"] if s in df_f["sub_type"].dropna().unique()]
    subtypes = [s for s in (selected_sub_types or available_subs) if s in available_subs] or available_subs
    fig = go.Figure()
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        groups = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, groups, show_years)
        for sub in subtypes:
            sub_df = df_p[df_p["sub_type"] == sub]
            y_vals, texts = [], []
            if show_years:
                for pl in groups:
                    for yl in _sort_year_labels(year_labels):
                        r = sub_df[(sub_df["prog_label"] == pl) & (sub_df["year_display"] == yl)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val); texts.append(_fmt(val, False))
            else:
                for pl in groups:
                    r = sub_df[sub_df["prog_label"] == pl]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside",
                                 marker_color=IV3_E_SUBTYPE_COLORS.get(sub, "#999")))
        _apply_layout(fig, title=title, x_title="Študijný program", y_title="Vek (roky)",
                      legend_title="Štatistika", height=max(500, 400 + len(groups) * 18),
                      x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        for sub in subtypes:
            sub_df = df_a[df_a["sub_type"] == sub]
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        r = sub_df[(sub_df["area"] == area) & (sub_df["year_display"] == yl)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val); texts.append(_fmt(val, False))
            else:
                for area in areas_sorted:
                    r = sub_df[sub_df["area"] == area]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val); texts.append(_fmt(val, False))
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=sub,
                                 text=texts, textposition="outside",
                                 marker_color=IV3_E_SUBTYPE_COLORS.get(sub, "#999")))
        _apply_layout(fig, title=title, x_title="Odbor", y_title="Vek (roky)",
                      legend_title="Štatistika", x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def _plot_iv3_ratio(df, code, title, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    df_f = df[(df["indicator_code"] == code) & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        groups = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, groups, show_years)
        y_vals, texts = [], []
        if show_years:
            for pl in groups:
                for yl in _sort_year_labels(year_labels):
                    r = df_p[(df_p["prog_label"] == pl) & (df_p["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
        else:
            for pl in groups:
                r = df_p[df_p["prog_label"] == pl]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val * 100 if val is not None else None)
                texts.append(f"{val*100:.2f}%" if val is not None else "")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
        _apply_layout(fig, title=title, x_title="Študijný program", y_title="Podiel (%)",
                      height=max(500, 400 + len(groups) * 18), x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    r = df_a[(df_a["area"] == area) & (df_a["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
        else:
            for area in areas_sorted:
                r = df_a[df_a["area"] == area]
                val = r["value"].iloc[0] if not r.empty else None
                y_vals.append(val * 100 if val is not None else None)
                texts.append(f"{val*100:.2f}%" if val is not None else "")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
        _apply_layout(fig, title=title, x_title="Odbor", y_title="Podiel (%)",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_iv3_f(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_ratio(df, "IV3_f", "IV-3 f. podiel učiteľov – absolventov fakulty",
                           selected_areas, selected_programs, show_years, chart_type=chart_type)

def plot_iv3_g(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_ratio(df, "IV3_g", "IV-3 g. podiel učiteľov, ktorí sú zároveň výskumnými pracovníkmi",
                           selected_areas, selected_programs, show_years, chart_type=chart_type)

def plot_iv3_h(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    return _plot_iv3_ratio(df, "IV3_h", "IV-3 h. podiel učiteľov s praxou v relevantnej oblasti mimo akademickej sféry",
                           selected_areas, selected_programs, show_years, chart_type=chart_type)

def plot_iv3_j(df, selected_areas, selected_sub_type="vyslaní", selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    is_pct = (selected_sub_type == "vyslaní")
    title = "IV-3 j. podiel vyslaných učiteľov" if is_pct else "IV-3 j. počty vyslaných učiteľov (súčet)"
    df_f = df[(df["indicator_code"] == "IV3_j") & (df["area"].isin(selected_areas)) & (df["sub_type"] == selected_sub_type)].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        groups = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, groups, show_years)
        y_vals, texts = [], []
        if show_years:
            for pl in groups:
                for yl in _sort_year_labels(year_labels):
                    r = df_p[(df_p["prog_label"] == pl) & (df_p["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    disp = val * 100 if (val is not None and is_pct) else val
                    y_vals.append(disp)
                    texts.append(f"{disp:.2f}%" if (disp is not None and is_pct) else _fmt(disp, False))
        else:
            for pl in groups:
                r = df_p[df_p["prog_label"] == pl]
                val = r["value"].iloc[0] if not r.empty else None
                disp = val * 100 if (val is not None and is_pct) else val
                y_vals.append(disp)
                texts.append(f"{disp:.2f}%" if (disp is not None and is_pct) else _fmt(disp, False))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Podiel (%)" if is_pct else "Počet učiteľov",
                      height=max(500, 400 + len(groups) * 18), x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        y_vals, texts = [], []
        if show_years:
            for area in areas_sorted:
                for yl in _sort_year_labels(year_labels):
                    r = df_a[(df_a["area"] == area) & (df_a["year_display"] == yl)]
                    val = r["value"].iloc[0] if not r.empty else None
                    disp = val * 100 if (val is not None and is_pct) else val
                    y_vals.append(disp)
                    texts.append(f"{disp:.2f}%" if (disp is not None and is_pct) else _fmt(disp, False))
        else:
            for area in areas_sorted:
                r = df_a[df_a["area"] == area]
                val = r["value"].iloc[0] if not r.empty else None
                disp = val * 100 if (val is not None and is_pct) else val
                y_vals.append(disp)
                texts.append(f"{disp:.2f}%" if (disp is not None and is_pct) else _fmt(disp, False))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_labels, y=y_vals, text=texts, textposition="outside", marker_color="#636EFA"))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Podiel (%)" if is_pct else "Počet učiteľov",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig

def plot_v5_a(df, selected_areas, selected_programs=None, show_years=False, chart_type="Stĺpcový"):
    title = "V-a. miera uplatniteľnosti absolventov TUKE/ŠP"
    df_f = df[(df["indicator_code"] == "V5_a") & (df["area"].isin(selected_areas))].copy()
    if df_f.empty:
        return _empty_fig(title)
    df_f["area_rank"] = df_f["area"].map(_area_rank)
    fig = go.Figure()
    if selected_programs:
        df_p = df_f[df_f["program"].isin(selected_programs)].sort_values("area_rank")
        if len(selected_areas) > 1:
            df_p["prog_label"] = df_p["area"] + ": " + df_p["program"]
        else:
            df_p["prog_label"] = df_p["program"]
        groups = list(dict.fromkeys(df_p.sort_values("area_rank")["prog_label"].tolist()))
        year_labels = _sort_year_labels(df_p["year_display"].unique().tolist())
        x_labels = _build_x_labels(year_labels, groups, show_years)
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for pl in groups:
                    for yl in _sort_year_labels(year_labels):
                        r = df_p[(df_p["prog_label"] == pl) & (df_p["year_display"] == yl) & (df_p["degree"] == deg)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val * 100 if val is not None else None)
                        texts.append(f"{val*100:.2f}%" if val is not None else "")
            else:
                for pl in groups:
                    r = df_p[(df_p["prog_label"] == pl) & (df_p["degree"] == deg)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        _apply_layout(fig, title=title, x_title="Študijný program",
                      y_title="Miera uplatniteľnosti (%)", legend_title="Stupeň",
                      height=max(500, 400 + len(groups) * 18), x_labels=x_labels)
    else:
        df_a = df_f[df_f["program"].isna()].sort_values("area_rank")
        areas_sorted, year_labels, x_labels = _iv2_base_areas_years(df_a, selected_areas, show_years)
        for deg in ["Bc", "Ing", "PhD"]:
            y_vals, texts = [], []
            if show_years:
                for area in areas_sorted:
                    for yl in _sort_year_labels(year_labels):
                        r = df_a[(df_a["area"] == area) & (df_a["year_display"] == yl) & (df_a["degree"] == deg)]
                        val = r["value"].iloc[0] if not r.empty else None
                        y_vals.append(val * 100 if val is not None else None)
                        texts.append(f"{val*100:.2f}%" if val is not None else "")
            else:
                for area in areas_sorted:
                    r = df_a[(df_a["area"] == area) & (df_a["degree"] == deg)]
                    val = r["value"].iloc[0] if not r.empty else None
                    y_vals.append(val * 100 if val is not None else None)
                    texts.append(f"{val*100:.2f}%" if val is not None else "")
            fig.add_trace(go.Bar(x=x_labels, y=y_vals, name=deg,
                                 text=texts, textposition="outside",
                                 marker_color=DEGREE_COLORS.get(deg, "#999")))
        _apply_layout(fig, title=title, x_title="Odbor",
                      y_title="Miera uplatniteľnosti (%)", legend_title="Stupeň",
                      x_labels=x_labels)

    if chart_type == "Čiarový":
        fig = convert_bar_to_line(fig)

    return fig