"""
Tokyo Electricity Demand Dashboard (Streamlit + Plotly)

Data: tokyo_hourly_clean.csv.gz - 39,744 hourly records, 2022-04-01 to 2026-10-12 (JST)
  * TEPCO Power Grid "でんき予報": demand, forecast, supply capacity, usage rate, solar output (GW)
  * Japan Meteorological Agency: hourly temperature, humidity and sunshine (Tokyo station)

Run locally:  streamlit run app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
DATA = HERE / "tokyo_hourly_clean.csv.gz"

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK_2, GRID = "#52514e", "#e6e5e1"
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
SEASON_COLORS = {"Winter": BLUE, "Spring": AQUA, "Summer": ORANGE, "Autumn": YELLOW}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

st.set_page_config(page_title="Tokyo Electricity Demand Dashboard", page_icon="⚡", layout="wide")


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["datetime"])
    df["date"] = df["datetime"].dt.normalize()
    df["day_type"] = np.where(df["is_workday"], "Workday", "Weekend / holiday")
    df["net_demand_gw"] = df["demand_gw"] - df["solar_gw"]
    df["forecast_error_pct"] = (df["demand_gw"] - df["tepco_forecast_gw"]).abs() / df["demand_gw"] * 100
    edges = list(range(-4, 42, 2))
    df["temp_band"] = pd.cut(df["temp_tokyo_c"], bins=edges, right=False,
                             labels=[f"{a}–{a + 2} °C" for a in edges[:-1]])
    return df


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=78, b=10),
        title=dict(y=0.985, yanchor="top", x=0, xanchor="left", font=dict(size=15)), plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=13, color="#0b0b0b"), hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, title=None) if legend else None,
        showlegend=legend,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=INK_2))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=INK_2))
    return fig


df_all = load_data()

# --------------------------------------------------------------------------------------
# Header + filters
# --------------------------------------------------------------------------------------
st.title("⚡ Tokyo Electricity Demand Dashboard")
st.caption("Hourly electricity demand in the TEPCO (Tokyo) area with Japan Meteorological Agency weather, "
           "Apr 2022 – Oct 2026. Data © TEPCO Power Grid and the Japan Meteorological Agency (processed).")

min_d, max_d = df_all["date"].min().date(), df_all["date"].max().date()
f1, f2, f3, f4 = st.columns([1.3, 1.6, 1.1, 1.4])
with f1:
    dates = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
with f2:
    seasons = st.multiselect("Season", SEASONS, default=SEASONS)
with f3:
    day_type = st.selectbox("Day type", ["All days", "Workday", "Weekend / holiday"])
with f4:
    t_lo, t_hi = float(np.floor(df_all["temp_tokyo_c"].min())), float(np.ceil(df_all["temp_tokyo_c"].max()))
    temp_range = st.slider("Tokyo temperature (°C)", t_lo, t_hi, (t_lo, t_hi), step=1.0, format="%.0f °C")

start, end = (dates if isinstance(dates, tuple) and len(dates) == 2 else (min_d, max_d))
mask = (
    df_all["date"].between(pd.Timestamp(start), pd.Timestamp(end))
    & df_all["season"].isin(seasons)
    & df_all["temp_tokyo_c"].between(*temp_range)
)
if day_type != "All days":
    mask &= df_all["day_type"] == day_type
df = df_all[mask]

if df.empty:
    st.warning("No hours match these filters. Widen the date range, seasons or temperature range.")
    st.stop()

st.caption(f"Showing **{len(df):,}** of {len(df_all):,} hours "
           f"({df['date'].nunique():,} days, {start:%d %b %Y} – {end:%d %b %Y}).")

# --------------------------------------------------------------------------------------
# Key metrics
# --------------------------------------------------------------------------------------
peak = df.loc[df["demand_gw"].idxmax()]
low = df.loc[df["demand_gw"].idxmin()]
tight = df.loc[df["usage_rate_pct"].idxmax()]
avg_all = df_all["demand_gw"].mean()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Average demand", f"{df['demand_gw'].mean():.1f} GW",
          f"{df['demand_gw'].mean() - avg_all:+.1f} GW vs all data", delta_color="off", delta_arrow="off", border=True)
k2.metric("Peak demand", f"{peak['demand_gw']:.1f} GW",
          f"{peak['datetime']:%d %b %Y %H:00}, {peak['temp_tokyo_c']:.1f} °C", delta_color="off", delta_arrow="off", border=True)
k3.metric("Lowest demand", f"{low['demand_gw']:.1f} GW", f"{low['datetime']:%d %b %Y %H:00}", delta_color="off", delta_arrow="off", border=True)
k4.metric("Energy used", f"{df['demand_gw'].sum() / 1000:,.0f} TWh", f"{len(df):,} hours", delta_color="off", delta_arrow="off", border=True)
k5.metric("Solar share", f"{df['solar_gw'].sum() / df['demand_gw'].sum() * 100:.1f} %",
          f"max {df['solar_gw'].max():.1f} GW", delta_color="off", delta_arrow="off", border=True)
k6.metric("Highest usage rate", f"{int(tight['usage_rate_pct'])} %",
          f"{tight['datetime']:%d %b %Y %H:00}", delta_color="off", delta_arrow="off", border=True)

# --------------------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------------------
tab_trend, tab_temp, tab_time, tab_solar, tab_data = st.tabs(
    ["📈 Trends", "🌡️ Temperature", "🕒 Daily & weekly patterns", "☀️ Solar & supply", "📋 Data tables"])

# ---- Trends --------------------------------------------------------------------------
with tab_trend:
    monthly = df.set_index("datetime").resample("MS").agg(
        avg_demand_gw=("demand_gw", "mean"), peak_demand_gw=("demand_gw", "max"),
        avg_temp_c=("temp_tokyo_c", "mean")).dropna().reset_index()
    fig = go.Figure()
    fig.add_scatter(x=monthly["datetime"], y=monthly["peak_demand_gw"], name="Monthly peak", mode="lines",
                    line=dict(color=ORANGE, width=2),
                    hovertemplate="%{x|%b %Y}<br>Peak %{y:.1f} GW<extra></extra>")
    fig.add_scatter(x=monthly["datetime"], y=monthly["avg_demand_gw"], name="Monthly average", mode="lines+markers",
                    line=dict(color=BLUE, width=2), marker=dict(size=5),
                    hovertemplate="%{x|%b %Y}<br>Average %{y:.1f} GW<extra></extra>")
    fig.update_layout(title="Monthly average and peak demand", yaxis_title="GW")
    st.plotly_chart(style(fig, 400), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        yearly = df.groupby("year").agg(
            hours=("demand_gw", "size"), avg_demand_gw=("demand_gw", "mean"), peak_demand_gw=("demand_gw", "max"),
            energy_twh=("demand_gw", lambda s: s.sum() / 1000),
            hours_35c_plus=("temp_tokyo_c", lambda s: int((s >= 35).sum())),
            max_solar_gw=("solar_gw", "max")).round(2)
        st.markdown("**Year by year**")
        st.dataframe(yearly, width="stretch")
        st.caption("2022 starts in April and 2026 ends on 12 October, so their totals cover part of the year.")
    with c2:
        by_month = df.groupby("month")["demand_gw"].mean().reindex(range(1, 13))
        top = by_month.nlargest(2).index
        fig = go.Figure(go.Bar(
            x=MONTHS, y=by_month.values, marker_color=[ORANGE if m in top else BLUE for m in by_month.index],
            hovertemplate="%{x}<br>%{y:.1f} GW<extra></extra>"))
        fig.update_layout(title="Average demand by calendar month (orange: two highest)", yaxis_title="GW")
        st.plotly_chart(style(fig, 340, legend=False), width="stretch")

# ---- Temperature ---------------------------------------------------------------------
with tab_temp:
    daily = df.groupby(["date", "day_type"], as_index=False).agg(
        peak_gw=("demand_gw", "max"), max_temp_c=("temp_tokyo_c", "max"))
    c1, c2 = st.columns([1.25, 1])
    with c1:
        fig = px.scatter(daily, x="max_temp_c", y="peak_gw", color="day_type",
                         color_discrete_map={"Workday": BLUE, "Weekend / holiday": ORANGE},
                         custom_data=["date"],
                         labels={"max_temp_c": "Daily max temperature in Tokyo (°C)", "peak_gw": "Daily peak (GW)"})
        fig.update_traces(marker=dict(size=7, opacity=0.75, line=dict(width=0.5, color="white")),
                          hovertemplate="%{customdata[0]|%d %b %Y}<br>%{x:.1f} °C → %{y:.1f} GW<extra></extra>")
        fig.update_layout(title="Daily peak demand vs daily maximum temperature")
        st.plotly_chart(style(fig, 430), width="stretch")
    with c2:
        band = df.groupby("temp_band", observed=True).agg(
            hours=("demand_gw", "size"), avg=("demand_gw", "mean"), peak=("demand_gw", "max")).reset_index()
        band = band[band["hours"] >= 30]
        fig = go.Figure()
        fig.add_bar(x=band["temp_band"].astype(str), y=band["avg"], name="Average", marker_color=BLUE,
                    customdata=band["hours"], hovertemplate="%{x}<br>Average %{y:.1f} GW<br>%{customdata:,} h"
                                                            "<extra></extra>")
        fig.add_scatter(x=band["temp_band"].astype(str), y=band["peak"], name="Peak", mode="lines+markers",
                        line=dict(color=ORANGE, width=2), hovertemplate="%{x}<br>Peak %{y:.1f} GW<extra></extra>")
        fig.update_layout(title="Demand by temperature band (bands with ≥ 30 h)", yaxis_title="GW")
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(style(fig, 430), width="stretch")
    if len(band):
        lo_b = band.loc[band["avg"].idxmin()]
        hi_b = band.loc[band["avg"].idxmax()]
        st.info(f"**Insight:** in the selected data, demand is lowest at **{lo_b['temp_band']}** "
                f"({lo_b['avg']:.1f} GW on average) and highest at **{hi_b['temp_band']}** ({hi_b['avg']:.1f} GW). "
                "Both heating in cold weather and air conditioning in hot weather push demand up, giving a U-shape.")

# ---- Daily & weekly patterns ---------------------------------------------------------
with tab_time:
    c1, c2 = st.columns(2)
    with c1:
        prof = df.groupby(["season", "hour"], as_index=False)["demand_gw"].mean()
        fig = px.line(prof, x="hour", y="demand_gw", color="season", color_discrete_map=SEASON_COLORS,
                      category_orders={"season": SEASONS},
                      labels={"hour": "Hour of day", "demand_gw": "Average demand (GW)", "season": "Season"})
        fig.update_traces(line=dict(width=2), hovertemplate="%{x}:00<br>%{y:.1f} GW<extra></extra>")
        fig.update_layout(title="Average demand by hour of day", hovermode="x unified")
        fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)])
        st.plotly_chart(style(fig, 380), width="stretch")
    with c2:
        wd = df.groupby("weekday")["demand_gw"].mean().reindex(DAYS).dropna()
        fig = go.Figure(go.Bar(x=[d[:3] for d in wd.index], y=wd.values,
                               marker_color=[ORANGE if d in ("Saturday", "Sunday") else BLUE for d in wd.index],
                               hovertemplate="%{x}<br>%{y:.1f} GW<extra></extra>"))
        fig.update_layout(title="Average demand by day of week (orange: weekend)", yaxis_title="GW")
        st.plotly_chart(style(fig, 380, legend=False), width="stretch")

    heat = df.pivot_table(index="hour", columns="month", values="demand_gw", aggfunc="mean")
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=[MONTHS[m - 1] for m in heat.columns], y=[f"{h:02d}:00" for h in heat.index],
        colorscale=[[0, "#cde2fb"], [0.5, BLUE], [1, "#0d366b"]], colorbar=dict(title="GW"),
        hovertemplate="%{x} %{y}<br>%{z:.1f} GW<extra></extra>", xgap=1, ygap=1))
    fig.update_layout(title="Average demand: hour of day × month")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 520, legend=False), width="stretch")

# ---- Solar & supply ------------------------------------------------------------------
with tab_solar:
    c1, c2 = st.columns(2)
    with c1:
        sp = df.groupby("hour")[["demand_gw", "net_demand_gw", "solar_gw"]].mean().reset_index()
        fig = go.Figure()
        fig.add_scatter(x=sp["hour"], y=sp["demand_gw"], name="Total demand", line=dict(color=BLUE, width=2),
                        hovertemplate="%{x}:00 total %{y:.1f} GW<extra></extra>")
        fig.add_scatter(x=sp["hour"], y=sp["net_demand_gw"], name="Demand minus solar", fill="tonexty",
                        fillcolor="rgba(235,104,52,0.12)", line=dict(color=ORANGE, width=2),
                        hovertemplate="%{x}:00 minus solar %{y:.1f} GW<extra></extra>")
        fig.update_layout(title="How solar changes the daily demand curve", yaxis_title="Average GW",
                          xaxis_title="Hour of day", hovermode="x unified")
        fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)])
        st.plotly_chart(style(fig, 380), width="stretch")
        noon = sp.set_index("hour").loc[12]
        st.caption(f"At 12:00 solar covers on average {noon['solar_gw']:.1f} GW, "
                   f"{noon['solar_gw'] / noon['demand_gw'] * 100:.0f} % of demand in the selected hours.")
    with c2:
        fig = px.histogram(df, x="usage_rate_pct", nbins=40, color_discrete_sequence=[BLUE],
                           labels={"usage_rate_pct": "Usage rate (demand ÷ supply capacity, %)"})
        fig.add_vline(x=95, line_dash="dash", line_color=ORANGE,
                      annotation_text="95 %: tight", annotation_font_color=ORANGE)
        fig.update_traces(hovertemplate="%{x} %<br>%{y:,} hours<extra></extra>")
        fig.update_layout(title="How close demand came to supply capacity", yaxis_title="Hours")
        st.plotly_chart(style(fig, 380, legend=False), width="stretch")
        st.caption(f"{int((df['usage_rate_pct'] >= 95).sum()):,} hours at 95 % usage or more in the selection.")

    fc = df.groupby("season", observed=True)["forecast_error_pct"].mean().reindex(SEASONS).dropna()
    fig = go.Figure(go.Bar(x=fc.index, y=fc.values, marker_color=[SEASON_COLORS[s] for s in fc.index],
                           hovertemplate="%{x}<br>%{y:.2f} % average error<extra></extra>"))
    fig.update_layout(title="TEPCO forecast accuracy: mean absolute error by season", yaxis_title="%")
    st.plotly_chart(style(fig, 320, legend=False), width="stretch")

# ---- Data tables ---------------------------------------------------------------------
with tab_data:
    cols = {"datetime": "Date & hour", "demand_gw": "Demand (GW)", "temp_tokyo_c": "Tokyo temp (°C)",
            "usage_rate_pct": "Usage rate (%)", "solar_gw": "Solar (GW)", "day_type": "Day type"}
    def table_view(sub):
        out = sub[list(cols)].copy()
        out["datetime"] = out["datetime"].dt.strftime("%Y-%m-%d %H:00")
        out["solar_gw"] = out["solar_gw"].round(2)
        out["temp_tokyo_c"] = out["temp_tokyo_c"].round(1)
        return out.rename(columns=cols)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**10 highest-demand hours**")
        st.dataframe(table_view(df.nlargest(10, "demand_gw")), hide_index=True,
                     width="stretch")
    with c2:
        st.markdown("**10 lowest-demand hours**")
        st.dataframe(table_view(df.nsmallest(10, "demand_gw")), hide_index=True,
                     width="stretch")
    st.markdown("**Monthly summary**")
    summary = df.set_index("datetime").resample("MS").agg(
        avg_demand_gw=("demand_gw", "mean"), peak_demand_gw=("demand_gw", "max"),
        min_demand_gw=("demand_gw", "min"), avg_temp_c=("temp_tokyo_c", "mean"),
        max_temp_c=("temp_tokyo_c", "max"), max_solar_gw=("solar_gw", "max")).dropna().round(2)
    summary.index = summary.index.strftime("%Y-%m")
    st.dataframe(summary, width="stretch", height=320)
    st.download_button("⬇️ Download the filtered hourly data (CSV)",
                       df.drop(columns=["date"]).to_csv(index=False).encode("utf-8"),
                       file_name="tokyo_demand_filtered.csv", mime="text/csv")

# --------------------------------------------------------------------------------------
with st.expander("📌 Key findings from the full dataset"):
    st.markdown(
        "- **Summer sets the record:** all 10 highest-demand hours were on 2–3 Aug 2022, peaking at 59.3 GW "
        "with Tokyo at about 35 °C.\n"
        "- **U-shaped temperature effect:** demand is lowest at about 16–20 °C and rises with both cold and heat; "
        "each degree of heat adds more demand than each degree of cold.\n"
        "- **Calendar effect:** workdays average about 4 GW more than weekends and holidays; Golden Week has the "
        "lowest demand of the year.\n"
        "- **Peak hours shift with the season:** summer peaks in the early afternoon, winter in the morning and "
        "evening.\n"
        "- **Solar reshapes the day:** at noon solar covers about a third of spring demand, so the demand left for "
        "other power plants is lowest at midday and peaks after sunset.")
