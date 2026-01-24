// Dashboard.js - Production-Grade Sports Betting Dashboard
// Features: SSE real-time, skeleton loading, toast notifications, percentage formatting

// ============================================================================
// 1. TOAST NOTIFICATION SYSTEM
// ============================================================================
class ToastManager {
    constructor() {
        this.container = null;
        this._createContainer();
    }

    _createContainer() {
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 9999;
            display: flex; flex-direction: column; gap: 8px;
        `;
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast-item toast-${type}`;
        
        const icons = {
            success: '<i class="bi bi-check-circle-fill"></i>',
            error: '<i class="bi bi-x-circle-fill"></i>',
            warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
            info: '<i class="bi bi-info-circle-fill"></i>'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type]}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="bi bi-x"></i>
            </button>
        `;
        
        this.container.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => toast.classList.add('toast-visible'));
        
        // Auto dismiss
        setTimeout(() => {
            toast.classList.remove('toast-visible');
            setTimeout(() => toast.remove(), 300);
        }, duration);
        
        return toast;
    }
    
    success(msg) { return this.show(msg, 'success'); }
    error(msg) { return this.show(msg, 'error', 6000); }
    warning(msg) { return this.show(msg, 'warning'); }
    info(msg) { return this.show(msg, 'info'); }
}

const toast = new ToastManager();

// ============================================================================
// 2. SKELETON LOADING SYSTEM
// ============================================================================
class SkeletonManager {
    static show(selector, rows = 3) {
        const container = document.querySelector(selector);
        if (!container) return;
        
        container.innerHTML = Array(rows).fill(0).map(() => `
            <tr class="skeleton-row">
                <td><div class="skeleton skeleton-text"></div></td>
                <td><div class="skeleton skeleton-text"></div></td>
                <td><div class="skeleton skeleton-text"></div></td>
                <td><div class="skeleton skeleton-text"></div></td>
            </tr>
        `).join('');
    }
    
    static showCard(selector) {
        const container = document.querySelector(selector);
        if (!container) return;
        
        container.innerHTML = `
            <div class="skeleton skeleton-chart" style="height: 300px;"></div>
        `;
    }
    
    static hide(selector) {
        const container = document.querySelector(selector);
        if (container) container.innerHTML = '';
    }
}

// ============================================================================
// 3. SSE CONNECTION MANAGER (Enhanced)
// ============================================================================
class SSEManager {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.handlers = new Map();
        this.isConnected = false;
    }

    connect() {
        if (this.eventSource) this.eventSource.close();

        const token = localStorage.getItem('access_token');
        if (!token) {
            console.warn('No auth token for SSE');
            return;
        }

        this.eventSource = new EventSource(`/api/v1/dashboard/stream?token=${token}`);

        this.eventSource.onopen = () => {
            console.log('SSE connected');
            this.reconnectAttempts = 0;
            this.isConnected = true;
            statusManager.setConnectionStatus(true);
            toast.success('Live data stream connected');
        };

        this.eventSource.onerror = (err) => {
            console.error('SSE error:', err);
            this.isConnected = false;
            statusManager.setConnectionStatus(false);
            this.eventSource.close();
            this._scheduleReconnect();
        };

        ['status', 'games', 'positions', 'heartbeat', 'error'].forEach(type => {
            this.eventSource.addEventListener(type, (e) => this._handleEvent(type, e));
        });
    }

    on(eventType, handler) {
        if (!this.handlers.has(eventType)) this.handlers.set(eventType, []);
        this.handlers.get(eventType).push(handler);
    }

    _handleEvent(type, event) {
        try {
            const data = JSON.parse(event.data);
            (this.handlers.get(type) || []).forEach(h => h(data));
        } catch (e) {
            console.error(`SSE event ${type} parse error:`, e);
        }
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            toast.error('Connection lost. Please refresh the page.');
            return;
        }
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts++);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            this.isConnected = false;
        }
    }
}

const sseManager = new SSEManager();

// ============================================================================
// 4. STATUS MANAGER (With Percentage Display)
// ============================================================================
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
        toast.success('Wallet connected');
    }

    disconnectWallet() {
        this.state.wallet = { connected: false, address: null };
        this._updateUI();
        toast.info('Wallet disconnected');
    }

    updateBotStatus(status) {
        const isRunning = status.state === 'running';
        const wasRunning = this.state.bot.running;
        
        this.state.bot = {
            running: isRunning,
            markets: status.tracked_games || 0,
            dailyPnl: status.daily_pnl || 0,
            tradesToday: status.trades_today || 0
        };
        this.state.connection.websocket = status.websocket_status === 'connected';
        
        // Toast on state change
        if (isRunning && !wasRunning) toast.success('Bot started');
        else if (!isRunning && wasRunning) toast.info('Bot stopped');
        
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
        toast.error(message);
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
            wInd.className = this.state.wallet.connected 
                ? 'status-indicator connected' 
                : 'status-indicator';
            wVal.textContent = this.state.wallet.connected 
                ? this._shortenAddress(this.state.wallet.address) 
                : 'Disconnected';
        }

        // Bot UI
        const bInd = document.getElementById('bot-indicator');
        const bVal = document.getElementById('bot-status-text');
        if (bInd && bVal) {
            bInd.className = this.state.bot.running 
                ? 'status-indicator running' 
                : 'status-indicator paused';
            bVal.textContent = this.state.bot.running 
                ? `Active (${this.state.bot.markets} games)` 
                : 'Stopped';
        }

        // Stats
        const dailyPnlEl = document.getElementById('daily-pnl');
        const tradesTodayEl = document.getElementById('trades-today');
        if (dailyPnlEl) {
            dailyPnlEl.textContent = formatCurrency(this.state.bot.dailyPnl);
            dailyPnlEl.className = `stat-value ${this.state.bot.dailyPnl >= 0 ? 'text-success' : 'text-danger'}`;
        }
        if (tradesTodayEl) tradesTodayEl.textContent = this.state.bot.tradesToday;

        // Errors
        if (alertsSection) {
            alertsSection.style.display = this.state.errors.length > 0 ? 'flex' : 'none';
            if (this.state.errors.length > 0) {
                alertsSection.innerHTML = this.state.errors.map(err => `
                    <div class="status-item critical">
                        <span class="status-indicator error"></span>
                        <span class="status-label">Error</span>
                        <span class="status-value">${err.message}</span>
                        <button class="status-action" onclick="statusManager.dismissError(${err.id})">X</button>
                    </div>
                `).join('');
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
            const text = sseIndicator.querySelector('span:last-child');
            if (text) text.textContent = this.state.connection.sse ? 'Live' : 'Offline';
        }
        
        if (wsIndicator) {
            wsIndicator.className = this.state.connection.websocket 
                ? 'status-pill status-active' 
                : 'status-pill status-inactive';
            const text = wsIndicator.querySelector('span:last-child');
            if (text) text.textContent = this.state.connection.websocket ? 'WS OK' : 'WS Off';
        }
    }

    _showError(id, msg) {
        this._updateUI();
        console.warn(`[Alert] ${msg}`);
    }

    _shortenAddress(addr) {
        return addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : '';
    }
}

const statusManager = new StatusManager();

// ============================================================================
// 5. LIVE GAMES TABLE (Sports-Centric)
// ============================================================================
class GamesTableManager {
    constructor(tbodySelector) {
        this.tbody = document.querySelector(tbodySelector);
        this.rows = new Map();
    }

    update(games) {
        if (!this.tbody || !games) return;
        
        const incomingIds = new Set(games.map(g => g.event_id));
        
        // Remove stale
        for (const [id, row] of this.rows) {
            if (!incomingIds.has(id)) {
                row.classList.add('fade-out');
                setTimeout(() => { row.remove(); this.rows.delete(id); }, 300);
            }
        }

        // Update or create
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
        
        if (oldPrice !== newPrice) {
            const newCell = tr.querySelector('[data-key="price"]');
            this._flashCell(newCell, newPrice - oldPrice);
        }
    }

    _getRowHTML(game) {
        const prob = (game.current_price || 0.5) * 100;
        const baseline = (game.baseline_price || 0.5) * 100;
        const diff = prob - baseline;
        const diffClass = diff >= 0 ? 'text-success' : 'text-danger';
        const statusBadge = game.has_position 
            ? '<span class="badge bg-primary">IN POSITION</span>' 
            : '';
        
        // Format as percentage (sports betting style)
        return `
            <td class="ps-3">
                <span class="badge bg-dark text-uppercase">${game.sport || 'N/A'}</span>
            </td>
            <td>
                <div class="fw-semibold">${game.matchup || 'Unknown'}</div>
                <div class="text-secondary text-xs">${game.league || ''}</div>
            </td>
            <td class="text-center">
                <span class="fw-bold">${game.score || '0-0'}</span>
                <div class="text-xs text-secondary">Q${game.period || 0} ${game.clock || ''}</div>
            </td>
            <td data-key="price" data-value="${game.current_price || 0}">
                <div class="d-flex align-items-center gap-2">
                    <span class="prob-display">${prob.toFixed(1)}%</span>
                    <span class="prob-change ${diffClass}">${diff > 0 ? '+' : ''}${diff.toFixed(1)}%</span>
                </div>
                <div class="prob-bar">
                    <div class="prob-fill" style="width: ${prob}%"></div>
                </div>
            </td>
            <td class="text-end pe-3">${statusBadge}</td>
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

// ============================================================================
// 6. PERFORMANCE CHART (Win Probability Style)
// ============================================================================
let performanceChart;
let performanceSeries;

function initPerformanceChart() {
    const container = document.getElementById('chart-container');
    if (!container || typeof LightweightCharts === 'undefined') {
        SkeletonManager.showCard('#chart-container');
        return;
    }

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
            scaleMargins: { top: 0.05, bottom: 0.05 },
            // Format as percentage
            format: {
                type: 'custom',
                formatter: (price) => `${(price * 100).toFixed(0)}%`
            }
        },
        timeScale: {
            borderColor: '#27272a',
            timeVisible: true,
            secondsVisible: false,
        },
        crosshair: {
            vertLine: { labelVisible: false, width: 1, color: 'rgba(255,255,255,0.1)' },
            horzLine: { labelVisible: true },
        },
        localization: {
            priceFormatter: (price) => `${(price * 100).toFixed(1)}%`
        }
    });

    performanceSeries = performanceChart.addAreaSeries({
        topColor: 'rgba(16, 185, 129, 0.4)',
        bottomColor: 'rgba(16, 185, 129, 0.0)',
        lineColor: '#10b981',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 5,
        crosshairMarkerBackgroundColor: '#10b981',
        priceLineVisible: true,
        lastValueVisible: true,
    });

    // Responsive
    new ResizeObserver(entries => {
        if (entries[0]?.target === container) {
            const { width, height } = entries[0].contentRect;
            performanceChart.applyOptions({ width, height });
        }
    }).observe(container);

    loadPerformanceData();
}

