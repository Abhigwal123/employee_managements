"""
User schemas for API requests and responses
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    """User creation schema"""
    password: str


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class UserInDB(UserBase):
    """User in database schema"""
    id: int
    hashed_password: str
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    timezone: str
    language: str
    subscription_plan: str
    subscription_expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class User(UserBase):
    """User response schema"""
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    timezone: str
    language: str
    subscription_plan: str
    subscription_expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """User login schema"""
    username: str
    password: str


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data schema"""
    username: Optional[str] = None
