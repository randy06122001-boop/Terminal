import os
import re

# 1. Patch backtesting_engine.py
with open("backtesting_engine.py", "r") as f:
    bt_code = f.read()

old_bt_func = '''def run_vectorbt_backtest(ticker, start_date, end_date, fast_ma=10, slow_ma=50):
    """
    Runs a fast, vectorized backtest using vectorbt.
    Best for brute-force parameter sweeps, portfolio optimizations, and speed.
    """
    print(f"--- Running vectorbt Backtest for {ticker} ---")
    
    # 1. Fetch data
    price = yf.download(ticker, start=start_date, end=end_date)['Close']
    
    if isinstance(price, pd.DataFrame):
        price = price[ticker] # Handle multi-index yfinance output if present
        
    # 2. Compute Moving Averages
    fast_ma_line = vbt.MA.run(price, window=fast_ma)
    slow_ma_line = vbt.MA.run(price, window=slow_ma)
    
    # 3. Generate Trading Signals (Crossover)
    entries = fast_ma_line.ma_crossed_above(slow_ma_line)
    exits = fast_ma_line.ma_crossed_below(slow_ma_line)
    
    # 4. Run Portfolio Simulation
    portfolio = vbt.Portfolio.from_signals(
        price, entries, exits, init_cash=10000, fees=0.001, freq='1d'
    )
    
    # 5. Extract Key Metrics
    stats = portfolio.stats()
    print(stats)
    
    return {
        "Total Return [%]": stats.get('Total Return [%]'),
        "Sharpe Ratio": stats.get('Sharpe Ratio'),
        "Max Drawdown [%]": stats.get('Max Drawdown [%]'),
        "Win Rate [%]": stats.get('Win Rate [%]')
    }'''

new_bt_func = '''def run_vectorbt_backtest(ticker, start_date, end_date, strategy="EMA"):
    """
    Runs a fast, vectorized backtest using vectorbt.
    Takes a strategy string and executes the corresponding logic.
    """
    print(f"--- Running vectorbt Backtest for {ticker} using {strategy} ---")
    
    # 1. Fetch data
    price = yf.download(ticker, start=start_date, end=end_date)['Close']
    
    if isinstance(price, pd.DataFrame):
        price = price[ticker] # Handle multi-index yfinance output if present
        
    strategy = strategy.upper()
    strat_name = "EMA Crossover (10/50)"
    
    if strategy == 'RSI':
        rsi = vbt.RSI.run(price, window=14)
        entries = rsi.rsi_crossed_below(30)
        exits = rsi.rsi_crossed_above(70)
        strat_name = "RSI Mean Reversion (14)"
    elif strategy == 'MACD':
        macd = vbt.MACD.run(price)
        entries = macd.macd_crossed_above(macd.signal)
        exits = macd.macd_crossed_below(macd.signal)
        strat_name = "MACD Momentum"
    elif strategy == 'BB':
        bb = vbt.BBANDS.run(price)
        entries = price.vbt.crossed_below(bb.lower)
        exits = price.vbt.crossed_above(bb.upper)
        strat_name = "Bollinger Bands Reversion"
    else:
        # Default EMA
        fast_ma = vbt.MA.run(price, window=10)
        slow_ma = vbt.MA.run(price, window=50)
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)
        strat_name = "EMA Crossover (10/50)"
        
    portfolio = vbt.Portfolio.from_signals(
        price, entries, exits, init_cash=10000, fees=0.001, freq='1d'
    )
    
    stats = portfolio.stats()
    
    return {
        "Total Return [%]": stats.get('Total Return [%]', 0),
        "Sharpe Ratio": stats.get('Sharpe Ratio', 0),
        "Max Drawdown [%]": stats.get('Max Drawdown [%]', 0),
        "Win Rate [%]": stats.get('Win Rate [%]', 0),
        "Strategy Name": strat_name
    }'''

if old_bt_func in bt_code:
    bt_code = bt_code.replace(old_bt_func, new_bt_func)
else:
    bt_code = bt_code.replace(old_bt_func.replace('\n', '\r\n'), new_bt_func)

with open("backtesting_engine.py", "w") as f:
    f.write(bt_code)


# 2. Patch backend.py
with open("backend.py", "r") as f:
    backend_code = f.read()

old_backend_func = '''@app.get("/api/backtest")
def get_backtest(ticker: str = "AAPL", start: str = "2020-01-01", end: str = "2024-01-01"):
    """
    Run backtest using vectorbt with strategy: Fast MA crosses Slow MA.
    """
    try:
        results = run_vectorbt_backtest(ticker, start, end)
        return {"status": "success", "data": results}'''

new_backend_func = '''@app.get("/api/backtest")
def get_backtest(ticker: str = "AAPL", strategy: str = "EMA", start: str = "2020-01-01", end: str = "2024-01-01"):
    """
    Run backtest using vectorbt with strategy parameter.
    """
    try:
        results = run_vectorbt_backtest(ticker, start, end, strategy)
        return {"status": "success", "data": results}'''

if old_backend_func in backend_code:
    backend_code = backend_code.replace(old_backend_func, new_backend_func)
else:
    backend_code = backend_code.replace(old_backend_func.replace('\n', '\r\n'), new_backend_func)

with open("backend.py", "w") as f:
    f.write(backend_code)


# 3. Patch script.js
with open("script.js", "r", encoding="utf-8") as f:
    js_code = f.read()

# Replace runBacktest call in command parsing
old_bt_call = """                } else if (val.startsWith('BT ')) {
                    const ticker = val.substring(3).trim();
                    runBacktest(ticker);"""

new_bt_call = """                } else if (val.startsWith('BT ')) {
                    const args = val.substring(3).trim().split(' ');
                    const ticker = args[0];
                    const strategy = args.length > 1 ? args[1] : 'EMA';
                    runBacktest(ticker, strategy);"""

if old_bt_call in js_code:
    js_code = js_code.replace(old_bt_call, new_bt_call)
else:
    js_code = js_code.replace(old_bt_call.replace('\n', '\r\n'), new_bt_call)

# Replace runBacktest signature and fetch
js_code = re.sub(r"async function runBacktest\(ticker\) \{", "async function runBacktest(ticker, strategy) {", js_code)
js_code = re.sub(r"fetch\(`http://localhost:8000/api/backtest\?ticker=\$\{ticker\}`\);", "fetch(`/api/backtest?ticker=${ticker}&strategy=${strategy}`);", js_code)
js_code = re.sub(r"fetch\(`/api/backtest\?ticker=\$\{ticker\}`\);", "fetch(`/api/backtest?ticker=${ticker}&strategy=${strategy}`);", js_code)

# Replace the HTML output in runBacktest
old_html = """<div style="margin-top: 25px; color: #555; font-size: 10px; text-transform: uppercase; border-top: 1px dashed #333; padding-top: 10px;">STRAT: EMA Crossover<br>PARAM: 10/50 Length<br>PERIOD: 2020-2024<br>ENGINE: vectorbt</div>"""
new_html = """<div style="margin-top: 25px; color: #555; font-size: 10px; text-transform: uppercase; border-top: 1px dashed #333; padding-top: 10px;">STRAT: ${data["Strategy Name"] || strategy}<br>PERIOD: 2020-2024<br>ENGINE: vectorbt</div>"""
js_code = js_code.replace(old_html, new_html)

with open("script.js", "w", encoding="utf-8") as f:
    f.write(js_code)

print("Patch applied successfully.")
