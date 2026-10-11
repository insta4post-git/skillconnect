from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import crud, schemas, storage
from app.database import get_db
from app.models import User
from app.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

# Every endpoint here works on the logged-in user only ("me").
# There is no user id in any URL, so nobody can touch another user's profile.


@router.get("/me/profile", response_model=schemas.UserProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/profile", response_model=schemas.UserProfileOut)
def update_my_profile(
    payload: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.update_user_profile(db, current_user, payload)


@router.post("/me/photo", response_model=schemas.UserProfileOut)
def upload_my_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = file.file.read(storage.MAX_PHOTO_BYTES + 1)
    if len(data) > storage.MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413, detail="Photo is too large. Maximum size is 2 MB."
        )
    extension = storage.detect_image_extension(data)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG or WEBP images are allowed.",
        )

    old_url = current_user.photo_url
    current_user.photo_url = storage.save_photo(current_user.id, data, extension)
    db.commit()
    db.refresh(current_user)
    storage.delete_photo(old_url)
    return current_user


@router.delete("/me/photo", response_model=schemas.UserProfileOut)
def delete_my_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    old_url = current_user.photo_url
    current_user.photo_url = None
    db.commit()
    db.refresh(current_user)
    storage.delete_photo(old_url)
    return current_user
