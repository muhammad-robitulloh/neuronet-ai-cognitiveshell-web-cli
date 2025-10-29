import json
import logging
import pty
import os
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Literal
from fastapi.exceptions import RequestValidationError
from logging.config import dictConfig
import signal
import sys

from . import config
from .utils import file_utils, shell_utils, telegram_utils
from .ai_core import ai_core_instance
from .config import _load_settings, _save_settings

# --- Custom Logging Formatter ---
class CustomFormatter(logging.Formatter):
    """A custom log formatter to shorten module names."""
    def format(self, record):
        if "uvicorn" in record.name:
            record.name = "uvicorn"
        else:
            # Shorten the module name
            parts = record.name.split('.')
            if len(parts) > 1:
                record.name = parts[-1]
        return super().format(record)

# --- Logging Configuration ---
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": CustomFormatter,
            "fmt": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}

dictConfig(LOGGING_CONFIG)

# --- Logger for this module ---
logger = logging.getLogger(__name__)

# --- Pydantic Models for API Data Validation ---
class ChatRequest(BaseModel):
    chat_id: int
    message: str
    attached_file_path: str | None = None

class AutoDebugRequest(BaseModel):
    request_id: str | None = None
    error_details: str | None = None

class AgentExecuteRequest(BaseModel):
    chat_id: int
    command: str

class FileRequest(BaseModel):
    path: str

class FileWriteRequest(FileRequest):
    content: str

class SettingsUpdateRequest(BaseModel):
    key: str
    value: str

class FileOperationRequest(BaseModel):
    file_path: str

class TelegramSettings(BaseModel):
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str

class WebSearchSettings(BaseModel):
    web_search_enabled: bool
    serper_api_key: str

# --- FastAPI Application Setup ---

app = FastAPI(
    title="Cognitive Shell Backend API",
    description="API to power the NeuroNet AI Cognitive Shell web interface.",
    version="2.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], # Standard React dev ports
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- Application Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")
    if config.TELEGRAM_ENABLED:
        logger.info("Telegram is enabled, attempting to start bot...")
        asyncio.create_task(telegram_utils.start_telegram_bot())
    else:
        logger.info("Telegram is disabled.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")
    await telegram_utils.stop_telegram_bot()

# --- Standard REST API Endpoints ---

import psutil

@app.get("/api/system_stats")
def get_system_stats():
    stats = {}
    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=1, percpu=True)
    except PermissionError:
        stats["cpu_percent"] = [psutil.cpu_percent(interval=1)] # Fallback to overall CPU
    except Exception:
        stats["cpu_percent"] = None

    try:
        stats["cpu_count"] = psutil.cpu_count(logical=True)
    except Exception:
        stats["cpu_count"] = None

    try:
        virtual_memory = psutil.virtual_memory()
        stats["memory_total"] = virtual_memory.total
        stats["memory_available"] = virtual_memory.available
        stats["memory_percent"] = virtual_memory.percent
        stats["memory_used"] = virtual_memory.used
    except Exception:
        stats["memory_total"] = None
        stats["memory_available"] = None
        stats["memory_percent"] = None
        stats["memory_used"] = None

    try:
        swap_memory = psutil.swap_memory()
        stats["swap_total"] = swap_memory.total
        stats["swap_used"] = swap_memory.used
        stats["swap_percent"] = swap_memory.percent
    except Exception:
        stats["swap_total"] = None
        stats["swap_used"] = None
        stats["swap_percent"] = None

    try:
        stats["boot_time"] = psutil.boot_time()
    except PermissionError:
        stats["boot_time"] = "Permission Denied"
    except Exception:
        stats["boot_time"] = None

    try:
        uname_info = os.uname()
        stats["os_name"] = uname_info.sysname
        stats["os_version"] = uname_info.version
        stats["os_release"] = uname_info.release
        stats["machine"] = uname_info.machine
    except Exception:
        stats["os_name"] = None
        stats["os_version"] = None
        stats["os_release"] = None
        stats["machine"] = None

    stats["shell"] = os.environ.get("SHELL", "N/A")

    return stats

@app.get("/api/history/{history_type}")
def get_history(history_type: Literal['chat', 'shell']):
    return file_utils.get_history(history_type)

@app.post("/api/history/clear")
def clear_history():
    result = file_utils.clear_all_history()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["message"])
    return result

class HistoryUpdateRequest(BaseModel):
    history_type: Literal['chat', 'shell']
    history: list

