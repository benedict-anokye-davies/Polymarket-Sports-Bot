let currentStep = 1;
const totalSteps = 5;
let walletConnected = false;

function updateProgress() {
    const progress = (currentStep / totalSteps) * 100;
    document.getElementById('progress-bar').style.width = `${progress}%`;
    document.getElementById('step-indicator').textContent = `Step ${currentStep} of ${totalSteps}`;
    
    document.getElementById('prev-btn').disabled = currentStep === 1;
    
    if (currentStep === totalSteps) {
        document.getElementById('next-btn').innerHTML = 'Finish<i class="bi bi-check-lg ms-2"></i>';
    } else {
        document.getElementById('next-btn').innerHTML = 'Next<i class="bi bi-arrow-right ms-2"></i>';
    }
}

function showStep(step) {
    document.querySelectorAll('.step-content').forEach(el => el.classList.add('d-none'));
    document.getElementById(`step-${step}`).classList.remove('d-none');
}

async function nextStep() {
    if (currentStep === 2 && !walletConnected) {
        showStepAlert('Please test and connect your wallet before proceeding', 'warning');
        return;
    }
    
    if (currentStep === totalSteps) {
        await finishOnboarding();
        return;
    }
    
    currentStep++;
    showStep(currentStep);
    updateProgress();
}

function prevStep() {
    if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
        updateProgress();
    }
}

async function testWalletConnection() {
    const privateKey = document.getElementById('private-key').value;
    const funderAddress = document.getElementById('funder-address').value;
    const signatureType = document.getElementById('signature-type').value;
    
    if (!privateKey || !funderAddress) {
        showWalletStatus('Please fill in all fields', 'danger');
        return;
    }
    
    showWalletStatus('<span class="spinner-border spinner-border-sm me-2"></span>Testing connection...', 'info');
    
    try {
        const response = await apiRequest('/onboarding/wallet/test', {
            method: 'POST',
            body: JSON.stringify({
                private_key: privateKey,
                funder_address: funderAddress,
                signature_type: parseInt(signatureType)
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            walletConnected = true;
            showWalletStatus(`<i class="bi bi-check-circle me-2"></i>Connected! Address: ${data.address}`, 'success');
            
            await apiRequest('/onboarding/wallet/connect', {
                method: 'POST',
                body: JSON.stringify({
                    private_key: privateKey,
                    funder_address: funderAddress,
                    signature_type: parseInt(signatureType)
                })
            });
        } else {
            showWalletStatus(`<i class="bi bi-x-circle me-2"></i>${data.detail || 'Connection failed'}`, 'danger');
        }
    } catch (error) {
        showWalletStatus('<i class="bi bi-x-circle me-2"></i>Connection error', 'danger');
    }
}

function showWalletStatus(message, type) {
    document.getElementById('wallet-status').innerHTML = `
        <div class="alert alert-${type} mb-0">${message}</div>
    `;
}

function showStepAlert(message, type) {
    const existingAlert = document.querySelector('.step-content:not(.d-none) .step-alert');
    if (existingAlert) existingAlert.remove();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} step-alert mt-3`;
    alert.innerHTML = message;
    
    document.querySelector('.step-content:not(.d-none)').prepend(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

async function testDiscord() {
    const webhook = document.getElementById('discord-webhook').value;
    
    if (!webhook) {
        showStepAlert('Please enter a Discord webhook URL', 'warning');
        return;
    }
    
    try {
        const response = await fetch(webhook, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: 'Polymarket Bot test message - Connection successful!'
            })
        });
        
        if (response.ok) {
            showStepAlert('Test message sent successfully!', 'success');
        } else {
            showStepAlert('Failed to send test message. Check your webhook URL.', 'danger');
        }
    } catch (error) {
        showStepAlert('Failed to connect to Discord', 'danger');
    }
}

async function finishOnboarding() {
    const btn = document.getElementById('next-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    
    try {
        const sportConfigs = [];
        ['nba', 'nfl', 'mlb', 'nhl'].forEach(sport => {
            const checkbox = document.getElementById(`sport-${sport}`);
            if (checkbox && checkbox.checked) {
                sportConfigs.push({
                    sport: sport,
                    entry_threshold_pct: parseFloat(document.getElementById('entry-threshold')?.value || 5),
                    absolute_entry_price: parseFloat(document.getElementById('absolute-entry')?.value || 0.35),
                    take_profit_pct: parseFloat(document.getElementById('take-profit')?.value || 10),
                    stop_loss_pct: parseFloat(document.getElementById('stop-loss')?.value || 15),
                    enabled: true
                });
            }
        });
        
        for (const config of sportConfigs) {
            await apiRequest('/settings/sport', {
                method: 'POST',
                body: JSON.stringify(config)
            });
        }
        
        await apiRequest('/settings/global', {
            method: 'PUT',
            body: JSON.stringify({
                max_daily_loss_usdc: parseFloat(document.getElementById('max-daily-loss')?.value || 100),
                max_portfolio_exposure_usdc: parseFloat(document.getElementById('max-exposure')?.value || 500),
                discord_webhook_url: document.getElementById('discord-webhook')?.value || null,
                discord_alerts_enabled: document.getElementById('discord-enabled')?.checked || false
            })
        });
        
        await apiRequest('/onboarding/complete', { method: 'POST' });
        
        window.location.href = '/dashboard';
    } catch (error) {
        console.error('Onboarding error:', error);
        showStepAlert('Failed to save settings. Please try again.', 'danger');
        btn.disabled = false;
        btn.innerHTML = 'Finish<i class="bi bi-check-lg ms-2"></i>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateProgress();
});
