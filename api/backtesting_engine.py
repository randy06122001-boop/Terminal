import yfinance as yf
import pandas as pd
import numpy as np

def run_vectorbt_backtest(ticker, start_date, end_date, strategy="EMA"):
    """
    Runs a fast, vectorized backtest using pure Pandas/Numpy.
    Named 'run_vectorbt_backtest' to maintain compatibility with index.py without changing imports there.
    """
    print(f"--- Running Pandas Backtest for {ticker} using {strategy} ---")
    
    # 1. Fetch data
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if data.empty:
        return {"error": "No data found"}
        
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    price = data['Close']
    strategy = strategy.upper()
    strat_name = "EMA Crossover (10/50)"
    
    # Generate signals
    signals = pd.Series(0, index=price.index)
    
    if strategy == 'RSI':
        window = 14
        delta = price.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Buy when RSI < 30, Sell when RSI > 70
        # Simple signal logic: stays in position until exit
        curr_pos = 0
        for i in range(len(rsi)):
            if rsi.iloc[i] < 30:
                curr_pos = 1
            elif rsi.iloc[i] > 70:
                curr_pos = 0
            signals.iloc[i] = curr_pos
        strat_name = "RSI Mean Reversion (14)"
        
    elif strategy == 'MACD':
        exp1 = price.ewm(span=12, adjust=False).mean()
        exp2 = price.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=9, adjust=False).mean()
        
        # Buy when macd > signal_line
        signals = (macd > signal_line).astype(int)
        strat_name = "MACD Momentum"
        
    elif strategy == 'BB':
        sma = price.rolling(window=20).mean()
        std = price.rolling(window=20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        # Buy when price < lower, Sell when price > upper
        curr_pos = 0
        for i in range(len(price)):
            if price.iloc[i] < lower.iloc[i]:
                curr_pos = 1
            elif price.iloc[i] > upper.iloc[i]:
                curr_pos = 0
            signals.iloc[i] = curr_pos
        strat_name = "Bollinger Bands Reversion"
        
    else:
        # Default EMA
        fast_ma = price.ewm(span=10).mean()
        slow_ma = price.ewm(span=50).mean()
        signals = (fast_ma > slow_ma).astype(int)
        strat_name = "EMA Crossover (10/50)"
    
    # Calculate Returns
    returns = price.pct_change()
    strat_returns = returns * signals.shift(1)
    
    # Portfolio cumulative values
    cum_returns = (1 + strat_returns.fillna(0)).cumprod()
    total_return = (cum_returns.iloc[-1] - 1) * 100
    
    # Sharpe Ratio (annualized, assuming 252 trading days)
    risk_free_rate = 0.02
    daily_rf = (1 + risk_free_rate)**(1/252) - 1
    excess_returns = strat_returns - daily_rf
    sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() != 0 else 0
    
    # Max Drawdown
    rolling_max = cum_returns.cummax()
    drawdown = (cum_returns - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100
    
    # Win Rate
    # A "trade" is defined as a day with a positive return vs negative return
    # (Simplified for the dashboard)
    pos_trades = strat_returns[strat_returns > 0]
    total_active_trades = strat_returns[strat_returns != 0]
    win_rate = (len(pos_trades) / len(total_active_trades) * 100) if len(total_active_trades) > 0 else 0
    
    return {
        "Total Return [%]": float(total_return),
        "Sharpe Ratio": float(sharpe),
        "Max Drawdown [%]": float(max_drawdown),
        "Win Rate [%]": float(win_rate),
        "Strategy Name": strat_name
    }

# Removed Backtrader classes as they are not used in production and bloat dependencies.
