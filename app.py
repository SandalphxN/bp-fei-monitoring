import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.storage.db import init_db, get_years, load_records, list_uploads, delete_upload, list_faculties
from src.pipeline.run_pipeline import import_excel_to_db
from src.analytics.aggregations import get_programs_for_area
from src.viz.charts import (
    plot_indicator_comparison,
    plot_program_comparison,
    plot_iv_a,
    plot_iv_a_programme,
    plot_iv_bc,
    plot_iv_d,
    plot_iv_e,
    plot_iv_f,
    plot_iv_g,
    plot_iv_h,
    plot_iv_i,
    plot_iv2_a,
    plot_iv2_b,
    plot_iv2_c,
    plot_iv2_d,
    plot_iv2_e,
    plot_iv2_f,
    plot_iv2_g,
    plot_iv2_h,
    plot_iv2_i,
    plot_iv2_j,
    plot_iv3_a,
    plot_iv3_b,
    plot_iv3_c,
    plot_iv3_d,
    plot_iv3_e,
    plot_iv3_f,
    plot_iv3_g,
    plot_iv3_h,
    plot_iv3_i,
    plot_iv3_j,
    plot_v5_a,
)
from src.utils.config import load_indicators, load_settings
from src.auth.ldap_auth import LdapConfig, ldap_authenticate
from src.auth.rbac import (
    resolve_role,
    ROLE_TEACHER,
    can_upload,
    can_manage_datasets,
    can_export,
)

_settings = load_settings()
_app_title = _settings.get("app", {}).get("title", "Monitorovanie kvality vzdelávania FEI TUKE")

