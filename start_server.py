"""
Production-ready server startup script.
Initializes database and starts the FastAPI application.
"""
import sys
import asyncio
import uvicorn

print("=" * 60)
print("POLYMARKET SPORTS TRADING BOT - SERVER STARTUP")
print("=" * 60)

# Test imports
print("\n[1/2] Checking imports...")
try:
    from src.config import get_settings
    print("[OK] All imports successful")
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)

# Start server (database is initialized in app lifespan)
print("\n[2/2] Starting FastAPI server...")
try:
    settings = get_settings()
    print(f"[OK] Server starting on http://{settings.host}:{settings.port}")
    print("\n" + "=" * 60)
    print("POLYMARKET TRADING BOT - PRODUCTION")
    print("=" * 60)
    print("\nEndpoints:")
    print("  - Health: GET /health")
    print("  - Register: POST /api/v1/auth/register")
    print("  - Login: POST /api/v1/auth/login")
    print("  - Dashboard: GET /dashboard")
    print("  - API Docs: GET /docs")
    print("\nPress CTRL+C to stop")
    print("=" * 60 + "\n")

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )
except KeyboardInterrupt:
    print("\n\n[OK] Server shutdown requested")
    sys.exit(0)
except Exception as e:
    print(f"\n[ERROR] Server startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
