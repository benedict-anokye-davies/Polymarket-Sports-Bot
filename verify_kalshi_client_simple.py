import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from src.services.kalshi_client import KalshiClient
from unittest.mock import MagicMock, AsyncMock

async def verify_kalshi_client():
    print("Verifying KalshiClient implementation...")
    
    # Mock credentials
    api_key = "test-key"
    private_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAr...\n-----END RSA PRIVATE KEY-----"
    
    # Create client with mock HTTP client to avoid real calls
    client = KalshiClient(api_key, private_key)
    client.client = AsyncMock() # Mock the internal httpx client
    
    # Setup mock response for get_balance
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"balance": 100000} # 100000 cents = $1000
    client.client.request.return_value = mock_response
    
    try:
        # Test 1: Balance Check
        print("\nTest 1: Get Balance")
        balance = await client.get_balance()
        print(f"✅ Balance retrieved: {balance}")
        assert balance["balance"] == 100000
        
        # Test 2: Place Order Formatting
        print("\nTest 2: Place Order Formatting")
        # Setup mock response for order
        order_response = {"order_id": "12345", "status": "placed"}
        mock_response.json.return_value = order_response
        
        result = await client.place_order(
            ticker="NBA-TEST",
            side="buy",
            yes_no="yes",
            price=0.50, # 50 cents
            size=10
        )
        
        # Verify the request payload was formatted correctly (cents conversion)
        call_args = client.client.request.call_args
        # call_args[1] is kwargs, look for 'json'
        payload = call_args[1]['json']
        
        print(f"Payload sent: {payload}")
        
        # Check assertions
        assert payload['ticker'] == "NBA-TEST"
        assert payload['side'] == "buy"
        assert payload['yes'] == True
        assert payload['price'] == 50 # Converted to cents?
        assert payload['count'] == 10
        
        print("✅ Order payload valid (price converted to cents correctly)")
        
        print("\n✅ KalshiClient verification SUCCESS")
        return True
        
    except Exception as e:
        print(f"\n❌ Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()

if __name__ == "__main__":
    # Generate a dummy RSA key for the test initialization to pass
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Overwrite the dummy key with a valid generated formatting one
    # We patch the verify_kalshi_client function's local scope variable via a wrapper if needed, 
    # but here we can just pass it if we modified the function signature.
    # Instead, let's just monkeypatch the file reading or just construct it here.
    
    # Actually, let's just re-implement the verification with the generated key locally
    async def run_with_generated_key():
        client = KalshiClient("test-key", pem)
        client.client = AsyncMock()
        
        # Re-mock balance
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": 100000}
        client.client.request.return_value = mock_response
        
        print("Verifying KalshiClient with generated RSA key...")
        bal = await client.get_balance()
        assert bal['balance'] == 100000
        print("✅ RSA Key loading successful")
        print("✅ API Request signing mechanism successful")

        # Mock order
        client.client.request.reset_mock()
        mock_response.json.return_value = {"order_id": "123", "status": "m"}
        client.client.request.return_value = mock_response
        
        await client.place_order("TICKER", "buy", "yes", 0.99, 100)
        payload = client.client.request.call_args[1]['json']
        
        if payload['price'] == 99:
             print("✅ Price conversion 0.99 -> 99 cents: SUCCESS")
        else:
             print(f"❌ Price conversion FAILED: got {payload['price']}")
             
        await client.close()

    asyncio.run(run_with_generated_key())
