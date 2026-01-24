// Dashboard.js - Advanced Real-Time features
// Implements surgical DOM diffing, lightweight charts, and status management

// --- 1. Status Manager & Visual Hierarchy ---
class StatusManager {
    constructor() {
        this.state = {
            wallet: { connected: false, address: null },
            bot: { running: false, markets: 0 },
            errors: []
        };
        // Simulated initial state
        this.disconnectWallet(); 
        this.stopBot();
    }

    connectWallet(address) {
        this.state.wallet = { connected: true, address };
        this._updateUI();
    }

    disconnectWallet() {
        this.state.wallet = { connected: false, address: null };
        this._updateUI();
    }

    startBot(markets = 0) {
        this.state.bot = { running: true, markets };
        this._updateUI();
    }

    stopBot() {
        this.state.bot = { running: false, markets: 0 };
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
        if (this.state.wallet.connected) {
            wInd.className = 'status-indicator connected';
            wVal.textContent = this._shortenAddress(this.state.wallet.address);
        } else {
            wInd.className = 'status-indicator';
            wVal.textContent = 'Disconnected';
        }

        // Bot UI
        const bInd = document.getElementById('bot-indicator');
        const bVal = document.getElementById('bot-status-text');
        if (this.state.bot.running) {
            bInd.className = 'status-indicator running';
            bVal.textContent = \Active (\ mkts)\;
        } else {
            bInd.className = 'status-indicator paused';
            bVal.textContent = 'Stopped';
        }

        // Errors UI
        if (this.state.errors.length > 0) {
            alertsSection.style.display = 'flex';
            alertsSection.innerHTML = this.state.errors.map(err => \
                <div class="status-item critical">
                    <span class="status-indicator error"></span>
                    <span class="status-label">Error</span>
                    <span class="status-value">\</span>
                    <button class="status-action" onclick="statusManager.dismissError(\)">✕</button>
                </div>
            \).join('');
        } else {
            alertsSection.style.display = 'none';
        }
    }

    _showError(id, msg) {
        this._updateUI();
        console.warn(\[System Alert] \\);
    }

    _shortenAddress(addr) {
        return addr ? \\...\\ : '';
    }
}

const statusManager = new StatusManager();

// --- 2. OrderBook Differ (Surgical DOM Updates) ---
class OrderBookDiffer {
    constructor(tbodySelector) {
        this.tbody = document.querySelector(tbodySelector);
        this.rows = new Map(); // price -> tr element
    }

    update(data) {
        // data = [{ price: 0.50, size: 1000, total: 5000, type: 'bid'|'ask' }, ...]
        if (!this.tbody) return;

        const incomingPrices = new Set(data.map(d => d.price));
        
        // Remove stale rows
        for (const [price, row] of this.rows) {
            if (!incomingPrices.has(price)) {
                row.remove();
                this.rows.delete(price);
            }
        }

        // Update or create rows
        data.forEach(item => {
            if (this.rows.has(item.price)) {
                this._updateRow(this.rows.get(item.price), item);
            } else {
                const newRow = this._createRow(item);
                this._insertSorted(newRow, item.price);
                this.rows.set(item.price, newRow);
            }
        });
    }

    _createRow(item) {
        const tr = document.createElement('tr');
        tr.dataset.price = item.price;
        tr.innerHTML = \
            <td class="\">\</td>
            <td class="text-end" data-key="size">\</td>
            <td class="text-end text-secondary" data-key="total">\</td> 
        \; 
        return tr;
    }

    _updateRow(tr, item) {
        const sizeCell = tr.querySelector('[data-key="size"]');
        const oldSize = parseInt(sizeCell.textContent);
        
        if (oldSize !== item.size) {
            sizeCell.textContent = item.size;
            this._flashCell(sizeCell, item.size - oldSize);
        }
    }

    _flashCell(cell, diff) {
        cell.classList.remove('cell-flash-up', 'cell-flash-down');
        void cell.offsetWidth; // Force reflow
        cell.classList.add(diff > 0 ? 'cell-flash-up' : 'cell-flash-down');
    }

    _insertSorted(newRow, price) {
        // Appending for visual simplicity in this demo
        this.tbody.appendChild(newRow);
    }
}

