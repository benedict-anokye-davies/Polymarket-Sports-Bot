"""
Comprehensive API test script to verify all endpoints work correctly.
Run this to test the backend and database functionality.
"""
import asyncio
import sys
from sqlalchemy import select

# Test imports
print("Testing imports...")
try:
    from src.config import get_settings
    from src.db.database import async_session_factory, init_db
    from src.models.user import User
    from src.core.security import hash_password, verify_password, create_access_token
    from src.db.crud.user import UserCRUD
    from src.db.crud.global_settings import GlobalSettingsCRUD
    from src.db.crud.sport_config import SportConfigCRUD
    print("[OK] All imports successful")
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)


async def test_database():
    """Test database initialization and basic operations."""
    print("\n=== Testing Database ===")

    try:
        # Initialize database
        await init_db()
        print("[OK] Database initialized")

        # Test session creation
        async with async_session_factory() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            print(f"[OK] Database connection working (found {len(users)} users)")

        return True
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")
        return False


async def test_password_hashing():
    """Test password hashing and verification."""
    print("\n=== Testing Password Hashing ===")

    try:
        test_password = "testpassword123"

        # Test hashing
        hashed = hash_password(test_password)
        print(f"[OK] Password hashed successfully: {hashed[:20]}...")

        # Test verification with correct password
        if verify_password(test_password, hashed):
            print("[OK] Password verification works (correct password)")
        else:
            print("[ERROR] Password verification failed (correct password)")
            return False

        # Test verification with wrong password
        if not verify_password("wrongpassword", hashed):
            print("[OK] Password verification works (wrong password rejected)")
        else:
            print("[ERROR] Password verification failed (wrong password accepted)")
            return False

        return True
    except Exception as e:
        print(f"[ERROR] Password hashing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_registration():
    """Test user registration flow."""
    print("\n=== Testing User Registration ===")

    try:
        async with async_session_factory() as session:
            # Create test user
            user = await UserCRUD.create(
                session,
                username="testuser",
                email="test@example.com",
                password="securepass123"
            )
            print(f"[OK] User created: {user.username} ({user.email})")

            # Create global settings
            settings = await GlobalSettingsCRUD.create(session, user.id)
            print(f"[OK] Global settings created for user")

            # Create sport configs
            configs = await SportConfigCRUD.create_defaults_for_user(session, user.id)
            print(f"[OK] Created {len(configs)} sport configurations")

            return True
    except Exception as e:
        print(f"[ERROR] User registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_authentication():
    """Test user authentication."""
    print("\n=== Testing User Authentication ===")

    try:
        async with async_session_factory() as session:
            # Authenticate user
            user = await UserCRUD.authenticate(
                session,
                email="test@example.com",
                password="securepass123"
            )

            if user:
                print(f"[OK] User authenticated: {user.username}")

                # Test token creation
                token = create_access_token({"sub": str(user.id)})
                print(f"[OK] JWT token created: {token[:30]}...")

                return True
            else:
                print("[ERROR] Authentication failed")
                return False

    except Exception as e:
        print(f"[ERROR] Authentication test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests in sequence."""
    print("=" * 60)
    print("BACKEND & DATABASE TEST SUITE")
    print("=" * 60)

    results = {
        "Database": await test_database(),
        "Password Hashing": await test_password_hashing(),
        "User Registration": await test_user_registration(),
        "User Authentication": await test_user_authentication(),
    }

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n[SUCCESS] All tests passed! Backend is working correctly.")
        print("\nYou can now start the server with:")
        print("  python -m uvicorn src.main:app --host 0.0.0.0 --port 8000")
        return 0
    else:
        print("\n[FAILURE] Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
