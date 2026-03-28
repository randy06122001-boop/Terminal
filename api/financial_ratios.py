# %% [markdown]
# # Financial Statements & Advanced Valuation Models with yfinance
# This script extracts financial statements, calculates key ratios, 
# and builds advanced valuation models including DuPont Analysis, EV/EBITDA, and DCF.

# %%
import yfinance as yf
import pandas as pd

# Define the ticker symbol (e.g., Apple)
ticker_symbol = "AAPL"
stock = yf.Ticker(ticker_symbol)

# %% [markdown]
# ## 1. Pull Core Financial Statements
# Extract Income Statement, Balance Sheet, and Cash Flow DataFrames.

# %%
income_statement = stock.financials
balance_sheet = stock.balance_sheet
cash_flow = stock.cashflow
info = stock.info

print(f"--- {ticker_symbol} Financial Statements Loaded ---")
print(f"Most recent reporting date: {income_statement.columns[0].date()}")

# Get the most recent year's data
latest_is = income_statement.iloc[:, 0]
latest_bs = balance_sheet.iloc[:, 0]
latest_cf = cash_flow.iloc[:, 0]

# %% [markdown]
# ## 2. Core Financial Ratios (Liquidity & Profitability)

# %%
print(f"\n--- 1. Core Financial Ratios ---")

current_assets = latest_bs.get('Current Assets')
current_liabilities = latest_bs.get('Current Liabilities')
if current_assets and current_liabilities:
    print(f"Current Ratio:          {current_assets / current_liabilities:.2f}")

gross_profit = latest_is.get('Gross Profit')
total_revenue = latest_is.get('Total Revenue')
if gross_profit and total_revenue:
    print(f"Gross Margin:           {gross_profit / total_revenue:.2%}")

total_debt = latest_bs.get('Total Debt')
equity = latest_bs.get('Stockholders Equity', latest_bs.get('Total Stockholder Equity'))
if total_debt is not None and equity is not None:
    print(f"Debt to Equity Ratio:   {total_debt / equity:.2f}")


# %% [markdown]
# ## 3. Advanced Model: DuPont Analysis (Return on Equity Breakdown)
# Breaks down ROE into three components: Net Margin, Asset Turnover, and Financial Leverage.

# %%
print(f"\n--- 2. DuPont Analysis ---")

net_income = latest_is.get('Net Income')
total_assets = latest_bs.get('Total Assets')

if all(v is not None for v in [net_income, total_revenue, total_assets, equity]):
    net_profit_margin = net_income / total_revenue
    asset_turnover = total_revenue / total_assets
    equity_multiplier = total_assets / equity
    roe = net_profit_margin * asset_turnover * equity_multiplier
    
    print(f"Net Profit Margin:      {net_profit_margin:.2%}")
    print(f"Asset Turnover:         {asset_turnover:.2f}x")
    print(f"Equity Multiplier:      {equity_multiplier:.2f}x")
    print(f"Return on Equity (ROE): {roe:.2%} (DuPont Derived)")
else:
    print("Insufficient data for DuPont Analysis.")


# %% [markdown]
# ## 4. Advanced Model: Enterprise Value to EBITDA (EV/EBITDA)
# A key ratio used to determine the value of a company relative to its cash earnings.

# %%
print(f"\n--- 3. EV/EBITDA Valuation ---")

market_cap = info.get('marketCap')
cash_and_equiv = latest_bs.get('Cash And Cash Equivalents', 0)

# Estimate EBITDA (sometimes available directly in Income Statement, otherwise EBIT + D&A)
ebitda = latest_is.get('EBITDA', latest_is.get('EBIT', 0) + latest_cf.get('Depreciation And Amortization', 0))

if market_cap and total_debt is not None and ebitda:
    enterprise_value = market_cap + total_debt - cash_and_equiv
    ev_ebitda = enterprise_value / ebitda
    
    print(f"Enterprise Value (EV):  ${enterprise_value:,.0f}")
    print(f"EBITDA:                 ${ebitda:,.0f}")
    print(f"EV / EBITDA Multiple:   {ev_ebitda:.2f}x")
else:
    print("Insufficient data for EV/EBITDA Calculation.")


# %% [markdown]
# ## 5. Advanced Model: Simplified Discounted Cash Flow (DCF)
# Estimates intrinsic value by projecting future Free Cash Flows and discounting them to the present.

# %%
print(f"\n--- 4. Simplified DCF Valuation ---")

operating_cf = latest_cf.get('Operating Cash Flow')
capex = latest_cf.get('Capital Expenditure')

if operating_cf is not None and capex is not None:
    # CapEx is often reported as a negative number
    fcf = operating_cf + capex if capex < 0 else operating_cf - capex
    
    # Model Assumptions (Adjust these for real analysis)
    growth_rate = 0.05       # 5% projected growth rate for next 5 years
    perpetual_rate = 0.025   # 2.5% terminal growth rate
    wacc = 0.08              # 8% Weighted Average Cost of Capital (Discount Rate)
    shares_outstanding = info.get('sharesOutstanding', 1)
    
    print(f"Base Free Cash Flow:    ${fcf:,.0f}")
    print(f"Assumed Growth Rate:    {growth_rate:.1%}")
    print(f"Assumed WACC:           {wacc:.1%}")
    
    # Project FCF for 5 years
    projected_fcf = [fcf * (1 + growth_rate)**i for i in range(1, 6)]
    
    # Calculate Terminal Value and Present Values
    terminal_value = (projected_fcf[-1] * (1 + perpetual_rate)) / (wacc - perpetual_rate)
    pv_fcf = sum([cf / ((1 + wacc)**(i+1)) for i, cf in enumerate(projected_fcf)])
    pv_terminal_value = terminal_value / ((1 + wacc)**5)
    
    # Intrinsic Enterprise Value -> Intrinsic Equity Value
    intrinsic_ev = pv_fcf + pv_terminal_value
    implied_equity_value = intrinsic_ev - (total_debt or 0) + cash_and_equiv
    intrinsic_price = implied_equity_value / shares_outstanding
    
    current_price = info.get('currentPrice', info.get('regularMarketPrice'))
    
    print(f"Intrinsic Value/Share:  ${intrinsic_price:.2f}")
    if current_price:
        print(f"Current Price:          ${current_price:.2f}")
        upside = (intrinsic_price - current_price) / current_price
        diff_str = f"+{upside:.2%}" if upside > 0 else f"{upside:.2%}"
        print(f"Implied Upside/Downside:{diff_str}")
else:
    print("Insufficient data for DCF Calculation.")