st.set_page_config(
    page_title=_app_title,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.main { background-color: #0e1117; color: #ffffff; }
.stApp > header { background-color: transparent; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_from_db_cached(years: tuple, faculty: str):
    return load_records(list(years), faculty=faculty)


def format_year_display(year: int) -> str:
    return f"{year}-{year + 1}"


def format_uploaded_at(raw: str) -> str:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return raw


def _ldap_cfg_from_settings(settings: dict) -> LdapConfig | None:
    auth = settings.get("auth", {}) if isinstance(settings, dict) else {}
    ldap = auth.get("ldap", {}) if isinstance(auth, dict) else {}
    if not ldap or not ldap.get("enabled", False):
        return None
    return LdapConfig(
        server_uri=ldap.get("server_uri", ""),
        user_dn_template=ldap.get("user_dn_template", ""),
        use_ssl=bool(ldap.get("use_ssl", False)),
        connect_timeout=int(ldap.get("connect_timeout", 5)),
    )


def auth_block(settings: dict) -> tuple[str, str | None]:
    if "auth_user" not in st.session_state:
        st.session_state["auth_user"] = None
        st.session_state["auth_role"] = ROLE_TEACHER

    role = st.session_state.get("auth_role", ROLE_TEACHER)
    user = st.session_state.get("auth_user", None)

    st.sidebar.title("Nastavenia")
    st.sidebar.markdown("---")

    auth = settings.get("auth", {}) if isinstance(settings, dict) else {}
    ldap_cfg = _ldap_cfg_from_settings(settings)
    ldap_enabled = ldap_cfg is not None

    exp_title = "Prihlásenie (LDAP)" if ldap_enabled else "Prihlásenie (lokálne)"
    with st.sidebar.expander(exp_title, expanded=False):
        if user:
            st.write(f"Prihlásený: **{user}**")
            st.write(f"Rola: **{role}**")
            if st.button("Odhlásiť"):
                st.session_state["auth_user"] = None
                st.session_state["auth_role"] = ROLE_TEACHER
                st.rerun()
        else:
            st.caption("Prihlásenie je potrebné pre administrátora.")
            username = st.text_input("Login", key="auth_user_input")
            password = st.text_input("Heslo", type="password", key="auth_pass_input")

            if st.button("Prihlásiť"):
                username = username.strip()

                if ldap_enabled:
                    if not ldap_cfg.server_uri or not ldap_cfg.user_dn_template:
                        st.error("LDAP nie je správne nakonfigurovaný v settings.yml")
                        return st.session_state["auth_role"], st.session_state["auth_user"]
                    ok = ldap_authenticate(username, password, ldap_cfg)
                    if not ok:
                        st.error("LDAP prihlásenie zlyhalo.")
                        return st.session_state["auth_role"], st.session_state["auth_user"]
                    resolved = resolve_role(username, settings)
                    st.session_state["auth_user"] = username
                    st.session_state["auth_role"] = resolved
                    st.success(f"OK - Rola: {resolved}")
                    st.rerun()
                else:
                    local_users = auth.get("local_users", {}) if isinstance(auth, dict) else {}
                    if not isinstance(local_users, dict) or username not in local_users:
                        st.error("Neznámy používateľ.")
                        return st.session_state["auth_role"], st.session_state["auth_user"]
                    expected_pw = (local_users.get(username) or {}).get("password", "")
                    if password != expected_pw:
                        st.error("Nesprávne heslo.")
                        return st.session_state["auth_role"], st.session_state["auth_user"]
                    resolved = resolve_role(username, settings)
                    st.session_state["auth_user"] = username
                    st.session_state["auth_role"] = resolved
                    st.success(f"OK - Rola: {resolved}")
                    st.rerun()

    return st.session_state["auth_role"], st.session_state["auth_user"]

SECTION_LABELS = {
    "III": "Čl. III — Ukazovatele vstupu",
    "IV":  "Čl. IV — Ukazovatele procesu vzdelávania",
    "V":   "Čl. V — Ukazovatele výstupu zo vzdelávania",
}

SECTION_SUBSECTIONS = {
    "III": {
        "(žiadna)": ["III_a", "III_b", "III_c", "III_d", "III_e", "III_f", "III_g", "III_h"],
    },
    "IV": {
        "IV-1 — Prijímacie konanie, priebeh a ukončenie štúdia": [
            "IV1_a", "IV1_b", "IV1_c", "IV1_d", "IV1_e", "IV1_f", "IV1_g", "IV1_h", "IV1_i",
        ],
        "IV-2 — Učenie sa, vyučovanie a hodnotenie orientované na študenta": [
            "IV2_a", "IV2_b", "IV2_c", "IV2_d", "IV2_e",
            "IV2_f", "IV2_g", "IV2_h", "IV2_i", "IV2_j",
        ],
        "IV-3 — Učitelia": [
            "IV3_a", "IV3_b", "IV3_c", "IV3_d", "IV3_e",
            "IV3_f", "IV3_g", "IV3_h", "IV3_i", "IV3_j",
        ],
    },
    "V": {
        "(žiadna)": ["V_a"],
    },
}


def _build_indicator_selector(all_indicators: dict) -> str:
    section_key = st.sidebar.selectbox(
        "Časť:",
        list(SECTION_LABELS.keys()),
        format_func=lambda k: SECTION_LABELS[k],
        key="ind_section",
    )

    subsections = SECTION_SUBSECTIONS.get(section_key, {})

    if len(subsections) == 1:
        subsection_key = list(subsections.keys())[0]
    else:
        subsection_key = st.sidebar.selectbox(
            "Podčasť:",
            list(subsections.keys()),
            key="ind_subsection",
        )

    allowed_codes = subsections.get(subsection_key, [])
    available = {k: v for k, v in all_indicators.items() if k in allowed_codes}

    if not available:
        st.sidebar.warning("Pre túto podsekciu nie sú dostupné žiadne ukazovatele.")
        return list(all_indicators.keys())[0]

    selected = st.sidebar.selectbox(
        "Ukazovateľ:",
        list(available.keys()),
        format_func=lambda x: f"{x.split('_')[-1]}. {available[x]}",
        key="ind_indicator",
    )
    return selected

def _get_programs(df: pd.DataFrame, db_code: str, areas: list) -> list:
    sub = df[(df["indicator_code"] == db_code) & (df["program"].notna())]
    if areas:
        sub = sub[sub["area"].isin(areas)]
    return sorted(sub["program"].unique().tolist())

def _render_iv2_a(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    from src.analytics.aggregations import get_programs_for_area

    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        programs_all.extend(get_programs_for_area(df[df["indicator_code"] == "IV2_a"], area))
    programs_all = list(dict.fromkeys(programs_all))

    selected_programs = []
    sel_all = False
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv2_a_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv2_a_programs"
                )

    selected_sub = "Bc a Ing k 31.10"
    if not selected_programs and not sel_all:
        snap_choice = st.radio(
            "Termín dát:",
            ["Začiatok ZS", "Koniec ZS (len pre 1. ročník, Bc)"],
            horizontal=True, key="iv2_a_snap"
        )
        selected_sub = "Bc a Ing k 31.10" if snap_choice == "Začiatok ZS" else "Bc 1.roč k 31.3"

    fig = plot_iv2_a(
        df, selected_areas,
        selected_sub_types=[selected_sub],
        selected_programs=selected_programs or None,
        show_years=multiple_years,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_b(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    from src.analytics.aggregations import get_programs_for_area

    df_g = df[(df["indicator_code"] == "IV2_b") & (df["area"].isin(selected_areas))]
    all_subs_ordered = ["všetci učitelia", "obsadení vedúci", "len počty vrátane DzP"]
    available_subs = [s for s in all_subs_ordered if s in df_g["sub_type"].dropna().unique()]
    selected_subs = st.multiselect(
        "Typ výpočtu:", available_subs,
        default=available_subs[:1], key="iv2_b_subtypes"
    )

    show_prog = any(s != "len počty vrátane DzP" for s in (selected_subs or available_subs[:1]))
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    if show_prog:
        for area in non_fei:
            programs_all.extend(get_programs_for_area(df[df["indicator_code"] == "IV2_b"], area))
        programs_all = list(dict.fromkeys(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv2_b_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv2_b_programs"
                )

    fig = plot_iv2_b(
        df, selected_areas,
        selected_sub_types=selected_subs or None,
        selected_programs=selected_programs or None,
        show_years=multiple_years,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_c(df, selected_areas, multiple_years, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        programs_all.extend(get_programs_for_area(df[df["indicator_code"] == "IV2_c"], area))
    programs_all = list(dict.fromkeys(programs_all))
    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv2_c_all_progs")
        with col2:
            selected_programs = programs_all if sel_all else st.multiselect(
                "Študijné programy:", programs_all, default=[], key="iv2_c_programs")
    fig = plot_iv2_c(df, selected_areas, selected_programs or None, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_d(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv2_d(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_e(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv2_e(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_f(df, selected_areas, multiple_years, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        programs_all.extend(get_programs_for_area(df[df["indicator_code"] == "IV2_f"], area))
    programs_all = list(dict.fromkeys(programs_all))
    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv2_f_all_progs")
        with col2:
            selected_programs = programs_all if sel_all else st.multiselect(
                "Študijné programy:", programs_all, default=[], key="iv2_f_programs")
    fig = plot_iv2_f(df, selected_areas, selected_programs or None, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_g(df, selected_areas, multiple_years, chart_type):
    col1, col2 = st.columns([1, 2])
    with col1:
        df_g = df[(df["indicator_code"] == "IV2_g") & (df["area"].isin(selected_areas))]
        available_subs = [s for s in ["reálne", "oficiálne"]
                          if s in df_g["sub_type"].dropna().unique()]
        selected_subs = st.multiselect(
            "Typ ankety:", available_subs,
            default=available_subs, key="iv2_g_subtypes"
        )
    with col2:
        snap_choice = st.radio(
            "Termín:", ["ak.rok", "ZS", "LS"],
            horizontal=True, key="iv2_g_snap"
        )

    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        programs_all.extend(get_programs_for_area(
            df[(df["indicator_code"] == "IV2_g") & (df["snapshot_type"] == snap_choice)], area))
    programs_all = list(dict.fromkeys(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv2_g_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv2_g_programs"
                )

    fig = plot_iv2_g(
        df, selected_areas,
        selected_sub_types=selected_subs or None,
        selected_snapshot=snap_choice,
        selected_programs=selected_programs or None,
        show_years=multiple_years,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_h(df, selected_areas, multiple_years, chart_type):
    snap_choice = st.radio(
        "Termín:", ["ak.rok", "ZS", "LS"],
        horizontal=True, key="iv2_h_snap"
    )
    fig = plot_iv2_h(df, selected_areas,
                     selected_snapshot=snap_choice,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_i(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv2_i(df, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv2_j(df, selected_areas, multiple_years, chart_type):
    df_j = df[(df["indicator_code"] == "IV2_j")]
    all_subs = ["spolu", "študentský senát", "študijné oddelenie", "študijní poradcovia"]
    available_subs = [s for s in all_subs if s in df_j["sub_type"].dropna().unique()]
    selected_subs = st.multiselect(
        "Typ podnetu:", available_subs,
        default=available_subs, key="iv2_j_subtypes"
    )
    fig = plot_iv2_j(df,
                     selected_sub_types=selected_subs or None,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_a(df, selected_areas, multiple_years, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == "IV3_a") &
                   (df["area"] == area) &
                   (df["program"].notna())]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_ordered = []
    if "spolu" in programs_all:
        programs_ordered.append("spolu")
    programs_ordered += sorted([p for p in dict.fromkeys(programs_all) if p != "spolu"])

    selected_programs = []
    sel_all = False
    if programs_ordered:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv3_a_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_ordered
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_ordered, default=[], key="iv3_a_programs")

    selected_subs = None
    if selected_programs or sel_all:
        df_a = df[(df["indicator_code"] == "IV3_a") & (df["area"].isin(selected_areas))]
        available_subs = [s for s in ["prof", "doc", "OA"]
                          if s in df_a["sub_type"].dropna().unique()]
        selected_subs = st.multiselect(
            "Hodnosť:", available_subs, default=available_subs, key="iv3_a_subtypes")

    fig = plot_iv3_a(df, selected_areas,
                     selected_sub_types=selected_subs,
                     selected_programs=selected_programs or None,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_b(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv3_b(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_c(df, selected_areas, multiple_years, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == "IV3_c") &
                   (df["area"] == area) & df["program"].notna()]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_all = sorted(set(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv3_c_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv3_c_programs")

    fig = plot_iv3_c(df, selected_areas,
                     selected_programs=selected_programs or None,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_d(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv3_d(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_e(df, selected_areas, multiple_years, chart_type):
    df_e = df[(df["indicator_code"] == "IV3_e") & (df["area"].isin(selected_areas))]
    available_subs = [s for s in ["priemer", "od", "do"]
                      if s in df_e["sub_type"].dropna().unique()]

    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == "IV3_e") &
                   (df["area"] == area) & df["program"].notna()]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_all = sorted(set(programs_all))

    selected_programs = []
    sel_all = False
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv3_e_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv3_e_programs")

    selected_subs = st.multiselect(
        "Zobraziť:", available_subs, default=available_subs, key="iv3_e_subtypes")

    fig = plot_iv3_e(df, selected_areas,
                     selected_sub_types=selected_subs or None,
                     selected_programs=selected_programs or None,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_ratio(df, selected_areas, multiple_years, code, plot_func, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == code) &
                   (df["area"] == area) & df["program"].notna()]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_all = sorted(set(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key=f"{code}_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key=f"{code}_programs")

    fig = plot_func(df, selected_areas,
                    selected_programs=selected_programs or None,
                    show_years=multiple_years,
                    chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_f(df, selected_areas, multiple_years, chart_type):
    _render_iv3_ratio(df, selected_areas, multiple_years, "IV3_f", plot_iv3_f, chart_type)


def _render_iv3_g(df, selected_areas, multiple_years, chart_type):
    _render_iv3_ratio(df, selected_areas, multiple_years, "IV3_g", plot_iv3_g, chart_type)


def _render_iv3_h(df, selected_areas, multiple_years, chart_type):
    _render_iv3_ratio(df, selected_areas, multiple_years, "IV3_h", plot_iv3_h, chart_type)


def _render_iv3_i(df, selected_areas, multiple_years, chart_type):
    fig = plot_iv3_i(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv3_j(df, selected_areas, multiple_years, chart_type):
    sub_choice = st.radio(
        "Typ údajov:", ["vyslaní", "súčet"],
        horizontal=True, key="iv3_j_sub"
    )

    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == "IV3_j") &
                   (df["area"] == area) &
                   (df["sub_type"] == sub_choice) &
                   df["program"].notna()]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_all = sorted(set(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="iv3_j_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="iv3_j_programs")

    fig = plot_iv3_j(df, selected_areas,
                     selected_sub_type=sub_choice,
                     selected_programs=selected_programs or None,
                     show_years=multiple_years,
                     chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_v5_a(df, selected_areas, multiple_years, chart_type):
    non_fei = [a for a in selected_areas if a != "FEI"]
    programs_all = []
    for area in non_fei:
        progs = df[(df["indicator_code"] == "V5_a") &
                   (df["area"] == area) & df["program"].notna()]["program"].unique().tolist()
        programs_all.extend(progs)
    programs_all = sorted(set(programs_all))

    selected_programs = []
    if programs_all:
        col1, col2 = st.columns([1, 3])
        with col1:
            sel_all = st.checkbox("Všetky programy", value=False, key="v5_a_all_progs")
        with col2:
            if sel_all:
                selected_programs = programs_all
            else:
                selected_programs = st.multiselect(
                    "Študijné programy:", programs_all, default=[], key="v5_a_programs")

    fig = plot_v5_a(df, selected_areas,
                    selected_programs=selected_programs or None,
                    show_years=multiple_years,
                    chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)

def _render_iv_a(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    selected_rocnik = st.selectbox(
        "Ročník:",
        ["všetci", "1r", "2r", "3r", "4r", "5r"],
        key="iv_a_rocnik",
    )

    snapshot_type = "ZS"
    if selected_rocnik == "1r":
        snapshot_choice = st.radio(
            "Termín dát:",
            ["Začiatok ZS", "Koniec ZS"],
            horizontal=True,
            key="iv_a_snapshot",
        )
        snapshot_type = "ZS" if "Začiatok ZS" in snapshot_choice else "LS"

    selected_programs = []
    show_prog_picker = (snapshot_type == "ZS") or (snapshot_type == "LS" and selected_rocnik == "1r")

    if show_prog_picker and any(a != "FEI" for a in selected_areas):
        non_fei = [a for a in selected_areas if a != "FEI"]
        programs_all = _get_programs(df, "IV_a", non_fei)
        if programs_all:
            col1, col2 = st.columns([1, 3])
            with col1:
                select_all_prog = st.checkbox("Všetky programy", value=False, key="iv_a_all_prog")
            with col2:
                if select_all_prog:
                    selected_programs = programs_all
                else:
                    selected_programs = st.multiselect(
                        "Študijné programy:", programs_all, default=[], key="iv_a_programs"
                    )

    if selected_programs:
        fig = plot_iv_a_programme(
            df, selected_areas,
            snapshot_type=snapshot_type,
            selected_programs=selected_programs,
            show_years=multiple_years,
            chart_type=chart_type,
        )
    else:
        fig = plot_iv_a(
            df, selected_areas,
            snapshot_type=snapshot_type,
            show_years=multiple_years,
            selected_rocnik=selected_rocnik,
            chart_type=chart_type,
        )

    st.plotly_chart(fig, use_container_width=True)


def _render_iv_bc(df: pd.DataFrame, ind_code: str, ind_name: str,
                  selected_areas: list, multiple_years: bool, chart_type: str):
    col1, col2 = st.columns([2, 3])

    with col1:
        if ind_code == "IV_c":
            semester = "ZS"
            st.markdown("**Termín:** ZS")
        else:
            semester = st.radio(
                "Termín:",
                ["ZS", "LS"],
                horizontal=True,
                key=f"{ind_code}_semester",
            )

    with col2:
        all_subtypes = ["spolu", "vylúčenie", "zanechanie", "zmena ŠP"]
        selected_sub = st.multiselect(
            "Typ ukončenia:",
            all_subtypes,
            default=["spolu"],
            key=f"{ind_code}_subtype",
        )

    fig = plot_iv_bc(
        df,
        ind_code,
        ind_name,
        selected_areas,
        snapshot_type=semester,
        selected_sub_types=selected_sub or None,
        show_programmes=False,
        show_years=multiple_years,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_d(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    selected_rocnik = st.selectbox(
        "Ročník:",
        ["všetci", "1r", "2r", "3r", "4r", "5r"],
        key="iv_d_rocnik",
    )

    snapshot_type = "ZS"
    if selected_rocnik == "1r":
        snap_choice = st.radio(
            "Termín dát:", ["Začiatok ZS", "Koniec ZS"],
            horizontal=True, key="iv_d_snap"
        )
        snapshot_type = "ZS" if snap_choice == "Začiatok ZS" else "LS"

    fig = plot_iv_d(df, selected_areas, snapshot_type=snapshot_type,
                    show_years=multiple_years, selected_rocnik=selected_rocnik,
                    chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_e(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    col1, col2 = st.columns([2, 3])
    with col1:
        snap_choice = st.radio(
            "Termín dát:",
            ["Začiatok ZS", "Koniec ZS (len 1. ročník, Bc)"],
            horizontal=False,
            key="iv_e_snap"
        )
    snapshot_type = "ZS" if snap_choice == "Začiatok ZS" else "LS"
    fig = plot_iv_e(df, selected_areas, snapshot_type=snapshot_type,
                    show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_f(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    selected_programs = []
    if any(a != "FEI" for a in selected_areas):
        df_ivf = df[(df["indicator_code"] == "IV_f") & (df["program"].notna())]
        programs_all = sorted(df_ivf[df_ivf["area"].isin(selected_areas)]["program"].unique().tolist())
        if programs_all:
            col1, col2 = st.columns([1, 3])
            with col1:
                sel_all = st.checkbox("Všetky programy", value=False, key="iv_f_all_prog")
            with col2:
                if sel_all:
                    selected_programs = programs_all
                else:
                    selected_programs = st.multiselect(
                        "Študijné programy:", programs_all, default=[], key="iv_f_programs"
                    )
    fig = plot_iv_f(df, selected_areas,
                    show_years=multiple_years,
                    selected_programs=selected_programs or None,
                    chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_g(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    df_g = df[(df["indicator_code"] == "IV_g") & (df["area"].isin(selected_areas))]

    available_subtypes = [s for s in [
        "akademické podvody spolu",
        "podvody",
        "plagiáty spolu",
        "plagiáty - záverečné práce",
        "plagiáty - ZAP",
        "plagiáty - OOP",
    ] if s in df_g["sub_type"].dropna().unique()]

    selected_sub = st.multiselect(
        "Typ podvodu:",
        available_subtypes,
        default=[available_subtypes[0]] if available_subtypes else [],
        key="iv_g_subtype",
    )

    fig = plot_iv_g(
        df, selected_areas,
        selected_sub_types=selected_sub or None,
        show_years=multiple_years,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_h(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    fig = plot_iv_h(df, selected_areas, show_years=multiple_years, chart_type=chart_type)
    st.plotly_chart(fig, use_container_width=True)


def _render_iv_i(df: pd.DataFrame, selected_areas: list, multiple_years: bool, chart_type: str):
    selected_programs = []
    if any(a != "FEI" for a in selected_areas):
        df_i = df[(df["indicator_code"] == "IV_i") & (df["program"].notna())]
        programs_all = sorted(
            df_i[df_i["area"].isin(selected_areas)]["program"].unique().tolist()
        )
        if programs_all:
            col1, col2 = st.columns([1, 3])
            with col1:
                sel_all = st.checkbox("Všetky programy", value=False, key="iv_i_all_prog")
            with col2:
                if sel_all:
                    selected_programs = programs_all
                else:
                    selected_programs = st.multiselect(
                        "Študijné programy:", programs_all, default=[], key="iv_i_programs"
                    )

    fig = plot_iv_i(
        df, selected_areas,
        show_years=multiple_years,
        selected_programs=selected_programs or None,
        chart_type=chart_type,
    )
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.title(_app_title)
    st.markdown("---")

    init_db()

    role, username = auth_block(_settings)

    if can_upload(role):
        st.sidebar.markdown("---")
        st.sidebar.subheader("Nahrať Excel do databázy")

        uploaded = st.sidebar.file_uploader("Nahraj .xlsx", type=["xlsx"])
        faculty_upload = st.sidebar.text_input("Fakulta (kód)", value="FEI")

        if uploaded is not None:
            from src.utils.filename_year import infer_start_year_from_filename
            inferred_year = infer_start_year_from_filename(uploaded.name)

            if inferred_year:
                st.sidebar.info(f"Rok určený z názvu súboru: **{format_year_display(inferred_year)}**")
            else:
                st.sidebar.warning("Rok sa nepodarilo určiť z názvu súboru. Zadaj manuálne.")
                inferred_year = st.sidebar.number_input(
                    "Akademický rok (start)", min_value=2000, max_value=2100, value=2023, step=1
                )

            if st.sidebar.button("Nahrať a importovať"):
                content = uploaded.read()
                try:
                    import_excel_to_db(
                        content=content,
                        filename=uploaded.name,
                        faculty=faculty_upload.strip(),
                        year=int(inferred_year),
                    )
                    st.sidebar.success("Import úspešný")
                    st.cache_data.clear()
                except Exception as e:
                    st.sidebar.error(f"Import zlyhal: {e}")

    if can_manage_datasets(role):
        with st.expander("Zoznam nahratých datasetov"):
            uploads_df = list_uploads()
            if not uploads_df.empty:
                for _, urow in uploads_df.iterrows():
                    uid = int(urow["id"])
                    yr = int(urow["year"])
                    fname = urow.get("filename", "")
                    uploaded_at = format_uploaded_at(urow.get("uploaded_at", ""))
                    col_info, col_btn = st.columns([5, 1])
                    with col_info:
                        st.markdown(f"**ID {uid}** — {yr}–{yr + 1} | `{fname}` | {uploaded_at}")
                    with col_btn:
                        if st.button("Zmazať", key=f"del_{uid}"):
                            delete_upload(uid)
                            st.success(f"Dataset ID {uid} bol zmazaný.")
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.info("Žiadne datasety. Nahraj Excel súbor vľavo.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filtre")

    available_faculties = list_faculties()
    if not available_faculties:
        st.error("V databáze nie sú žiadne údaje. Nahraj Excel súbor (admin).")
        return

    selected_faculty = st.sidebar.selectbox("Vyber fakultu:", available_faculties, index=0)

    available_years = get_years(faculty=selected_faculty)
    if not available_years:
        st.error(f"Pre fakultu {selected_faculty} nie sú žiadne údaje.")
        return

    year_options = [format_year_display(y) for y in available_years]
    select_all_years = st.sidebar.checkbox("Vybrať všetky roky", value=False)
    if select_all_years:
        selected_years_str = year_options
    else:
        selected_years_str = st.sidebar.multiselect(
            "Vyberte roky:", year_options, default=[year_options[-1]]
        )
    if not selected_years_str:
        st.warning("Vyberte aspoň jeden rok.")
        return
    selected_years = [int(y.split("-")[0]) for y in selected_years_str]
    multiple_years = len(selected_years) > 1

    with st.spinner("Načítavanie údajov z databázy..."):
        df = load_from_db_cached(tuple(selected_years), faculty=selected_faculty)

    if df is None or df.empty:
        st.error("Údaje nie sú k dispozícii.")
        return

    area_options = ["FEI", "Elektrotechnika", "Informatika"]
    unique_areas = df[df["area_type"] == "area"]["area"].unique().tolist()
    for a in sorted(unique_areas):
        if a not in area_options:
            area_options.append(a)

    select_all_areas = st.sidebar.checkbox("Vybrať všetky odbory", value=False)
    if select_all_areas:
        selected_areas = area_options
    else:
        selected_areas = st.sidebar.multiselect("Odbory:", area_options, default=["FEI"])

    if not selected_areas:
        st.warning("Vyberte aspoň jeden odbor.")
        return

    selected_degrees = ["Bc", "Ing", "PhD"]

    _raw_indicators = load_indicators()

    all_indicators = {
        k: v.get("short", k)
        for k, v in sorted(_raw_indicators.items())
        if isinstance(v, dict)
    }

    db_code_map = {
        k: v.get("db_code", k)
        for k, v in _raw_indicators.items()
        if isinstance(v, dict)
    }

    st.sidebar.markdown("---")
    st.sidebar.subheader("Ukazovatel")
    selected_indicator = _build_indicator_selector(all_indicators)

    # ── GLOBAL CHART TYPE SELECTOR ────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Typ grafu")
    # Čiarový má zmysel len keď je vybraná JEDNA položka
    _one_area = len(selected_areas) == 1
    _selected_programs_count = sum(
        len(v) if isinstance(v, list) else 0
        for k in st.session_state
        if k.endswith("_programs") or k.endswith("_progs")
        for v in [st.session_state.get(k, [])]
    )
    _all_progs = any(
        st.session_state.get(k) is True
        for k in st.session_state
        if k.endswith("_all_progs") or k.endswith("_all_prog")
    )
    _line_allowed = _one_area and not _all_progs and _selected_programs_count <= 1

    if _line_allowed:
        chart_type = st.sidebar.radio(
            "Zobrazenie:",
            ["Stĺpcový", "Čiarový"],
            index=0,
            key="global_chart_type",
            help="Čiarový graf sleduje vývoj jednej položky v čase.",
        )
    else:
        chart_type = "Stĺpcový"
        st.sidebar.caption("💡 Čiarový graf je dostupný pri výbere jedného odboru alebo jedného programu.")
    # ─────────────────────────────────────────────────────────────────────────

    db_code = db_code_map.get(selected_indicator, selected_indicator)

    df_filtered = df[df["area"].isin(selected_areas)].copy()
    df_filtered = df_filtered[
        df_filtered["degree"].isin(selected_degrees + ["ratio", "spolu"])
    ].copy()

    ind_meta = _raw_indicators.get(selected_indicator, {})
    is_iv  = db_code.startswith("IV_")
    is_iv2 = db_code.startswith("IV2_")
    is_iv3 = db_code.startswith("IV3_")

    tab1, tab2 = st.tabs(["Grafy", "Tabuľka"])

    with tab1:
        if is_iv2 and not is_iv3:
            if db_code == "IV2_a":
                _render_iv2_a(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_b":
                _render_iv2_b(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_c":
                _render_iv2_c(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_d":
                _render_iv2_d(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_e":
                _render_iv2_e(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_f":
                _render_iv2_f(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_g":
                _render_iv2_g(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_h":
                _render_iv2_h(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_i":
                _render_iv2_i(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV2_j":
                _render_iv2_j(df_filtered, selected_areas, multiple_years, chart_type)

        elif db_code.startswith("V5_"):
            if db_code == "V5_a":
                _render_v5_a(df_filtered, selected_areas, multiple_years, chart_type)

        elif is_iv3:
            if db_code == "IV3_a":
                _render_iv3_a(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_b":
                _render_iv3_b(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_c":
                _render_iv3_c(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_d":
                _render_iv3_d(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_e":
                _render_iv3_e(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_f":
                _render_iv3_f(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_g":
                _render_iv3_g(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_h":
                _render_iv3_h(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_i":
                _render_iv3_i(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV3_j":
                _render_iv3_j(df_filtered, selected_areas, multiple_years, chart_type)

        elif is_iv:
            if db_code == "IV_a":
                _render_iv_a(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV_d":
                _render_iv_d(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV_e":
                _render_iv_e(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV_f":
                _render_iv_f(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code in ("IV_b", "IV_c"):
                _render_iv_bc(
                    df_filtered,
                    db_code,
                    all_indicators[selected_indicator],
                    selected_areas,
                    multiple_years,
                    chart_type,
                )
            elif db_code == "IV_g":
                _render_iv_g(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV_h":
                _render_iv_h(df_filtered, selected_areas, multiple_years, chart_type)
            elif db_code == "IV_i":
                _render_iv_i(df_filtered, selected_areas, multiple_years, chart_type)

        else:
            prog_indicator_codes = [
                v.get("db_code", k) for k, v in _raw_indicators.items()
                if isinstance(v, dict) and v.get("level") == "program"
            ]

            iii_selected_programs = []
            if db_code in prog_indicator_codes and any(a != "FEI" for a in selected_areas):
                non_fei = [a for a in selected_areas if a != "FEI"]
                programs_all = _get_programs(df_filtered, db_code, non_fei)
                if programs_all:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        sel_all = st.checkbox("Všetky programy", value=False, key="iii_all_prog")
                    with col2:
                        if sel_all:
                            iii_selected_programs = programs_all
                        else:
                            iii_selected_programs = st.multiselect(
                                "Študijné programy:", programs_all, default=[],
                                key="iii_programs"
                            )

            df_iii = df_filtered.copy()
            if iii_selected_programs:
                df_iii = df_iii[df_iii["program"].isin(iii_selected_programs)]
                display_level = "program"
            else:
                df_iii = df_iii[df_iii["program"].isna()]
                display_level = "area"

            if df_iii.empty:
                st.warning("Pre tieto filtre nie sú k dispozícii žiadne údaje.")
            elif display_level == "program" and db_code in prog_indicator_codes:
                fig = plot_program_comparison(
                    df_iii,
                    db_code,
                    all_indicators[selected_indicator],
                    selected_areas,
                    iii_selected_programs,
                    show_years=multiple_years,
                    chart_type=chart_type,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                fig = plot_indicator_comparison(
                    df_iii,
                    db_code,
                    all_indicators[selected_indicator],
                    show_years=multiple_years,
                    chart_type=chart_type,
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        def fmt_val(row):
            if pd.isna(row["value"]):
                return "-"
            return f"{row['value'] * 100:.2f}%" if row["is_percentage"] else f"{row['value']:.0f}"

        df_t = df_filtered[df_filtered["indicator_code"] == db_code].copy()
        df_t["formatted_value"] = df_t.apply(fmt_val, axis=1)

        _any_all_progs = any(
            st.session_state.get(k) is True
            for k in st.session_state
            if k.endswith("_all_progs") or k.endswith("_all_prog")
        )
        _any_progs_list = any(
            bool(st.session_state.get(k))
            for k in st.session_state
            if k.endswith("_programs") or k.endswith("_progs")
        )
        if not _any_all_progs and not _any_progs_list:
            df_t = df_t[df_t["program"].isna()]

        _AREA_RANK = {"FEI": 0, "Elektrotechnika": 1, "Informatika": 2}
        df_t["_area_rank"] = df_t["area"].map(_AREA_RANK).fillna(99)
        df_t["_prog_is_prog"] = df_t["program"].notna().astype(int)
        df_t["_prog_sort"] = df_t["program"].fillna("")
        df_t["_year_sort"] = df_t["year"].fillna(0)
        df_t = df_t.sort_values(
            ["_area_rank", "_prog_is_prog", "_prog_sort", "_year_sort"],
            ascending=[True, True, True, True],
        ).drop(columns=["_area_rank", "_prog_is_prog", "_prog_sort", "_year_sort"])

        display_cols = {
            "year_display": "Akademický rok",
            "area": "Odbor",
            "program": "Študijný program",
            "degree": "Stupeň",
            "indicator_code": "Kód",
            "indicator_name": "Ukazovateľ",
            "sub_type": "Typ",
            "snapshot_type": "Termín",
            "study_year": "Ročník",
            "formatted_value": "Hodnota",
        }
        show_cols = [c for c in display_cols if c in df_t.columns]

        if df_t.empty:
            st.info("Pre vybraný ukazovateľ nie sú k dispozícii žiadne údaje.")
        else:
            st.dataframe(
                df_t[show_cols].rename(columns=display_cols),
                use_container_width=True,
                hide_index=True,
            )

    if can_export(role):
        st.markdown("---")
        st.subheader("Export údajov")

        df_export = df_filtered[df_filtered["indicator_code"] == db_code].copy()
        df_export["formatted_value"] = df_export.apply(fmt_val, axis=1)

        df_export = df_export.drop(
            columns=["id", "upload_id", "is_percentage", "area_type", "value", "year"], errors="ignore"
        )
        if "area" in df_export.columns:
            df_export = df_export.rename(
                columns={"area": "odbor", "year_display": "akademicky_rok"}
            )

        _AREA_RANK_EXP = {"FEI": 0, "Elektrotechnika": 1, "Informatika": 2}
        if "odbor" in df_export.columns:
            df_export["_ar"] = df_export["odbor"].map(_AREA_RANK_EXP).fillna(99)
            df_export["_pp"] = df_export["program"].notna().astype(int) if "program" in df_export.columns else 0
            df_export["_ps"] = df_export["program"].fillna("") if "program" in df_export.columns else ""
            df_export["_ys"] = df_export["akademicky_rok"].fillna("") if "akademicky_rok" in df_export.columns else ""
            df_export = df_export.sort_values(["_ar", "_pp", "_ps", "_ys"]).drop(columns=["_ar", "_pp", "_ps", "_ys"])

        if len(selected_years) == 1:
            year_str = format_year_display(selected_years[0]).replace("-", "_")
        else:
            year_str = (
                f"{format_year_display(min(selected_years))}_"
                f"{format_year_display(max(selected_years))}"
            ).replace("-", "_")

        file_base = f"FEI_{selected_indicator}_{year_str}"

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Stiahnuť CSV",
                df_export.to_csv(index=False).encode("utf-8-sig"),
                f"{file_base}.csv",
                "text/csv",
            )
        with col2:
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Ukazovatele")
            st.download_button(
                "Stiahnuť Excel",
                output.getvalue(),
                f"{file_base}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    main()