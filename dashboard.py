"""
HFT Bot v0.7 - Dashboard Module
FastAPI + WebSocket 실시간 대시보드
"""

import asyncio
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn


class WebSocketManager:
    """WebSocket 연결 관리"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, data: dict):
        """모든 클라이언트에 브로드캐스트"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except:
                dead_connections.append(connection)
        
        # 죽은 연결 제거
        for conn in dead_connections:
            self.disconnect(conn)


def create_dashboard_app(bot_state: Dict) -> tuple:
    """
    Dashboard 앱 생성
    
    Returns:
        (app, ws_manager)
    """
    app = FastAPI(title="HFT Bot v0.7 Dashboard")
    ws_manager = WebSocketManager()
    
    @app.get("/")
    async def dashboard():
        return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>HFT Bot v0.7 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        h1 {
            font-size: 36px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            margin-left: 15px;
        }
        .status-running { background: #10b981; color: white; }
        .status-stopped { background: #ef4444; color: white; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
            border-color: #667eea;
        }
        .card-title {
            font-size: 12px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .card-value {
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .card-sub {
            font-size: 14px;
            color: #64748b;
        }
        .positive { color: #10b981; }
        .negative { color: #ef4444; }
        .neutral { color: #64748b; }
        .chart-container {
            background: #1e293b;
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #334155;
            margin-bottom: 25px;
        }
        .chart-container h2 {
            margin-bottom: 20px;
            font-size: 20px;
            color: #e2e8f0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }
        th {
            color: #94a3b8;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }
        .indicator-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .dot-good { background: #10b981; }
        .dot-warning { background: #f59e0b; }
        .dot-bad { background: #ef4444; }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 HFT Bot v0.7</h1>
        <span class="status-badge" id="status-badge">CONNECTING...</span>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">Daily PnL</div>
                <div class="card-value" id="daily-pnl">-</div>
                <div class="card-sub">Peak: <span id="peak-pnl">-</span></div>
            </div>
            
            <div class="card">
                <div class="card-title">Win Rate</div>
                <div class="card-value" id="win-rate">-</div>
                <div class="card-sub"><span id="win-loss">-</span></div>
            </div>
            
            <div class="card">
                <div class="card-title">Sharpe Ratio</div>
                <div class="card-value" id="sharpe">-</div>
                <div class="card-sub">Annualized</div>
            </div>
            
            <div class="card">
                <div class="card-title">Active Positions</div>
                <div class="card-value" id="positions-count">-</div>
                <div class="card-sub">Max: <span id="max-pos">3</span></div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>📈 PnL History</h2>
            <canvas id="pnlChart" height="80"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>💹 Active Positions</h2>
            <div id="positions-container">
                <div class="no-data">No active positions</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>📉 Market Signals</h2>
            <table id="symbols-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Signal Score</th>
                        <th>W-OBI Z</th>
                        <th>RSI</th>
                        <th>MACD</th>
                        <th>BB Position</th>
                        <th>Spread</th>
                    </tr>
                </thead>
                <tbody id="symbols-body">
                    <tr><td colspan="8" class="no-data">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        // WebSocket 연결
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        // PnL Chart 초기화
        const pnlCtx = document.getElementById('pnlChart').getContext('2d');
        const pnlChart = new Chart(pnlCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Cumulative PnL (KRW)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        labels: { color: '#e2e8f0', font: { size: 14 } }
                    }
                },
                scales: {
                    y: { 
                        ticks: { color: '#94a3b8' }, 
                        grid: { color: '#334155' }
                    },
                    x: { 
                        ticks: { color: '#94a3b8', maxTicksLimit: 10 }, 
                        grid: { color: '#334155' }
                    }
                }
            }
        });
        
        let pnlHistory = [];
        
        // WebSocket 메시지 핸들러
        ws.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('status-badge').textContent = 'CONNECTED';
            document.getElementById('status-badge').className = 'status-badge status-running';
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };
        
        ws.onclose = () => {
            console.log('WebSocket disconnected');
            document.getElementById('status-badge').textContent = 'DISCONNECTED';
            document.getElementById('status-badge').className = 'status-badge status-stopped';
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        function updateDashboard(data) {
            // Status
            const statusBadge = document.getElementById('status-badge');
            statusBadge.textContent = data.status || 'UNKNOWN';
            statusBadge.className = 'status-badge status-' + (data.status || 'stopped').toLowerCase();
            
            // Daily Stats
            const stats = data.daily_stats || {};
            
            const pnl = stats.pnl || 0;
            document.getElementById('daily-pnl').textContent = pnl.toLocaleString() + ' KRW';
            document.getElementById('daily-pnl').className = 'card-value ' + (pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral');
            
            document.getElementById('peak-pnl').textContent = (stats.peak_pnl || 0).toLocaleString() + ' KRW';
            
            const winRate = stats.win_rate || 0;
            document.getElementById('win-rate').textContent = (winRate * 100).toFixed(1) + '%';
            document.getElementById('win-loss').textContent = `${stats.wins || 0}W / ${stats.losses || 0}L`;
            
            // Sharpe
            const sharpe = stats.sharpe_ratio || 0;
            document.getElementById('sharpe').textContent = sharpe.toFixed(2);
            
            // Positions
            const positions = data.positions || [];
            document.getElementById('positions-count').textContent = positions.length;
            
            const posContainer = document.getElementById('positions-container');
            if (positions.length === 0) {
                posContainer.innerHTML = '<div class="no-data">No active positions</div>';
            } else {
                posContainer.innerHTML = '<table style="width:100%"><thead><tr><th>Symbol</th><th>Entry</th><th>Amount</th><th>Score</th><th>Time</th></tr></thead><tbody>' +
                    positions.map(p => {
                        const entryTime = new Date(p.entry_time);
                        const holdTime = Math.floor((Date.now() - entryTime.getTime()) / 1000);
                        return `
                            <tr>
                                <td><strong>${p.symbol}</strong></td>
                                <td>${parseFloat(p.entry_price).toLocaleString()} KRW</td>
                                <td>${parseFloat(p.amount).toFixed(6)}</td>
                                <td>${parseFloat(p.signal_score).toFixed(3)}</td>
                                <td>${holdTime}s</td>
                            </tr>
                        `;
                    }).join('') +
                    '</tbody></table>';
            }
            
            // Symbols Table
            const symbols = data.symbols || {};
            const symbolsBody = document.getElementById('symbols-body');
            
            if (Object.keys(symbols).length === 0) {
                symbolsBody.innerHTML = '<tr><td colspan="8" class="no-data">No data</td></tr>';
            } else {
                symbolsBody.innerHTML = Object.entries(symbols).map(([sym, info]) => {
                    const ind = info.indicators || {};
                    const score = info.signal_score || 0;
                    
                    let scoreDot = 'dot-bad';
                    if (score >= 0.6) scoreDot = 'dot-good';
                    else if (score >= 0.4) scoreDot = 'dot-warning';
                    
                    return `
                        <tr>
                            <td><strong>${sym}</strong></td>
                            <td>${(info.price || 0).toLocaleString()} KRW</td>
                            <td>
                                <span class="indicator-dot ${scoreDot}"></span>
                                ${score.toFixed(3)}
                            </td>
                            <td>${(ind.wobi_z || 0).toFixed(2)}</td>
                            <td>${(ind.rsi || 0).toFixed(1)}</td>
                            <td>${(ind.macd || 0).toFixed(3)}</td>
                            <td>${(ind.bb_position || 0).toFixed(2)}</td>
                            <td>${(info.spread_bps || 0).toFixed(2)} bps</td>
                        </tr>
                    `;
                }).join('');
            }
            
            // PnL Chart 업데이트
            if (pnl !== 0) {
                const now = new Date().toLocaleTimeString();
                pnlHistory.push({time: now, pnl: pnl});
                
                if (pnlHistory.length > 50) {
                    pnlHistory.shift();
                }
                
                pnlChart.data.labels = pnlHistory.map(h => h.time);
                pnlChart.data.datasets[0].data = pnlHistory.map(h => h.pnl);
                pnlChart.update('none');
            }
        }
    </script>
</body>
</html>
        """)
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                # 1초마다 상태 전송
                await asyncio.sleep(1)
                await websocket.send_json(bot_state)
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
    
    @app.get("/api/status")
    async def api_status():
        """REST API"""
        return bot_state
    
    return app, ws_manager


def run_dashboard(bot_state: Dict, host: str = "0.0.0.0", port: int = 8000):
    """Dashboard 실행 (별도 스레드)"""
    app, ws_manager = create_dashboard_app(bot_state)
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    
    import asyncio
    asyncio.run(server.serve())
