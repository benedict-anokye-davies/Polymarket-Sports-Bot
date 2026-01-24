document.addEventListener('DOMContentLoaded', () => {
    loadCurrentSettings();
});

async function loadCurrentSettings() {
    try {
        const [globalResponse, sportsResponse] = await Promise.all([
            apiRequest('/settings/global'),
            apiRequest('/settings/sports')
        ]);
        
        if (globalResponse.ok) {
            const global = await globalResponse.json();
            document.getElementById('max-daily-loss').value = global.max_daily_loss_usdc || 100;
            document.getElementById('max-exposure').value = global.max_portfolio_exposure_usdc || 500;
            document.getElementById('discord-webhook').value = global.discord_webhook_url || '';
            document.getElementById('discord-enabled').checked = global.discord_alerts_enabled || false;
        }
        
        if (sportsResponse.ok) {
            const sports = await sportsResponse.json();
            sports.forEach(sport => {
                const checkbox = document.getElementById(`sport-${sport.sport}`);
                if (checkbox) {
                    checkbox.checked = sport.enabled;
                }
                
                const sportCard = document.querySelector(`[data-sport="${sport.sport}"]`);
                if (sportCard) {
                    sportCard.querySelector('.entry-threshold')?.setAttribute('value', sport.entry_threshold_pct);
                    sportCard.querySelector('.take-profit')?.setAttribute('value', sport.take_profit_pct);
                    sportCard.querySelector('.stop-loss')?.setAttribute('value', sport.stop_loss_pct);
                }
            });
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveGlobalSettings() {
    const btn = document.querySelector('#global-settings-form button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    btn.disabled = true;
    
    try {
        const response = await apiRequest('/settings/global', {
            method: 'PUT',
            body: JSON.stringify({
                max_daily_loss_usdc: parseFloat(document.getElementById('max-daily-loss').value),
                max_portfolio_exposure_usdc: parseFloat(document.getElementById('max-exposure').value),
                discord_webhook_url: document.getElementById('discord-webhook').value || null,
                discord_alerts_enabled: document.getElementById('discord-enabled').checked
            })
        });
        
        if (response.ok) {
            showSettingsAlert('Settings saved successfully', 'success');
        } else {
            const data = await response.json();
            showSettingsAlert(data.detail || 'Failed to save settings', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Failed to save settings', 'danger');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function saveSportSettings(sport) {
    const card = document.querySelector(`[data-sport="${sport}"]`);
    const btn = card.querySelector('.save-sport-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;
    
    try {
        const response = await apiRequest('/settings/sport', {
            method: 'PUT',
            body: JSON.stringify({
                sport: sport,
                entry_threshold_pct: parseFloat(card.querySelector('.entry-threshold').value),
                absolute_entry_price: parseFloat(card.querySelector('.absolute-entry')?.value || 0.35),
                take_profit_pct: parseFloat(card.querySelector('.take-profit').value),
                stop_loss_pct: parseFloat(card.querySelector('.stop-loss').value),
                enabled: document.getElementById(`sport-${sport}`).checked
            })
        });
        
        if (response.ok) {
            showSettingsAlert(`${sport.toUpperCase()} settings saved`, 'success');
        } else {
            const data = await response.json();
            showSettingsAlert(data.detail || 'Failed to save settings', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Failed to save settings', 'danger');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function testWalletConnection() {
    const btn = document.getElementById('test-wallet-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
    btn.disabled = true;
    
    try {
        const response = await apiRequest('/polymarket/test-connection');
        const data = await response.json();
        
        if (response.ok && data.connected) {
            document.getElementById('wallet-status').innerHTML = `
                <span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Connected</span>
            `;
            showSettingsAlert(`Wallet connected: ${data.address}`, 'success');
        } else {
            document.getElementById('wallet-status').innerHTML = `
                <span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Disconnected</span>
            `;
            showSettingsAlert(data.detail || 'Connection failed', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Connection test failed', 'danger');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function updateWallet() {
    const privateKey = document.getElementById('private-key').value;
    const funderAddress = document.getElementById('funder-address').value;
    const signatureType = document.getElementById('signature-type').value;
    
    if (!privateKey || !funderAddress) {
        showSettingsAlert('Please fill in all wallet fields', 'warning');
        return;
    }
    
    const btn = document.getElementById('update-wallet-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
    btn.disabled = true;
    
    try {
        const response = await apiRequest('/polymarket/credentials', {
            method: 'PUT',
            body: JSON.stringify({
                private_key: privateKey,
                funder_address: funderAddress,
                signature_type: parseInt(signatureType)
            })
        });
        
        if (response.ok) {
            showSettingsAlert('Wallet credentials updated', 'success');
            document.getElementById('private-key').value = '';
            document.getElementById('funder-address').value = '';
            
            const walletModal = bootstrap.Modal.getInstance(document.getElementById('walletModal'));
            walletModal.hide();
            
            await testWalletConnection();
        } else {
            const data = await response.json();
            showSettingsAlert(data.detail || 'Failed to update credentials', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Failed to update credentials', 'danger');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function testDiscordWebhook() {
    const webhook = document.getElementById('discord-webhook').value;
    
    if (!webhook) {
        showSettingsAlert('Please enter a Discord webhook URL', 'warning');
        return;
    }
    
    const btn = document.getElementById('test-discord-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
    btn.disabled = true;
    
    try {
        const response = await fetch(webhook, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: 'Polymarket Bot test notification - Connection successful!'
            })
        });
        
        if (response.ok) {
            showSettingsAlert('Discord test message sent successfully', 'success');
        } else {
            showSettingsAlert('Failed to send Discord test message', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Failed to connect to Discord', 'danger');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function resetDailyStats() {
    if (!confirm('Are you sure you want to reset today\'s statistics?')) {
        return;
    }
    
    try {
        const response = await apiRequest('/trading/reset-daily', { method: 'POST' });
        
        if (response.ok) {
            showSettingsAlert('Daily statistics reset', 'success');
        } else {
            showSettingsAlert('Failed to reset statistics', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Failed to reset statistics', 'danger');
    }
}

async function exportSettings() {
    try {
        const response = await apiRequest('/settings/export');
        const data = await response.json();
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'polymarket-bot-settings.json';
        a.click();
        URL.revokeObjectURL(url);
        
        showSettingsAlert('Settings exported', 'success');
    } catch (error) {
        showSettingsAlert('Failed to export settings', 'danger');
    }
}

async function importSettings(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    try {
        const text = await file.text();
        const settings = JSON.parse(text);
        
        const response = await apiRequest('/settings/import', {
            method: 'POST',
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showSettingsAlert('Settings imported successfully', 'success');
            await loadCurrentSettings();
        } else {
            showSettingsAlert('Failed to import settings', 'danger');
        }
    } catch (error) {
        showSettingsAlert('Invalid settings file', 'danger');
    }
    
    event.target.value = '';
}

function showSettingsAlert(message, type) {
    const container = document.getElementById('settings-alerts') || createAlertsContainer();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.appendChild(alert);
    
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}

function createAlertsContainer() {
    const container = document.createElement('div');
    container.id = 'settings-alerts';
    container.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 1050; max-width: 400px;';
    document.body.appendChild(container);
    return container;
}