@app.post("/api/history/save")
def save_history(request: HistoryUpdateRequest):
    file_path = config.CHAT_HISTORY_FILE if request.history_type == 'chat' else config.SHELL_HISTORY_FILE
    try:
        with open(file_path, 'w') as f:
            json.dump(request.history, f, indent=4)
        return {"status": "success", "message": f"{request.history_type} history saved."}
    except Exception as e:
        logger.error(f"Error saving {request.history_type} history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save {request.history_type} history.")

@app.post("/api/clear_history")
def clear_history_legacy():
    # This endpoint is for backward compatibility with older frontend calls
    result = file_utils.clear_all_history()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["message"])
    return result

# --- File System API ---
@app.post("/api/fs/list")
def list_files_fs(request: FileRequest):
    # This endpoint is for general file system browsing, not specific generated/uploaded files
    result = file_utils.list_files_in_path(request.path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/fs/read")
def read_file_fs(request: FileRequest):
    result = file_utils.read_file(request.path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/fs/write")
def write_file_fs(request: FileWriteRequest):
    result = file_utils.write_file(request.path, request.content)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/fs/delete")
async def delete_file_fs(request: FileRequest):
    result = file_utils.delete_file(request.path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# --- Settings API ---
@app.get("/api/settings/llm_config")
def get_llm_config():
    # Return relevant LLM config from config.py
    return {
        "CODE_GEN_MODEL": config.CODE_GEN_MODEL,
        "ERROR_FIX_MODEL": config.ERROR_FIX_MODEL,
        "CONVERSATION_MODEL": config.CONVERSATION_MODEL,
        "COMMAND_CONVERSION_MODEL": config.COMMAND_CONVERSION_MODEL,
        "FILENAME_GEN_MODEL": config.FILENAME_GEN_MODEL,
        "INTENT_DETECTION_MODEL": config.INTENT_DETECTION_MODEL,
        "REASONING_ENABLED": config.REASONING_ENABLED,
        "REASONING_MODEL": config.REASONING_MODEL,
        "REASONING_MAX_TOKENS": config.REASONING_MAX_TOKENS,
        "REASONING_TEMPERATURE": config.REASONING_TEMPERATURE,
        "REASONING_APPLY_TO_MODELS": config.REASONING_APPLY_TO_MODELS,
        "DEFAULT_MAX_TOKENS": config.DEFAULT_MAX_TOKENS,
        "DEFAULT_TEMPERATURE": config.DEFAULT_TEMPERATURE,
    }

@app.get("/api/settings/reasoning_enabled")
def get_reasoning_enabled():
    return {"reasoning_enabled": config.REASONING_ENABLED}

@app.put("/api/settings/llm_config")
def update_llm_config(request: Dict[str, Any]):
    for key, value in request.items():
        if hasattr(config, key):
            # Special handling for boolean and list types
            if key == "REASONING_ENABLED" or key == "TELEGRAM_ENABLED":
                setattr(config, key, bool(value))
            elif key == "REASONING_APPLY_TO_MODELS":
                setattr(config, key, value) # Value is already a list from frontend
            elif key == "REASONING_MAX_TOKENS" or key == "DEFAULT_MAX_TOKENS":
                setattr(config, key, int(value))
            elif key == "REASONING_TEMPERATURE" or key == "DEFAULT_TEMPERATURE":
                setattr(config, key, float(value))
            else:
                setattr(config, key, value)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
    _save_settings()
    return {"status": "success", "message": "LLM configuration updated."}

@app.get("/api/settings/api_key")
def get_api_key():
    return {"api_key": config.OPENROUTER_API_KEY}

@app.put("/api/settings/api_key")
def update_api_key(request: SettingsUpdateRequest):
    config.OPENROUTER_API_KEY = request.value
    _save_settings()
    return {"status": "success", "message": "API Key updated."}


@app.get("/api/settings/llm_base_url")
def get_llm_base_url():
    return {"llm_base_url": config.LLM_BASE_URL}

@app.put("/api/settings/llm_base_url")
def update_llm_base_url(request: SettingsUpdateRequest):
    config.LLM_BASE_URL = request.value
    _save_settings()
    return {"status": "success", "message": "LLM Base URL updated."}


@app.get("/api/settings/telegram_bot")
def get_telegram_settings():
    return {
        "telegram_enabled": config.TELEGRAM_ENABLED,
        "telegram_bot_token": config.TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": config.TELEGRAM_CHAT_ID,
    }

@app.put("/api/settings/telegram_bot")
async def update_telegram_settings(request: TelegramSettings):
    # Stop bot if it's currently running and being disabled or token is changing
    if telegram_utils.telegram_application and telegram_utils.telegram_application.running and \
       (config.TELEGRAM_ENABLED and not request.telegram_enabled or \
        config.TELEGRAM_BOT_TOKEN != request.telegram_bot_token):
        await telegram_utils.stop_telegram_bot()

    # Update config variables directly
    config.TELEGRAM_ENABLED = request.telegram_enabled
    config.TELEGRAM_BOT_TOKEN = request.telegram_bot_token
    config.TELEGRAM_CHAT_ID = request.telegram_chat_id
    _save_settings()

    # Start bot if it's enabled and not already running
    if config.TELEGRAM_ENABLED and not (telegram_utils.telegram_application and telegram_utils.telegram_application.running):
        asyncio.create_task(telegram_utils.start_telegram_bot())

    return {"status": "success", "message": "Telegram bot settings updated."}

@app.get("/api/settings/web_search")
def get_web_search_settings():
    return {
        "web_search_enabled": config.WEB_SEARCH_ENABLED,
        "serper_api_key": config.SERPER_API_KEY,
    }

@app.put("/api/settings/web_search")
def update_web_search_settings(request: WebSearchSettings):
    config.WEB_SEARCH_ENABLED = request.web_search_enabled
    config.SERPER_API_KEY = request.serper_api_key
    _save_settings()
    return {"status": "success", "message": "Web search settings updated."}

@app.get("/api/files")
def get_files():
    # List all files, categorized by type
    categorized_files = file_utils.list_all_files_categorized()
    return categorized_files

@app.post("/api/files/read")
def read_any_file(request: FileOperationRequest):
    # file_utils.read_file now handles path validation
    result = file_utils.read_file(request.file_path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"file_path": request.file_path, "content": result["content"]}

@app.delete("/api/files/delete")
def delete_any_file(request: FileOperationRequest):
    # file_utils.delete_file now handles path validation
    result = file_utils.delete_file(request.file_path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success", "message": f"File {request.file_path} deleted."}

@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        result = file_utils.save_uploaded_file(file.filename, content)
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["message"])
        return {"status": "success", "message": f"File {file.filename} uploaded successfully.", "path": result["path"]}
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")

# --- Analytics API ---
@app.get("/api/analytics/token_usage")
def get_token_usage():
    return {"token_usage": file_utils.get_token_usage_data()}

# --- Streaming API Endpoints ---

@app.post("/api/chat")
def chat_stream(request: ChatRequest):
    """Handles a chat message and streams the AI's response back."""
    return StreamingResponse(ai_core_instance.process_chat_stream(request.chat_id, request.message, request.attached_file_path), media_type="application/x-ndjson")

@app.post("/api/agent/execute")
def agent_execute_stream(request: AgentExecuteRequest):
    """Handles an agent execution request and streams the output and analysis."""
    return StreamingResponse(ai_core_instance.execute_and_analyze_stream(request.chat_id, request.command), media_type="application/x-ndjson")

from fastapi.exceptions import RequestValidationError

# ... (rest of imports)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"[Main] Request validation error: {exc.errors()} for request: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body})
    )

@app.exception_handler(Exception)
async def critical_error_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exception, logs it, and triggers a graceful shutdown.
    This is a fail-safe to prevent the server from running in a broken state.
    """
    # Log the critical error with traceback
    logger.critical(f"Critical unhandled exception on request to {request.url}: {exc}", exc_info=True)
    
    # Trigger a graceful shutdown of the server
    logger.info("Triggering graceful shutdown due to critical error...")
    os.kill(os.getpid(), signal.SIGTERM)
    
    # Return a generic 500 error response to the client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A critical internal server error occurred. The server is shutting down."}
    )

# ... (rest of app setup)

@app.post("/api/auto_debug")
async def auto_debug_stream(request: AutoDebugRequest, raw_request: Request):
    request_body = await raw_request.json()
    logger.info(f"[Main] Received auto_debug request body: {request_body}")
    return StreamingResponse(ai_core_instance.process_auto_debug_request(request.request_id), media_type="application/x-ndjson")

# --- WebSocket Endpoint for Interactive Shell ---

@app.websocket("/ws/shell/{chat_id}")
async def websocket_shell(websocket: WebSocket, chat_id: str):
    await websocket.accept()
    
    # Create a pseudo-terminal (pty)
    master_fd, slave_fd = pty.openpty()
    
    # Start a shell process (e.g., bash) in the pty
    shell_process = await asyncio.create_subprocess_exec(
        os.environ.get("SHELL", "/bin/bash"),
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=config.PROJECT_ROOT # Use config.PROJECT_ROOT
    )

    # Get a non-blocking file-like object for the master end of the pty
    master_reader = os.fdopen(master_fd, 'rb', 0)

    async def forward_shell_to_client():
        """Reads from the shell's output and sends it to the WebSocket client."""
        try:
            while True:
                output = await asyncio.to_thread(master_reader.read, 1024)
                if not output:
                    logger.info(f"[WebSocket] Shell output stream for client {chat_id} ended.")
                    break
                await websocket.send_text(output.decode(errors='ignore'))
        except (IOError, WebSocketDisconnect) as e:
            logger.info(f"[WebSocket] Shell output stream for client {chat_id} closed due to: {e}")
        except Exception as e:
            logger.error(f"[WebSocket] Unexpected error in forward_shell_to_client for client {chat_id}: {e}", exc_info=True)
        finally:
            # This task is only for forwarding. The main loop handles all cleanup.
            logger.info(f"[WebSocket] forward_shell_to_client task for client {chat_id} finishing.")

    client_task = asyncio.create_task(forward_shell_to_client(), name=f"shell_forwarder_{chat_id}")

    try:
        while True:
            # Wait for data from the client
            data = await websocket.receive_text()
            logger.debug(f"[WebSocket] Received data from client {chat_id}: {data[:100]}...") # Log first 100 chars
            # Check for resize command (sent as JSON from frontend)
            try:
                data_json = json.loads(data)
                if 'resize' in data_json:
                    import fcntl, termios, struct
                    cols, rows = data_json['resize']['cols'], data_json['resize']['rows']
                    logger.info(f"[WebSocket] Resizing PTY for client {chat_id} to {cols}x{rows}")
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
                    continue # Skip writing resize command to shell
            except json.JSONDecodeError:
                pass # It's regular user input, not a resize command

            # Forward user input to the shell
            os.write(master_fd, data.encode())

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client {chat_id} disconnected.")
    except Exception as e:
        logger.error(f"[WebSocket] Unexpected error in main WebSocket loop for client {chat_id}: {e}", exc_info=True)
    finally:
        logger.info(f"[WebSocket] Cleaning up resources for client {chat_id}.")
        # Clean up: terminate the shell process and cancel the reading task
        client_task.cancel()
        if shell_process.returncode is None:
            logger.info(f"[WebSocket] Terminating shell process for client {chat_id}.")
            shell_process.terminate()
        
        try:
            await shell_process.wait()
        except asyncio.CancelledError:
            logger.info(f"Shell process cleanup for client {chat_id} was interrupted by server shutdown.")

        master_reader.close()
        os.close(master_fd) # Explicitly close the master file descriptor
        os.close(slave_fd) # Explicitly close the slave file descriptor
        logger.info(f"[WebSocket] Resources cleaned up for client {chat_id}.")

# --- Static Files and Frontend Serving ---

# Define the path to the frontend build directory
frontend_build_dir = os.path.abspath(os.path.join(config.PROJECT_ROOT, 'ai_web_dashboard', 'frontend', 'build'))

# Mount the 'static' directory from the build folder
app.mount("/static", StaticFiles(directory=os.path.join(frontend_build_dir, "static")), name="static")

@app.get("/manifest.json")
async def get_manifest():
    return FileResponse(os.path.join(frontend_build_dir, "manifest.json"), media_type="application/manifest+json")

@app.get("/favicon.ico")
async def get_favicon():
    return FileResponse(os.path.join(frontend_build_dir, "favicon.ico"), media_type="image/x-icon")

@app.get("/{rest_of_path:path}")
async def serve_react_app(request: Request, rest_of_path: str):
    """
    Serves the React application.
    This endpoint catches all GET requests that were not handled by other routes.
    It serves the 'index.html' file, which is the entry point for the React app.
    The React router will then handle the specific path on the client-side.
    """
    index_path = os.path.join(frontend_build_dir, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        logger.error(f"Frontend entry point not found: {index_path}")
        raise HTTPException(status_code=404, detail="Frontend not found. Please build the frontend first.")