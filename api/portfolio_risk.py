# %% [markdown]
# # Portfolio & Risk Framework
import numpy as np
import pandas as pd
import yfinance as yf

# PyPortfolioOpt modules
from pypfopt.expected_returns import mean_historical_return
from pypfopt.risk_models import CovarianceShrinkage
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt.hierarchical_portfolio import HRPOpt
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

import warnings
warnings.filterwarnings("ignore")

def get_portfolio_risk_data(holdings={"AAPL": 50, "MSFT": 100, "GOOGL": 20}, start_date="2020-01-01", end_date="2023-12-31"):
    tickers = list(holdings.keys())
    
    # Download data
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
    
    latest_prices = get_latest_prices(df)

    # 1. Current Portfolio Metrics
    shares = pd.Series(holdings)
    # Align indices
    latest_prices_aligned = latest_prices.reindex(shares.index).fillna(0)
    current_value = (shares * latest_prices_aligned).sum()
    current_weights = (shares * latest_prices_aligned) / current_value

    mu = mean_historical_return(df)
    S = CovarianceShrinkage(df).ledoit_wolf()

    current_return = np.dot(current_weights.reindex(mu.index).fillna(0), mu)
    
    # Pad current weights to match S columns for dot product
    cw_aligned = current_weights.reindex(S.columns).fillna(0)
    current_volatility = np.sqrt(np.dot(cw_aligned.T, np.dot(S, cw_aligned)))
    current_sharpe = (current_return - 0.02) / current_volatility if current_volatility > 0 else 0

    # 2. Max Sharpe Optimization
    weight_bound = (0, 0.4) if len(tickers) >= 3 else (0, 1)
    
    ef = EfficientFrontier(mu, S, weight_bounds=weight_bound)
    raw_weights_sharpe = ef.max_sharpe()
    cleaned_weights_sharpe = ef.clean_weights()
    perf = ef.portfolio_performance()

    # 3. HRP Allocation
    returns = df.pct_change().dropna()
    hrp = HRPOpt(returns)
    raw_weights_hrp = hrp.optimize()
    cleaned_weights_hrp = hrp.clean_weights()

    # 4. Monte Carlo
    num_portfolios = 1000
    num_assets = len(tickers)
    results = np.zeros((3, num_portfolios))
    if num_assets > 1:
        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        for i in range(num_portfolios):
            weights = np.random.random(num_assets)
            weights /= np.sum(weights)
            port_return = np.sum(mean_returns * weights)
            port_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe_ratio = (port_return - 0.02) / port_std_dev
            
            results[0,i] = port_std_dev
            results[1,i] = port_return
            results[2,i] = sharpe_ratio

        max_sharpe_idx = np.argmax(results[2])
        min_vol_idx = np.argmin(results[0])
    else:
        max_sharpe_idx, min_vol_idx = 0, 0
        results[0,0], results[1,0], results[2,0] = current_volatility, current_return, current_sharpe

    # 5. Discrete Allocation
    da = DiscreteAllocation(cleaned_weights_sharpe, latest_prices, total_portfolio_value=current_value)
    allocation, leftover = da.lp_portfolio()
    
    # 6. Trade Recommendations
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
            "expected_return": float(perf[0]),
            "annual_volatility": float(perf[1]),
            "sharpe_ratio": float(perf[2]),
            "max_sharpe_weights": {k: float(v) for k, v in cleaned_weights_sharpe.items() if v > 0},
            "hrp_weights": {k: float(v) for k, v in cleaned_weights_hrp.items() if v > 0},
            "allocation": {k: int(v) for k, v in allocation.items()},
            "leftover": float(leftover)
        },
        "trades": trades,
        "monte_carlo": {
            "num_simulated": num_portfolios,
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

if __name__ == "__main__":
    print(get_portfolio_risk_data())

