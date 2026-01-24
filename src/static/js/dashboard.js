let pnlChart = null;
let winrateChart = null;
let refreshInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboardData();
    initCharts();
    
    refreshInterval = setInterval(loadDashboardData, 10000);
});

async function loadDashboardData() {
    try {
        const [statsResponse, marketsResponse, activityResponse] = await Promise.all([
            apiRequest('/dashboard/stats'),
            apiRequest('/trading/markets'),
            apiRequest('/logs?limit=5')
        ]);
        
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateStats(stats);
        }
        
        if (marketsResponse.ok) {
            const markets = await marketsResponse.json();
            updateLiveMarkets(markets);
        }
        
        if (activityResponse.ok) {
            const activity = await activityResponse.json();
            updateRecentActivity(activity);
        }
        
        await loadBotStatus();
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

async function loadBotStatus() {
    try {
        const response = await apiRequest('/bot/status');
        if (response.ok) {
            const data = await response.json();
            updateBotStatus(data.bot_enabled);
        }
    } catch (error) {
        console.error('Failed to load bot status:', error);
    }
}

function updateStats(stats) {
    document.getElementById('portfolio-value').textContent = formatCurrency(stats.portfolio_value || 0);
    
    const pnl = stats.daily_pnl || 0;
    const pnlElement = document.getElementById('daily-pnl');
    pnlElement.textContent = formatCurrency(pnl);
    pnlElement.className = pnl >= 0 ? 'text-success mb-0' : 'text-danger mb-0';
    
    document.getElementById('open-positions').textContent = stats.open_positions || 0;
    document.getElementById('tracked-markets').textContent = stats.tracked_markets || 0;
}

function updateBotStatus(enabled) {
    const badge = document.getElementById('bot-status-badge');
    const btn = document.getElementById('toggle-bot-btn');
    const text = document.getElementById('toggle-bot-text');
    
    if (enabled) {
        badge.className = 'badge bg-success';
        badge.textContent = 'Running';
        btn.className = 'btn btn-danger btn-sm';
        text.textContent = 'Stop';
    } else {
        badge.className = 'badge bg-secondary';
        badge.textContent = 'Stopped';
        btn.className = 'btn btn-success btn-sm';
        text.textContent = 'Start';
    }
}

async function toggleBot() {
    const btn = document.getElementById('toggle-bot-btn');
    btn.disabled = true;
    
    try {
        const response = await apiRequest('/bot/toggle', { method: 'POST' });
        if (response.ok) {
            const data = await response.json();
            updateBotStatus(data.bot_enabled);
        }
    } catch (error) {
        console.error('Failed to toggle bot:', error);
    } finally {
        btn.disabled = false;
    }
}

function updateLiveMarkets(markets) {
    const table = document.getElementById('live-markets-table');
    const liveCount = document.getElementById('live-count');
    
    const liveMarkets = markets.filter(m => m.is_live);
    liveCount.textContent = `${liveMarkets.length} Live`;
    
    if (liveMarkets.length === 0) {
        table.innerHTML = `
            <tr>
                <td colspan="4" class="text-center text-secondary py-4">
                    No live markets being tracked
                </td>
            </tr>
        `;
        return;
    }
    
    table.innerHTML = liveMarkets.map(market => {
        const change = ((market.current_price_yes - market.baseline_price_yes) / market.baseline_price_yes * 100).toFixed(1);
        const changeClass = parseFloat(change) >= 0 ? 'text-success' : 'text-danger';
        const changeIcon = parseFloat(change) >= 0 ? 'bi-caret-up-fill' : 'bi-caret-down-fill';
        
        return `
            <tr class="border-secondary">
                <td>
                    <div class="fw-medium text-light">${market.home_abbrev} vs ${market.away_abbrev}</div>
                    <small class="text-secondary">${market.sport.toUpperCase()}</small>
                </td>
                <td class="text-light">${formatPrice(market.current_price_yes)}</td>
                <td class="${changeClass}">
                    <i class="bi ${changeIcon}"></i> ${change}%
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-success" onclick="viewMarket('${market.id}')">
                        <i class="bi bi-eye"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function updateRecentActivity(logs) {
    const container = document.getElementById('recent-activity');
    
    if (!logs.length) {
        container.innerHTML = `
            <div class="list-group-item bg-dark border-secondary text-center text-secondary py-4">
                No recent activity
            </div>
        `;
        return;
    }
    
    container.innerHTML = logs.map(log => {
        const levelClass = {
            'INFO': 'text-info',
            'WARNING': 'text-warning',
            'ERROR': 'text-danger',
            'SUCCESS': 'text-success'
        }[log.level] || 'text-secondary';
        
        const icon = {
            'INFO': 'bi-info-circle',
            'WARNING': 'bi-exclamation-triangle',
            'ERROR': 'bi-x-circle',
            'SUCCESS': 'bi-check-circle'
        }[log.level] || 'bi-circle';
        
        return `
            <div class="list-group-item bg-dark border-secondary">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <i class="bi ${icon} ${levelClass} me-2"></i>
                        <span class="text-light">${log.message}</span>
                    </div>
                    <small class="text-secondary">${formatTime(log.created_at)}</small>
                </div>
            </div>
        `;
    }).join('');
}

function initCharts() {
    const pnlCtx = document.getElementById('pnl-chart');
    if (pnlCtx) {
        pnlChart = new Chart(pnlCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'P&L',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#6c757d' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { 
                            color: '#6c757d',
                            callback: (value) => '$' + value
                        }
                    }
                }
            }
        });
    }
    
    const winrateCtx = document.getElementById('winrate-chart');
    if (winrateCtx) {
        winrateChart = new Chart(winrateCtx, {
            type: 'doughnut',
            data: {
                labels: ['Wins', 'Losses'],
                datasets: [{
                    data: [0, 0],
                    backgroundColor: ['#28a745', '#dc3545'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#6c757d' }
                    }
                }
            }
        });
    }
}

function formatCurrency(value) {
    const num = parseFloat(value);
    const prefix = num >= 0 ? '$' : '-$';
    return prefix + Math.abs(num).toFixed(2);
}

function formatPrice(value) {
    return '$' + parseFloat(value).toFixed(4);
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}

function viewMarket(marketId) {
    window.location.href = `/markets/${marketId}`;
}
