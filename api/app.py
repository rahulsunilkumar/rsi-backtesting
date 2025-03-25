from flask import Flask, render_template, request
import random
import plotly.graph_objects as go
from plotly.offline import plot

app = Flask(__name__, template_folder="templates")

# Define tickers and simulation length
TICKERS = ["VTI", "QQQ", "VT", "DIA", "SPY"]
NUM_DAYS = 200

def fetch_dummy_data(ticker):
    """Generate a dummy price series with a random walk for a given ticker."""
    data = []
    base = 100 + random.random() * 50  # random starting base price
    for _ in range(NUM_DAYS):
        base = base * (1 + (random.random() - 0.5) * 0.02)
        data.append(base)
    return data

def compute_rsi(close_array):
    """Compute a simple RSI for a given array of close prices."""
    up = 0.0
    down = 0.0
    for i in range(1, len(close_array)):
        diff = close_array[i] - close_array[i-1]
        if diff >= 0:
            up += diff
        else:
            down += abs(diff)
    if down == 0:
        return 100.0
    return 100 - 100 / (1 + up / down)

def compute_rsi_window(dataset, tickers, window):
    """Compute RSI for each ticker over a moving window."""
    result = {}
    for tick in tickers:
        result[tick] = []
        n = len(dataset[tick])
        for i in range(window, n + 1):
            slice_prices = dataset[tick][i - window:i]
            rsi_value = compute_rsi(slice_prices)
            result[tick].append(rsi_value)
    return result

def run_strategy(dataset, tickers, window_size, tx_fee, interest_rate, weight_per_stock):
    """
    Run the trading strategy:
      - Close short positions when RSI < 33,
      - Enter short when RSI > 66,
      - Close long positions when RSI > 66,
      - Enter long when RSI < 33.
    """
    balance = 100000.0
    cRor = 1.0
    positions = {tick: 'neutral' for tick in tickers}
    entry_price = {tick: None for tick in tickers}
    volume = {tick: 0.0 for tick in tickers}

    # Precompute RSI arrays for each ticker.
    rsi_data = compute_rsi_window(dataset, tickers, window_size)
    n = len(dataset[tickers[0]])
    
    # Iterate over days (starting at index = window_size)
    for t in range(window_size, n):
        for tick in tickers:
            rsi_index = t - window_size
            the_rsi = rsi_data[tick][rsi_index]
            current_price = dataset[tick][t]

            # CLOSE SHORT: if currently short and RSI drops below 33, close short then open long
            if the_rsi < 33 and positions[tick] == 'short':
                positions[tick] = 'neutral'
                balance = balance \
                    + entry_price[tick] * (1 - tx_fee) * volume[tick] \
                    - current_price * (1 + tx_fee) * volume[tick] \
                    - (interest_rate * entry_price[tick] * volume[tick])
                rate_of_return = ((entry_price[tick]*(1 - tx_fee)) / (current_price*(1 + tx_fee))) - 1.0 - interest_rate
                cRor *= (1 + rate_of_return)
            
            # ENTER SHORT: if neutral and RSI > 66, open a short position
            if the_rsi > 66 and positions[tick] == 'neutral':
                positions[tick] = 'short'
                entry_price[tick] = current_price
                volume[tick] = (balance * weight_per_stock) / current_price

            # CLOSE LONG: if currently long and RSI > 66, close the long position
            if the_rsi > 66 and positions[tick] == 'long':
                positions[tick] = 'neutral'
                balance = balance \
                    + (current_price * volume[tick]) * (1 - tx_fee) \
                    - (entry_price[tick] * volume[tick]) * (1 + tx_fee)
                rate_of_return = (current_price*(1 - tx_fee)) / (entry_price[tick]*(1 + tx_fee)) - 1.0
                cRor *= (1 + rate_of_return)
            
            # ENTER LONG: if neutral and RSI < 33, open a long position
            if the_rsi < 33 and positions[tick] == 'neutral':
                positions[tick] = 'long'
                entry_price[tick] = current_price
                volume[tick] = (balance * weight_per_stock) / current_price

    final_return = cRor - 1
    return balance, final_return, rsi_data

@app.route("/", methods=["GET", "POST"])
def index():
    # Retrieve parameters from the request (or use defaults)
    window_size = int(request.values.get("windowSize", 50))
    tx_fee = float(request.values.get("fee", 0.005))
    interest_rate = float(request.values.get("interest", 0.03))
    weight_per_stock = float(request.values.get("weight", 0.05))

    # Generate dummy dataset for each ticker
    TICKERS = ["VTI", "QQQ", "VT", "DIA", "SPY"]
    NUM_DAYS = 200
    dataset = {tick: fetch_dummy_data(tick) for tick in TICKERS}

    # Run the RSI trading strategy simulation
    final_balance, final_return, rsi_data = run_strategy(
        dataset, TICKERS, window_size, tx_fee, interest_rate, weight_per_stock
    )

    # Prepare an interactive RSI plot using Plotly
    traces = []
    x_values = list(range(window_size, NUM_DAYS + 1))
    for tick in TICKERS:
        traces.append(go.Scatter(x=x_values, y=rsi_data[tick], mode='lines', name=tick))
    layout = go.Layout(
        title="RSI Over Time",
        xaxis=dict(title="Day Index"),
        yaxis=dict(title="RSI (0-100)"),
        margin=dict(l=50, r=20, t=30, b=40)
    )
    fig = go.Figure(data=traces, layout=layout)
    plot_div = plot(fig, output_type="div", include_plotlyjs="cdn")

    # Render the HTML template with our plot and results
    return render_template(
        "index.html",
        plot_div=plot_div,
        final_balance=f"${final_balance:,.2f}",
        final_return=f"{final_return * 100:.2f}%",
        window_size=window_size,
        fee=tx_fee,
        interest=interest_rate,
        weight=weight_per_stock
    )

# Make sure Vercel can find the 'app' object
if __name__ == "__main__":
    app.run(debug=True)