const orderBookDiffer = new OrderBookDiffer('#orderbook-body');

// --- 3. Charting (Lightweight Charts) ---
let chart;
let candleSeries;

function initChart() {
    const container = document.getElementById('chart-container');
    if (!container) return;

    chart = LightweightCharts.createChart(container, {
        layout: {
            textColor: '#a1a1aa',
            background: { type: 'solid', color: 'transparent' }
        },
        grid: {
            vertLines: { color: '#27272a' },
            horzLines: { color: '#27272a' },
        },
        rightPriceScale: {
            borderColor: '#27272a',
        },
        timeScale: {
            borderColor: '#27272a',
            timeVisible: true,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444', 
        borderVisible: false, 
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444'
    });

    const initialData = generateMockCandles(100);
    candleSeries.setData(initialData);

    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== container) { return; }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(container);
}

// --- 4. Main Initialization & Simulation ---

document.addEventListener('DOMContentLoaded', async () => {
    initChart();
    startSimulation(); // Remove this when real WebSocket is added
    
    refreshInterval = setInterval(loadDashboardData, 10000); // Keep for stats
    await loadDashboardData();
});

// Mock Data Generators
function generateMockCandles(count) {
    let data = [];
    let time = Math.floor(Date.now() / 1000) - (count * 60);
    let value = 0.50;
    
    for (let i = 0; i < count; i++) {
        let open = value;
        let close = value + (Math.random() - 0.5) * 0.02;
        let high = Math.max(open, close) + Math.random() * 0.01;
        let low = Math.min(open, close) - Math.random() * 0.01;
        
        data.push({ time: time + (i * 60), open, high, low, close });
        value = close;
    }
    return data;
}

function startSimulation() {
    setInterval(() => {
        const basePrice = 0.50;
        const mockBook = [];
        for (let i = 5; i > 0; i--) {
            mockBook.push({ price: basePrice + (i * 0.01), size: Math.floor(Math.random() * 1000) + 100, type: 'ask' });
        }
        for (let i = 0; i < 5; i++) {
            mockBook.push({ price: basePrice - (i * 0.01), size: Math.floor(Math.random() * 1000) + 100, type: 'bid' });
        }
        orderBookDiffer.update(mockBook);
    }, 1000);
}

// --- Existing Dashboard Logic (Adapted) ---
let refreshInterval = null;

async function loadDashboardData() {
    try {
        const stats = await apiRequest('/dashboard/stats').then(r => r.ok ? r.json() : null);
        if (stats) updateStats(stats);

        const botStatus = await apiRequest('/bot/status').then(r => r.ok ? r.json() : null);
        if (botStatus && botStatus.bot_enabled) {
            statusManager.startBot(5);
        } else {
            statusManager.stopBot();
        }
        
    } catch (e) {
        // statusManager.error("Connection lost"); // Optional: don't spam on poll fail
    }
}

function updateStats(stats) {
    if (!stats) return;
    document.getElementById('portfolio-value').textContent = formatCurrency(stats.portfolio_value || 0);
    document.getElementById('active-pnl').textContent = formatCurrency(stats.active_pnl || 0);
    document.getElementById('open-positions').textContent = stats.open_positions || 0;
    document.getElementById('tracked-markets').textContent = stats.tracked_markets || 0;
}

window.toggleBot = async () => {
    const isRunning = document.getElementById('bot-indicator').classList.contains('running');
    const endpoint = isRunning ? '/bot/stop' : '/bot/start';
    
    try {
        const res = await apiRequest(endpoint, 'POST');
        if (res.ok) {
            isRunning ? statusManager.stopBot() : statusManager.startBot();
        } else {
            statusManager.error("Failed to toggle bot");
        }
    } catch (e) {
        statusManager.error(e.message);
    }
};

window.toggleWallet = () => {
    const isConnected = document.getElementById('wallet-indicator').classList.contains('connected');
    if (isConnected) {
        statusManager.disconnectWallet();
    } else {
        statusManager.connectWallet('0x7a2c1e8d4c9Ff3');
    }
};

function formatCurrency(val) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
}
