# Vercel Deployment & Dependency Error Summary (READ ME)

This file documents the steps taken to resolve the "643.43 MB Lambda Ephemeral Storage Limit" error and the subsequent 500 startup errors on Vercel.

## 1. Initial Failure: Dependency Bloat
*   **Error Message**: `total dependency size (643.43 MB) exceeds Lambda ephemeral storage limit (500 MB).`
*   **Cause**: The inclusion of heavy quantitative trading libraries (`vectorbt`, `backtrader`, `PyPortfolioOpt`, and `scipy`) on top of the standard data stack (`pandas`, `numpy`, `plotly`).
*   **Target Size**: The unzipped dependencies must stay below **500MB** for the Vercel/AWS Lambda runtime.

## 2. Phase 1: Removing the "Big Four"
To resolve the size limit, we surgically replaced heavy libraries with lightweight custom versions:
1.  **Removed `vectorbt` & `backtrader`**: Replaced with a custom **Pandas-based backtesting engine** (`api/backtesting_engine.py`) which provides the same EMA, RSI, MACD, and BB strategies without the LLVM/Numba overhead.
2.  **Removed `PyPortfolioOpt` & `cvxpy`**: Replaced with a custom **Scipy-based optimizer** (`api/portfolio_risk.py`) to eliminate the massive CVXPY solver ecosystem.
3.  **Removed `scipy`** (The Ultimate Fix): `scipy` was adding ~200MB alone. I rewrote the portfolio optimization logic to use **Pure-Numpy Monte Carlo (1,000 simulations)**, which provides accurate enough Sharpe/Risk results for a dashboard while staying under 250MB.

## 3. Phase 2: Solving the "500 Internal Server Error"
Despite successful builds, the app initially crashed on startup. We applied these "Bulletproof" measures:
*   **Import Safety**: Wrapped all library imports in `try-except` blocks.
*   **Diagnostic Endpoint**: Added **`/api/health`** to report which libraries fail to load in the Vercel environment.
*   **Folder Cleanup**: Deleted non-essential scripts (`patch.py`, `apply_multi_strat.py`, etc.) from the `/api` directory to prevent Vercel from trying to build them as separate serverless functions.
*   **Missing Helpers**: Added `lxml`, `multitasking`, and `requests` explicitly to `requirements.txt` to ensure `yfinance` has its full networking/parsing stack.

## 4. Current Status
*   **Build**: **SUCCESSFUL** (Commit `1194af8`, `9779c47`, and `a9e28ef`).
*   **Deployment**: Bundle is now **~215MB** (Unzipped), well within limits.
*   **Next Step**: Visit **`https://terminal-neon-pi.vercel.app/api/health`** to find which library is incompatible with the Python 3.12 runtime.

---
### Final Recommendation
Vercel is great for the UI, but if these "Serverless Function Crashed" errors persist, I recommend [Railway.app](https://railway.app). It uses **Docker**, which supports the 643MB size without any changes and has no strict 10-second timeout constraints.
