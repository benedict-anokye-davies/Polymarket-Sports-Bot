const API_BASE = '/api/v1';

function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

async function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        return null;
    }
    
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            const refreshed = await refreshToken();
            if (!refreshed) {
                logout();
                return null;
            }
            return checkAuth();
        }
        
        if (!response.ok) {
            logout();
            return null;
        }
        
        return await response.json();
    } catch (error) {
        console.error('Auth check failed:', error);
        return null;
    }
}

async function refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;
    
    try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            return true;
        }
        return false;
    } catch (error) {
        return false;
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
}

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            ...getAuthHeaders(),
            ...(options.headers || {})
        }
    });
    
    if (response.status === 401) {
        const refreshed = await refreshToken();
        if (refreshed) {
            return apiRequest(endpoint, options);
        }
        logout();
        throw new Error('Authentication failed');
    }
    
    return response;
}

document.addEventListener('DOMContentLoaded', async () => {
    const publicPaths = ['/login', '/register'];
    if (publicPaths.includes(window.location.pathname)) {
        return;
    }
    
    const user = await checkAuth();
    if (user) {
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay) {
            usernameDisplay.textContent = user.username;
        }
        
        if (!user.onboarding_completed && window.location.pathname !== '/onboarding') {
            window.location.href = '/onboarding';
        }
    }
});
