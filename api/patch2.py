import os

# Patch script.js
with open('script.js', 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Patch BACK command logic to also hide sentiment-results
old_back = """                    const btResults = document.getElementById('backtest-results');
                    const newsList = document.getElementById('news-list');
                    const sidebarTitle = document.getElementById('sidebar-title');
                    if (btResults && newsList) {
                        btResults.style.display = 'none';
                        newsList.style.display = 'block';
                        sidebarTitle.textContent = 'TOP NEWS';
                    }"""

new_back = """                    const btResults = document.getElementById('backtest-results');
                    const newsList = document.getElementById('news-list');
                    const sidebarTitle = document.getElementById('sidebar-title');
                    const sentResults = document.getElementById('sentiment-results');
                    if (newsList) {
                        if (btResults) btResults.style.display = 'none';
                        if (sentResults) sentResults.style.display = 'none';
                        newsList.style.display = 'block';
                        if (sidebarTitle) sidebarTitle.textContent = 'TOP NEWS';
                    }"""

if old_back in js:
    js = js.replace(old_back, new_back)
else:
    old_back_crlf = old_back.replace('\\n', '\\r\\n')
    js = js.replace(old_back_crlf, new_back)

# 2. Patch SENT command parser
old_parser = """                } else if (val.startsWith('BT ')) {
                    const ticker = val.substring(3).trim();
                    runBacktest(ticker);
                } else {"""
                
new_parser = """                } else if (val.startsWith('BT ')) {
                    const ticker = val.substring(3).trim();
                    runBacktest(ticker);
                } else if (val.startsWith('SENT ')) {
                    const ticker = val.substring(5).trim();
                    runSentiment(ticker);
                } else {"""

if old_parser in js:
    js = js.replace(old_parser, new_parser)
else:
    old_parser_crlf = old_parser.replace('\\n', '\\r\\n')
    js = js.replace(old_parser_crlf, new_parser)
    
# 3. Add runSentiment function
sent_func = """
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
"""

# Append runSentiment before // 6. Live Polling (Real Data)
live_polling_str = "// 6. Live Polling (Real Data)"
if live_polling_str in js:
    js = js.replace(live_polling_str, sent_func + "\\n    " + live_polling_str)
else:
    js += sent_func

with open('script.js', 'w', encoding='utf-8') as f:
    f.write(js)
