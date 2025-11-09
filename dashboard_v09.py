"""
HFT Bot v0.9 - Enhanced Dashboard with Hierarchical Signal Visualization
계층적 신호 + 실시간 차트 + TTL 진행바
"""

import asyncio
from typing import Dict, List, Optional
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

        for conn in dead_connections:
            self.disconnect(conn)


def create_enhanced_dashboard_app(bot_state: Dict) -> tuple:
    """
    Enhanced Dashboard v0.9

    Returns:
        (app, ws_manager)
    """
    app = FastAPI(title="HFT Bot v0.9 - Hierarchical Dashboard")
    ws_manager = WebSocketManager()

    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        return HTML_TEMPLATE_V09

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                # 클라이언트로부터 메시지 대기
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app, ws_manager


# Enhanced HTML Template with Hierarchical Visualization
HTML_TEMPLATE_V09 = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HFT Bot v0.9 - Hierarchical Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
        }

        .header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .header h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 5px;
        }

        .header .subtitle {
            color: #666;
            font-size: 14px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .card-title {
            font-size: 14px;
            color: #888;
            margin-bottom: 10px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .card-value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }

        .card-value.positive { color: #10b981; }
        .card-value.negative { color: #ef4444; }
        .card-value.neutral { color: #6b7280; }

        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .status-badge.status-running {
            background: #10b981;
            color: white;
        }

        .status-badge.status-stopped {
            background: #ef4444;
            color: white;
        }

        .status-badge.status-paused {
            background: #f59e0b;
            color: white;
        }

        /* Hierarchical Signal Flow */
        .signal-flow {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .signal-level {
            margin-bottom: 30px;
            padding: 20px;
            border-radius: 8px;
            background: #f9fafb;
            border-left: 4px solid #ddd;
            position: relative;
        }

        .signal-level.level-macro { border-left-color: #3b82f6; }
        .signal-level.level-strategic { border-left-color: #8b5cf6; }
        .signal-level.level-tactical { border-left-color: #ec4899; }

        .signal-level.active {
            background: #f0fdf4;
            box-shadow: 0 0 0 2px #10b981;
        }

        .signal-level.blocked {
            background: #fef2f2;
            opacity: 0.6;
        }

        .signal-level-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .signal-level-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }

        .signal-level-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .signal-level-badge.pass { background: #d1fae5; color: #065f46; }
        .signal-level-badge.fail { background: #fee2e2; color: #991b1b; }

        .signal-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }

        .signal-metric {
            display: flex;
            flex-direction: column;
        }

        .signal-metric-label {
            font-size: 12px;
            color: #888;
            margin-bottom: 5px;
        }

        .signal-metric-value {
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }

        /* TTL Progress Bar */
        .ttl-progress {
            margin-top: 15px;
        }

        .ttl-progress-label {
            font-size: 12px;
            color: #888;
            margin-bottom: 5px;
        }

        .ttl-progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
        }

        .ttl-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #3b82f6);
            transition: width 0.3s ease;
        }

        /* Chart Area */
        .chart-area {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            height: 400px;
        }

        .chart-placeholder {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f9fafb;
            border-radius: 8px;
            color: #888;
            font-size: 18px;
        }

        /* Positions Table */
        .positions-table {
            width: 100%;
            border-collapse: collapse;
        }

        .positions-table th {
            background: #f9fafb;
            padding: 12px;
            text-align: left;
            font-size: 12px;
            color: #888;
            font-weight: 600;
            text-transform: uppercase;
        }

        .positions-table td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }

        .arrow-down {
            text-align: center;
            font-size: 24px;
            color: #888;
            margin: 10px 0;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .live-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🤖 HFT Bot v0.9 - Hierarchical Dashboard</h1>
            <p class="subtitle">
                <span class="live-indicator"></span>
                Live | <span id="status-text">Connected</span> | Updated: <span id="last-update">--</span>
            </p>
        </div>

        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <div class="card-title">Status</div>
                <div class="card-value">
                    <span class="status-badge" id="status-badge">STOPPED</span>
                </div>
            </div>
            <div class="card">
                <div class="card-title">Daily P&L</div>
                <div class="card-value" id="daily-pnl">0 KRW</div>
            </div>
            <div class="card">
                <div class="card-title">Win Rate</div>
                <div class="card-value neutral" id="win-rate">0.0%</div>
                <div style="font-size: 14px; color: #888; margin-top: 5px;" id="win-loss">0W / 0L</div>
            </div>
            <div class="card">
                <div class="card-title">Sharpe Ratio</div>
                <div class="card-value neutral" id="sharpe">0.00</div>
            </div>
        </div>

        <!-- Hierarchical Signal Flow -->
        <div class="signal-flow">
            <h2 style="margin-bottom: 20px; color: #333;">📊 Hierarchical Signal Flow</h2>

            <!-- Level 1: Macro Filter -->
            <div class="signal-level level-macro" id="macro-level">
                <div class="signal-level-header">
                    <div class="signal-level-title">
                        🌍 Level 1: Macro Filter (Risk Management)
                    </div>
                    <span class="signal-level-badge fail" id="macro-badge">BLOCKED</span>
                </div>
                <div class="signal-metrics">
                    <div class="signal-metric">
                        <div class="signal-metric-label">Score</div>
                        <div class="signal-metric-value" id="macro-score">0.00</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Daily Loss</div>
                        <div class="signal-metric-value" id="macro-loss">0 KRW</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Consecutive Losses</div>
                        <div class="signal-metric-value" id="macro-consecutive">0</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Active Positions</div>
                        <div class="signal-metric-value" id="macro-positions">0 / 3</div>
                    </div>
                </div>
                <div class="ttl-progress">
                    <div class="ttl-progress-label">TTL: <span id="macro-ttl">60s</span></div>
                    <div class="ttl-progress-bar">
                        <div class="ttl-progress-fill" id="macro-ttl-bar" style="width: 100%"></div>
                    </div>
                </div>
            </div>

            <div class="arrow-down">↓</div>

            <!-- Level 2: Strategic -->
            <div class="signal-level level-strategic" id="strategic-level">
                <div class="signal-level-header">
                    <div class="signal-level-title">
                        📈 Level 2: Strategic (RSI/MACD/BB)
                    </div>
                    <span class="signal-level-badge fail" id="strategic-badge">NO SIGNAL</span>
                </div>
                <div class="signal-metrics">
                    <div class="signal-metric">
                        <div class="signal-metric-label">Direction</div>
                        <div class="signal-metric-value" id="strategic-direction">NEUTRAL</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Score</div>
                        <div class="signal-metric-value" id="strategic-score">0.00</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">RSI</div>
                        <div class="signal-metric-value" id="strategic-rsi">--</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">MACD</div>
                        <div class="signal-metric-value" id="strategic-macd">--</div>
                    </div>
                </div>
                <div class="ttl-progress">
                    <div class="ttl-progress-label">TTL: <span id="strategic-ttl">30s</span></div>
                    <div class="ttl-progress-bar">
                        <div class="ttl-progress-fill" id="strategic-ttl-bar" style="width: 0%"></div>
                    </div>
                </div>
            </div>

            <div class="arrow-down">↓</div>

            <!-- Level 3: Tactical -->
            <div class="signal-level level-tactical" id="tactical-level">
                <div class="signal-level-header">
                    <div class="signal-level-title">
                        ⚡ Level 3: Tactical (W-OBI Execution)
                    </div>
                    <span class="signal-level-badge fail" id="tactical-badge">UNFAVORABLE</span>
                </div>
                <div class="signal-metrics">
                    <div class="signal-metric">
                        <div class="signal-metric-label">Execution Score</div>
                        <div class="signal-metric-value" id="tactical-score">0.00</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Position Size</div>
                        <div class="signal-metric-value" id="tactical-size">0 KRW</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">W-OBI Z-Score</div>
                        <div class="signal-metric-value" id="tactical-wobi">--</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Spread</div>
                        <div class="signal-metric-value" id="tactical-spread">--</div>
                    </div>
                </div>
                <div class="ttl-progress">
                    <div class="ttl-progress-label">TTL: <span id="tactical-ttl">10s</span></div>
                    <div class="ttl-progress-bar">
                        <div class="ttl-progress-fill" id="tactical-ttl-bar" style="width: 0%"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chart Placeholder -->
        <div class="chart-area">
            <div class="chart-placeholder">
                📊 Real-time Price Chart (Coming Soon - 차트 라이브러리 추가 필요)
            </div>
        </div>

        <!-- Active Positions -->
        <div class="card">
            <div class="card-title">Active Positions (<span id="positions-count">0</span>)</div>
            <div id="positions-container">
                <div style="color: #888; padding: 20px; text-align: center;">No active positions</div>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);

        ws.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('status-text').textContent = 'Connected';
            ws.send('ping');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            document.getElementById('status-text').textContent = 'Error';
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            document.getElementById('status-text').textContent = 'Disconnected';
        };

        function updateDashboard(data) {
            // Update timestamp
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

            // Status
            const statusBadge = document.getElementById('status-badge');
            statusBadge.textContent = data.status || 'UNKNOWN';
            statusBadge.className = 'status-badge status-' + (data.status || 'stopped').toLowerCase();

            // Daily Stats
            const stats = data.daily_stats || {};
            const pnl = stats.pnl || 0;
            document.getElementById('daily-pnl').textContent = pnl.toLocaleString() + ' KRW';
            document.getElementById('daily-pnl').className = 'card-value ' + (pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral');

            const winRate = stats.win_rate || 0;
            document.getElementById('win-rate').textContent = (winRate * 100).toFixed(1) + '%';
            document.getElementById('win-loss').textContent = `${stats.wins || 0}W / ${stats.losses || 0}L`;

            const sharpe = stats.sharpe_ratio || 0;
            document.getElementById('sharpe').textContent = sharpe.toFixed(2);

            // Hierarchical Signals
            if (data.hierarchical_signals) {
                updateHierarchicalSignals(data.hierarchical_signals);
            }

            // Positions
            const positions = data.positions || [];
            document.getElementById('positions-count').textContent = positions.length;
            // ... (positions table update logic)
        }

        function updateHierarchicalSignals(signals) {
            // Macro Level
            if (signals.macro) {
                const macroLevel = document.getElementById('macro-level');
                const macroBadge = document.getElementById('macro-badge');

                if (signals.macro.pass) {
                    macroLevel.classList.add('active');
                    macroLevel.classList.remove('blocked');
                    macroBadge.textContent = 'PASS';
                    macroBadge.className = 'signal-level-badge pass';
                } else {
                    macroLevel.classList.remove('active');
                    macroLevel.classList.add('blocked');
                    macroBadge.textContent = 'BLOCKED';
                    macroBadge.className = 'signal-level-badge fail';
                }

                document.getElementById('macro-score').textContent = (signals.macro.score || 0).toFixed(2);
                document.getElementById('macro-ttl-bar').style.width = (signals.macro.ttl_percent || 0) + '%';
            }

            // Strategic Level
            if (signals.strategic) {
                const strategicLevel = document.getElementById('strategic-level');
                const strategicBadge = document.getElementById('strategic-badge');

                if (signals.strategic.direction !== 'NEUTRAL') {
                    strategicLevel.classList.add('active');
                    strategicBadge.textContent = signals.strategic.direction;
                    strategicBadge.className = 'signal-level-badge pass';
                } else {
                    strategicLevel.classList.remove('active');
                    strategicBadge.textContent = 'NO SIGNAL';
                    strategicBadge.className = 'signal-level-badge fail';
                }

                document.getElementById('strategic-score').textContent = (signals.strategic.score || 0).toFixed(2);
                document.getElementById('strategic-direction').textContent = signals.strategic.direction;
                document.getElementById('strategic-ttl-bar').style.width = (signals.strategic.ttl_percent || 0) + '%';
            }

            // Tactical Level
            if (signals.tactical) {
                const tacticalLevel = document.getElementById('tactical-level');
                const tacticalBadge = document.getElementById('tactical-badge');

                if (signals.tactical.execute) {
                    tacticalLevel.classList.add('active');
                    tacticalBadge.textContent = 'EXECUTE';
                    tacticalBadge.className = 'signal-level-badge pass';
                } else {
                    tacticalLevel.classList.remove('active');
                    tacticalBadge.textContent = 'UNFAVORABLE';
                    tacticalBadge.className = 'signal-level-badge fail';
                }

                document.getElementById('tactical-score').textContent = (signals.tactical.score || 0).toFixed(2);
                document.getElementById('tactical-size').textContent = (signals.tactical.position_size || 0).toLocaleString() + ' KRW';
                document.getElementById('tactical-ttl-bar').style.width = (signals.tactical.ttl_percent || 0) + '%';
            }
        }
    </script>
</body>
</html>
"""


def run_dashboard(bot_state: Dict, host: str = "0.0.0.0", port: int = 8080):
    """대시보드 실행"""
    app, ws_manager = create_enhanced_dashboard_app(bot_state)

    # Store ws_manager in app state for bot to access
    app.state.ws_manager = ws_manager
    app.state.bot_state = bot_state

    uvicorn.run(app, host=host, port=port)
