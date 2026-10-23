"""
FloatChat - AI-powered ARGO ocean data explorer (Streamlit frontend)
Talks to the FastAPI backend in main.py.
"""

import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

import config

st.set_page_config(
    page_title="FloatChat - ARGO Data Explorer",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API = config.BACKEND_URL.rstrip("/")
MAP_CENTER = {"lat": -8, "lon": 75}
TEMP_SCALE = "Turbo"
MAP_CONFIG = {"scrollZoom": False}  # keep the mouse wheel for page scrolling

SUGGESTIONS = [  # (icon, topic, question)
    ("🌡️", "Depth structure", "What is the average temperature at different depths?"),
    ("🗺️", "Regions", "Compare surface temperature across ocean regions"),
    ("🔎", "Find profiles", "Show me salinity profiles near the equator in March 2024"),
    ("🫧", "Oxygen minimum", "Which floats measured low oxygen in the Arabian Sea?"),
    ("🧪", "Biogeochemistry", "Average dissolved oxygen by ocean zone"),
    ("📅", "Trends", "Show the monthly temperature trend"),
]
SAMPLE_QUESTIONS = [q for _, _, q in SUGGESTIONS]
PAGES = ["Overview", "Ask FloatChat"]

st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1400px; }
    .hero {
        background: radial-gradient(circle at 15% 20%, rgba(56,189,248,0.25), transparent 45%),
                    radial-gradient(circle at 85% 80%, rgba(52,211,153,0.18), transparent 45%),
                    linear-gradient(135deg, #0f1e3d 0%, #0b1220 100%);
        border: 1px solid rgba(56,189,248,0.25);
        border-radius: 20px;
        padding: 2.6rem 2.4rem;
        margin-bottom: 1.4rem;
    }
    .hero h1 {
        font-size: 3rem; font-weight: 800; margin: 0 0 .4rem 0;
        background: linear-gradient(90deg, #7dd3fc, #34d399);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .hero .tagline { font-size: 1.25rem; color: #bae6fd; margin-bottom: .8rem; }
    .hero p { color: #cbd5e1; max-width: 860px; line-height: 1.6; margin: 0; }
    .card {
        background: #111a2e; border: 1px solid #1e2b45; border-radius: 14px;
        padding: 1.2rem 1.3rem; height: 100%;
    }
    .card h4 { margin: 0 0 .5rem 0; color: #7dd3fc; }
    .card p { color: #94a3b8; margin: 0; font-size: .95rem; line-height: 1.5; }
    div[data-testid="stMetric"] {
        background: #111a2e; border: 1px solid #1e2b45; border-radius: 14px; padding: .9rem 1.1rem;
    }
    .status-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
    .footer { text-align: center; color: #64748b; font-size: .85rem; margin-top: 3rem; padding: 1.5rem 0;
              border-top: 1px solid #1e2b45; }
    .footer a { color: #7dd3fc; }
    .pills { margin-top: 1.1rem; display: flex; flex-wrap: wrap; gap: .5rem; }
    .pill, .badge {
        display: inline-block; padding: .2rem .7rem; border-radius: 999px; font-size: .82rem;
        background: rgba(56,189,248,0.10); border: 1px solid rgba(56,189,248,0.28); color: #bae6fd;
    }
    .badge { font-size: .75rem; margin: 0 .35rem .5rem 0; padding: .1rem .6rem; }
    .badge.sql { background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.35); color: #fdba74; }
    .badge.rag { background: rgba(52,211,153,0.12); border-color: rgba(52,211,153,0.35); color: #6ee7b7; }
    .badge.muted { background: transparent; border-color: #1e2b45; color: #94a3b8; }
    .topic { color: #7dd3fc; font-size: .78rem; font-weight: 600; text-transform: uppercase;
             letter-spacing: .06em; margin: .2rem 0 .3rem .1rem; }
    [class*="st-key-suggest_"] button {
        min-height: 4.2rem; justify-content: flex-start; text-align: left;
        background: #111a2e; border: 1px solid #1e2b45; border-radius: 14px;
    }
    [class*="st-key-suggest_"] button:hover { border-color: #38bdf8; background: #13213b; }
    [class*="st-key-suggest_"] button > div, [class*="st-key-suggest_"] button p {
        justify-content: flex-start; text-align: left; width: 100%;
    }
    .empty-state { text-align: center; padding: 1.5rem 0 1rem 0; }
    .empty-state h3 { margin-bottom: .2rem; }
    .empty-state p { color: #94a3b8; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- API access

def api_get(path: str, timeout: int = 15):
    resp = requests.get(f"{API}{path}", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, payload: dict, timeout: int = 120):
    resp = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp


@st.cache_data(ttl=30, show_spinner=False)
def get_health():
    try:
        return api_get("/health", timeout=5)
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def get_stats():
    return api_get("/stats")


@st.cache_data(ttl=600, show_spinner=False)
def get_floats():
    return pd.DataFrame(api_get("/floats"))


@st.cache_data(ttl=600, show_spinner=False)
def get_float_track(float_id: str):
    return pd.DataFrame(api_get(f"/profiles/float/{float_id}"))


@st.cache_data(ttl=600, show_spinner=False)
def get_profiles(profile_ids: tuple):
    return pd.DataFrame(api_post("/get_profiles", {"profile_ids": list(profile_ids)}).json())


@st.cache_data(ttl=600, show_spinner=False)
def export_profiles(profile_ids: tuple, fmt: str) -> bytes:
    return api_post("/export", {"format": fmt, "profile_ids": list(profile_ids)}).content


def ask_backend(question: str) -> dict:
    try:
        started = time.perf_counter()
        response = api_post("/query", {"query_text": question}).json()
        response["elapsed"] = time.perf_counter() - started
        return response
    except requests.exceptions.RequestException as e:
        return {"answer": f"⚠️ I couldn't reach the FloatChat API at `{API}` ({e.__class__.__name__}). "
                          "Is the backend running?", "query_type": "error", "retrieved_metadata": []}


# ---------------------------------------------------------------- charts

def style(fig, height=460):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(17,26,46,0.6)",
        font=dict(color="#e2e8f0"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def float_map(floats: pd.DataFrame):
    fig = px.scatter_map(
        floats, lat="lat", lon="lon", color="surface_temperature",
        color_continuous_scale=TEMP_SCALE, zoom=2.1, center=MAP_CENTER,
        hover_name="float_id",
        hover_data={"region": True, "last_profile": True, "n_profiles": True,
                    "surface_temperature": ":.2f", "surface_salinity": ":.2f", "lat": ":.2f", "lon": ":.2f"},
        labels={"surface_temperature": "Surface °C", "surface_salinity": "Surface PSU",
                "n_profiles": "Profiles", "last_profile": "Last profile"},
        map_style="carto-darkmatter",
    )
    fig.update_traces(marker=dict(size=9, opacity=0.9))
    fig.update_layout(title="Latest position of every float (colored by surface temperature)")
    return style(fig, 560)


def profiles_map(meta: pd.DataFrame):
    fig = px.scatter_map(
        meta, lat="lat", lon="lon", color="region", hover_name="float_id",
        hover_data={"date": True, "cycle_number": True, "lat": ":.2f", "lon": ":.2f", "region": False},
        zoom=3 if meta["lat"].max() - meta["lat"].min() < 25 else 2.1,
        center={"lat": meta["lat"].mean(), "lon": meta["lon"].mean()}, map_style="carto-darkmatter",
    )
    fig.update_traces(marker=dict(size=13))
    fig.update_layout(title="Where the matching profiles were recorded")
    return style(fig, 460)


def profile_plot(data: pd.DataFrame):
    has_oxygen = data["oxygen"].notna().any()
    variables = [("temperature", "Temperature (°C)"), ("salinity", "Salinity (PSU)")]
    if has_oxygen:
        variables.append(("oxygen", "Oxygen (µmol/kg)"))
    fig = make_subplots(rows=1, cols=len(variables), shared_yaxes=True,
                        subplot_titles=[label for _, label in variables])
    palette = px.colors.qualitative.Set2
    for i, (key, group) in enumerate(data.groupby(["float_id", "cycle_number"], sort=False)):
        label = f"Float {key[0]} · cycle {key[1]}"
        color = palette[i % len(palette)]
        for col, (var, _) in enumerate(variables, start=1):
            if group[var].notna().any():
                fig.add_trace(go.Scatter(x=group[var], y=group["depth"], mode="lines+markers", name=label,
                                         legendgroup=label, showlegend=col == 1,
                                         line=dict(color=color, width=2), marker=dict(size=4)),
                              row=1, col=col)
    fig.update_yaxes(autorange="reversed", title_text="Depth (m)", row=1, col=1)
    style(fig, 520)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.08, x=0), margin=dict(t=40))
    return fig


def analytical_chart(df: pd.DataFrame, intent: str):
    if df.empty:
        return None
    if intent == "avg_by_depth":
        fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                            subplot_titles=["Mean temperature (°C)", "Mean salinity (PSU)"])
        fig.add_trace(go.Scatter(x=df["avg_temperature"], y=df["depth"], mode="lines+markers",
                                 name="Temperature", line=dict(color="#f97316", width=3)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["avg_salinity"], y=df["depth"], mode="lines+markers",
                                 name="Salinity", line=dict(color="#38bdf8", width=3)), row=1, col=2)
        fig.update_yaxes(autorange="reversed", title_text="Depth (m)", row=1, col=1)
        return style(fig)
    if intent == "regional_comparison":
        fig = px.bar(df, x="region", y="avg_temperature", color="avg_salinity",
                     color_continuous_scale="Viridis", text_auto=".1f",
                     labels={"avg_temperature": "Mean temperature, upper 100 m (°C)", "avg_salinity": "Salinity",
                             "region": ""}, title="Upper-ocean temperature by region")
        fig.update_traces(textposition="outside")
        return style(fig)
    if intent == "depth_ranges":
        fig = px.bar(df, x="depth_range", y="avg_temperature", color="avg_salinity",
                     color_continuous_scale="Viridis", text_auto=".1f",
                     labels={"avg_temperature": "Mean temperature (°C)", "depth_range": "", "avg_salinity": "Salinity"},
                     title="Temperature by depth layer")
        fig.update_traces(textposition="outside")
        return style(fig)
    if intent == "temporal_trends":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df["month"], y=df["avg_temperature"], name="Temperature (°C)",
                                 mode="lines+markers", line=dict(color="#f97316", width=3)))
        fig.add_trace(go.Scatter(x=df["month"], y=df["avg_salinity"], name="Salinity (PSU)",
                                 mode="lines+markers", line=dict(color="#38bdf8", width=3)), secondary_y=True)
        fig.update_layout(title="Monthly means")
        return style(fig)
    if intent == "float_summary":
        top = df.sort_values("total_profiles", ascending=False).head(20)
        fig = px.bar(top, x="float_id", y="total_profiles", color="avg_temperature",
                     color_continuous_scale=TEMP_SCALE,
                     labels={"float_id": "Float", "total_profiles": "Profiles", "avg_temperature": "Mean °C"},
                     title="Most active floats")
        fig.update_xaxes(type="category")
        return style(fig)
    if intent == "bgc_analysis":
        fig = px.bar(df, x="ocean_zone", y="avg_oxygen",
                     error_y=df["max_oxygen"] - df["avg_oxygen"], error_y_minus=df["avg_oxygen"] - df["min_oxygen"],
                     labels={"avg_oxygen": "Dissolved oxygen (µmol/kg)", "ocean_zone": ""},
                     title="Dissolved oxygen by ocean zone (bars = mean, whiskers = range)")
        fig.update_traces(marker_color="#34d399")
        return style(fig)
    # Generic: first text column vs first numeric column
    text_cols = [c for c in df.columns if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object]
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if text_cols and num_cols:
        return style(px.bar(df.head(30), x=text_cols[0], y=num_cols[0]))
    return None


# ---------------------------------------------------------------- UI pieces

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🌊 FloatChat")
        page = st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")

        st.markdown("#### System status")
        health = get_health()

        def row(ok, label, detail=""):
            color = "#34d399" if ok else ("#fbbf24" if ok is None else "#f87171")
            st.markdown(f'<span class="status-dot" style="background:{color}"></span>{label}'
                        f'<span style="color:#64748b"> {detail}</span>', unsafe_allow_html=True)

        if health is None:
            row(False, "API offline", API)
        else:
            row(health["database"] == "connected", "PostgreSQL", f"{health['measurements']:,} measurements")
            row(health["chromadb"] == "connected", "Vector index", f"{health['indexed_profiles']:,} profiles")
            llm_info = health["llm"]
            if not llm_info["configured"]:
                row(None, "LLM", "not configured (data-only answers)")
            else:
                row(llm_info["reachable"], "LLM", llm_info["model"] if llm_info["reachable"]
                    else f"{llm_info['model']} – {llm_info.get('error') or 'unreachable'}")

        if page == "Ask FloatChat" and st.session_state.messages:
            st.markdown("#### Try asking")
            for icon, _, q in SUGGESTIONS:
                st.button(q, key=f"sample_{q}", icon=icon, width="stretch", on_click=ask, args=(q,))
            if st.button("🗑️ Clear conversation", width="stretch"):
                st.session_state.messages = []
                st.rerun()


def ask(question: str):
    """Button callback: switch to the chat and queue a question."""
    st.session_state.page = "Ask FloatChat"
    st.session_state.pending_question = question


def go_to(page: str):
    st.session_state.page = page


def render_overview():
    st.markdown("""
    <div class="hero">
        <h1>FloatChat</h1>
        <div class="tagline">Ask the ocean questions in plain English.</div>
        <p>FloatChat lets scientists, students and curious people explore real ARGO float observations from the
        Indian Ocean. Ask about temperature, salinity or oxygen; it writes the SQL or searches thousands of profiles
        for you, then draws the maps and charts.</p>
        <div class="pills">
            <span class="pill">🛰️ Real ARGO observations</span>
            <span class="pill">🧮 Natural language → SQL</span>
            <span class="pill">🔎 RAG over 3,900 profiles</span>
            <span class="pill">📦 CSV · NetCDF · ASCII export</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    cta1, cta2, _ = st.columns([1, 1.2, 3])
    cta1.button("💬 Start asking", type="primary", width="stretch", on_click=go_to, args=("Ask FloatChat",))
    cta2.button("✨ Try a demo question", width="stretch",
                on_click=ask, args=("Which floats measured low oxygen in the Arabian Sea?",))

    try:
        stats, floats = get_stats(), get_floats()
    except Exception:
        st.error(f"Can't reach the FloatChat API at `{API}`. Start it with `uvicorn main:app` "
                 "(or `docker compose up`) and refresh.")
        return

    start, end = pd.to_datetime(stats["start_date"]), pd.to_datetime(stats["end_date"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ARGO floats", f"{stats['floats']:,}")
    c2.metric("Profiles", f"{stats['profiles']:,}")
    c3.metric("Measurements", f"{stats['measurements']:,}")
    c4.metric("BGC (oxygen) floats", f"{stats['bgc_floats']:,}")
    if start.year == end.year:
        c5.metric(f"Period ({end.year})", f"{start:%b}–{end:%b}")
    else:
        c5.metric("Period", f"{start:%Y}–{end:%Y}")

    floats = floats.reset_index(drop=True)
    left, right = st.columns([3, 1])
    with left:
        event = st.plotly_chart(float_map(floats), config=MAP_CONFIG, key="float_map",
                                on_select="rerun", selection_mode="points")
        # Clicking a float opens it in the explorer below (only react to new clicks)
        points = tuple(p.get("point_index") for p in (event.selection.points if event else []))
        if points and points != st.session_state.get("last_map_click"):
            st.session_state.last_map_click = points
            st.session_state.explorer_float = floats.loc[points[0], "float_id"]
        st.caption("💡 Click any float to explore its trajectory and profiles below.")
    with right:
        regions = pd.DataFrame(stats["regions"]).sort_values("profiles")
        fig = px.bar(regions, x="profiles", y="region", orientation="h", text_auto=True,
                     labels={"profiles": "", "region": ""}, title="Profiles by region")
        fig.update_traces(marker_color="#38bdf8", textposition="auto")
        fig.update_xaxes(showticklabels=False, showgrid=False)
        st.plotly_chart(style(fig, 560))

    st.markdown("### How it works")
    cards = [
        ("🧮 Analytical questions → SQL",
         "Questions like <i>\"average temperature at different depths\"</i> become SQL that runs on PostgreSQL. "
         "Common patterns use vetted templates; anything else is written by the LLM and checked to be read-only."),
        ("🔎 Descriptive questions → RAG",
         "Every profile is summarised in words and embedded into ChromaDB. FloatChat finds the closest matches, "
         "narrowed by any region or month you mention, and the LLM answers from them."),
        ("📈 Visualize & export",
         "Each answer comes with maps, depth profiles or charts, and the underlying data can be downloaded "
         "as CSV, NetCDF or ASCII."),
    ]
    for col, (title, body) in zip(st.columns(3), cards):
        col.markdown(f'<div class="card"><h4>{title}</h4><p>{body}</p></div>', unsafe_allow_html=True)

    st.markdown("### Explore a single float")
    options = floats.sort_values("n_profiles", ascending=False)
    labels = {r.float_id: f"{r.float_id} · {r.region} · {r.n_profiles} profiles" for r in options.itertuples()}
    st.session_state.setdefault("explorer_float", next(iter(labels)))
    float_id = st.selectbox("Float", list(labels), format_func=labels.get, key="explorer_float")
    track = get_float_track(float_id)
    if not track.empty:
        a, b = st.columns(2)
        with a:
            fig = px.line_map(track, lat="profile_lat", lon="profile_lon", zoom=3.5,
                              center={"lat": track["profile_lat"].mean(), "lon": track["profile_lon"].mean()},
                              map_style="carto-darkmatter", hover_data=["cycle_number", "profile_date"])
            fig.add_trace(go.Scattermap(lat=track["profile_lat"], lon=track["profile_lon"], mode="markers",
                                        marker=dict(size=9, color=track["avg_temp"], colorscale=TEMP_SCALE),
                                        text=track["profile_date"], name="Profiles"))
            fig.update_layout(title=f"Trajectory of float {float_id}", showlegend=False)
            st.plotly_chart(style(fig, 520), config=MAP_CONFIG)
        with b:
            latest = tuple(track.sort_values("cycle_number")["profile_id"].tail(3).tolist())
            st.plotly_chart(profile_plot(get_profiles(latest)))


def answer_badges(response: dict) -> str:
    kind = response.get("query_type")
    meta = response.get("retrieved_metadata") or []
    badges = []
    if kind == "analytical":
        info = meta[0] if meta else {}
        badges.append(f'<span class="badge sql">🧮 SQL · {info.get("intent", "query").replace("_", " ")} · '
                      f'{info.get("row_count", 0)} rows</span>')
    elif kind == "semantic":
        badges.append(f'<span class="badge rag">🔎 Profile search · {len(meta)} matches</span>')
    if "elapsed" in response:
        badges.append(f'<span class="badge muted">⏱ {response["elapsed"]:.1f} s</span>')
    return "".join(badges)


def render_response(msg: dict, idx: int):
    """Charts and data that accompany an assistant answer."""
    response = msg.get("response") or {}
    kind = response.get("query_type")
    meta = response.get("retrieved_metadata") or []

    if kind == "analytical" and response.get("sql_results"):
        info = meta[0] if meta else {}
        df = pd.DataFrame(response["sql_results"])
        if "month" in df:
            df["month"] = pd.to_datetime(df["month"])
        fig = analytical_chart(df, info.get("intent", "custom"))
        if fig is not None:
            st.plotly_chart(fig, key=f"chart_{idx}")
        with st.expander("Data & SQL"):
            st.dataframe(df, hide_index=True)
            st.code(info.get("sql_query", ""), language="sql")

    elif kind == "semantic" and meta:
        meta_df = pd.DataFrame(meta)
        profile_ids = tuple(int(p) for p in meta_df["profile_id"])
        tab_map, tab_profiles, tab_data = st.tabs(["🗺️ Map", "📈 Profiles", "📋 Data & export"])
        with tab_map:
            st.plotly_chart(profiles_map(meta_df), key=f"map_{idx}", config=MAP_CONFIG)
        with tab_profiles:
            shown = st.multiselect(
                "Profiles to plot", profile_ids, default=list(profile_ids[:3]), key=f"sel_{idx}",
                format_func=lambda p: "Float {float_id} · {date}".format(**meta_df.set_index("profile_id").loc[p]),
            )
            if shown:
                st.plotly_chart(profile_plot(get_profiles(tuple(shown))), key=f"prof_{idx}")
        with tab_data:
            st.dataframe(meta_df[["float_id", "cycle_number", "date", "lat", "lon", "region"]], hide_index=True)
            cols = st.columns(3)
            for col, (fmt, ext, mime) in zip(cols, [("csv", "csv", "text/csv"),
                                                    ("netcdf", "nc", "application/x-netcdf"),
                                                    ("ascii", "txt", "text/plain")]):
                col.download_button(f"Download {fmt.upper()}", data=lambda f=fmt: export_profiles(profile_ids, f),
                                    file_name=f"floatchat_profiles.{ext}", mime=mime,
                                    key=f"dl_{fmt}_{idx}", width="stretch")
        with st.expander("Retrieved context"):
            for doc in response.get("context_documents", []):
                st.caption(doc)


def render_chat():
    st.markdown("## 💬 Ask FloatChat")
    st.caption("Ask about temperature, salinity or oxygen in the Indian Ocean (Jan–Mar 2024). "
               "Statistical questions run as SQL; descriptive ones search the profile index.")

    if not st.session_state.messages:
        st.markdown("""
        <div class="empty-state">
            <h3>What would you like to know about the ocean?</h3>
            <p>Pick a question to get started, or type your own below.</p>
        </div>
        """, unsafe_allow_html=True)
        for row in (SUGGESTIONS[:3], SUGGESTIONS[3:]):
            for col, (icon, topic, q) in zip(st.columns(3), row):
                with col:
                    st.markdown(f'<div class="topic">{icon} {topic}</div>', unsafe_allow_html=True)
                    st.button(q, key=f"suggest_{topic}", width="stretch", wrap=True, on_click=ask, args=(q,))

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🌊"):
            if msg["role"] == "assistant" and msg.get("response"):
                st.markdown(answer_badges(msg["response"]), unsafe_allow_html=True)
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                render_response(msg, idx)

    question = st.chat_input("e.g. Show me salinity profiles near the equator in March 2024")
    question = question or st.session_state.pop("pending_question", None)
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.spinner("Diving into the data…"):
            response = ask_backend(question)
        st.session_state.messages.append({"role": "assistant", "content": response["answer"], "response": response})
        st.rerun()


def main():
    st.session_state.setdefault("page", "Overview")
    st.session_state.setdefault("messages", [])

    # Shareable demo links: ?q=<question> opens the chat and asks it
    if "q" in st.query_params and not st.session_state.get("query_param_used"):
        st.session_state.query_param_used = True
        st.session_state.page = "Ask FloatChat"
        st.session_state.pending_question = st.query_params["q"]

    render_sidebar()
    if st.session_state.page == "Overview":
        render_overview()
    else:
        render_chat()

    st.markdown("""
    <div class="footer">
        FloatChat · data: <a href="https://argo.ucsd.edu/" target="_blank">Argo Program</a> via
        <a href="https://erddap.ifremer.fr/erddap/" target="_blank">Ifremer ERDDAP</a> ·
        built with FastAPI, PostgreSQL, ChromaDB and Streamlit
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
