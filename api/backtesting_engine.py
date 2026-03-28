import yfinance as yf
import vectorbt as vbt
import backtrader as bt
import pandas as pd

def run_vectorbt_backtest(ticker, start_date, end_date, strategy="EMA"):
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
    }

# --- Backtrader Component ---

class SmaCrossStrategy(bt.Strategy):
    """
    Event-driven Trading Strategy using Backtrader.
    Best for complex execution logic, position sizing, and granular trade management.
    """
    params = (
        ('fast', 10),
        ('slow', 50),
    )

    def __init__(self):
        # Moving averages
        self.sma_fast = bt.ind.SMA(period=self.p.fast)
        self.sma_slow = bt.ind.SMA(period=self.p.slow)
        # Crossover indicator
        self.crossover = bt.ind.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        # Event-driven core logic evaluated on every new data bar
        if not self.position:
            if self.crossover > 0: # Fast crosses above Slow
                self.buy()
        elif self.crossover < 0: # Fast crosses below Slow
            self.close()

def run_backtrader_backtest(ticker, start_date, end_date):
    print(f"\n--- Running Backtrader Backtest for {ticker} ---")
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    # 1. Fetch and add data
    df = yf.download(ticker, start=start_date, end=end_date)
    # yfinance multi-index column fix
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    
    # 2. Add Strategy
    cerebro.addstrategy(SmaCrossStrategy)
    
    # 3. Add Analyzers (Sharpe, Drawdown, Trades)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    print(f"Starting Portfolio Value: ${cerebro.broker.getvalue():.2f}")
    
    # 4. Execute Backtest
    results = cerebro.run()
    strat = results[0]
    
    print(f"Final Portfolio Value: ${cerebro.broker.getvalue():.2f}")
    
    # 5. Extract Results
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    
    win_rate = 0
    if 'total' in trades and trades.total.closed > 0:
        win_rate = (trades.won.total / trades.total.closed) * 100

    print("\nPerformance Report:")
    print(f"Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
    print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")
    print(f"Win Rate: {win_rate:.2f}%")
    
    return {
        "Sharpe": sharpe.get('sharperatio'),
        "Drawdown [%]": drawdown.max.drawdown,
        "Win Rate [%]": win_rate
    }

if __name__ == '__main__':
    # Shared Inputs
    TARGET_TICKER = 'AAPL'
    START = '2020-01-01'
    END = '2023-01-01'
    
    # Execute vectorbt (Fast, vectorized)
    vbt_results = run_vectorbt_backtest(TARGET_TICKER, START, END)
    
    # Execute Backtrader (Event-driven, granular)
    bt_results = run_backtrader_backtest(TARGET_TICKER, START, END)
