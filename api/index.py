import os
import json
import traceback
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
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
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.io as pio
except Exception as e:
    go = pio = make_subplots = None
    load_errors["plotly"] = str(e)

@app.get("/api/health")
def health_check():
    import sys
    return {
        "status": "online",
        "python_version": sys.version,
        "environment": "Vercel/Lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "Local",
        "load_errors": load_errors
    }

def calculate_sma(data, window):
    return data['Close'].rolling(window=window).mean()

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@app.get("/api/chart")
def get_chart(ticker: str = "AAPL", period: str = "1mo", interval: str = "1d"):
    if yf is None or pd is None or go is None:
        return JSONResponse(status_code=500, content={"error": "Required libraries (yf/pd/go) failed to load.", "details": load_errors})
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return JSONResponse(status_code=404, content={"error": "No data found."})
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        data['SMA_20'] = calculate_sma(data, 20)
        data['SMA_50'] = calculate_sma(data, 50)
        data['RSI'] = calculate_rsi(data, 14)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3], subplot_titles=(f"{ticker.upper()} Price", "RSI (14)"))
        fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price", increasing_line_color='#00FF81', decreasing_line_color='#FF3131'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], line=dict(color='orange', width=1.5), name='SMA 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_50'], line=dict(color='cyan', width=1.5), name='SMA 50'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], line=dict(color='magenta', width=1.5), name='RSI'), row=2, col=1)
        fig.update_layout(paper_bgcolor="#0c0d0f", plot_bgcolor="#0c0d0f", font=dict(color="#808080", family="monospace", size=10), margin=dict(l=40, r=40, t=30, b=40), xaxis_rangeslider_visible=False)
        return JSONResponse(content=json.loads(fig.to_json()))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quotes")
def get_quotes(tickers: str = "AAPL,MSFT,GOOGL"):
    if yf is None: return {"error": "yfinance not loaded"}
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(',')]
        data = yf.download(ticker_list, period="5d", progress=False)
        results = []
        for ticker in ticker_list:
            try:
                hist = data.xs(ticker, level=1, axis=1) if len(ticker_list) > 1 and isinstance(data.columns, pd.MultiIndex) else data
                if hist.empty: continue
                latest = hist.iloc[-1]; prev = hist.iloc[-2] if len(hist) > 1 else latest
                results.append({"symbol": ticker, "price": float(latest['Close']), "change": float(latest['Close'] - prev['Close']), "change_pct": float((latest['Close'] - prev['Close']) / prev['Close'] * 100)})
            except: continue
        return {"quotes": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/backtest")
def get_backtest(ticker: str = "AAPL", strategy: str = "EMA", start: str = "2020-01-01", end: str = "2024-01-01"):
    try:
        from backtesting_engine import run_vectorbt_backtest
        results = run_vectorbt_backtest(ticker, start, end, strategy)
        return {"status": "success", "data": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/sentiment")
def get_sentiment(ticker: str = "AAPL"):
    try:
        if yf is None: return {"error": "yfinance not loaded"}
        t = yf.Ticker(ticker); news = t.news
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        results = []; total_score = 0
        for item in (news or []):
            title = item.get("title", "")
            if not title: continue
            score = analyzer.polarity_scores(title)['compound']
            total_score += score
            results.append({"title": title, "score": score})
        return {"status": "success", "ticker": ticker, "average_sentiment": total_score/len(results) if results else 0, "news": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/portfolio")
def get_portfolio(holdings: str = "AAPL:50,MSFT:100,GOOGL:20"):
    try:
        from portfolio_risk import get_portfolio_risk_data
        holdings_dict = {item.split(':')[0].strip().upper(): float(item.split(':')[1]) for item in holdings.split(',') if ':' in item}
        return get_portfolio_risk_data(holdings=holdings_dict)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# General Catch-all News
@app.get("/api/news")
def get_general_news():
    try:
        if yf is None: return {"error": "yfinance not loaded"}
        t = yf.Ticker("SPY"); news = t.news; formatted = []
        for item in (news or []):
            formatted.append({"time": "00:00", "title": item.get("title", "")})
        return {"status": "success", "news": formatted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
