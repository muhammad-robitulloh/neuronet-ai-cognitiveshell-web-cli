import json
from pathlib import Path
import logging
import shutil
from typing import Optional, Dict, Any, List
from .. import config

logger = logging.getLogger(__name__)

def get_history(history_type: str):
    filepath = config.CHAT_HISTORY_FILE if history_type == 'chat' else config.SHELL_HISTORY_FILE
    try:
        return json.loads(filepath.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def clear_all_history():
    """Clears all history files and in-memory stores."""
    try:
        for filepath in [config.CHAT_HISTORY_FILE, config.SHELL_HISTORY_FILE, config.TOKEN_USAGE_FILE]:
            if filepath.exists():
                filepath.write_text("[]")
        logger.info("[Core] All history cleared.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"[Core] Failed to clear history: {e}")
        return {"status": "error", "message": str(e)}

def save_uploaded_file(file_name: str, file_content: bytes):
    """Saves an uploaded file to the files_storage directory."""
    try:
        # Ensure the files_storage directory exists
        config.FILES_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        file_path = config.FILES_STORAGE_PATH / file_name
        file_path.write_bytes(file_content)
        return {"status": "success", "path": str(file_path.relative_to(config.PROJECT_ROOT))}
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        return {"status": "error", "message": str(e)}

def list_files(storage_type: str = 'generated') -> Dict[str, Any]:
    """Lists files from either generated_files or files_storage directory."""
    if storage_type == 'generated':
        target_dir = config.GENERATED_FILES_PATH
    elif storage_type == 'uploaded':
        target_dir = config.FILES_STORAGE_PATH
    else:
        return {"error": "Invalid storage type. Must be 'generated' or 'uploaded'."}

    try:
        items = []
        for item in sorted(list(target_dir.iterdir()), key=lambda f: (f.is_file(), f.name.lower())):
            items.append({
                "name": item.name,
                "path": str(item.relative_to(config.PROJECT_ROOT)),
                "is_dir": item.is_dir()
            })
        return {"path": str(target_dir.relative_to(config.PROJECT_ROOT)), "items": items}
    except Exception as e:
        return {"error": str(e)}

def list_all_files_categorized() -> Dict[str, List[Dict[str, Any]]]:
    """Lists all files from generated_files and files_storage, categorizing them."""
    generated_files = []
    uploaded_files = []
    system_json_files = []

    # System JSON files
    system_json_paths = [
        config.CHAT_HISTORY_FILE,
        config.SHELL_HISTORY_FILE,
        config.TOKEN_USAGE_FILE,
        config.SETTINGS_FILE,
    ]

    # Process generated_files
    try:
        for item in sorted(list(config.GENERATED_FILES_PATH.iterdir()), key=lambda f: (f.is_file(), f.name.lower())):
            if item.is_file():
                if item in system_json_paths:
                    system_json_files.append({
                        "name": item.name,
                        "path": str(item.relative_to(config.PROJECT_ROOT)),
                        "is_dir": False,
                        "is_system_file": True
                    })
                else:
                    generated_files.append({
                        "name": item.name,
                        "path": str(item.relative_to(config.PROJECT_ROOT)),
                        "is_dir": False,
                        "is_system_file": False
                    })
    except Exception as e:
        logger.error(f"Error listing generated files in {config.GENERATED_FILES_PATH}: {e}")

    # Process files_storage
    try:
        for item in sorted(list(config.FILES_STORAGE_PATH.iterdir()), key=lambda f: (f.is_file(), f.name.lower())):
            if item.is_file():
                uploaded_files.append({
                    "name": item.name,
                    "path": str(item.relative_to(config.PROJECT_ROOT)),
                    "is_dir": False,
                    "is_system_file": False # Uploaded files are never system files
                })
    except Exception as e:
        logger.error(f"Error listing uploaded files in {config.FILES_STORAGE_PATH}: {e}")

    return {
        "generated_files": generated_files,
        "uploaded_files": uploaded_files,
        "system_json_files": system_json_files
    }

def read_file(file_path: str):
    """Reads and returns the content of a specified file from allowed directories."""
    target_path = (config.PROJECT_ROOT / file_path).resolve()

    # Check if the file is within generated_files or files_storage
    if not (target_path.is_relative_to(config.GENERATED_FILES_PATH) or
            target_path.is_relative_to(config.FILES_STORAGE_PATH)):
        return {"error": "Access Denied. File not in allowed directories."}

    if target_path.is_dir():
        return {"error": "Access Denied. Path is a directory."}

    try:
        return {"path": file_path, "content": target_path.read_text()}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}

def write_file(file_path: str, content: str):
    """Writes content to a specified file, restricted to generated_files."""
    target_path = (config.PROJECT_ROOT / file_path).resolve()
    if not target_path.is_relative_to(config.GENERATED_FILES_PATH) or target_path.is_dir():
        return {"error": "Access Denied or is a directory. Can only write to generated_files."}
    try:
        target_path.write_text(content)
        return {"status": "success", "path": file_path}
    except Exception as e:
        return {"error": f"Failed to write to file: {e}"}

def delete_file(file_path: str):
    """Deletes a specified file from allowed directories."""
    target_path = (config.PROJECT_ROOT / file_path).resolve()

    # Check if the file is within generated_files or files_storage
    if not (target_path.is_relative_to(config.GENERATED_FILES_PATH) or
            target_path.is_relative_to(config.FILES_STORAGE_PATH)):
        return {"error": "Access Denied. File not in allowed directories."}

    if target_path.is_dir():
        return {"error": "Access Denied. Path is a directory."}

    # Prevent deletion of system JSON files
    system_json_paths = [
        config.CHAT_HISTORY_FILE,
        config.SHELL_HISTORY_FILE,
        config.TOKEN_USAGE_FILE,
    ]
    if target_path in system_json_paths:
        return {"error": "Access Denied. Cannot delete system JSON files."}

    try:
        target_path.unlink()
        return {"status": "success", "path": file_path}
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        return {"error": f"Failed to delete file: {e}"}

def get_token_usage_data():
    try:
        return json.loads(config.TOKEN_USAGE_FILE.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_token_usage_data(data: list):
    try:
        config.TOKEN_USAGE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"[Core] Failed to save token usage data: {e}")


