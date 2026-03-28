import os
import json
import traceback
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diagnostic tracker
load_errors = {}

# Safe import wrappers
try:
    import yfinance as yf
except Exception as e:
    yf = None
    load_errors["yfinance"] = str(e)

try:
    import pandas as pd
except Exception as e:
    pd = None
    load_errors["pandas"] = str(e)

try:
    import numpy as np
except Exception as e:
    np = None
    load_errors["numpy"] = str(e)

# 1. Root Route - Serve index.html
@app.get("/")
def read_root():
    # Vercel structure: the root files are accessible from the project root
    # Try multiple common paths for Vercel environments
    paths = ["index.html", "../index.html", "/var/task/index.html"]
    for path in paths:
        if os.path.exists(path):
            return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "index.html not found", "cwd": os.getcwd(), "ls": os.listdir(".")})

@app.get("/api/health")
def health_check():
    import sys
    return {
        "status": "online",
        "python_version": sys.version,
        "environment": "Vercel/Lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("VERCEL") else "Local",
        "load_errors": load_errors
    }

# 2. Market History (Aligned with script.js)
@app.get("/api/history")
def get_history(ticker: str = "AAPL", period: str = "1mo", interval: str = "1d"):
    if yf is None or pd is None:
        return JSONResponse(status_code=500, content={"error": "yf/pd failed to load.", "details": load_errors})
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return JSONResponse(status_code=404, content={"error": "No data found."})
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        
        # Format for script.js (Canvas drawing)
        formatted_data = []
        for index, row in data.iterrows():
            formatted_data.append({
                "date": index.strftime('%Y-%m-%d %H:%M') if interval in ['1m','5m','15m','30m','60m','1h'] else index.strftime('%Y-%m-%d'),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            })
        
        return {"status": "success", "ticker": ticker, "data": formatted_data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 3. Single Quote
@app.get("/api/quote")
def get_single_quote(ticker: str = "AAPL"):
    if yf is None: return {"error": "yfinance not loaded"}
    try:
        t = yf.Ticker(ticker)
        # Fast way to get price: download 1 day
        data = yf.download(ticker, period="1d", progress=False)
        if data.empty: return {"error": "No data"}
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)
        
        last_close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2]) if len(data) > 1 else last_close
        
        return {
            "symbol": ticker,
            "price": last_close,
            "change": last_close - prev_close,
            "change_pct": ((last_close - prev_close) / prev_close * 100) if prev_close != 0 else 0
        }
    except Exception as e:
        return {"error": str(e)}

