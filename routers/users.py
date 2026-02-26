from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
from models import User, UserCreate, UserResponse, Token
from auth import (
    get_user,
    get_user_by_email,
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    db_email = get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, username=form_data.username)
    
    # Allow login by email as well
    if not user:
        user = get_user_by_email(db, email=form_data.username)
        
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

from models import UserUpdateUsername, UserUpdateEmail, UserUpdatePassword
from fastapi import UploadFile, File
import os
import uuid
import datetime

@router.put("/me/username", response_model=UserResponse)
def update_username(req: UserUpdateUsername, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.last_username_change:
        days_since = (datetime.datetime.now(datetime.timezone.utc) - current_user.last_username_change).days
        if days_since < 7:
            raise HTTPException(status_code=400, detail=f"Имя пользователя можно менять раз в 7 дней. Осталось {7 - days_since} дней.")
    
    # Check if taken
    if get_user(db, req.username) and current_user.username != req.username:
        raise HTTPException(status_code=400, detail="Это имя пользователя уже занято.")

    current_user.username = req.username
    current_user.last_username_change = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/email", response_model=UserResponse)
def update_email(req: UserUpdateEmail, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.last_email_change:
        days_since = (datetime.datetime.now(datetime.timezone.utc) - current_user.last_email_change).days
        if days_since < 30:
            raise HTTPException(status_code=400, detail=f"Email можно менять раз в 30 дней. Осталось {30 - days_since} дней.")
    
    if get_user_by_email(db, req.email) and current_user.email != req.email:
        raise HTTPException(status_code=400, detail="Этот email уже используется.")

    current_user.email = req.email
    current_user.last_email_change = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password")
def update_password(req: UserUpdatePassword, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    current_user.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"status": "success"}

@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")
    
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join("static", "avatars", filename)
    
    with open(filepath, "wb") as f:
        f.write(await file.read())
        
    # Delete old avatar if exists
    if current_user.avatar_url:
        old_path = current_user.avatar_url.lstrip("/") # remove leading slash
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except:
                pass

    current_user.avatar_url = f"/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user
from models import AnimeListItemCreateUpdate, AnimeListItemResponse, UserAnimeList
from typing import List

@router.get("/me/list", response_model=List[AnimeListItemResponse])
def get_user_list(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Returns all items in the user's list
    return current_user.anime_list

@router.post("/me/list", response_model=AnimeListItemResponse)
def add_or_update_list_item(item: AnimeListItemCreateUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if this anime is already in the user's list
    existing_item = db.query(UserAnimeList).filter(
        UserAnimeList.user_id == current_user.id,
        UserAnimeList.shikimori_id == item.shikimori_id
    ).first()
    
    if existing_item:
        # Update fields if provided
        if item.status is not None:
            existing_item.status = item.status
        if item.is_favorite is not None:
            existing_item.is_favorite = item.is_favorite
        if item.episodes_watched is not None:
            existing_item.episodes_watched = item.episodes_watched
        if item.score is not None:
            existing_item.score = item.score
            
        db.commit()
        db.refresh(existing_item)
        return existing_item
        
    else:
        # Create new list item
        new_item = UserAnimeList(
            user_id=current_user.id,
            shikimori_id=item.shikimori_id,
            status=item.status or "planned",
            is_favorite=item.is_favorite if item.is_favorite is not None else False,
            episodes_watched=item.episodes_watched or 0,
            score=item.score
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item

@router.delete("/me/list/{shikimori_id}")
def remove_list_item(shikimori_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing_item = db.query(UserAnimeList).filter(
        UserAnimeList.user_id == current_user.id,
        UserAnimeList.shikimori_id == shikimori_id
    ).first()
    
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found in your list")
        
    db.delete(existing_item)
    db.commit()
    return {"status": "success", "message": "Item removed from list"}
