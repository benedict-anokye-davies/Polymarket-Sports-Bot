// Dashboard.js - Real-Time SSE Integration
// Implements Server-Sent Events for live updates, surgical DOM diffing, and lightweight charts

// --- 1. SSE Connection Manager ---
class SSEManager {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.handlers = new Map();
    }

    connect() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        const token = localStorage.getItem('access_token');
        if (!token) {
            console.warn('No auth token, cannot connect SSE');
            return;
        }

        // SSE with auth via query param
        this.eventSource = new EventSource(`/api/v1/dashboard/stream?token=${token}`);

        this.eventSource.onopen = () => {
            console.log('SSE connected');
            this.reconnectAttempts = 0;
            statusManager.setConnectionStatus(true);
        };

        this.eventSource.onerror = (err) => {
            console.error('SSE error:', err);
            statusManager.setConnectionStatus(false);
            this.eventSource.close();
            this._scheduleReconnect();
        };

        // Register event listeners
        this.eventSource.addEventListener('status', (e) => this._handleEvent('status', e));
        this.eventSource.addEventListener('games', (e) => this._handleEvent('games', e));
        this.eventSource.addEventListener('positions', (e) => this._handleEvent('positions', e));
        this.eventSource.addEventListener('heartbeat', (e) => this._handleEvent('heartbeat', e));
        this.eventSource.addEventListener('error', (e) => this._handleEvent('error', e));
    }

    on(eventType, handler) {
        if (!this.handlers.has(eventType)) {
            this.handlers.set(eventType, []);
        }
        this.handlers.get(eventType).push(handler);
    }

    _handleEvent(type, event) {
        try {
            const data = JSON.parse(event.data);
            const handlers = this.handlers.get(type) || [];
            handlers.forEach(handler => handler(data));
        } catch (e) {
            console.error(`Failed to handle SSE event ${type}:`, e);
        }
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max SSE reconnect attempts reached');
            statusManager.error('Connection lost. Please refresh the page.');
            return;
        }

        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        this.reconnectAttempts++;
        
        console.log(`SSE reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

const sseManager = new SSEManager();

// --- 2. Status Manager & Visual Hierarchy ---
class StatusManager {
    constructor() {
        this.state = {
            wallet: { connected: false, address: null },
            bot: { running: false, markets: 0, dailyPnl: 0, tradesToday: 0 },
            connection: { sse: false, websocket: false },
            errors: []
        };
    }

    setConnectionStatus(connected) {
        this.state.connection.sse = connected;
        this._updateConnectionUI();
    }

    connectWallet(address) {
        this.state.wallet = { connected: true, address };
        this._updateUI();
    }

    disconnectWallet() {
        this.state.wallet = { connected: false, address: null };
        this._updateUI();
    }

    updateBotStatus(status) {
        const isRunning = status.state === 'running';
        this.state.bot = {
            running: isRunning,
            markets: status.tracked_games || 0,
            dailyPnl: status.daily_pnl || 0,
            tradesToday: status.trades_today || 0
        };
        this.state.connection.websocket = status.websocket_status === 'connected';
        this._updateUI();
        this._updateConnectionUI();
    }

    startBot(markets = 0) {
        this.state.bot = { ...this.state.bot, running: true, markets };
        this._updateUI();
    }

    stopBot() {
        this.state.bot = { ...this.state.bot, running: false, markets: 0 };
        this._updateUI();
    }

    error(message, duration = 5000) {
        const errorId = Date.now();
        this.state.errors.push({ id: errorId, message });
        this._showError(errorId, message);
        setTimeout(() => this.dismissError(errorId), duration);
    }

    dismissError(errorId) {
        this.state.errors = this.state.errors.filter(e => e.id !== errorId);
        this._updateUI();
    }

    _updateUI() {
        const walletItem = document.getElementById('wallet-status');
        const botItem = document.getElementById('bot-status');
        const alertsSection = document.getElementById('alerts');

        if (!walletItem || !botItem) return;

        // Wallet UI
        const wInd = document.getElementById('wallet-indicator');
        const wVal = document.getElementById('wallet-address');
        if (wInd && wVal) {
            if (this.state.wallet.connected) {
                    wInd.className = 'status-indicator connected';
                wVal.textContent = this._shortenAddress(this.state.wallet.address);
            } else {
                wInd.className = 'status-indicator';
                wVal.textContent = 'Disconnected';
            }
        }

        // Bot UI
        const bInd = document.getElementById('bot-indicator');
        const bVal = document.getElementById('bot-status-text');
        if (bInd && bVal) {
            if (this.state.bot.running) {
                bInd.className = 'status-indicator running';
                bVal.textContent = `Active (${this.state.bot.markets} games)`;
            } else {
                bInd.className = 'status-indicator paused';
                bVal.textContent = 'Stopped';
            }
        }

        // Update stats
        const dailyPnlEl = document.getElementById('daily-pnl');
        const tradesTodayEl = document.getElementById('trades-today');
        if (dailyPnlEl) {
            const pnl = this.state.bot.dailyPnl;
            dailyPnlEl.textContent = formatCurrency(pnl);
            dailyPnlEl.className = pnl >= 0 ? 'text-success' : 'text-danger';
        }
        if (tradesTodayEl) {
            tradesTodayEl.textContent = this.state.bot.tradesToday;
        }

        // Errors UI
        if (alertsSection) {
            if (this.state.errors.length > 0) {
                alertsSection.style.display = 'flex';
                alertsSection.innerHTML = this.state.errors.map(err => `
                    <div class="status-item critical">
                        <span class="status-indicator error"></span>
                        <span class="status-label">Error</span>
                        <span class="status-value">${err.message}</span>
                        <button class="status-action" onclick="statusManager.dismissError(${err.id})">X</button>
                    </div>
                `).join('');
            } else {
                alertsSection.style.display = 'none';
            }
        }
    }

    _updateConnectionUI() {
        const sseIndicator = document.getElementById('sse-indicator');
        const wsIndicator = document.getElementById('ws-indicator');
        
        if (sseIndicator) {
            sseIndicator.className = this.state.connection.sse 
                ? 'status-pill status-active' 
                : 'status-pill status-inactive';
            const sseText = sseIndicator.querySelector('span:last-child');
            if (sseText) sseText.textContent = this.state.connection.sse ? 'Live' : 'Offline';
        }
        
        if (wsIndicator) {
            wsIndicator.className = this.state.connection.websocket 
                ? 'status-pill status-active' 
                : 'status-pill status-inactive';
            const wsText = wsIndicator.querySelector('span:last-child');
            if (wsText) wsText.textContent = this.state.connection.websocket ? 'WS Connected' : 'WS Offline';
        }
    }

    _showError(id, msg) {
        this._updateUI();
        console.warn(`[System Alert] ${msg}`);
    }

    _shortenAddress(addr) {
        return addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : '';
    }
}

const statusManager = new StatusManager();

// --- 3. Games Table Manager ---
class GamesTableManager {
    constructor(tbodySelector) {
        this.tbody = document.querySelector(tbodySelector);
        this.rows = new Map();
    }

    update(games) {
        if (!this.tbody || !games) return;

        const incomingIds = new Set(games.map(g => g.event_id));
        
        // Remove stale rows
        for (const [id, row] of this.rows) {
            if (!incomingIds.has(id)) {
                row.remove();
                this.rows.delete(id);
            }
        }

        // Update or create rows
        games.forEach(game => {
            if (this.rows.has(game.event_id)) {
                this._updateRow(this.rows.get(game.event_id), game);
            } else {
                const newRow = this._createRow(game);
                this.tbody.appendChild(newRow);
                this.rows.set(game.event_id, newRow);
            }
        });
    }

    _createRow(game) {
        const tr = document.createElement('tr');
        tr.dataset.eventId = game.event_id;
        tr.innerHTML = this._getRowHTML(game);
        return tr;
    }

    _updateRow(tr, game) {
        const priceCell = tr.querySelector('[data-key="price"]');
        const oldPrice = parseFloat(priceCell?.dataset.value || 0);
        const newPrice = game.current_price || 0;
        
        tr.innerHTML = this._getRowHTML(game);
        
        if (priceCell && oldPrice !== newPrice) {
            const newPriceCell = tr.querySelector('[data-key="price"]');
            this._flashCell(newPriceCell, newPrice - oldPrice);
        }
    }

    _getRowHTML(game) {
        const priceDiff = game.baseline_price && game.current_price 
            ? ((game.current_price - game.baseline_price) / game.baseline_price * 100).toFixed(1)
            : 0;
        const priceClass = priceDiff >= 0 ? 'text-success' : 'text-danger';
        const statusBadge = game.has_position 
            ? '<span class="badge bg-primary">Position</span>' 
            : '';
        
        return `
            <td class="ps-3">${game.sport?.toUpperCase() || 'N/A'}</td>
            <td>${game.matchup || 'Unknown'}</td>
            <td>${game.score || '0-0'}</td>
            <td>Q${game.period || 0}</td>
            <td data-key="price" data-value="${game.current_price || 0}">
                $${(game.current_price || 0).toFixed(4)}
                <span class="${priceClass} ms-1">(${priceDiff > 0 ? '+' : ''}${priceDiff}%)</span>
            </td>
            <td>${statusBadge}</td>
        `;
    }

    _flashCell(cell, diff) {
        if (!cell) return;
        cell.classList.remove('cell-flash-up', 'cell-flash-down');
        void cell.offsetWidth;
        cell.classList.add(diff > 0 ? 'cell-flash-up' : 'cell-flash-down');
    }
}

const gamesTableManager = new GamesTableManager('#games-table-body');

// --- 4. Performance Chart ---
let performanceChart;
let performanceSeries;

function initPerformanceChart() {
    const container = document.getElementById('performance-chart');
    if (!container || typeof LightweightCharts === 'undefined') return;

    performanceChart = LightweightCharts.createChart(container, {
        layout: {
            textColor: '#a1a1aa',
            background: { type: 'solid', color: 'transparent' }
        },
        grid: {
            vertLines: { visible: false },
            horzLines: { color: '#27272a' },
        },
        rightPriceScale: {
            borderColor: '#27272a',
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
            borderColor: '#27272a',
            timeVisible: true,
        },
        crosshair: {
            vertLine: { labelVisible: false, width: 1, color: 'rgba(255, 255, 255, 0.1)' },
            horzLine: { labelVisible: true },
        },
    });

    performanceSeries = performanceChart.addAreaSeries({
        topColor: 'rgba(16, 185, 129, 0.5)',
        bottomColor: 'rgba(16, 185, 129, 0.0)',
        lineColor: '#10b981',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
    });

    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== container) return;
        const rect = entries[0].contentRect;
        performanceChart.applyOptions({ height: rect.height, width: rect.width });
    }).observe(container);

    loadPerformanceData();
}

async function loadPerformanceData() {
    try {
        const res = await apiRequest('/dashboard/performance?days=30');
        if (!res.ok) return;
        
        const data = await res.json();
        
        if (performanceSeries && data.chart_data) {
            const chartData = data.chart_data.map(point => ({
                time: point.date,
                value: point.cumulative
            }));
            performanceSeries.setData(chartData);
        }

        // Update summary stats
        if (data.summary) {
            const summaryEl = document.getElementById('performance-summary');
            if (summaryEl) {
                summaryEl.innerHTML = `
                    <div class="d-flex gap-4 text-sm">
                        <span>Win Rate: <strong class="text-success">${data.summary.win_rate}%</strong></span>
                        <span>Total Trades: <strong>${data.summary.total_trades}</strong></span>
                        <span>Total P&L: <strong class="${data.summary.total_pnl >= 0 ? 'text-success' : 'text-danger'}">${formatCurrency(data.summary.total_pnl)}</strong></span>
                    </div>
                `;
            }
        }
    } catch (e) {
        console.error('Failed to load performance data:', e);
    }
}

// --- 5. SSE Event Handlers ---
function setupSSEHandlers() {
    sseManager.on('status', (data) => {
        if (data.data) {
            statusManager.updateBotStatus(data.data);
        }
    });

    sseManager.on('games', (data) => {
        if (data.data) {
            gamesTableManager.update(data.data);
        }
    });

    sseManager.on('positions', (data) => {
        if (data.data) {
            updatePositionsUI(data.data);
        }
    });

    sseManager.on('heartbeat', (data) => {
        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
        }
    });

    sseManager.on('error', (data) => {
        console.error('SSE error event:', data);
        statusManager.error(data.error || 'Stream error');
    });
}

function updatePositionsUI(positions) {
    const container = document.getElementById('positions-list');
    if (!container) return;

    if (positions.length === 0) {
        container.innerHTML = '<div class="text-secondary text-center py-4">No open positions</div>';
        return;
    }

    container.innerHTML = positions.map(pos => `
        <div class="position-item d-flex justify-content-between align-items-center p-3 border-bottom border-dark">
            <div>
                <span class="badge bg-${pos.side === 'YES' ? 'success' : 'danger'} me-2">${pos.side}</span>
                <span class="text-light">${pos.team || pos.condition_id.slice(0, 12)}...</span>
            </div>
            <div class="text-end">
                <div class="text-light">$${pos.entry_price.toFixed(4)}</div>
                <div class="text-secondary text-sm">${pos.entry_size} contracts</div>
            </div>
        </div>
    `).join('');
}

// --- 6. Main Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    setupSSEHandlers();
    initPerformanceChart();
    sseManager.connect();
    await loadDashboardData();
    
    // Fallback polling (in case SSE fails)
    setInterval(loadDashboardData, 30000);
});

// --- Existing Dashboard Logic ---
async function loadDashboardData() {
    try {
        const stats = await apiRequest('/dashboard/stats').then(r => r.ok ? r.json() : null);
        if (stats) updateStats(stats);
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

function updateStats(stats) {
    if (!stats) return;
    
    const portfolioEl = document.getElementById('portfolio-value');
    const pnlEl = document.getElementById('active-pnl');
    const positionsEl = document.getElementById('open-positions');
    const marketsEl = document.getElementById('tracked-markets');
    
    if (portfolioEl) portfolioEl.textContent = formatCurrency(stats.balance_usdc || 0);
    if (pnlEl) {
        pnlEl.textContent = formatCurrency(stats.total_pnl_today || 0);
        pnlEl.className = (stats.total_pnl_today || 0) >= 0 ? 'text-success' : 'text-danger';
    }
    if (positionsEl) positionsEl.textContent = stats.open_positions_count || 0;
    if (marketsEl) marketsEl.textContent = stats.active_markets_count || 0;
    
    // Update bot status from stats
    if (stats.bot_status === 'running') {
        statusManager.startBot(stats.active_markets_count || 0);
    } else {
        statusManager.stopBot();
    }
}

window.toggleBot = async () => {
    const isRunning = document.getElementById('bot-indicator')?.classList.contains('running');
    const endpoint = isRunning ? '/bot/stop' : '/bot/start';
    
    try {
        const res = await apiRequest(endpoint, 'POST');
        if (res.ok) {
            isRunning ? statusManager.stopBot() : statusManager.startBot();
        } else {
            const err = await res.json();
            statusManager.error(err.detail || 'Failed to toggle bot');
        }
    } catch (e) {
        statusManager.error(e.message);
    }
};

window.toggleWallet = () => {
    const isConnected = document.getElementById('wallet-indicator')?.classList.contains('connected');
    if (isConnected) {
        statusManager.disconnectWallet();
    } else {
        statusManager.connectWallet('0x7a2c1e8d4c9Ff3');
    }
};

function formatCurrency(val) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    sseManager.disconnect();
});
