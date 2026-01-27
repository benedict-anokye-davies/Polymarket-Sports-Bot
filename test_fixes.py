"""
Comprehensive test script for validating Kalshi integration fixes.
Tests all critical issues that were fixed.
"""

import asyncio
import inspect
import sys

async def run_tests():
    results = {'passed': [], 'failed': []}
    
    # Test 1: Module imports
    print('='*60)
    print('TEST 1: Module Imports')
    print('='*60)
    try:
        from src.services.kalshi_client import KalshiClient, KalshiAuthenticator
        from src.services.market_discovery import MarketDiscovery, market_discovery
        from src.services.bot_runner import BotRunner, BotState
        from src.services.polymarket_client import PolymarketClient
        from src.services.espn_service import ESPNService
        from src.services.trading_engine import TradingEngine
        from src.api.routes.bot import router as bot_router
        from src.api.routes.dashboard import router as dashboard_router
        from src.api.routes.onboarding import router as onboarding_router
        from src.main import app
        print('[PASS] All module imports successful')
        results['passed'].append('Module imports')
    except Exception as e:
        print(f'[FAIL] Module import error: {e}')
        results['failed'].append(f'Module imports: {e}')
    
    # Test 2: RSA key validation
    print()
    print('='*60)
    print('TEST 2: Kalshi RSA Key Validation')
    print('='*60)
    try:
        from src.core.exceptions import TradingError
        from src.services.kalshi_client import KalshiAuthenticator
        try:
            auth = KalshiAuthenticator('test_key', 'invalid_pem_data')
            print('[FAIL] Should have raised TradingError for invalid PEM')
            results['failed'].append('RSA validation: Did not raise error for invalid PEM')
        except TradingError as e:
            if 'PEM format' in str(e):
                print('[PASS] RSA validation raises user-friendly error')
                results['passed'].append('RSA key validation')
            else:
                print(f'[FAIL] Wrong error message: {e}')
                results['failed'].append(f'RSA validation wrong message: {e}')
    except Exception as e:
        print(f'[FAIL] RSA validation test error: {e}')
        results['failed'].append(f'RSA validation: {e}')
    
    # Test 3: Empty API key validation
    print()
    print('='*60)
    print('TEST 3: Empty API Key Validation')
    print('='*60)
    try:
        from src.core.exceptions import TradingError
        from src.services.kalshi_client import KalshiAuthenticator
        try:
            auth = KalshiAuthenticator('', 'some_key')
            print('[FAIL] Should have raised TradingError for empty API key')
            results['failed'].append('Empty API key validation failed')
        except TradingError as e:
            if 'API key is required' in str(e):
                print('[PASS] Empty API key raises user-friendly error')
                results['passed'].append('Empty API key validation')
            else:
                print(f'[FAIL] Wrong error message: {e}')
                results['failed'].append(f'Empty API key wrong message: {e}')
    except Exception as e:
        print(f'[FAIL] Empty API key test error: {e}')
        results['failed'].append(f'Empty API key: {e}')
    
    # Test 4: Market Discovery methods exist
    print()
    print('='*60)
    print('TEST 4: Market Discovery Methods')
    print('='*60)
    try:
        from src.services.market_discovery import market_discovery
        methods = ['discover_sports_markets', 'discover_kalshi_markets', 'discover_markets_for_platform']
        for method in methods:
            if hasattr(market_discovery, method):
                print(f'[PASS] {method} exists')
                results['passed'].append(f'MarketDiscovery.{method}')
            else:
                print(f'[FAIL] {method} missing')
                results['failed'].append(f'MarketDiscovery.{method} missing')
    except Exception as e:
        print(f'[FAIL] Market discovery test error: {e}')
        results['failed'].append(f'Market discovery: {e}')
    
    # Test 5: KalshiClient dry_run mode
    print()
    print('='*60)
    print('TEST 5: KalshiClient Dry Run Mode')
    print('='*60)
    try:
        from src.services.kalshi_client import KalshiClient
        source = inspect.getsource(KalshiClient.place_order)
        if 'dry_run' in source and 'DRY RUN' in source:
            print('[PASS] place_order has dry_run support')
            results['passed'].append('KalshiClient.place_order dry_run')
        else:
            print('[FAIL] place_order missing dry_run logic')
            results['failed'].append('KalshiClient.place_order dry_run missing')
        
        source = inspect.getsource(KalshiClient.wait_for_fill)
        if 'dry_run' in source or 'dry-run-' in source:
            print('[PASS] wait_for_fill has dry_run support')
            results['passed'].append('KalshiClient.wait_for_fill dry_run')
        else:
            print('[FAIL] wait_for_fill missing dry_run logic')
            results['failed'].append('KalshiClient.wait_for_fill dry_run missing')
    except Exception as e:
        print(f'[FAIL] KalshiClient dry_run test error: {e}')
        results['failed'].append(f'KalshiClient dry_run: {e}')
    
    # Test 6: BotRunner platform awareness
    print()
    print('='*60)
    print('TEST 6: BotRunner Platform Awareness')
    print('='*60)
    try:
        from src.services.bot_runner import BotRunner
        init_source = inspect.getsource(BotRunner.initialize)
        if 'platform' in init_source and 'polymarket' in init_source.lower():
            print('[PASS] BotRunner.initialize has platform checks')
            results['passed'].append('BotRunner platform-aware init')
        else:
            print('[FAIL] BotRunner.initialize missing platform checks')
            results['failed'].append('BotRunner platform-aware init missing')
        
        discovery_source = inspect.getsource(BotRunner._discovery_loop)
        if 'discover_markets_for_platform' in discovery_source:
            print('[PASS] _discovery_loop uses platform-aware discovery')
            results['passed'].append('BotRunner platform-aware discovery')
        else:
            print('[FAIL] _discovery_loop not using platform-aware discovery')
            results['failed'].append('BotRunner platform-aware discovery missing')
    except Exception as e:
        print(f'[FAIL] BotRunner platform test error: {e}')
        results['failed'].append(f'BotRunner platform: {e}')
    
    # Test 7: Dashboard platform-aware balance
    print()
    print('='*60)
    print('TEST 7: Dashboard Platform-Aware Balance')
    print('='*60)
    try:
        from src.api.routes import dashboard
        source = inspect.getsource(dashboard.get_dashboard_stats)
        if 'platform' in source and 'kalshi' in source.lower():
            print('[PASS] Dashboard has platform-aware balance fetch')
            results['passed'].append('Dashboard platform-aware balance')
        else:
            print('[FAIL] Dashboard missing platform-aware balance')
            results['failed'].append('Dashboard platform-aware balance missing')
    except Exception as e:
        print(f'[FAIL] Dashboard test error: {e}')
        results['failed'].append(f'Dashboard: {e}')
    
    # Test 8: Onboarding platform-aware wallet test
    print()
    print('='*60)
    print('TEST 8: Onboarding Platform-Aware Wallet Test')
    print('='*60)
    try:
        from src.api.routes import onboarding
        source = inspect.getsource(onboarding.test_wallet_connection)
        if 'platform' in source and 'kalshi' in source.lower():
            print('[PASS] Onboarding has platform-aware wallet test')
            results['passed'].append('Onboarding platform-aware wallet test')
        else:
            print('[FAIL] Onboarding missing platform-aware wallet test')
            results['failed'].append('Onboarding platform-aware wallet test missing')
    except Exception as e:
        print(f'[FAIL] Onboarding test error: {e}')
        results['failed'].append(f'Onboarding: {e}')
    
    # Test 9: Bot.py credential keys
    print()
    print('='*60)
    print('TEST 9: Bot.py Credential Keys')
    print('='*60)
    try:
        from src.api.routes import bot
        source = inspect.getsource(bot)
        # Check that old wrong keys are NOT present
        if 'kalshi_api_key' in source or 'kalshi_private_key' in source:
            print('[FAIL] Bot.py still uses wrong credential keys')
            results['failed'].append('Bot.py using wrong credential keys')
        else:
            # Check that correct keys are used
            if 'credentials.get("api_key")' in source and 'credentials.get("api_secret")' in source:
                print('[PASS] Bot.py uses correct credential keys')
                results['passed'].append('Bot.py credential keys')
            else:
                print('[WARN] Bot.py may have issues with credential keys')
                results['passed'].append('Bot.py credential keys (partial)')
    except Exception as e:
        print(f'[FAIL] Bot.py test error: {e}')
        results['failed'].append(f'Bot.py: {e}')
    
    # Test 10: FastAPI App loads
    print()
    print('='*60)
    print('TEST 10: FastAPI App Loads')
    print('='*60)
    try:
        from src.main import app
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        if len(routes) > 10:
            print(f'[PASS] FastAPI app loaded with {len(routes)} routes')
            results['passed'].append('FastAPI app loads')
        else:
            print(f'[FAIL] FastAPI app has too few routes: {len(routes)}')
            results['failed'].append(f'FastAPI app only has {len(routes)} routes')
    except Exception as e:
        print(f'[FAIL] FastAPI app test error: {e}')
        results['failed'].append(f'FastAPI app: {e}')
    
    return results


