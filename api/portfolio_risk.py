import numpy as np
import pandas as pd
import yfinance as yf
import warnings

warnings.filterwarnings("ignore")

def get_portfolio_risk_data(holdings={"AAPL": 50, "MSFT": 100, "GOOGL": 20}, start_date="2022-01-01", end_date="2024-01-01"):
    """
    Ultra-lightweight Portfolio Optimization using Pure Numpy/Pandas.
    Replaces Scipy/CVXPY to keep the deployment size tiny.
    """
    tickers = list(holdings.keys())
    
    # 1. Download data (reduced to 2 years for speed)
    data = yf.download(tickers, start=start_date, end=end_date, progress=False)
    
    # Handle single ticker data shape
    if len(tickers) == 1:
        if 'Close' in data:
            df = data['Close'].to_frame(name=tickers[0])
        else:
            df = data.to_frame(name=tickers[0])
    else:
        df = data['Close'] if 'Close' in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else data['Close']
    
    df.ffill(inplace=True)
    df.dropna(inplace=True)
    
    returns_df = df.pct_change().dropna()
    latest_prices = df.iloc[-1]

    # 2. Current Portfolio Metrics
    shares = pd.Series(holdings)
    current_value = (shares * latest_prices).sum()
    current_weights = (shares * latest_prices) / current_value

    ann_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    
    # Calculate stats for a collection of weights
    def get_stats(w_arr):
        ret = np.sum(ann_returns.values * w_arr, axis=1)
        vol = np.sqrt(np.einsum('ij,jk,ik->i', w_arr, cov_matrix.values, w_arr))
        sharpe = (ret - 0.02) / vol
        return ret, vol, sharpe

    # 3. High-Speed Monte Carlo Simulation (1,000 runs)
    num_assets = len(tickers)
    num_portfolios = 1000
    
    # Generate random weights in bulk for speed
    rand_weights = np.random.random((num_portfolios, num_assets))
    rand_weights = rand_weights / np.sum(rand_weights, axis=1)[:, np.newaxis]
    
    p_rets, p_vols, p_sharpes = get_stats(rand_weights)
    
    # Find the best port in the simulation
    max_sharpe_idx = np.argmax(p_sharpes)
    min_vol_idx = np.argmin(p_vols)
    
    optimal_weights = rand_weights[max_sharpe_idx]
    opt_perf = [p_rets[max_sharpe_idx], p_vols[max_sharpe_idx], p_sharpes[max_sharpe_idx]]
    
    cleaned_weights_sharpe = dict(zip(tickers, optimal_weights))

    # 4. Discrete Allocation (Simple Quantization)
    allocation = {}
    for ticker, weight in cleaned_weights_sharpe.items():
        share_count = int((weight * current_value) / latest_prices[ticker])
        if share_count > 0:
            allocation[ticker] = share_count
            
    leftover = current_value - sum(allocation[t] * latest_prices[t] for t in allocation)

    # 5. Trade Recommendations
    trades = {}
    for ticker in tickers:
        current_share = holdings.get(ticker, 0)
        target_share = allocation.get(ticker, 0)
        diff = target_share - current_share
        if diff != 0:
            trades[ticker] = diff

    return {
        "current_portfolio": {
            "value": float(current_value),
            "expected_return": float(np.dot(current_weights, ann_returns)),
            "annual_volatility": float(np.sqrt(np.dot(current_weights.T, np.dot(cov_matrix, current_weights)))),
            "sharpe_ratio": float((np.dot(current_weights, ann_returns) - 0.02) / np.sqrt(np.dot(current_weights.T, np.dot(cov_matrix, current_weights)))),
            "holdings": holdings,
            "weights": {k: float(v) for k, v in current_weights.items()}
        },
        "optimal_portfolio": {
            "expected_return": float(opt_perf[0]),
            "annual_volatility": float(opt_perf[1]),
            "sharpe_ratio": float(opt_perf[2]),
            "max_sharpe_weights": {k: float(v) for k, v in cleaned_weights_sharpe.items() if v > 0.01},
            "allocation": {k: int(v) for k, v in allocation.items()},
            "leftover": float(leftover)
        },
        "trades": trades,
        "monte_carlo": {
            "num_simulated": num_portfolios,
            "max_sharpe": {
                "sharpe": float(p_sharpes[max_sharpe_idx]),
                "return": float(p_rets[max_sharpe_idx]),
                "volatility": float(p_vols[max_sharpe_idx])
            },
            "min_vol": {
                "sharpe": float(p_sharpes[min_vol_idx]),
                "return": float(p_rets[min_vol_idx]),
                "volatility": float(p_vols[min_vol_idx])
            }
        }
    }
