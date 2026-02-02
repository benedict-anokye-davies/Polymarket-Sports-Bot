"""Start server and test endpoints."""
import asyncio
import subprocess
import time
import httpx
import sys

async def test_api():
    """Test API endpoints."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        tests = [
            ("/health", "Health check"),
            ("/api/v1/leagues", "Leagues endpoint"),
            ("/login", "Login page"),
        ]
        
        for endpoint, name in tests:
            try:
                response = await client.get(f"{base_url}{endpoint}", timeout=10)
                print(f"✓ {name}: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.text[:100]}...")
            except Exception as e:
                print(f"✗ {name}: Failed - {e}")

if __name__ == "__main__":
    print("Testing API endpoints...")
    print("Make sure server is running: uvicorn src.main:app --reload")
    asyncio.run(test_api())
