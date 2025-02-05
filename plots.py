import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import datetime as dt
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
    'es': '^GSPC',         # S&P 500
    'nq': '^NDX',          # Nasdaq 100
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
    'ftse': 'gold',   # yellow-like
    'es': 'cyan'
}

# ----------------------------
# Utility Functions
# ----------------------------
def get_reference_time():
    # Reference is 4:30 PM yesterday.
    today = dt.datetime.now().date()
    yesterday = today - dt.timedelta(days=1)
    return dt.datetime.combine(yesterday, dt.time(16, 30))

def fetch_intraday_data(ticker, ref_time):
    # Use yfinance to get intraday data for the past day (1m interval)
    # Download data for today + yesterday so we can get the reference point.
    start_dt = ref_time.date() - dt.timedelta(days=0)
    end_dt = dt.datetime.now()
    # yfinance expects period or start/end; here we use period='2d'
    try:
        df = yf.download(ticker, period="2d", interval="1m", progress=False)
        if df.empty:
            return None
        # Ensure the index is in datetime
        df.index = pd.to_datetime(df.index)
        # Filter to data from ref_time onward
        df = df[df.index >= ref_time]
        return df
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return None

def compute_pct_change(df, ref_time):
    # Get the price at ref_time (closest available)
    try:
        ref_price = df.loc[df.index >= ref_time]['Close'].iloc[0]
    except IndexError:
        ref_price = df['Close'].iloc[0]
    # Compute percentage change
    df['PctChange'] = (df['Close'] - ref_price) / ref_price * 100
    return df, ref_price

def annotate_current_value(ax, x, y, label, color):
    ax.annotate(f"{label}\n{y:.2f}",
                xy=(1.02, y), xycoords=('axes fraction', 'data'),
                color=color, fontsize=10, fontweight='bold',
                va='center')

# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="Intraday Percentage Change", layout="wide")
st.title("Intraday Percentage Change (Since 4:30pm Yesterday)")

# Auto refresh every 60 seconds
count = st_autorefresh(interval=60 * 1000, limit=None, key="fizzbuzz")

# Sidebar for mode selection
mode = st.sidebar.radio("Select Mode", ("Group mode", "Individual mode"))

selected_tickers = []
if mode == "Group mode":
    selected_groups = st.sidebar.multiselect("Select Groups", options=list(groups.keys()))
    # If a group is selected, all tickers in that group will be used
    for grp in selected_groups:
        selected_tickers.extend(groups[grp])
    selected_tickers = list(set(selected_tickers))
else:
    # Individual mode: allow selection from all tickers
    options = list(yfinance_tickers.keys())
    selected_tickers = st.sidebar.multiselect("Select Indices", options=options)

if not selected_tickers:
    st.warning("Please select at least one index to plot.")
    st.stop()

# Reference time is 4:30pm yesterday
ref_time = get_reference_time()

# Dictionary to hold current values and last update times
current_values = {}
st.write(f"**Last update:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Create a matplotlib figure with dark background
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(12, 6))

# To collect stale indices (if last timestamp is >30 minutes old)
stale_indices = []

# Plot each selected ticker
for key in selected_tickers:
    yf_ticker = yfinance_tickers[key]
    df = fetch_intraday_data(yf_ticker, ref_time)
    if df is None or df.empty:
        st.error(f"No data for {key.upper()} ({yf_ticker})")
        continue
    df, ref_price = compute_pct_change(df, ref_time)
    # Use fixed color if available, else use default (cycle)
    color = fixed_colors.get(key, None)
    line, = ax.plot(df.index, df['PctChange'], label=key.upper(), color=color, linewidth=2)
    # Record current (last) value
    current_value = df['Close'].iloc[-1]
    current_values[key.upper()] = current_value
    # Check if data is stale (last timestamp more than 30 minutes ago)
    last_timestamp = df.index[-1]
    if (dt.datetime.now() - last_timestamp).total_seconds() > 1800:
        stale_indices.append(key.upper())

    # Annotate current value on the right side (using ax.text)
    annotate_current_value(ax, 1, df['PctChange'].iloc[-1], key.upper(), color if color else line.get_color())

# Formatting the plot
ax.set_title("Percentage Price Change Since 4:30pm Yesterday")
ax.set_xlabel("Time")
ax.set_ylabel("Percentage Change (%)")
ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0.)
plt.tight_layout()

st.pyplot(fig)

# Display current values in a sidebar tag
st.sidebar.markdown("### Current Values")
for label, value in current_values.items():
    st.sidebar.write(f"**{label}:** {value:.2f}")

# If any stale indices, show a warning
if stale_indices:
    st.warning(f"Data for {', '.join(stale_indices)} may be stale (last update > 30 minutes ago).")

# Display update timestamp at bottom
st.markdown(f"<div style='text-align: right; font-size: 12px;'>Last updated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
