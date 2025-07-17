import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import yfinance as yf
import numpy as np
from datetime import datetime

# --- CONFIGURATION ---
TICKERS = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'AVGO', 'META', 'NFLX', 'AMZN', 'TSLA', 'AMD']
INDEX_NAME = "AnsCom AI10 Index"
INDEX_BASE_VALUE = 1000
UPDATE_INTERVAL_MS = 15000  # Update every 15 seconds
MAX_DATAPOINTS = 300       # Keep only the last 300 data points to stay lightweight

# --- DATA STORAGE & INITIALIZATION ---
data_store = {
    'shares_outstanding': {},
    'base_market_cap': 0,
    'prev_close': {},
    'last_price': {},
    'text_artists': {}
}
index_values = []
timestamps = []

def initialize_index():
    """Fetches initial data once to set up the index base."""
    print("Initializing AnsCom AI10 Index...")
    total_base_cap = 0
    tickers_str = " ".join(TICKERS)
    
    # Use '5d' to ensure we get a valid previous close even after weekends/holidays
    hist_data = yf.download(tickers_str, period="5d", interval="1d", progress=False)
    if hist_data.empty or len(hist_data) < 2:
        raise ConnectionError("Could not download initial historical data. Check connection.")
        
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            shares = stock.info.get('sharesOutstanding')
            if not shares:
                print(f"Warning: Estimating shares outstanding for {ticker}.")
                shares = stock.info.get('marketCap', 0) / stock.info.get('previousClose', 1)
                
            prev_close_price = hist_data['Close'][ticker].iloc[-2]
            
            data_store['shares_outstanding'][ticker] = shares
            data_store['prev_close'][ticker] = prev_close_price
            data_store['last_price'][ticker] = prev_close_price
            
            total_base_cap += shares * prev_close_price
            print(f"  - Initialized {ticker}: Prev Close ${prev_close_price:,.2f}")
            
        except Exception as e:
            print(f"Could not initialize {ticker}: {e}. It will be excluded.")
            TICKERS.remove(ticker)
            
    data_store['base_market_cap'] = total_base_cap
    if data_store['base_market_cap'] == 0:
        raise ValueError("Base market cap is zero. Cannot start index.")
    print(f"\nBase Market Cap for Index: ${total_base_cap:,.2f}\nInitialization Complete.")

# --- THEME & STYLING ---
plot_bgcolor = '#121212'; axes_color = '#181818'; line_color_index = '#00A2FF'
text_color_primary = '#E0E0E0'; text_color_secondary = '#888888'; grid_color = '#333333'
accent_color_green = '#44D400'; accent_color_red = '#FF3B30'; accent_color_neutral = '#AAAAAA'

plt.rcParams.update({
    'axes.facecolor': axes_color, 'figure.facecolor': plot_bgcolor, 'axes.edgecolor': grid_color,
    'axes.labelcolor': text_color_secondary, 'xtick.color': text_color_secondary,
    'ytick.color': text_color_secondary, 'grid.color': grid_color, 'text.color': text_color_primary,
    'font.family': ['Consolas', 'Courier New', 'monospace']
})

# --- FIGURE AND AXES SETUP ---
fig, ax = plt.subplots(figsize=(16, 9))
line, = ax.plot([], [], color=line_color_index, linewidth=2.5)
ax.set_title(INDEX_NAME, fontsize=24, color=text_color_primary, weight='bold', pad=35)
ax.set_xlabel("Time", fontsize=12, color=text_color_secondary); ax.set_ylabel("Index Value", fontsize=12, color=text_color_secondary)
ax.grid(True, linestyle='--', color=grid_color, alpha=0.6)

y_pos = 0.80
for i, ticker in enumerate(TICKERS):
    y = y_pos - (i * 0.055)
    ticker_label = ax.text(1.02, y, f"{ticker}:", transform=ax.transAxes, fontsize=11, weight='bold', va='top', ha='left', color=text_color_primary)
    price_text = ax.text(1.07, y, '', transform=ax.transAxes, fontsize=11, weight='bold', va='top', ha='left')
    pct_text = ax.text(1.15, y, '', transform=ax.transAxes, fontsize=11, weight='bold', va='top', ha='left')
    data_store['text_artists'][ticker] = (ticker_label, price_text, pct_text)

# --- UPDATE FUNCTION ---
def update(frame):
    global index_values, timestamps
    try:
        # --- ROBUST DATA FETCHING WITH FALLBACK ---
        try:
            # 1. First, try to get live, 1-minute data
            live_data = yf.download(tickers=" ".join(TICKERS), period="2m", interval="1m", progress=False)
            if live_data.empty:
                raise ValueError("Live data feed returned empty, likely market closed.")
        except (Exception) as e:
            # 2. If it fails, print a warning and fallback to the last daily price
            if frame < 2: print(f"Warning: Live 1-min data not available (market may be closed). Fetching last known price.")
            live_data = yf.download(tickers=" ".join(TICKERS), period="1d", interval="1d", progress=False)

        if live_data.empty: return # If even the fallback fails, skip this update
            
        latest_prices = live_data['Close'].iloc[-1]
        
        current_total_cap = sum(data_store['shares_outstanding'][t] * latest_prices[t] for t in TICKERS if t in latest_prices)
        current_index_value = INDEX_BASE_VALUE * (current_total_cap / data_store['base_market_cap'])
        
        index_values.append(current_index_value)
        timestamps.append(datetime.now().strftime("%H:%M:%S"))
        if len(index_values) > MAX_DATAPOINTS:
            index_values, timestamps = index_values[-MAX_DATAPOINTS:], timestamps[-MAX_DATAPOINTS:]
        
        line.set_data(np.arange(len(index_values)), index_values)
        ax.set_xlim(0, max(len(index_values) - 1, 1))
        if len(index_values) > 1:
            min_val, max_val = min(index_values), max(index_values)
            padding = (max_val - min_val) * 0.1 + 0.01
            ax.set_ylim(min_val - padding, max_val + padding)
        
        # --- UPDATE SIDEBAR TEXTS WITH DUAL-COLOR LOGIC ---
        for ticker in TICKERS:
            if ticker not in latest_prices: continue
            price = latest_prices[ticker]
            daily_change_pct = ((price - data_store['prev_close'][ticker]) / data_store['prev_close'][ticker]) * 100
            daily_color = accent_color_green if daily_change_pct >= 0 else accent_color_red
            
            if price > data_store['last_price'][ticker]: tick_color = accent_color_green
            elif price < data_store['last_price'][ticker]: tick_color = accent_color_red
            else: tick_color = accent_color_neutral
            
            _, price_artist, pct_artist = data_store['text_artists'][ticker]
            price_artist.set_text(f"${price:>7.2f}"); price_artist.set_color(tick_color)
            pct_artist.set_text(f"({daily_change_pct:+.2f}%)"); pct_artist.set_color(daily_color)
            
            data_store['last_price'][ticker] = price

    except Exception as e:
        print(f"An error occurred during update: {e}")

# --- RUN THE APPLICATION ---
try:
    initialize_index()
    plt.tight_layout(rect=[0.02, 0.05, 0.8, 0.93]) 
    
    # Use blit=False for reliability and save_count to suppress the warning
    ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False, save_count=50)
    
    plt.show()

except (Exception, KeyboardInterrupt) as e:
    print(f"\nProgram stopped. Reason: {e}")