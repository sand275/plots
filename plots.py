import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime as dt
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# Ticker Mapping (updated)
# ----------------------------
yfinance_tickers = {
    'aex': '^AEX',         # AEX index
    'banks': '^SX7E',      # European banks sector
    'cac': '^FCHI',        # CAC 40
    'dax': '^GDAXI',       # DAX
    'ftse': '^FTSE',       # FTSE 100
    'mib': '^FTSEMIB.MI',  # FTSE MIB
    'smi': '^SSMI',        # SMI
    'sx5e': '^STOXX50E',   # Euro STOXX 50
    'es': 'ES=F',         # S&P 500
    'nq': 'NQ=F',         # Nasdaq 100
    'nky': '^N225'        # Nikkei 225
}

# ----------------------------
# Explicit Group Definitions
# ----------------------------
groups = {
    "All": list(yfinance_tickers.keys()),
    "Majors": ['sx5e', 'es', 'ftse'],  # nky removed from Majors
    "Europe": ['aex', 'banks', 'cac', 'dax', 'ftse', 'mib', 'smi', 'sx5e'],
    "US": ['es', 'nq']
}

# Colors for selected tickers (if available)
fixed_colors = {
    'sx5e': 'darkblue',
    'ftse': 'gold',
    'es': 'cyan'
}

# ----------------------------
# Utility Functions
# ----------------------------
def fetch_data(ticker, lookback_days):
    """
    Returns a tuple (df, ref_price) for a given ticker and lookback period.
    
    - For lookback_days == 0 (intraday):
      Downloads 2-day 1-minute data, converts to Europe/London,
      determines the reference price from yesterday at 16:30 UK time,
      and filters to today's data from 8:00am onward.
      
    - For lookback_days >= 1 (daily):
      Downloads (lookback_days+1) days of daily data,
      localizes the index to Europe/London.
    """
    if lookback_days == 0:
        df_all = yf.download(ticker, period="2d", interval="1m", progress=False)
        if df_all.empty:
            return None, None
        df_all.index = pd.to_datetime(df_all.index)
        df_all = df_all.tz_convert("Europe/London")
        now_uk = dt.datetime.now(ZoneInfo("Europe/London"))
        yesterday_date = now_uk.date() - dt.timedelta(days=1)
        ref_dt = dt.datetime.combine(yesterday_date, dt.time(16, 30, tzinfo=ZoneInfo("Europe/London")))
        df_yesterday = df_all[df_all.index.date == yesterday_date]
        if not df_yesterday.empty:
            df_yesterday_after = df_yesterday[df_yesterday.index >= ref_dt]
            if not df_yesterday_after.empty:
                ref_price = df_yesterday_after['Close'].iloc[0]
            else:
                ref_price = df_yesterday['Close'].iloc[-1]
        else:
            ref_price = df_all['Close'].iloc[0]
        today_date = now_uk.date()
        start_today = dt.datetime.combine(today_date, dt.time(8, 0, tzinfo=ZoneInfo("Europe/London")))
        df_today = df_all[df_all.index >= start_today]
        return df_today, ref_price
    else:
        df = yf.download(ticker, period=f"{lookback_days+1}d", interval="1d", progress=False)
        if df.empty:
            return None, None
        df.index = pd.to_datetime(df.index)
        df = df.tz_localize(ZoneInfo("Europe/London"))
        return df, None

def compute_pct_change(df, lookback_days, ref_price=None):
    """
    Computes percentage change relative to the reference price.
    
    - For intraday (lookback_days == 0): Uses the provided ref_price (from yesterday 16:30).
    - For daily data (lookback_days >= 1): Uses the first day's Close as the baseline (0% change).
    """
    if lookback_days == 0:
        base = ref_price
        df['PctChange'] = (df['Close'] - base) / base * 100
        return df, base
    else:
        base = df['Close'].iloc[0]
        df['PctChange'] = (df['Close'] - base) / base * 100
        return df, base

# ----------------------------
# Streamlit App Setup
# ----------------------------
st.set_page_config(page_title="Pct Change Plots (yfinance)", layout="wide")
st.title("Pct Change Plots")
st.markdown(
    "<span title='Intraday: Chart starts at 8am today; ref price from 16:30 yesterday. Multi-day: First day’s close is baseline.'>ℹ️</span>",
    unsafe_allow_html=True,
)

# Manual refresh button on front page
if st.button("Refresh Data"):
    try:
        st.experimental_rerun()
    except AttributeError:
        pass

_ = st_autorefresh(interval=60 * 1000, limit=None, key="fizzbuzz")

# ----------------------------
# Sidebar Controls – Mode Selection
# ----------------------------
mode = st.sidebar.radio("Select Mode", ("Group mode", "Individual mode", "Single Stocks Mode"))
lookback_days = st.sidebar.slider("Lookback Period (days)", min_value=0, max_value=10, value=0, step=1)