# 4. Multi-ticker Quotes (for Pulse)
@app.get("/api/quotes")
def get_quotes(tickers: str = "AAPL,MSFT,GOOGL"):
    if yf is None or pd is None: return {"error": "Libraries not loaded"}
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(',')]
        # Fetch 5 days to ensure we have a previous close for change calculation
        data = yf.download(ticker_list, period="5d", progress=False)
        results = []
        
        for ticker in ticker_list:
            try:
                # Handle MultiIndex vs SingleIndex
                if len(ticker_list) > 1:
                    hist = data.xs(ticker, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data[ticker]
                else:
                    hist = data
                    
                if hist.empty: continue
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                
                results.append({
                    "symbol": ticker,
                    "price": float(latest['Close']),
                    "change": float(latest['Close'] - prev['Close']),
                    "change_pct": float((latest['Close'] - prev['Close']) / prev['Close'] * 100) if prev['Close'] != 0 else 0
                })
            except:
                continue
        return {"quotes": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 5. Valuation (Lightweight logic)
@app.get("/api/valuation")
def get_valuation(ticker: str = "AAPL"):
    if yf is None: return {"error": "yfinance not loaded"}
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        # Simple ratios from info
        return {
            "ticker": ticker,
            "dupont_roe": info.get("returnOnEquity", 0.15),
            "ev_ebitda": info.get("enterpriseToEbitda", 15.0),
            "ratios": {
                "gross_margin": info.get("grossMargins", 0.40),
                "debt_to_equity": info.get("debtToEquity", 100.0) / 100.0 if info.get("debtToEquity") else 0.5
            },
            "dcf": {
                "intrinsic_price": info.get("targetMeanPrice", info.get("currentPrice", 100) * 1.1),
                "upside": (info.get("targetMeanPrice", info.get("currentPrice", 100) * 1.1) / info.get("currentPrice", 1) - 1) if info.get("currentPrice") else 0.1
            }
        }
    except Exception as e:
        return {"error": str(e)}

# 6. Options Activity
@app.get("/api/options")
def get_options(ticker: str = "AAPL"):
    if yf is None: return {"error": "yfinance not loaded"}
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations: return {"error": "No options"}
        
        # Just use the first expiry for simplicity
        opt = t.option_chain(expirations[0])
        call_vol = opt.calls['volume'].sum()
        put_vol = opt.puts['volume'].sum()
        pcr = put_vol / call_vol if call_vol > 0 else 1.0
        
        return {
            "expiration": expirations[0],
            "call_volume": int(call_vol),
            "put_volume": int(put_vol),
            "put_call_ratio": float(pcr),
            "sentiment": "Bullish" if pcr < 0.7 else ("Bearish" if pcr > 1.1 else "Neutral")
        }
    except Exception as e:
        return {"error": str(e)}

# 7. Sentiment
@app.get("/api/sentiment")
def get_sentiment(ticker: str = "AAPL"):
    try:
        if yf is None: return {"error": "yfinance not loaded"}
        t = yf.Ticker(ticker)
        news = t.news or []
        
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        
        results = []
        total_score = 0
        for item in news:
            title = item.get("title", "")
            if not title: continue
            score = analyzer.polarity_scores(title)['compound']
            total_score += score
            results.append({
                "title": title, 
                "score": score,
                "publisher": item.get("publisher", "Unknown")
            })
            
        return {
            "status": "success", 
            "ticker": ticker, 
            "average_sentiment": total_score/len(results) if results else 0, 
            "news": results
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 8. Portfolio Optimization
@app.get("/api/portfolio")
def get_portfolio(holdings: str = "AAPL:50,MSFT:100,GOOGL:20"):
    try:
        # Check if helper exists in api/
        import sys
        sys.path.append(os.path.dirname(__file__))
        import portfolio_risk
        
        holdings_dict = {}
        for item in holdings.split(','):
            if ':' in item:
                sym, val = item.split(':')
                holdings_dict[sym.strip().upper()] = float(val)
        
        return portfolio_risk.get_portfolio_risk_data(holdings=holdings_dict)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})

# 9. Backtest
@app.get("/api/backtest")
def get_backtest(ticker: str = "AAPL", strategy: str = "EMA", start: str = "2022-01-01", end: str = "2024-03-01"):
    try:
        import sys
        sys.path.append(os.path.dirname(__file__))
        import backtesting_engine
        
        results = backtesting_engine.run_vectorbt_backtest(ticker, start, end, strategy)
        return {"status": "success", "data": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})

# 10. General News
@app.get("/api/news")
def get_general_news():
    try:
        if yf is None: return {"error": "yfinance not loaded"}
        t = yf.Ticker("SPY")
        news = t.news or []
        formatted = []
        for item in news:
            formatted.append({"time": "Live", "title": item.get("title", "")})
        return {"status": "success", "news": formatted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 11. Static File Fallback (Fix for 404 on CSS/JS)
@app.get("/{path:path}")
def serve_static_files(path: str):
    # If it's empty, it's the root
    if not path or path == "":
        return read_root()
    
    # List of allowed static files to serve
    allowed = ["style.css", "script.js", "favicon.ico"]
    # Handle query params like script.js?v=2
    clean_path = path.split('?')[0]
    
    if clean_path in allowed:
        # Check potential locations
        for p in [clean_path, f"../{clean_path}", f"/var/task/{clean_path}"]:
            if os.path.exists(p):
                return FileResponse(p)
    
    return JSONResponse(status_code=404, content={"detail": "Not Found", "path": path})
