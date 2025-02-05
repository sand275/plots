import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime as dt
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# Settings & Ticker Mapping
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
}

# Define groups
groups = {
    "Majors": ['sx5e', 'es', 'ftse'],
    "Europe": [k for k in yfinance_tickers.keys() if k not in ['es', 'nq']],
    "US": ['es', 'nq']
}

# Fixed colors for specific tickers:
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
    
    - For lookback_days == 0:
      Downloads 2-day 1-minute data, converts to Europe/London,
      determines the reference price from yesterday at 16:30 UK time,
      and filters to today's data from 8:00am onward.
      
    - For lookback_days >= 1:
      Downloads (lookback_days+1) days of daily data,
      localizes to Europe/London, and returns df (ref_price will be computed later).
    """
    if lookback_days == 0:
        # Download 2-day intraday data (1-minute)
        df_all = yf.download(ticker, period="2d", interval="1m", progress=False)
        if df_all.empty:
            return None, None
        df_all.index = pd.to_datetime(df_all.index)
        # Convert to UK time
        df_all = df_all.tz_convert("Europe/London")
        now_uk = dt.datetime.now(ZoneInfo("Europe/London"))
        yesterday_date = now_uk.date() - dt.timedelta(days=1)
        ref_dt = dt.datetime.combine(yesterday_date, dt.time(16, 30, tzinfo=ZoneInfo("Europe/London")))
        # Get yesterday's data and choose the first price at or after 16:30
        df_yesterday = df_all[df_all.index.date == yesterday_date]
        if not df_yesterday.empty:
            df_yesterday_after = df_yesterday[df_yesterday.index >= ref_dt]
            if not df_yesterday_after.empty:
                ref_price = df_yesterday_after['Close'].iloc[0]
            else:
                ref_price = df_yesterday['Close'].iloc[-1]
        else:
            ref_price = df_all['Close'].iloc[0]
        # Filter for today's data starting from 8:00am UK time
        today_date = now_uk.date()
        start_today = dt.datetime.combine(today_date, dt.time(8, 0, tzinfo=ZoneInfo("Europe/London")))
        df_today = df_all[df_all.index >= start_today]
        return df_today, ref_price
    else:
        # Download daily data for lookback_days+1 days
        df = yf.download(ticker, period=f"{lookback_days+1}d", interval="1d", progress=False)
        if df.empty:
            return None, None
        df.index = pd.to_datetime(df.index)
        # Localize daily data to Europe/London
        df = df.tz_localize(ZoneInfo("Europe/London"))
        return df, None

def compute_pct_change(df, lookback_days, ref_price=None):
    """
    Computes percentage change relative to the reference price.
    
    - For lookback_days == 0 (intraday):
      Uses the provided ref_price (from yesterday at 16:30).
      
    - For daily data (lookback_days >= 1):
      Uses the first day's Close so that the first point is 0%.
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
st.set_page_config(page_title="Percentage Change Analysis", layout="wide")
st.title("Percentage Change Analysis")
st.markdown(
    "<span title='For intraday (0-day lookback) the chart starts at 8:00am today and the reference price is taken from 16:30 yesterday. For multi-day lookbacks, daily data is used and the first day’s close is the baseline (0%).'>ℹ️ Hover for info.</span>",
    unsafe_allow_html=True,
)

# Auto-refresh every 60 seconds.
_ = st_autorefresh(interval=60 * 1000, limit=None, key="fizzbuzz")

# ----------------------------
# Sidebar Controls
# ----------------------------
mode = st.sidebar.radio("Select Mode", ("Group mode", "Individual mode"))
# Slider: 0 (today only) to 10 days; default 0.
lookback_days = st.sidebar.slider("Lookback Period (days)", min_value=0, max_value=10, value=0, step=1)

selected_tickers = []
if mode == "Group mode":
    # Default group: "Majors"
    selected_groups = st.sidebar.multiselect("Select Groups", options=list(groups.keys()), default=["Majors"])
    for grp in selected_groups:
        selected_tickers.extend(groups[grp])
    selected_tickers = list(set(selected_tickers))
else:
    options = list(yfinance_tickers.keys())
    selected_tickers = st.sidebar.multiselect("Select Indices", options=options)

if not selected_tickers:
    st.warning("Please select at least one index to plot.")
    st.stop()

# ----------------------------
# Build Plotly Figure
# ----------------------------
fig = go.Figure()
current_values = {}
stale_tickers = []

# Loop over selected tickers
for key in selected_tickers:
    yf_ticker = yfinance_tickers[key]
    # Fetch data and (for 0-day) the reference price
    df, ref_price = fetch_data(yf_ticker, lookback_days)
    if df is None or df.empty:
        st.error(f"No data for {key.upper()} ({yf_ticker})")
        continue
    df, used_ref = compute_pct_change(df, lookback_days, ref_price)
    color = fixed_colors.get(key, None)
    
    # For daily data, show lines with markers; for intraday, use lines only.
    mode_trace = "lines+markers" if lookback_days > 0 else "lines"
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['PctChange'],
        mode=mode_trace,
        name=key.upper(),
        line=dict(color=color) if color else None,
    ))
    
    # Store current level and get the last data point.
    current_value = float(df['Close'].iloc[-1])
    current_values[key.upper()] = current_value
    last_time = df.index[-1]
    last_pct = df['PctChange'].iloc[-1]
    
    # Add an arrow annotation at the last data point.
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
    
    # Check for stale data (>30 minutes old)
    now_uk = dt.datetime.now(ZoneInfo("Europe/London"))
    if (now_uk - last_time).total_seconds() > 1800:
        stale_tickers.append(key.upper())

# Set x-axis lower bound for 0-day: force start at 8:00am today.
if lookback_days == 0:
    today_uk = dt.datetime.now(ZoneInfo("Europe/London")).date()
    start_bound = dt.datetime.combine(today_uk, dt.time(8, 0, tzinfo=ZoneInfo("Europe/London")))
    fig.update_xaxes(range=[start_bound, None])
else:
    # For multi-day, update tick format to show date and time.
    fig.update_xaxes(tickformat="%d %b<br>%H:%M")

fig.update_layout(
    title=dict(text="Percentage Change from Reference Price", font=dict(size=20)),
    xaxis_title="Time (UK)",
    yaxis_title="Percentage Change (%)",
    legend_title="Ticker",
    height=600,  # Reduced height for less tall chart
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
