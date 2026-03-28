import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize
import warnings

warnings.filterwarnings("ignore")

def get_portfolio_risk_data(holdings={"AAPL": 50, "MSFT": 100, "GOOGL": 20}, start_date="2020-01-01", end_date="2023-12-31"):
    """
    Manual implementation of Portfolio Optimization to remove heavy PyPortfolioOpt dependency.
    """
    tickers = list(holdings.keys())
    
    # 1. Download data
    data = yf.download(tickers, start=start_date, end=end_date, progress=False)
    if 'Close' in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else False:
        df = data['Close']
    else:
        df = data['Adj Close'] if 'Adj Close' in data else data

    if len(tickers) == 1:
        if isinstance(df, pd.Series):
            df = df.to_frame(name=tickers[0])

    df.ffill(inplace=True)
    df.dropna(inplace=True)
    
    returns_df = df.pct_change().dropna()
    latest_prices = df.iloc[-1]

    # 2. Current Portfolio Metrics
    shares = pd.Series(holdings)
    latest_prices_aligned = latest_prices.reindex(shares.index).fillna(0)
    current_value = (shares * latest_prices_aligned).sum()
    current_weights = (shares * latest_prices_aligned) / current_value

    # Performance metrics
    ann_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    
    cw_aligned = current_weights.reindex(ann_returns.index).fillna(0)
    current_return = np.dot(cw_aligned, ann_returns)
    current_volatility = np.sqrt(np.dot(cw_aligned.T, np.dot(cov_matrix, cw_aligned)))
    current_sharpe = (current_return - 0.02) / current_volatility if current_volatility > 0 else 0

    # 3. Optimization: Max Sharpe (Using SciPy)
    num_assets = len(tickers)
    
    def portfolio_stats(weights):
        p_ret = np.dot(weights, ann_returns)
        p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (p_ret - 0.02) / p_vol
        return np.array([p_ret, p_vol, sharpe])

    def neg_sharpe(weights):
        return -portfolio_stats(weights)[2]

    # Constraints: sum(weights) == 1
    cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
    # Bounds: 0 to 1 for each asset
    bounds = tuple((0.0, 1.0) for asset in range(num_assets))
    # Initial guess
    init_guess = num_assets * [1.0 / num_assets]
    
    # Run optimization
    opt_results = minimize(neg_sharpe, init_guess, method='SLSQP', bounds=bounds, constraints=cons)
    
    if opt_results.success:
        optimal_weights = opt_results.x
        opt_perf = portfolio_stats(optimal_weights)
    else:
        optimal_weights = current_weights.values
        opt_perf = [current_return, current_volatility, current_sharpe]

    cleaned_weights_sharpe = dict(zip(tickers, optimal_weights))
    
    # 4. HRP Allocation (Simplified Version using Volatility weighting as a proxy)
    # Since Hierarchical Risk Parity is complex, use "Inverse Volatility" weighting 
    # as a lightweight risk-parity proxy to replace the HRPOpt class.
    vols = returns_df.std() * np.sqrt(252)
    inv_vols = 1.0 / vols
    hrp_weights_raw = inv_vols / inv_vols.sum()
    cleaned_weights_hrp = hrp_weights_raw.to_dict()

    # 5. Monte Carlo
    num_simulated = 500
    results = np.zeros((3, num_simulated))
    for i in range(num_simulated):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)
        p_ret = np.dot(weights, ann_returns)
        p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        results[0,i] = p_vol
        results[1,i] = p_ret
        results[2,i] = (p_ret - 0.02) / p_vol if p_vol > 0 else 0

    max_sharpe_idx = np.argmax(results[2])
    min_vol_idx = np.argmin(results[0])

    # 6. Discrete Allocation (Simple rounding/quantizing)
    allocation = {}
    for ticker, weight in cleaned_weights_sharpe.items():
        share_count = int((weight * current_value) / latest_prices[ticker])
        if share_count > 0:
            allocation[ticker] = share_count
            
    leftover = current_value - sum(allocation[t] * latest_prices[t] for t in allocation)

    # 7. Trade Recommendations
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
            "expected_return": float(current_return),
            "annual_volatility": float(current_volatility),
            "sharpe_ratio": float(current_sharpe),
            "holdings": holdings,
            "weights": {k: float(v) for k, v in current_weights.items()}
        },
        "optimal_portfolio": {
            "expected_return": float(opt_perf[0]),
            "annual_volatility": float(opt_perf[1]),
            "sharpe_ratio": float(opt_perf[2]),
            "max_sharpe_weights": {k: float(v) for k, v in cleaned_weights_sharpe.items() if v > 0.01},
            "hrp_weights": {k: float(v) for k, v in cleaned_weights_hrp.items() if v > 0},
            "allocation": {k: int(v) for k, v in allocation.items()},
            "leftover": float(leftover)
        },
        "trades": trades,
        "monte_carlo": {
            "num_simulated": num_simulated,
            "max_sharpe": {
                "sharpe": float(results[2, max_sharpe_idx]),
                "return": float(results[1, max_sharpe_idx]),
                "volatility": float(results[0, max_sharpe_idx])
            },
            "min_vol": {
                "sharpe": float(results[2, min_vol_idx]),
                "return": float(results[1, min_vol_idx]),
                "volatility": float(results[0, min_vol_idx])
            }
        }
    }
