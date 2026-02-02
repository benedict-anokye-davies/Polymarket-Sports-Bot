"""Test API endpoints."""
import asyncio
import httpx
from src.main import app
from src.config import get_settings

async def test_health():
    """Test health endpoint."""
    settings = get_settings()
    base_url = f"http://localhost:{settings.port}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Health endpoint: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Health check failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_health())