async function loadPerformanceData() {
    try {
        const res = await apiRequest('/dashboard/performance?days=30');
        if (!res.ok) {
            // Use mock data for demo
            const mockData = generateMockProbabilityHistory(100);
            performanceSeries?.setData(mockData);
            return;
        }
        
        const data = await res.json();
        if (performanceSeries && data.chart_data) {
            performanceSeries.setData(data.chart_data.map(p => ({
                time: p.date,
                value: p.cumulative
            })));
        }

        if (data.summary) {
            const el = document.getElementById('performance-summary');
            if (el) {
                el.innerHTML = `
                    <div class="d-flex gap-4 text-sm">
                        <span>Win Rate: <strong class="text-success">${data.summary.win_rate}%</strong></span>
                        <span>Trades: <strong>${data.summary.total_trades}</strong></span>
                        <span>P&L: <strong class="${data.summary.total_pnl >= 0 ? 'text-success' : 'text-danger'}">${formatCurrency(data.summary.total_pnl)}</strong></span>
                    </div>
                `;
            }
        }
    } catch (e) {
        console.error('Performance load error:', e);
        // Fallback to mock
        const mockData = generateMockProbabilityHistory(100);
        performanceSeries?.setData(mockData);
    }
}

function generateMockProbabilityHistory(count) {
    const data = [];
    let time = Math.floor(Date.now() / 1000) - (count * 60);
    let value = 0.50;
    
    for (let i = 0; i < count; i++) {
        value = Math.max(0.01, Math.min(0.99, value + (Math.random() - 0.5) * 0.03));
        data.push({ time: time + (i * 60), value });
    }
    return data;
}

