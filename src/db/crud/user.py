"""
CRUD operations for User model.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.user import User
from src.core.security import hash_password, verify_password
from src.core.exceptions import NotFoundError, ValidationError


class UserCRUD:
    """
    Database operations for User model.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        username: str,
        email: str,
        password: str
    ) -> User:
        """
        Creates a new user with hashed password.
        
        Args:
            db: Database session
            username: Unique username
            email: User email address
            password: Plain text password (will be hashed)
        
        Returns:
            Created User instance
        
        Raises:
            ValidationError: If username or email already exists
        """
        existing = await db.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Username or email already registered")
        
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        """
        Retrieves a user by their ID.
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """
        Retrieves a user by their email address.
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> User | None:
        """
        Retrieves a user by their username.
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
        """
        Authenticates a user by email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
        
        Returns:
            User instance if credentials valid, None otherwise
        """
        user = await UserCRUD.get_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    @staticmethod
    async def update_onboarding_step(
        db: AsyncSession,
        user_id: uuid.UUID,
        step: int,
        completed: bool = False
    ) -> User:
        """
        Updates user's onboarding progress.
        
        Args:
            db: Database session
            user_id: User ID
            step: Current onboarding step number
            completed: Whether onboarding is fully complete
        
        Returns:
            Updated User instance
        """
        user = await UserCRUD.get_by_id(db, user_id)
        if not user:
            raise NotFoundError("User not found")
        
        user.onboarding_step = step
        user.onboarding_completed = completed
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def get_with_relationships(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        """
        Retrieves a user with all related data loaded.
        """
        result = await db.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.polymarket_account),
                selectinload(User.sport_configs),
                selectinload(User.global_settings)
            )
        )
        return result.scalar_one_or_none()