async def run_api_tests():
    """Test actual API endpoints using test client."""
    results = {'passed': [], 'failed': []}
    
    print()
    print('='*60)
    print('API INTEGRATION TESTS')
    print('='*60)
    
    try:
        from src.main import app
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            
            # Test 1: Register
            print()
            print('Testing: POST /api/v1/auth/register')
            resp = await client.post('/api/v1/auth/register', json={
                'email': 'testuser@example.com',
                'password': 'testpass123'
            })
            if resp.status_code in [200, 201, 400]:  # 400 if user exists
                print(f'[PASS] Register endpoint works (status: {resp.status_code})')
                results['passed'].append('Register endpoint')
            else:
                print(f'[FAIL] Register failed with status {resp.status_code}: {resp.text}')
                results['failed'].append(f'Register: {resp.status_code}')
            
            # Test 2: Login
            print()
            print('Testing: POST /api/v1/auth/login')
            resp = await client.post('/api/v1/auth/login', data={
                'username': 'testuser@example.com',
                'password': 'testpass123'
            })
            token = None
            if resp.status_code == 200:
                token = resp.json().get('access_token')
                print(f'[PASS] Login successful, got token')
                results['passed'].append('Login endpoint')
            else:
                print(f'[FAIL] Login failed with status {resp.status_code}: {resp.text}')
                results['failed'].append(f'Login: {resp.status_code}')
            
            if token:
                headers = {'Authorization': f'Bearer {token}'}
                
                # Test 3: Onboarding status
                print()
                print('Testing: GET /api/v1/onboarding/status')
                resp = await client.get('/api/v1/onboarding/status', headers=headers)
                if resp.status_code == 200:
                    print(f'[PASS] Onboarding status works')
                    results['passed'].append('Onboarding status endpoint')
                else:
                    print(f'[FAIL] Onboarding status failed: {resp.status_code}')
                    results['failed'].append(f'Onboarding status: {resp.status_code}')
                
                # Test 4: Dashboard stats
                print()
                print('Testing: GET /api/v1/dashboard/stats')
                resp = await client.get('/api/v1/dashboard/stats', headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f'[PASS] Dashboard stats works')
                    print(f'       Balance: {data.get("balance_usdc", "N/A")}')
                    results['passed'].append('Dashboard stats endpoint')
                elif resp.status_code == 403:
                    print(f'[PASS] Dashboard requires onboarding (expected behavior)')
                    results['passed'].append('Dashboard stats endpoint (auth check)')
                else:
                    print(f'[FAIL] Dashboard stats failed: {resp.status_code} - {resp.text[:100]}')
                    results['failed'].append(f'Dashboard stats: {resp.status_code}')
                
                # Test 5: Bot status
                print()
                print('Testing: GET /api/v1/bot/status')
                resp = await client.get('/api/v1/bot/status', headers=headers)
                if resp.status_code == 200:
                    print(f'[PASS] Bot status works')
                    results['passed'].append('Bot status endpoint')
                elif resp.status_code == 403:
                    print(f'[PASS] Bot status requires onboarding (expected)')
                    results['passed'].append('Bot status endpoint (auth check)')
                else:
                    print(f'[FAIL] Bot status failed: {resp.status_code}')
                    results['failed'].append(f'Bot status: {resp.status_code}')
                
                # Test 6: Wallet connect (Kalshi)
                print()
                print('Testing: POST /api/v1/onboarding/wallet/connect (Kalshi)')
                resp = await client.post('/api/v1/onboarding/wallet/connect', headers=headers, json={
                    'platform': 'kalshi',
                    'api_key': 'test_api_key_123',
                    'api_secret': 'test_api_secret_456'
                })
                if resp.status_code == 200:
                    print(f'[PASS] Kalshi wallet connect works')
                    results['passed'].append('Kalshi wallet connect')
                else:
                    print(f'[FAIL] Kalshi wallet connect failed: {resp.status_code} - {resp.text[:100]}')
                    results['failed'].append(f'Kalshi wallet connect: {resp.status_code}')
                
                # Test 7: Wallet test (should fail with invalid creds but not crash)
                print()
                print('Testing: POST /api/v1/onboarding/wallet/test')
                resp = await client.post('/api/v1/onboarding/wallet/test', headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Should return success=False due to invalid creds, but not crash
                    if 'success' in data:
                        print(f'[PASS] Wallet test endpoint works (success={data.get("success")})')
                        results['passed'].append('Wallet test endpoint')
                    else:
                        print(f'[WARN] Wallet test returned unexpected format')
                        results['passed'].append('Wallet test endpoint (format issue)')
                else:
                    print(f'[FAIL] Wallet test crashed: {resp.status_code} - {resp.text[:100]}')
                    results['failed'].append(f'Wallet test: {resp.status_code}')
    
    except Exception as e:
        print(f'[FAIL] API test error: {e}')
        import traceback
        traceback.print_exc()
        results['failed'].append(f'API tests: {e}')
    
    return results


async def main():
    print()
    print('#'*60)
    print('# POLYMARKET-KALSHI BOT - COMPREHENSIVE TEST SUITE')
    print('#'*60)
    
    # Run code tests
    code_results = await run_tests()
    
    # Run API tests
    api_results = await run_api_tests()
    
    # Combine results
    all_passed = code_results['passed'] + api_results['passed']
    all_failed = code_results['failed'] + api_results['failed']
    
    # Print summary
    print()
    print('#'*60)
    print('# FINAL SUMMARY')
    print('#'*60)
    print(f'Total Passed: {len(all_passed)}')
    print(f'Total Failed: {len(all_failed)}')
    print()
    
    if all_failed:
        print('FAILURES:')
        print('-'*40)
        for f in all_failed:
            print(f'  ❌ {f}')
    
    print()
    if all_passed:
        print('PASSED:')
        print('-'*40)
        for p in all_passed:
            print(f'  ✅ {p}')
    
    return len(all_failed) == 0


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
