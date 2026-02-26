from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
import re

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    avatar_url = Column(String, nullable=True)
    last_username_change = Column(DateTime(timezone=True), nullable=True)
    last_email_change = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    anime_list = relationship("UserAnimeList", back_populates="owner", cascade="all, delete-orphan")

class UserAnimeList(Base):
    __tablename__ = "user_anime_list"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    shikimori_id = Column(String, index=True) # ID аниме
    status = Column(String, index=True)       # watching, planned, completed, on_hold, dropped
    is_favorite = Column(Boolean, default=False)
    episodes_watched = Column(Integer, default=0)
    score = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    owner = relationship("User", back_populates="anime_list")

# Pydantic models for API requests/responses
class AnimeListItemCreateUpdate(BaseModel):
    shikimori_id: str
    status: str | None = None
    is_favorite: bool | None = None
    episodes_watched: int | None = None
    score: int | None = None

class AnimeListItemResponse(BaseModel):
    id: int
    user_id: int
    shikimori_id: str
    status: str
    is_favorite: bool
    episodes_watched: int
    score: int | None
    updated_at: datetime

    class Config:
        from_attributes = True

class UserUpdateUsername(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern="^[a-zA-Z0-9_.-]+$")

class UserUpdateEmail(BaseModel):
    email: EmailStr

class UserUpdatePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r"[a-z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        if not re.search(r"\d", v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern="^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=6)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r"[a-z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        if not re.search(r"\d", v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    avatar_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
