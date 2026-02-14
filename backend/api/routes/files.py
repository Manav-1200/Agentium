"""
File upload and download API for chat attachments.
Handles multipart file uploads, storage, and retrieval.
"""

import os
import uuid
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import aiofiles

from backend.models.database import get_db
from backend.core.auth import get_current_active_user
from backend.models.entities.user import User

router = APIRouter(prefix="/files", tags=["Files"])

# Configuration - use /tmp as primary storage (temporary)
def get_upload_dir() -> Path:
    """Get upload directory in /tmp."""
    path = Path("/tmp/agentium_uploads/files")
    path.mkdir(parents=True, exist_ok=True)
    return path

UPLOAD_DIR = get_upload_dir()
print(f"[Files] Using upload directory: {UPLOAD_DIR}")

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'],
    'video': ['.mp4', '.webm', '.mov', '.avi', '.mkv'],
    'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.webm'],
    'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
    'code': ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sql', '.md'],
    'archive': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
    'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
    'presentation': ['.ppt', '.pptx', '.odp']
}

# Flatten allowed extensions for validation
ALL_ALLOWED_EXTENSIONS = set()
for ext_list in ALLOWED_EXTENSIONS.values():
    ALL_ALLOWED_EXTENSIONS.update(ext_list)


def get_file_category(filename: str) -> str:
    """Determine file category based on extension."""
    ext = Path(filename).suffix.lower()
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return category
    return 'other'


def get_file_icon(category: str) -> str:
    """Get emoji icon for file category."""
    icons = {
        'image': '🖼️',
        'video': '🎬',
        'audio': '🎵',
        'document': '📄',
        'code': '💻',
        'archive': '📦',
        'spreadsheet': '📊',
        'presentation': '📽️',
        'other': '📎'
    }
    return icons.get(category, '📎')


def format_file_size(bytes_size: int) -> str:
    """Format file size for human reading."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in ALL_ALLOWED_EXTENSIONS


def generate_safe_filename(original_filename: str) -> str:
    """Generate a safe, unique filename for storage."""
    ext = Path(original_filename).suffix.lower()
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return f"{timestamp}_{unique_id}{ext}"


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload one or more files.
    Returns metadata for each uploaded file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )

    uploaded_files = []
    errors = []

    for file in files:
        # Validate filename
        if not file.filename:
            errors.append({"error": "File has no filename"})
            continue

        # Check file extension
        if not is_allowed_file(file.filename):
            errors.append({
                "filename": file.filename,
                "error": f"File type not allowed. Allowed: {', '.join(sorted(ALL_ALLOWED_EXTENSIONS))}"
            })
            continue

        # Read file content
        try:
            content = await file.read()
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": f"Failed to read file: {str(e)}"
            })
            continue

        # Check file size
        if len(content) > MAX_FILE_SIZE:
            errors.append({
                "filename": file.filename,
                "error": f"File exceeds {MAX_FILE_SIZE / (1024*1024):.0f}MB limit ({len(content) / (1024*1024):.1f}MB)"
            })
            continue

        # Generate safe filename and storage path
        safe_filename = generate_safe_filename(file.filename)
        user_dir = UPLOAD_DIR / str(current_user.id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = user_dir / safe_filename

        # Save file to disk
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": f"Failed to save file: {str(e)}"
            })
            continue

        # Determine MIME type
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
        category = get_file_category(file.filename)

        # Build response metadata
        file_info = {
            "id": str(uuid.uuid4()),
            "original_name": file.filename,
            "stored_name": safe_filename,
            "url": f"/api/v1/files/download/{current_user.id}/{safe_filename}",
            "type": mime_type,
            "category": category,
            "size": len(content),
            "uploaded_at": datetime.utcnow().isoformat()
        }
        uploaded_files.append(file_info)

    # If all files failed, return error
    if not uploaded_files and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors}
        )

    return {
        "success": True,
        "files": uploaded_files,
        "total_uploaded": len(uploaded_files),
        "errors": errors if errors else None
    }


@router.get("/download/{user_id}/{filename}")
async def download_file(
    user_id: str,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Download a specific file.
    Users can only access their own files unless they're admin.
    """
    # Security check - users can only access their own files
    if str(current_user.id) != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    file_path = UPLOAD_DIR / user_id / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Determine media type
    media_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/list")
async def list_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all files for the current user.
    """
    user_dir = UPLOAD_DIR / str(current_user.id)
    
    if not user_dir.exists():
        return {
            "files": [],
            "total": 0,
            "storage_used_bytes": 0
        }

    files = []
    total_size = 0

    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            size = stat.st_size
            total_size += size
            
            files.append({
                "filename": file_path.name,
                "stored_name": file_path.name,
                "url": f"/api/v1/files/download/{current_user.id}/{file_path.name}",
                "size": size,
                "category": get_file_category(file_path.name),
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    # Sort by upload time (newest first)
    files.sort(key=lambda x: x["uploaded_at"], reverse=True)

    return {
        "files": files,
        "total": len(files),
        "storage_used_bytes": total_size
    }


@router.delete("/{filename}")
async def delete_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a file.
    """
    user_dir = UPLOAD_DIR / str(current_user.id)
    file_path = user_dir / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    try:
        file_path.unlink()
        return {
            "success": True,
            "message": f"File {filename} deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/stats")
async def get_file_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get file statistics for the current user.
    """
    user_dir = UPLOAD_DIR / str(current_user.id)
    
    stats = {
        "total_files": 0,
        "total_size_bytes": 0,
        "by_category": {},
        "storage_limit_bytes": 500 * 1024 * 1024,  # 500MB limit per user
        "storage_used_percent": 0
    }

    if not user_dir.exists():
        return stats

    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            size = stat.st_size
            category = get_file_category(file_path.name)

            stats["total_files"] += 1
            stats["total_size_bytes"] += size
            
            if category not in stats["by_category"]:
                stats["by_category"][category] = 0
            stats["by_category"][category] += size

    # Calculate percentage
    stats["storage_used_percent"] = round(
        (stats["total_size_bytes"] / stats["storage_limit_bytes"]) * 100, 
        2
    )

    return stats


@router.get("/preview/{user_id}/{filename}")
async def preview_file(
    user_id: str,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Preview a file (for images/videos that can be displayed inline).
    Same security as download but with inline disposition.
    """
    # Security check
    if str(current_user.id) != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    file_path = UPLOAD_DIR / user_id / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    media_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    # Only allow preview for safe types
    if not (media_type.startswith('image/') or media_type.startswith('video/') or media_type == 'application/pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not supported for preview"
        )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        content_disposition_type="inline"
    )