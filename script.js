// Bloomberg Terminal Logic
document.addEventListener('DOMContentLoaded', () => {
    // 1. Clock
    const clockElement = document.getElementById('clock');
    function updateClock() {
        const now = new Date();
        clockElement.textContent = now.toTimeString().split(' ')[0];
    }
    setInterval(updateClock, 1000);
    updateClock();

    // 2. Market Pulse Data (Live)
    const pulseSymbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMZN', 'META'];
    const pulseList = document.getElementById('pulse-list');
    
    async function populatePulse() {
        try {
            const res = await fetch(`/api/quotes?tickers=${pulseSymbols.join(',')}`);
            if (!res.ok) return;
            const data = await res.json();
            
            pulseList.innerHTML = data.quotes.map(s => `
                <div class="pulse-item" onclick="document.querySelector('.command-input').value='${s.symbol}'; document.querySelector('.command-input').dispatchEvent(new KeyboardEvent('keydown', {key:'Enter'}));">
                    <span class="pulse-symbol">${s.symbol} US</span>
                    <span class="pulse-price ${s.change >= 0 ? 'green' : 'red'}">${s.price.toFixed(2)}</span>
                    <span class="pulse-change ${s.change >= 0 ? 'green' : 'red'}">${s.change >= 0 ? '+' : ''}${s.change.toFixed(2)} (${s.change_pct.toFixed(2)}%)</span>
                </div>
            `).join('');
            
            // Also update the bottom ticker using the same data
            updateTicker(data.quotes);
        } catch (err) {
            console.error("Failed to fetch pulse data:", err);
        }
    }

    function updateTicker(quotes) {
        const tickerHtml = quotes.map(q => `
            <div class="ticker-item">
                <span class="ticker-symbol">${q.symbol}</span> 
                <span class="ticker-val">${q.price.toFixed(2)}</span> 
                <span class="ticker-chg ${q.change >= 0 ? 'green' : 'red'}">${q.change >= 0 ? '+' : ''}${q.change_pct.toFixed(2)}%</span>
            </div>
        `).join('');
        
        const wrapper = document.querySelector('.ticker-wrapper');
        // Double it for seamless scrolling
        wrapper.innerHTML = tickerHtml + tickerHtml;
    }

    populatePulse();

    // 3. News Feed
    const newsList = document.getElementById('news-list');
    
    async function fetchLiveNews() {
        try {
            const res = await fetch('/api/news');
            if (!res.ok) return;
            const data = await res.json();
            
            if (data.status === 'success' && data.news && data.news.length > 0) {
                newsList.innerHTML = data.news.map(n => `
                    <div class="news-item">
                        <span class="news-time">${n.time}</span>
                        <span class="news-title">${n.title}</span>
                    </div>
                `).join('');
            }
        } catch (err) {
            console.error("Failed to fetch live news:", err);
        }
    }
    
    // Initial fetch
    fetchLiveNews();

    // 4. Custom Candlestick Chart
    const canvas = document.getElementById('main-chart');
    const ctx = canvas.getContext('2d');
    let chartData = [];
    let currentTicker = 'AAPL';
    let currentInterval = '5m';
    let currentPeriod = '60d';
    let viewStartIdx = 0;
    let viewEndIdx = 0;

    async function fetchChartData(ticker) {
        try {
            const res = await fetch(`/api/history?ticker=${ticker}&period=${currentPeriod}&interval=${currentInterval}`);
            if (!res.ok) throw new Error("Chart data fetch failed");
            const data = await res.json();
            
            chartData = data.data;
            viewStartIdx = Math.max(0, chartData.length - 100); // Default view shows last 100 periods
            viewEndIdx = chartData.length;
            drawChart();
            
            // Initial quote update for header
            if (chartData.length > 0) {
                const last = chartData[chartData.length - 1];
                const first = chartData[0];
                updateHeaderPrice(last.close, last.close - first.open, ((last.close - first.open) / first.open) * 100);
            }
        } catch (err) {
            console.error("Error fetching chart:", err);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#FF3131';
            ctx.font = '14px Inter';
            ctx.fillText(`Error loading data for ${ticker}`, 40, 40);
        }
    }

    function updateHeaderPrice(price, change, changePct) {
        const priceEl = document.getElementById('main-price');
        const changeEl = document.querySelector('.price-change');
        
        priceEl.textContent = price.toFixed(2);
        const sign = change >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
        
        const colorClass = change >= 0 ? 'green' : 'red';
        priceEl.className = `last-price ${colorClass}`;
        changeEl.className = `price-change ${colorClass}`;
    }

    function resizeCanvas() {
        const parent = canvas.parentElement;
        if (!parent) return;
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
        drawChart(); // Redraw immediately on resize
    }

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
    fetchChartData(currentTicker);

    function drawChart() {
        if (chartData.length === 0) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const visibleData = chartData.slice(viewStartIdx, viewEndIdx);
        if (visibleData.length === 0) return;

        const padding = 40;
        const drawWidth = canvas.width - padding * 2;
        const drawHeight = canvas.height - padding * 2;
        
        const minPriceRaw = Math.min(...visibleData.map(d => d.low));
        const maxPriceRaw = Math.max(...visibleData.map(d => d.high));
        const pricePadding = (maxPriceRaw - minPriceRaw) * 0.05 || 2;
        const minPrice = minPriceRaw - pricePadding;
        const maxPrice = maxPriceRaw + pricePadding;
        const priceRange = maxPrice - minPrice;
        
        const candleWidth = (drawWidth / visibleData.length) * 0.8;
        const candleGap = (drawWidth / visibleData.length) * 0.2;

        // Draw horizontal grid lines and price labels
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1;
        ctx.textAlign = 'left';
        for(let i = 0; i <= 5; i++) {
            const y = padding + (drawHeight / 5) * i;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(canvas.width - padding, y);
            ctx.stroke();

            // Price labels
            ctx.fillStyle = '#808080';
            ctx.font = '10px JetBrains Mono';
            const priceLabel = (maxPrice - (priceRange / 5) * i).toFixed(2);
            ctx.fillText(priceLabel, canvas.width - padding + 5, y + 4);
        }

        // Draw vertical grid lines and time labels
        if (visibleData.length > 0) {
            const labelInterval = Math.max(1, Math.floor(visibleData.length / 5));
            ctx.textAlign = 'center';
            for(let i = 0; i < visibleData.length; i += labelInterval) {
                if (i === 0) continue; // Skip first vertical line to avoid overlap with y-axis
                const x = padding + i * (candleWidth + candleGap);
                
                // Vertical grid line
                ctx.strokeStyle = '#1a1a1a';
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, canvas.height - padding);
                ctx.stroke();
                
                // Date and Time label
                const dateStr = visibleData[i].date;
                const parts = dateStr.split(' ');
                
                ctx.fillStyle = '#808080';
                ctx.font = '10px JetBrains Mono';
                
                if (parts.length > 1) {
                    // Intraday: show Date and Time on two lines
                    const datePart = parts[0].substring(5); // "MM-DD"
                    const timePart = parts[1]; // "HH:MM"
                    ctx.fillText(datePart, x, canvas.height - padding + 14);
                    ctx.fillText(timePart, x, canvas.height - padding + 26);
                } else {
                    // Daily: show full Date
                    ctx.fillText(parts[0], x, canvas.height - padding + 18);
                }
            }
            ctx.textAlign = 'left';
        }

        visibleData.forEach((d, i) => {
            const x = padding + i * (candleWidth + candleGap);
            const yHigh = padding + (1 - (d.high - minPrice) / priceRange) * drawHeight;
            const yLow = padding + (1 - (d.low - minPrice) / priceRange) * drawHeight;
            const yOpen = padding + (1 - (d.open - minPrice) / priceRange) * drawHeight;
            const yClose = padding + (1 - (d.close - minPrice) / priceRange) * drawHeight;

            const isUp = d.close >= d.open;
            ctx.strokeStyle = isUp ? '#00FF81' : '#FF3131';
            ctx.fillStyle = isUp ? '#00FF81' : '#FF3131';
            ctx.lineWidth = 1;

            // Wick
            ctx.beginPath();
            ctx.moveTo(x + candleWidth / 2, yHigh);
            ctx.lineTo(x + candleWidth / 2, yLow);
            ctx.stroke();

            // Body
            const bodyHeight = Math.abs(yClose - yOpen) || 1;
            ctx.fillRect(x, Math.min(yOpen, yClose), candleWidth, bodyHeight);
        });

        // Current Price Line
        const lastCandle = visibleData[visibleData.length - 1];
        if (lastCandle) {
            const lastY = padding + (1 - (lastCandle.close - minPrice) / priceRange) * drawHeight;
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = '#FFA500';
            ctx.beginPath();
            ctx.moveTo(padding, lastY);
            ctx.lineTo(canvas.width - padding, lastY);
            ctx.stroke();
            ctx.setLineDash([]);


            // Label on current price
            ctx.fillStyle = '#FFA500';
            ctx.fillRect(canvas.width - padding, lastY - 8, padding, 16);
            ctx.fillStyle = '#000';
            ctx.fillText(lastCandle.close.toFixed(2), canvas.width - padding + 2, lastY + 4);
        }
    }

    drawChart();

    // Zoom and Pan Interactions
    let isDragging = false;
    let lastMouseX = 0;

    canvas.style.cursor = 'crosshair';

    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomSpeed = Math.max(1, Math.floor((viewEndIdx - viewStartIdx) * 0.1));
        
        if (e.deltaY < 0) {
            // Zoom In (show fewer candles)
            if (viewEndIdx - viewStartIdx > 10) {
                const padding = 40;
                const drawWidth = canvas.width - padding * 2;
                const mouseXOffset = e.offsetX - padding;
                const ratio = Math.max(0, Math.min(1, mouseXOffset / drawWidth));
                
                const shiftLeft = Math.floor(zoomSpeed * ratio);
                const shiftRight = zoomSpeed - shiftLeft;
                
                viewStartIdx += shiftLeft;
                viewEndIdx -= shiftRight;
                if (viewEndIdx - viewStartIdx < 10) viewStartIdx = viewEndIdx - 10;
                drawChart();
            }
        } else {
            // Zoom Out (show more candles)
            const padding = 40;
            const drawWidth = canvas.width - padding * 2;
            const mouseXOffset = e.offsetX - padding;
            const ratio = Math.max(0, Math.min(1, mouseXOffset / drawWidth));
            
            const shiftLeft = Math.floor(zoomSpeed * ratio);
            const shiftRight = zoomSpeed - shiftLeft;
            
            viewStartIdx -= shiftLeft;
            viewEndIdx += shiftRight;
            
            if (viewStartIdx < 0) viewStartIdx = 0;
            if (viewEndIdx > chartData.length) viewEndIdx = chartData.length;
            drawChart();
        }
    });

    canvas.addEventListener('mousedown', (e) => {
        isDragging = true;
        lastMouseX = e.offsetX;
        canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
        canvas.style.cursor = 'crosshair';
    });

    canvas.addEventListener('mousemove', (e) => {
        if (!isDragging || chartData.length === 0) return;
        const deltaX = e.offsetX - lastMouseX;
        
        const padding = 40;
        const drawWidth = canvas.width - padding * 2;
        const windowSize = viewEndIdx - viewStartIdx;
        const candlePixelWidth = drawWidth / windowSize;
        
        if (Math.abs(deltaX) > candlePixelWidth) {
            const shiftCandles = Math.round(deltaX / candlePixelWidth);
            lastMouseX = e.offsetX; // Reset anchor after movement is processed
            
            const newStart = viewStartIdx - shiftCandles;
            const newEnd = viewEndIdx - shiftCandles;
            
            if (newStart >= 0 && newEnd <= chartData.length) {
                viewStartIdx = newStart;
                viewEndIdx = newEnd;
            } else if (newStart < 0) {
                viewStartIdx = 0;
                viewEndIdx = windowSize;
            } else if (newEnd > chartData.length) {
                viewEndIdx = chartData.length;
                viewStartIdx = chartData.length - windowSize;
            }
            drawChart();
        }
    });

    // Timeframe Button Logic
    const tfBtns = document.querySelectorAll('.tf-btn');
    tfBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active styling
            tfBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Set new parameters
            currentInterval = e.target.getAttribute('data-interval');
            currentPeriod = e.target.getAttribute('data-period');
            
            // Fetch updated data
            fetchChartData(currentTicker);
        });
    });

    // 5. Valuation API Call
    async function fetchValuation(ticker) {
        const valList = document.getElementById('valuation-list');
        valList.innerHTML = '<span style="color: var(--grey);">Calculating models...</span>';
        try {
            const res = await fetch(`/api/valuation?ticker=${ticker}`);
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            const formatPercent = (val) => val != null ? (val * 100).toFixed(2) + '%' : 'N/A';
            const formatNum = (val) => val != null ? val.toFixed(2) : 'N/A';
            
            const upside = data.dcf.upside;
            const upsideClass = upside != null ? (upside >= 0 ? 'green' : 'red') : '';
            const upsideStr = upside != null ? `${upside >= 0 ? '+' : ''}${(upside * 100).toFixed(2)}%` : 'N/A';

            valList.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>DuPont ROE:</span> <span class="green">${formatPercent(data.dupont_roe)}</span></div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>EV / EBITDA:</span> <span>${formatNum(data.ev_ebitda)}x</span></div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>Gross Margin:</span> <span>${formatPercent(data.ratios.gross_margin)}</span></div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;"><span>Debt/Equity:</span> <span>${formatNum(data.ratios.debt_to_equity)}</span></div>
                <div style="border-top: 1px dashed var(--border-color); padding-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between;">
                    <span>DCF Value:</span> <span style="font-weight: bold;">$${formatNum(data.dcf.intrinsic_price)}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Implied Upside:</span> <span class="${upsideClass}" style="font-weight: bold;">${upsideStr}</span>
                </div>
            `;
        } catch (err) {
            valList.innerHTML = `<span class="red">Error loading models for ${ticker}</span>`;
        }
    }

    // 5.5 Options API Call
    async function fetchOptions(ticker) {
        const optList = document.getElementById('options-list');
        if (!optList) return;
        optList.innerHTML = '<span style="color: var(--grey);">Calculating options sentiment...</span>';
        try {
            const res = await fetch(`/api/options?ticker=${ticker}`);
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            const formatNum = (val) => val != null ? val.toLocaleString() : 'N/A';
            const formatRatio = (val) => val != null ? val.toFixed(2) : 'N/A';
            
            const pcr = data.put_call_ratio;
            const pcrClass = pcr != null ? (pcr < 1 ? 'green' : (pcr > 1 ? 'red' : '')) : '';
            const sentimentClass = data.sentiment === 'Bullish' ? 'green' : (data.sentiment === 'Bearish' ? 'red' : '');

            optList.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>Nearest Expiry:</span> <span style="color: var(--cyan);">${data.expiration}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>Call Volume:</span> <span>${formatNum(data.call_volume)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span>Put Volume:</span> <span>${formatNum(data.put_volume)}</span>
                </div>
                <div style="border-top: 1px dashed var(--border-color); padding-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between;">
                    <span>Put/Call Ratio:</span> <span class="${pcrClass}" style="font-weight: bold;">${formatRatio(pcr)}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Implied Sentiment:</span> <span class="${sentimentClass}" style="font-weight: bold;">${data.sentiment || 'N/A'}</span>
                </div>
            `;
        } catch (err) {
            optList.innerHTML = `<span class="red">Options unavailable for ${ticker}</span>`;
        }
    }

    // Call it initially
    fetchValuation('AAPL');
    fetchOptions('AAPL');

    // 6. Command Logic
    const mainView = document.getElementById('main-view');
    const portfolioView = document.getElementById('portfolio-view');
    const chartHeaderInfo = document.querySelector('.chart-header-info');

    async function loadPortfolioData() {
        try {
            const holdings = document.getElementById('port-tickers').value;
            const res = await fetch(`/api/portfolio?holdings=${encodeURIComponent(holdings)}`);
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            // Render Current Metrics
            const curr = data.current_portfolio;
            document.getElementById('current-metrics').innerHTML = `
                <div class="stat"><span class="lbl">VALUE:</span> <span class="val white">$${curr.value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</span></div>
                <div class="stat"><span class="lbl">EXP RET:</span> <span class="val ${(curr.expected_return >= 0) ? 'green' : 'red'}">${(curr.expected_return * 100).toFixed(2)}%</span></div>
                <div class="stat"><span class="lbl">VOLATILITY:</span> <span class="val amber">${(curr.annual_volatility * 100).toFixed(2)}%</span></div>
                <div class="stat"><span class="lbl">SHARPE:</span> <span class="val cyan">${curr.sharpe_ratio.toFixed(2)}</span></div>
            `;

            // Render Optimal Metrics
            const opt = data.optimal_portfolio;
            document.getElementById('portfolio-metrics').innerHTML = `
                <div class="stat"><span class="lbl">EXP RET:</span> <span class="val ${(opt.expected_return >= 0) ? 'green' : 'red'}">${(opt.expected_return * 100).toFixed(2)}%</span></div>
                <div class="stat"><span class="lbl">VOLATILITY:</span> <span class="val amber">${(opt.annual_volatility * 100).toFixed(2)}%</span></div>
                <div class="stat"><span class="lbl">SHARPE:</span> <span class="val cyan">${opt.sharpe_ratio.toFixed(2)}</span></div>
            `;
            
            // Render Allocation Bars
            const holdingsMap = curr.holdings;
            const allTickers = Object.keys(holdingsMap);
            const currWeights = curr.weights;
            const optWeights = opt.max_sharpe_weights;
            
            const chartHtml = allTickers.map(ticker => {
                const cWeight = currWeights[ticker] || 0;
                const oWeight = optWeights[ticker] || 0;
                const cPct = (cWeight * 100).toFixed(1);
                const oPct = (oWeight * 100).toFixed(1);
                
                return `
                    <div class="alloc-row" style="margin-bottom: 20px;">
                        <div class="alloc-lbl" style="width: 70px;">${ticker}</div>
                        <div style="flex: 1; display: flex; flex-direction: column; gap: 4px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 45px; font-size: 0.75rem; color: var(--grey);">CURR</div>
                                <div class="alloc-bar-container" style="background: #111; height: 8px;">
                                    <div class="alloc-bar" style="width: ${cPct}%; background: var(--grey);"></div>
                                </div>
                                <div class="alloc-val" style="width: 45px; font-size: 0.8rem; color: var(--white);">${cPct}%</div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 45px; font-size: 0.75rem; color: var(--cyan);">TGT</div>
                                <div class="alloc-bar-container" style="background: #111; height: 8px;">
                                    <div class="alloc-bar" style="width: ${oPct}%; background: linear-gradient(90deg, #0088cc, var(--cyan));"></div>
                                </div>
                                <div class="alloc-val" style="width: 45px; font-size: 0.8rem; color: var(--cyan);">${oPct}%</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            document.getElementById('allocation-chart').innerHTML = `<h3 style="color:var(--grey); font-size:0.9rem; margin-bottom:16px;">ASSET WEIGHT COMPARISON</h3>` + chartHtml;
            
            // Render Monte Carlo
            const mc = data.monte_carlo;
            if (mc.num_simulated > 0) {
                document.getElementById('mc-stats').innerHTML = `
                    <div class="mc-row"><span>Max Sharpe Portfolio:</span> <span class="cyan">Sharpe ${mc.max_sharpe.sharpe.toFixed(2)} | Ret ${(mc.max_sharpe.return * 100).toFixed(1)}% | Vol ${(mc.max_sharpe.volatility * 100).toFixed(1)}%</span></div>
                    <div class="mc-row"><span>Min Volatility Portfolio:</span> <span class="amber">Sharpe ${mc.min_vol.sharpe.toFixed(2)} | Ret ${(mc.min_vol.return * 100).toFixed(1)}% | Vol ${(mc.min_vol.volatility * 100).toFixed(1)}%</span></div>
                `;
            } else {
                document.getElementById('mc-stats').innerHTML = `<div class="mc-row"><span>N/A (Provide multiple tickers to simulate correlation frontiers)</span></div>`;
            }

            // Render Trades
            const trades = data.trades;
            let tradesHtml = Object.entries(trades).map(([ticker, diff]) => {
                const action = diff > 0 ? 'BUY' : 'SELL';
                const color = diff > 0 ? 'green' : 'red';
                return `<div class="mc-row"><span>${ticker}</span> <span class="${color}">${action} ${Math.abs(diff)} shares</span></div>`;
            }).join('');
            if (tradesHtml === "") tradesHtml = `<div class="mc-row"><span>Portfolio is perfectly aligned.</span></div>`;
            
            document.getElementById('discrete-stats').innerHTML = 
                tradesHtml + 
                `<div class="mc-row" style="margin-top:8px; border-top:1px dashed #333; padding-top:8px;"><span>Target Cash Balance:</span> <span class="amber">$${opt.leftover.toFixed(2)}</span></div>`;

        } catch (e) {
            document.getElementById('portfolio-metrics').innerHTML = `<div style="color:var(--red)">ERROR: ${e.message}</div>`;
            document.getElementById('current-metrics').innerHTML = ``;
        }
    }

    const portUpdateBtn = document.getElementById('port-update-btn');
    if(portUpdateBtn) {
        portUpdateBtn.addEventListener('click', () => {
            document.getElementById('portfolio-metrics').innerHTML = '<div class="stat" style="color:var(--amber)">RE-OPTIMIZING... [▓▓▓▒░░]</div>';
            document.getElementById('current-metrics').innerHTML = '<div class="stat" style="color:var(--amber)">FETCHING LIVE PRICES...</div>';
            loadPortfolioData();
        });
    }

    const cmdInput = document.querySelector('.command-input');
    cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const val = cmdInput.value.toUpperCase().trim();
            if (val) {
                cmdInput.value = '';
                if (val === 'BACK') {
                    // Return to standard chart view
                    if (mainView) {
                        mainView.style.display = 'block';
                        chartHeaderInfo.style.display = 'flex';
                        portfolioView.style.display = 'none';
                    }
                    const btResults = document.getElementById('backtest-results');
                    const newsList = document.getElementById('news-list');
                    const sidebarTitle = document.getElementById('sidebar-title');
                    const sentResults = document.getElementById('sentiment-results');
                    if (newsList) {
                        if (btResults) btResults.style.display = 'none';
                        if (sentResults) sentResults.style.display = 'none';
                        newsList.style.display = 'block';
                        if (sidebarTitle) sidebarTitle.textContent = 'TOP NEWS';
                    }
                    // Reset ticker if it was accidentally set to BACK previously
                    if (currentTicker === 'BACK') {
                        currentTicker = 'AAPL';
                        document.querySelector('.symbol-name').textContent = 'AAPL US Equity';
                        fetchChartData('AAPL');
                        fetchValuation('AAPL');
                        fetchOptions('AAPL');
                    }
                } else if (val === 'PORT' || val === 'RISK') {
                    // Show Portfolio Mode
                    if (mainView && mainView.style.display !== 'none') {
                        mainView.style.display = 'none';
                        chartHeaderInfo.style.display = 'none';
                        portfolioView.style.display = 'flex';
                        document.getElementById('portfolio-metrics').innerHTML = '<div class="stat" style="color:var(--amber)">LOADING OPTIMIZATION DATA... [▓▓▓▒░░]</div>';
                        loadPortfolioData();
                    }
                } else if (val.startsWith('BT ')) {
                    // Extract ticker and optional strategy
                    const args = val.substring(3).trim().split(' ');
                    const ticker = args[0];
                    const strategy = args.length > 1 ? args[1] : 'EMA';
                    runBacktest(ticker, strategy);
                } else if (val.startsWith('SENT ')) {
                    const ticker = val.substring(5).trim();
                    runSentiment(ticker);
                } else {
                    // Chart Mode
                    if (mainView) {
                        mainView.style.display = 'block';
                        chartHeaderInfo.style.display = 'flex';
                        portfolioView.style.display = 'none';
                    }
                    
                    document.querySelector('.symbol-name').textContent = val + ' US Equity';
                    currentTicker = val;
                    // Fetch real data
                    fetchChartData(val);
                    fetchValuation(val);
                    fetchOptions(val);
                }
            }
        }
    });

    async function runBacktest(ticker, strategy = "EMA") {
        const sidebarTitle = document.getElementById('sidebar-title');
        const newsList = document.getElementById('news-list');
        const btResults = document.getElementById('backtest-results');

        if (!newsList || !btResults) return;

        sidebarTitle.textContent = `BACKTEST: ${ticker}`;
        newsList.style.display = 'none';
        btResults.style.display = 'block';
        btResults.innerHTML = '<div style="color: #FFA500; text-align: center; padding-top: 20px;">[RUNNING ENGINE...]</div>';

        try {
            const res = await fetch(`/api/backtest?ticker=${ticker}&strategy=${strategy}`);
            const json = await res.json();
            if (json.status === "success" && json.data) {
                const data = json.data;
                const winRate = data["Win Rate [%]"] || 0;
                const ret = data["Total Return [%]"] || 0;
                const maxDd = data["Max Drawdown [%]"] || 0;
                const sharpe = data["Sharpe Ratio"];
                const stratName = data["Strategy Name"] || strategy;
                btResults.innerHTML = `
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Total Return</span><span class="${ret >= 0 ? 'green' : 'red'}">${ret.toFixed(2)}%</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Win Rate</span><span>${winRate.toFixed(2)}%</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Sharpe Ratio</span><span class="${sharpe >= 1 ? 'green' : (sharpe < 0 ? 'red' : '')}">${sharpe !== null && sharpe !== undefined ? sharpe.toFixed(2) : 'N/A'}</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Max Drawdown</span><span class="red">${maxDd.toFixed(2)}%</span></div>
                    <div style="margin-top: 25px; color: #555; font-size: 10px; text-transform: uppercase; border-top: 1px dashed #333; padding-top: 10px;">STRAT: ${stratName}<br>PERIOD: 2020-2024<br>ENGINE: vectorbt</div>
                    <button id="close-bt-btn" style="margin-top: 20px; width: 100%; background: #222; border: 1px solid #444; color: #fff; padding: 8px; font-family: 'JetBrains Mono', monospace; cursor: pointer;">[CLOSE MODULE]</button>
                `;
                document.getElementById('close-bt-btn').addEventListener('click', () => {
                    btResults.style.display = 'none';
                    newsList.style.display = 'block';
                    sidebarTitle.textContent = 'TOP NEWS';
                });
            } else {
                btResults.innerHTML = `<div style="color: #FF3131; text-align: center; padding-top: 20px;">[ERROR EXECUTION FAILED]<br><br>${json.error || ''}</div>`;
            }
        } catch (err) {
            btResults.innerHTML = `<div style="color: #FF3131; text-align: center; padding-top: 20px;">[NETWORK ERROR]</div>`;
        }
    }

    
    async function runSentiment(ticker) {
        const sidebarTitle = document.getElementById('sidebar-title');
        const newsList = document.getElementById('news-list');
        const btResults = document.getElementById('backtest-results');
        const sentResults = document.getElementById('sentiment-results');

        if (!newsList || !sentResults) return;

        sidebarTitle.textContent = `SENTIMENT: ${ticker}`;
        newsList.style.display = 'none';
        if (btResults) btResults.style.display = 'none';
        sentResults.style.display = 'block';
        sentResults.innerHTML = '<div style="color: #FFA500; text-align: center; padding-top: 20px;">[RUNNING NLP MODEL...]</div>';

        try {
            const res = await fetch(`/api/sentiment?ticker=${ticker}`);
            const json = await res.json();
            if (json.status === "success" && json.news) {
                const avg = json.average_sentiment;
                const polarity = avg > 0.1 ? 'BULLISH' : (avg < -0.1 ? 'BEARISH' : 'NEUTRAL');
                const color = avg > 0.1 ? 'green' : (avg < -0.1 ? 'red' : 'amber');

                let html = `
                    <div style="text-align:center; padding-bottom: 12px; border-bottom: 1px dashed #333; margin-bottom: 12px;">
                        <div style="font-size: 10px; color: #808080;">OVERALL POLARITY</div>
                        <div class="${color}" style="font-size: 18px; font-weight: bold; font-family: 'JetBrains Mono';">${polarity} (${avg.toFixed(2)})</div>
                    </div>
                    <div style="max-height: 250px; overflow-y: auto;">
                `;

                json.news.forEach(item => {
                    const itemColor = item.score > 0.1 ? 'green' : (item.score < -0.1 ? 'red' : 'grey');
                    html += `
                        <div style="margin-bottom: 15px;">
                            <div style="font-size: 9px; color: var(--${itemColor}); margin-bottom: 2px;">SCORE: ${item.score.toFixed(2)} | ${item.publisher}</div>
                            <div style="color: #ddd;">${item.title.substring(0, 80)}${item.title.length > 80 ? '...' : ''}</div>
                        </div>
                    `;
                });
                
                html += `
                    </div>
                    <button id="close-sent-btn" style="margin-top: 20px; width: 100%; background: #222; border: 1px solid #444; color: #fff; padding: 8px; font-family: 'JetBrains Mono', monospace; cursor: pointer;">[CLOSE MODULE]</button>
                `;
                
                sentResults.innerHTML = html;
                document.getElementById('close-sent-btn').addEventListener('click', () => {
                    sentResults.style.display = 'none';
                    newsList.style.display = 'block';
                    sidebarTitle.textContent = 'TOP NEWS';
                });
            } else {
                sentResults.innerHTML = `<div style="color: #FF3131; text-align: center; padding-top: 20px;">[ERROR EXECUTION FAILED]<br><br>${json.error || ''}</div>`;
            }
        } catch (err) {
            sentResults.innerHTML = `<div style="color: #FF3131; text-align: center; padding-top: 20px;">[NETWORK ERROR]</div>`;
        }
    }

    // 6. Live Polling (Real Data)
    setInterval(() => {
        // Poll for active ticker quote
        if (currentTicker && mainView && mainView.style.display !== 'none') {
            fetch(`/api/quote?ticker=${currentTicker}`)
                .then(res => res.json())
                .then(data => {
                    if (data.price) updateHeaderPrice(data.price, data.change, data.change_pct);
                })
                .catch(console.error);
        }
        
        // Poll pulse list/ticker
        populatePulse();
    }, 15000); // Update every 15 seconds to avoid rate limiting
    
    // Poll news every 60 seconds
    setInterval(() => {
        fetchLiveNews();
    }, 60000);
});