// ============================================================================
// 7. SSE EVENT HANDLERS
// ============================================================================
function setupSSEHandlers() {
    sseManager.on('status', (data) => {
        if (data.data) statusManager.updateBotStatus(data.data);
    });

    sseManager.on('games', (data) => {
        if (data.data) gamesTableManager.update(data.data);
    });

    sseManager.on('positions', (data) => {
        if (data.data) updatePositionsUI(data.data);
    });

    sseManager.on('heartbeat', () => {
        const el = document.getElementById('last-update');
        if (el) el.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
    });

    sseManager.on('error', (data) => {
        console.error('SSE error:', data);
        statusManager.error(data.error || 'Stream error');
    });
}

function updatePositionsUI(positions) {
    const desktopBody = document.getElementById('positions-table-body');
    const mobileStack = document.getElementById('positions-mobile-stack');

    if (!positions.length) {
        const empty = '<div class="text-center text-secondary py-4">No active positions</div>';
        if (desktopBody) desktopBody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-4">No active positions</td></tr>`;
        if (mobileStack) mobileStack.innerHTML = empty;
        return;
    }

    // Desktop table
    if (desktopBody) {
        desktopBody.innerHTML = positions.map(pos => {
            const pnl = ((pos.current_price || pos.entry_price) - pos.entry_price) * pos.entry_size;
            const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
            return `
                <tr>
                    <td class="ps-4">${pos.team || pos.condition_id?.slice(0, 12) || 'Unknown'}...</td>
                    <td><span class="badge bg-${pos.side === 'YES' ? 'success' : 'danger'}">${pos.side}</span></td>
                    <td>${(pos.entry_price * 100).toFixed(1)}%</td>
                    <td>${((pos.current_price || pos.entry_price) * 100).toFixed(1)}%</td>
                    <td>${pos.entry_size} contracts</td>
                    <td class="${pnlClass}">${formatCurrency(pnl)}</td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-outline-danger" onclick="closePosition('${pos.position_id}')">Exit</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Mobile cards
    if (mobileStack) {
        mobileStack.innerHTML = positions.map(pos => {
            const pnl = ((pos.current_price || pos.entry_price) - pos.entry_price) * pos.entry_size;
            const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
            return `
                <div class="position-card">
                    <div class="card-field">
                        <span class="label">Market</span>
                        <span class="value">${pos.team || 'Position'}</span>
                    </div>
                    <div class="card-field">
                        <span class="label">Side</span>
                        <span class="value"><span class="badge bg-${pos.side === 'YES' ? 'success' : 'danger'}">${pos.side}</span></span>
                    </div>
                    <div class="card-field">
                        <span class="label">Entry / Current</span>
                        <span class="value">${(pos.entry_price * 100).toFixed(1)}% / ${((pos.current_price || pos.entry_price) * 100).toFixed(1)}%</span>
                    </div>
                    <div class="card-field">
                        <span class="label">P&L</span>
                        <span class="value ${pnlClass}">${formatCurrency(pnl)}</span>
                    </div>
                    <button class="btn btn-sm btn-outline-danger w-100 mt-2" onclick="closePosition('${pos.position_id}')">Exit Position</button>
                </div>
            `;
        }).join('');
    }
}

async function closePosition(positionId) {
    try {
        const res = await apiRequest(`/positions/${positionId}/close`, 'POST');
        if (res.ok) {
            toast.success('Position closed');
        } else {
            const err = await res.json();
            toast.error(err.detail || 'Failed to close position');
        }
    } catch (e) {
        toast.error(e.message);
    }
}

// ============================================================================
// 8. MAIN INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', async () => {
    // Show skeletons
    SkeletonManager.show('#positions-table-body', 2);
    SkeletonManager.show('#games-table-body', 3);
    
    // Initialize
    setupSSEHandlers();
    initPerformanceChart();
    sseManager.connect();
    
    // Load initial data
    await loadDashboardData();
    
    // Fallback polling
    setInterval(loadDashboardData, 30000);
    
    // Display date
    const dateEl = document.getElementById('current-date');
    if (dateEl) {
        dateEl.textContent = new Date().toLocaleDateString('en-US', {
            weekday: 'long', month: 'long', day: 'numeric'
        });
    }
});

// ============================================================================
// 9. API & UTILITIES
// ============================================================================
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
    
    const els = {
        portfolio: document.getElementById('portfolio-value'),
        pnl: document.getElementById('daily-pnl'),
        positions: document.getElementById('open-positions'),
        markets: document.getElementById('tracked-markets')
    };
    
    if (els.portfolio) els.portfolio.textContent = formatCurrency(stats.balance_usdc || 0);
    if (els.pnl) {
        const pnl = stats.total_pnl_today || 0;
        els.pnl.textContent = formatCurrency(pnl);
        els.pnl.className = `stat-value ${pnl >= 0 ? 'text-success' : 'text-danger'}`;
    }
    if (els.positions) els.positions.textContent = stats.open_positions_count || 0;
    if (els.markets) els.markets.textContent = stats.active_markets_count || 0;
    
    if (stats.bot_status === 'running') statusManager.startBot(stats.active_markets_count || 0);
    else statusManager.stopBot();
}

window.toggleBot = async () => {
    const isRunning = document.getElementById('bot-indicator')?.classList.contains('running');
    const endpoint = isRunning ? '/bot/stop' : '/bot/start';
    
    const btn = event?.target;
    if (btn) btn.disabled = true;
    
    try {
        const res = await apiRequest(endpoint, 'POST');
        if (res.ok) {
            isRunning ? statusManager.stopBot() : statusManager.startBot();
            toast.success(isRunning ? 'Bot stopped' : 'Bot started');
        } else {
            const err = await res.json();
            toast.error(err.detail || 'Failed to toggle bot');
        }
    } catch (e) {
        toast.error(e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
};

window.toggleWallet = () => {
    const isConnected = document.getElementById('wallet-indicator')?.classList.contains('connected');
    isConnected ? statusManager.disconnectWallet() : statusManager.connectWallet('0x7a2c1e8d4c9Ff3');
};

function formatCurrency(val) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

function formatPercent(val) {
    return `${(val * 100).toFixed(1)}%`;
}

// Cleanup
window.addEventListener('beforeunload', () => sseManager.disconnect());