if mode == "Group mode":
    selected_group = st.sidebar.pills(
        "Select Group",
        options=list(groups.keys()),
        selection_mode="single",
        default="Majors",
        help="Select one of the predefined groups."
    )
    selected_tickers = groups[selected_group]
elif mode == "Individual mode":
    options = list(yfinance_tickers.keys())
    selected_tickers = st.sidebar.multiselect("Select Indices", options=options)
elif mode == "Single Stocks Mode":
    default_single = {
        "Apple": "AAPL",
        "Nvidia": "NVDA",
        "Tesla": "TSLA",
        "Alphabet": "GOOGL",
        "Meta": "META",
        "Novo Nordisk": "NVO",
        "MicroStrategy": "MSTR"
    }
    selected_single = st.sidebar.multiselect("Select Single Stocks", options=list(default_single.keys()))
    custom_stocks = st.sidebar.text_input("Or add additional tickers (comma-separated)")
    selected_single_tickers = []
    for stock in selected_single:
        selected_single_tickers.append(default_single[stock])
    if custom_stocks:
        custom_list = [s.strip() for s in custom_stocks.split(",") if s.strip()]
        selected_single_tickers.extend(custom_list)
    if not selected_single_tickers:
        selected_single_tickers = ["es"]
    else:
        if "es" not in selected_single_tickers:
            selected_single_tickers = ["es"] + selected_single_tickers
    selected_tickers = selected_single_tickers

if not selected_tickers:
    st.warning("Please select at least one ticker to plot.")
    st.stop()

# ----------------------------
# Build Plotly Figure
# ----------------------------
fig = go.Figure()
current_values = {}
stale_tickers = []

for key in selected_tickers:
    if mode != "Single Stocks Mode":
        yf_ticker = yfinance_tickers[key]
    else:
        yf_ticker = yfinance_tickers.get(key, key)
    df, ref_price = fetch_data(yf_ticker, lookback_days)
    if df is None or df.empty:
        st.error(f"No data for {key.upper()} ({yf_ticker})")
        continue
    df, used_ref = compute_pct_change(df, lookback_days, ref_price)
    color = fixed_colors.get(key, None)
    
    # In Single Stocks Mode, make ES line stand out using dashed style and thicker width.
    if mode == "Single Stocks Mode" and key.lower() == "es":
        line_style = dict(color=color if color else "cyan", dash="dash", width=4)
    else:
        line_style = dict(color=color) if color else None

    mode_trace = "lines+markers" if lookback_days > 0 else "lines"
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['PctChange'],
        mode=mode_trace,
        name=key.upper(),
        line=line_style,
    ))
    # Use .item() to get a Python float from the single element Series.
    current_value = df['Close'].iloc[-1].item()
    current_values[key.upper()] = current_value
    last_time = df.index[-1]
    last_pct = df['PctChange'].iloc[-1]
    fig.add_annotation(
        x=last_time,
        y=last_pct,
        xref="x",
        yref="y",
        text=f"{key.upper()}<br>{current_value:.2f}",
        showarrow=True,
        arrowhead=3,
        ax=40,
        ay=0,
        font=dict(color=color if color else "white"),
        bgcolor="black",
        opacity=0.8
    )
    now_uk = dt.datetime.now(ZoneInfo("Europe/London"))
    if (now_uk - last_time).total_seconds() > 1800:
        stale_tickers.append(key.upper())

if lookback_days == 0:
    today_uk = dt.datetime.now(ZoneInfo("Europe/London")).date()
    start_bound = dt.datetime.combine(today_uk, dt.time(8, 0, tzinfo=ZoneInfo("Europe/London")))
    fig.update_xaxes(range=[start_bound, None])
else:
    fig.update_xaxes(tickformat="%d %b<br>%H:%M")

# Update legend to appear above the chart (to avoid squishing on phones)
fig.update_layout(
    title=dict(text="Pct Change Plots (yfinance)", font=dict(size=20)),
    xaxis_title="Time (UK)",
    yaxis_title="Percentage Change (%)",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    height=600,
    width=1200,
    template="plotly_dark",
    margin=dict(l=60, r=150, t=80, b=60)
)

st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# Sidebar: Current Values & Alerts
# ----------------------------
st.sidebar.markdown("### Current Values")
for label, value in current_values.items():
    st.sidebar.write(f"**{label}:** {value:.2f}")
if stale_tickers:
    st.sidebar.warning(f"Data for {', '.join(stale_tickers)} may be stale (>30 minutes old).")
st.sidebar.markdown(f"**Last update:** {dt.datetime.now(ZoneInfo('Europe/London')).strftime('%Y-%m-%d %H:%M:%S')}")
