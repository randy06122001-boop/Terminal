import os

# Patch index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('<section class="panel sidebar-panel">', '<section class="panel sidebar-panel" id="sidebar-panel">')
html = html.replace('<h2 class="panel-title">TOP NEWS</h2>', '<h2 class="panel-title" id="sidebar-title">TOP NEWS</h2>')
html = html.replace('</div>\n            </section>', '</div>\n\n                <!-- Backtest Results Container -->\n                <div class="backtest-results" id="backtest-results" style="display: none; padding: 15px; font-family: \'JetBrains Mono\', monospace; font-size: 12px; color: #ccc;">\n                </div>\n            </section>')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

# Patch script.js
with open('script.js', 'r', encoding='utf-8') as f:
    js = f.read()

old_cmd = """    // 5. Command Logic
    const cmdInput = document.querySelector('.command-input');
    cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const val = cmdInput.value.toUpperCase();
            if (val) {
                document.querySelector('.symbol-name').textContent = val + ' US Equity';
                cmdInput.value = '';
                // Refresh data
                chartData = [];
                generateInitialData();
            }
        }
    });"""

old_cmd_crlf = old_cmd.replace('\n', '\r\n')

new_cmd = """    // 5. Command Logic & Backtesting
    const cmdInput = document.querySelector('.command-input');
    cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const val = cmdInput.value.trim().toUpperCase();
            if (val) {
                if (val.startsWith('BT ')) {
                    const ticker = val.substring(3).trim();
                    cmdInput.value = '';
                    runBacktest(ticker);
                    return;
                }
                document.querySelector('.symbol-name').textContent = val + ' US Equity';
                cmdInput.value = '';
                chartData = [];
                generateInitialData();
            }
        }
    });

    async function runBacktest(ticker) {
        const sidebarTitle = document.getElementById('sidebar-title');
        const newsList = document.getElementById('news-list');
        const btResults = document.getElementById('backtest-results');

        sidebarTitle.textContent = `BACKTEST: ${ticker}`;
        newsList.style.display = 'none';
        btResults.style.display = 'block';
        btResults.innerHTML = '<div style="color: #FFA500; text-align: center; padding-top: 20px;">[RUNNING ENGINE...]</div>';

        try {
            const res = await fetch(`http://localhost:8000/api/backtest?ticker=${ticker}`);
            const json = await res.json();
            if (json.status === "success" && json.data) {
                const data = json.data;
                const winRate = data["Win Rate [%]"] || 0;
                const ret = data["Total Return [%]"] || 0;
                const maxDd = data["Max Drawdown [%]"] || 0;
                const sharpe = data["Sharpe Ratio"];
                btResults.innerHTML = `
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Total Return</span><span class="${ret >= 0 ? 'green' : 'red'}">${ret.toFixed(2)}%</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Win Rate</span><span>${winRate.toFixed(2)}%</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Sharpe Ratio</span><span class="${sharpe >= 1 ? 'green' : (sharpe < 0 ? 'red' : '')}">${sharpe !== null && sharpe !== undefined ? sharpe.toFixed(2) : 'N/A'}</span></div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span style="color: #808080">Max Drawdown</span><span class="red">${maxDd.toFixed(2)}%</span></div>
                    <div style="margin-top: 25px; color: #555; font-size: 10px; text-transform: uppercase; border-top: 1px dashed #333; padding-top: 10px;">STRAT: EMA Crossover<br>PARAM: 10/50 Length<br>PERIOD: 2020-2024<br>ENGINE: vectorbt</div>
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
    }"""

if old_cmd in js:
    js = js.replace(old_cmd, new_cmd)
elif old_cmd_crlf in js:
    js = js.replace(old_cmd_crlf, new_cmd)
else:
    print("Could not find the target code in script.js!")
    
with open('script.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("Patching complete!")
