import os
import json
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from backtesting_engine import run_vectorbt_backtest
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_sma(data, window):
    return data['Close'].rolling(window=window).mean()

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@app.get("/api/health")
def health_check():
    import sys
    import os
    return {
        "status": "online",
        "python_version": sys.version,
        "environment": "Vercel/Lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "Local"
    }

@app.get("/api/chart")
def get_chart(ticker: str = "AAPL", period: str = "1mo", interval: str = "1d"):
    """
    Fetch historical data for a ticker and build a Plotly chart.
    Includes Candlestick, SMA (overlay), and RSI (subplot).
    """
    try:
        # Fetch data
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return JSONResponse(status_code=404, content={"error": "No data found for this ticker."})

        # Calculate Indicators
        # Squeeze out MultiIndex if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
            
        data['SMA_20'] = calculate_sma(data, 20)
        data['SMA_50'] = calculate_sma(data, 50)
        data['RSI'] = calculate_rsi(data, 14)

        # Create Plotly figure with subplots: 1 for Price/Candle, 1 for RSI
        # Use row-heights to give more space to price chart
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"{ticker.upper()} Price", "RSI (14)")
        )

        # 1. Candlestick
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name="Price",
            increasing_line_color='#00FF81',
            decreasing_line_color='#FF3131'
        ), row=1, col=1)

        # 2. SMA 20 Overlay
        fig.add_trace(go.Scatter(
            x=data.index, y=data['SMA_20'],
            line=dict(color='orange', width=1.5),
            name='SMA 20'
        ), row=1, col=1)

        # 3. SMA 50 Overlay
        fig.add_trace(go.Scatter(
            x=data.index, y=data['SMA_50'],
            line=dict(color='cyan', width=1.5),
            name='SMA 50'
        ), row=1, col=1)
        
        # Overlay Alert / Highest High Threshold
        highest_close = data['Close'].max()
        fig.add_hline(y=highest_close, line_dash="dash", line_color="red", 
                      annotation_text=f"Alert: Period High ({highest_close:.2f})", 
                      annotation_position="bottom right", row=1, col=1)

        # 4. RSI Subplot
        fig.add_trace(go.Scatter(
            x=data.index, y=data['RSI'],
            line=dict(color='magenta', width=1.5),
            name='RSI'
        ), row=2, col=1)

        # Add RSI overbought/oversold levels
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # Update layout styling for "Bloomberg Terminal" look
        fig.update_layout(
            paper_bgcolor="#0c0d0f",
            plot_bgcolor="#0c0d0f",
            font=dict(color="#808080", family="JetBrains Mono, monospace", size=10),
            margin=dict(l=40, r=40, t=30, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis_rangeslider_visible=False
        )

        # Grid lines styling
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#222", zeroline=False)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#222", zeroline=False)

        # Serialize Plotly figure to JSON
        chart_json = fig.to_json()
        return JSONResponse(content=json.loads(chart_json))

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quote")
def get_quote(ticker: str = "AAPL"):
    """
    Fetch the latest quote data (current price & change).
    """
    try:
        t = yf.Ticker(ticker)
        # fast_info is faster for basic quotes, but let's try history for safety
        hist = t.history(period="5d")
        if hist.empty:
             return {"price": 0, "change": 0, "change_pct": 0, "symbol": ticker}
        
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        
        price = latest['Close']
        change = price - prev['Close']
        change_pct = (change / prev['Close']) * 100
        
        return {
            "symbol": ticker.upper(),
            "price": float(price),
            "change": float(change),
            "change_pct": float(change_pct)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quotes")
def get_quotes(tickers: str = "AAPL,MSFT,GOOGL"):
    """
    Fetch the latest quote data for multiple tickers in a comma-separated list.
    """
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(',')]
        data = yf.download(ticker_list, period="5d", progress=False)
        
        if data.empty:
            return JSONResponse(status_code=404, content={"error": "No data found for tickers."})
        
        results = []
        for ticker in ticker_list:
            try:
                # Handle single ticker return shape vs multi ticker return shape
                if len(ticker_list) == 1:
                    hist = data
                else:
                    hist = data.xs(ticker, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data[ticker]
                
                if hist.empty or hist['Close'].dropna().empty:
                    continue
                
                # Get the last two valid rows
                hist = hist.dropna(subset=['Close'])
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                
                price = latest['Close']
                change = price - prev['Close']
                change_pct = (change / prev['Close']) * 100
                
                results.append({
                    "symbol": ticker,
                    "price": float(price),
                    "change": float(change),
                    "change_pct": float(change_pct)
                })
            except Exception as inner_e:
                print(f"Error processing {ticker}: {inner_e}")
                continue
                
        return {"quotes": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/history")
def get_history(ticker: str = "AAPL", period: str = "1mo", interval: str = "1d"):
    """
    Fetch raw OHLC historical data for drawing the custom canvas chart.
    """
    try:
        # Yahoo Finance often throws an error if exactly 60d is requested for intraday data
        if period == "60d" and interval in ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]:
            period = "59d"
            
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return JSONResponse(status_code=404, content={"error": "No data found for this ticker."})

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
            
        # Drop NaN values that could break drawing
        data = data.dropna(subset=['Open', 'High', 'Low', 'Close'])
        
        history = []
        for i, (idx, row) in enumerate(data.iterrows()):
            history.append({
                "time": i,
                "date": idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, 'strftime') else str(idx),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close'])
            })
            
        return {"ticker": ticker.upper(), "data": history}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/valuation")
def get_valuation(ticker: str = "AAPL"):
    """
    Fetch advanced valuation models (DuPont, EV/EBITDA, DCF) for a ticker.
    """
    try:
        t = yf.Ticker(ticker)
        income_statement = t.financials
        balance_sheet = t.balance_sheet
        cash_flow = t.cashflow
        info = t.info
        
        if income_statement.empty or balance_sheet.empty or cash_flow.empty:
            return JSONResponse(status_code=404, content={"error": "Insufficient financial data."})
            
        latest_is = income_statement.iloc[:, 0]
        latest_bs = balance_sheet.iloc[:, 0]
        latest_cf = cash_flow.iloc[:, 0]
        
        # Fallbacks for Data Extraction
        total_revenue = latest_is.get('Total Revenue', latest_is.get('Operating Revenue', latest_is.get('Total Operating Revenue')))
        
        # Handle Gross Profit Fallback (Banks often don't have it, we use 0 or skip)
        gross_profit = latest_is.get('Gross Profit')
        if gross_profit is None and total_revenue is not None:
            cogs = latest_is.get('Cost Of Revenue', 0)
            gross_profit = total_revenue - cogs if cogs else None
            
        net_income = latest_is.get('Net Income', latest_is.get('Net Income Common Stockholders'))
        
        current_assets = latest_bs.get('Current Assets', latest_bs.get('Total Current Assets'))
        current_liabilities = latest_bs.get('Current Liabilities', latest_bs.get('Total Current Liabilities'))
        total_assets = latest_bs.get('Total Assets')
        
        total_debt = latest_bs.get('Total Debt', latest_bs.get('Long Term Debt', 0))
        equity = latest_bs.get('Stockholders Equity', latest_bs.get('Total Stockholder Equity', latest_bs.get('Common Stock Equity')))
        cash_and_equiv = latest_bs.get('Cash And Cash Equivalents', latest_bs.get('Cash', 0))
        
        operating_cf = latest_cf.get('Operating Cash Flow', latest_cf.get('Total Cash From Operating Activities'))
        capex = latest_cf.get('Capital Expenditure', latest_cf.get('Investments In Property Plant And Equipment'))
        
        ebitda = latest_is.get('EBITDA')
        if ebitda is None:
            ebit = latest_is.get('EBIT', latest_is.get('Operating Income', 0))
            da = latest_cf.get('Depreciation And Amortization', latest_cf.get('Depreciation', 0))
            ebitda = ebit + da if ebit else None

        # 1. Ratios
        current_ratio = float(current_assets / current_liabilities) if current_assets and current_liabilities else None
        gross_margin = float(gross_profit / total_revenue) if gross_profit is not None and total_revenue else None
        debt_to_equity = float(total_debt / equity) if total_debt is not None and equity else None
        
        # 2. DuPont
        roe = None
        if all(v is not None for v in [net_income, total_revenue, total_assets, equity]) and total_revenue != 0 and total_assets != 0 and equity != 0:
            net_profit_margin = net_income / total_revenue
            asset_turnover = total_revenue / total_assets
            equity_multiplier = total_assets / equity
            roe = float(net_profit_margin * asset_turnover * equity_multiplier)
            
        # 3. EV/EBITDA
        market_cap = info.get('marketCap')
        ev_ebitda = None
        if market_cap and ebitda and ebitda != 0:
            enterprise_value = market_cap + (total_debt or 0) - (cash_and_equiv or 0)
            ev_ebitda = float(enterprise_value / ebitda)
            
        # 4. DCF
        dcf_upside = None
        dcf_price = None
        if operating_cf is not None and capex is not None:
            fcf = operating_cf + capex if capex < 0 else operating_cf - capex
            growth_rate = 0.05
            perpetual_rate = 0.025
            wacc = 0.08
            shares_outstanding = info.get('sharesOutstanding', 1)
            
            projected_fcf = [fcf * (1 + growth_rate)**i for i in range(1, 6)]
            terminal_value = (projected_fcf[-1] * (1 + perpetual_rate)) / (wacc - perpetual_rate)
            pv_fcf = sum([cf / ((1 + wacc)**(i+1)) for i, cf in enumerate(projected_fcf)])
            pv_terminal_value = terminal_value / ((1 + wacc)**5)
            
            intrinsic_ev = pv_fcf + pv_terminal_value
            implied_equity_value = intrinsic_ev - (total_debt or 0) + (cash_and_equiv or 0)
            dcf_price = float(implied_equity_value / shares_outstanding)
            
            current_price = info.get('currentPrice', info.get('regularMarketPrice'))
            if current_price:
                dcf_upside = float((dcf_price - current_price) / current_price)
                
        return {
            "symbol": ticker.upper(),
            "ratios": {
                "current_ratio": current_ratio,
                "gross_margin": gross_margin,
                "debt_to_equity": debt_to_equity
            },
            "dupont_roe": roe,
            "ev_ebitda": ev_ebitda,
            "dcf": {
                "intrinsic_price": dcf_price,
                "upside": dcf_upside
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/news")
def get_general_news():
    """
    Fetch general market news by looking at a major index ticker (SPY).
    """
    try:
        t = yf.Ticker("SPY")
        news = t.news
        if not news:
            return {"status": "success", "news": []}
        
        formatted_news = []
        import datetime
        for item in news:
            if "content" in item:
                content_item = item["content"]
                title = content_item.get("title", "")
                pub_time = content_item.get("pubDate")
            else:
                title = item.get("title", "")
                pub_time = item.get("providerPublishTime")

            time_str = "00:00"
            if pub_time:
                if isinstance(pub_time, (int, float)):
                    dt = datetime.datetime.fromtimestamp(pub_time)
                    time_str = dt.strftime('%H:%M')
                elif isinstance(pub_time, str):
                    try:
                        dt = datetime.datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')
                    except Exception:
                        if len(pub_time) > 16:
                            time_str = pub_time[11:16]

            if title:
                formatted_news.append({
                    "time": time_str,
                    "title": title
                })
            
        return {"status": "success", "news": formatted_news}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/backtest")
def get_backtest(ticker: str = "AAPL", strategy: str = "EMA", start: str = "2020-01-01", end: str = "2024-01-01"):
    """
    Run backtest using vectorbt with strategy parameter.
    """
    try:
        results = run_vectorbt_backtest(ticker, start, end, strategy)
        return {"status": "success", "data": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/sentiment")
def get_sentiment(ticker: str = "AAPL"):
    """
    Fetch recent news using yfinance and run Vader Sentiment Analysis to determine
    the average compound polarity of the headlines.
    """
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return {"status": "success", "ticker": ticker, "average_sentiment": 0, "news": []}
            
        analyzer = SentimentIntensityAnalyzer()
        
        total_compound = 0
        analyzed_news = []
        for item in news:
            if "content" in item:
                content_item = item["content"]
                title = content_item.get("title", "")
                publisher = content_item.get("provider", {}).get("displayName", "")
            else:
                title = item.get("title", "")
                publisher = item.get("publisher", "")

            if not title:
                continue

            score = analyzer.polarity_scores(title)
            compound = score['compound']
            total_compound += compound
            analyzed_news.append({
                "title": title,
                "publisher": publisher,
                "score": compound
            })
            
        avg_score = total_compound / len(analyzed_news) if analyzed_news else 0
        
        return {
            "status": "success",
            "ticker": ticker, 
            "average_sentiment": avg_score, 
            "news": analyzed_news
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/options")
def get_options(ticker: str = "AAPL"):
    """
    Fetch near-term options chain and calculate the Put/Call Volume Ratio.
    """
    try:
        t = yf.Ticker(ticker)
        # Check if options are available
        if not t.options:
            return JSONResponse(status_code=404, content={"error": "No options data available."})
            
        # Get the nearest expiration date
        nearest_exp = t.options[0]
        chain = t.option_chain(nearest_exp)
        
        calls = chain.calls
        puts = chain.puts
        
        call_vol = int(calls['volume'].sum()) if 'volume' in calls and not calls['volume'].dropna().empty else 0
        put_vol = int(puts['volume'].sum()) if 'volume' in puts and not puts['volume'].dropna().empty else 0
        
        put_call_ratio = float(put_vol / call_vol) if call_vol > 0 else None
        
        return {
            "symbol": ticker.upper(),
            "expiration": nearest_exp,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "put_call_ratio": put_call_ratio,
            "sentiment": "Bearish" if put_call_ratio and put_call_ratio > 1 else ("Bullish" if put_call_ratio and put_call_ratio < 1 else "Neutral")
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/portfolio")
def get_portfolio(holdings: str = "AAPL:50,MSFT:100,GOOGL:20"):
    """
    Fetch the portfolio and risk optimization data based on current holdings.
    """
    try:
        from portfolio_risk import get_portfolio_risk_data
        
        # Parse holdings str into dict
        holdings_dict = {}
        for item in holdings.split(','):
            if ':' in item:
                ticker, shares = item.split(':')
                holdings_dict[ticker.strip().upper()] = float(shares.strip())
            else:
                # Fallback
                holdings_dict[item.strip().upper()] = 1.0
                
        data = get_portfolio_risk_data(holdings=holdings_dict)
        return data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# Serve the static HTML/CSS/JS files from the current directory
# curr_dir = os.path.dirname(os.path.abspath(__file__))
# app.mount("/", StaticFiles(directory=curr_dir, html=True), name="static")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("index:app", host="127.0.0.1", port=8000, reload=True)

