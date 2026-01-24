"""
Quick Supabase Migration Script
Run this after updating your .env with Supabase connection string
"""
import asyncio
import sys
import os

async def main():
    print("=" * 60)
    print("POLYMARKET BOT - SUPABASE MIGRATION")
    print("=" * 60)

    # Check if .env has been updated
    print("\n[1/4] Checking configuration...")
    from src.config import get_settings

    settings = get_settings()

    if "sqlite" in settings.database_url.lower():
        print("[ERROR] Still using SQLite!")
        print("\nPlease update your .env file first:")
        print("1. Go to https://supabase.com and create a project")
        print("2. Get your connection string from Settings > Database")
        print("3. Update DATABASE_URL in .env file")
        print("\nExample:")
        print("DATABASE_URL=postgresql://postgres:yourpassword@db.xxx.supabase.co:5432/postgres")
        sys.exit(1)

    print(f"[OK] Found PostgreSQL connection")
    print(f"     Host: {settings.database_url.split('@')[1].split('/')[0] if '@' in settings.database_url else 'unknown'}")

    # Test connection
    print("\n[2/4] Testing Supabase connection...")
    try:
        from src.db.database import engine
        import sqlalchemy

        # Try to connect
        async with engine.begin() as conn:
            result = await conn.execute(sqlalchemy.text("SELECT version()"))
            version = result.scalar()

        print(f"[OK] Connected to PostgreSQL")
        print(f"     Version: {version[:50]}...")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check your password is correct in .env")
        print("2. Verify Supabase project is 'Active' (green)")
        print("3. Wait 2-3 minutes if project just created")
        await engine.dispose()
        sys.exit(1)

    # Initialize database schema
    print("\n[3/4] Creating database tables...")
    try:
        # Import all models first so they register with Base.metadata
        from src.models import (
            User, PolymarketAccount, SportConfig, TrackedMarket,
            Position, Trade, GlobalSettings, ActivityLog
        )
        from src.db.database import init_db

        await init_db()
        print("[OK] All tables created successfully")
        print("     Tables: users, polymarket_accounts, sport_configs,")
        print("             tracked_markets, positions, trades,")
        print("             global_settings, activity_logs")
    except Exception as e:
        print(f"[ERROR] Failed to create tables: {e}")
        await engine.dispose()
        sys.exit(1)

    # Cleanup
    await engine.dispose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
        sys.exit(1)

    # Success!
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print("=" * 60)
    print("\nYour Polymarket Bot is now connected to Supabase!")
    print("\nNext steps:")
    print("1. Start server: python start_server.py")
    print("2. Open browser: http://localhost:8000")
    print("3. Register your account at /register")
    print("\nSupabase Dashboard:")
    print("- View data: https://supabase.com (Table Editor)")
    print("- Monitor usage: Settings > Database")
    print("\n" + "=" * 60)
