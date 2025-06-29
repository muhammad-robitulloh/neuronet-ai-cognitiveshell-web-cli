from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter, Body, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json

from . import ai_core

# Configure logging for main.py
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Web Dashboard Backend",
    description="Backend for AI Shell & Code Assistant Web Dashboard",
    version="0.1.0",
)

# Add CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request bodies
class ChatRequest(BaseModel):
    chat_id: int
    message: str

class FileReadRequest(BaseModel):
    filename: str

class FileDeleteRequest(BaseModel):
    filename: str

class LLMConfigUpdate(BaseModel):
    CODE_GEN_MODEL: str | None = None
    ERROR_FIX_MODEL: str | None = None
    CONVERSATION_MODEL: str | None = None
    COMMAND_CONVERSION_MODEL: str | None = None
    FILENAME_GEN_MODEL: str | None = None
    INTENT_DETECTION_MODEL: str | None = None

class APIKeyUpdate(BaseModel):
    api_key: str

class LLMBaseURLUpdate(BaseModel):
    base_url: str

class TelegramConfigUpdate(BaseModel):
    telegram_chat_id: str | None = None
    telegram_bot_token: str | None = None

class DebugRequest(BaseModel):
    chat_id: int
    response: str


@app.get("/")
async def read_root():
    return {"message": "AI Web Dashboard Backend is running!"}

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    try:
        response = await ai_core.process_user_message(request.chat_id, request.message)
        return response
    except Exception as e:
        logger.error(f"Error in /api/chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/debug")
async def handle_debug(request: DebugRequest):
    try:
        response = await ai_core.process_debug_request(request.chat_id, request.response)
        return response
    except Exception as e:
        logger.error(f"Error in /api/debug: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system_info")
async def get_system_info():
    return ai_core.get_system_info()

@app.get("/api/files")
async def list_files():
    return {"files": ai_core.list_generated_files()}

@app.post("/api/files/read")
async def read_file(request: FileReadRequest):
    success, content = ai_core.read_file_content(request.filename)
    if not success:
        raise HTTPException(status_code=404, detail=content)
    return {"filename": request.filename, "content": content}

@app.delete("/api/files/delete")
async def delete_file(request: FileDeleteRequest):
    success, message = ai_core.delete_file(request.filename)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}

@app.get("/api/settings/llm_config")
async def get_llm_config():
    return ai_core.get_current_llm_models()

@app.put("/api/settings/llm_config")
async def update_llm_config(config: LLMConfigUpdate):
    success, message = ai_core.set_llm_models(config.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}

@app.get("/api/settings/api_key")
async def get_api_key():
    return {"api_key": ai_core.get_openrouter_api_key()}

@app.put("/api/settings/api_key")
async def update_api_key(request: APIKeyUpdate):
    success, message = ai_core.set_openrouter_api_key(request.api_key)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}

@app.get("/api/settings/llm_base_url")
async def get_llm_base_url():
    return {"llm_base_url": ai_core.get_llm_base_url()}

@app.put("/api/settings/llm_base_url")
async def update_llm_base_url(request: LLMBaseURLUpdate):
    success, message = ai_core.set_llm_base_url(request.base_url)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}

@app.get("/api/settings/telegram_config")
async def get_telegram_config():
    return {
        "telegram_chat_id": ai_core.get_telegram_chat_id(),
        "telegram_bot_token": ai_core.get_telegram_bot_token()
    }

@app.put("/api/settings/telegram_config")
async def update_telegram_config(request: TelegramConfigUpdate):
    success_chat_id, msg_chat_id = True, ""
    success_bot_token, msg_bot_token = True, ""

    if request.telegram_chat_id is not None:
        success_chat_id, msg_chat_id = ai_core.set_telegram_chat_id(request.telegram_chat_id)
    if request.telegram_bot_token is not None:
        success_bot_token, msg_bot_token = ai_core.set_telegram_bot_token(request.telegram_bot_token)
    
    if not success_chat_id or not success_bot_token:
        raise HTTPException(status_code=400, detail=f"Chat ID update: {msg_chat_id}, Bot Token update: {msg_bot_token}")
    return {"message": "Telegram configuration updated successfully."}

@app.post("/api/clear_history")
async def clear_history():
    success, message = ai_core.clear_all_chat_history()
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"message": message}

@app.websocket("/ws/shell_output/{chat_id}")
async def websocket_shell_output(websocket: WebSocket, chat_id: int):
    await websocket.accept()
    logger.info(f"WebSocket connected for chat_id: {chat_id}")
    try:
        # Wait for the client to send the command to execute
        command_data = await websocket.receive_json()
        command_to_run = command_data.get("command")

        if not command_to_run:
            await websocket.send_text(json.dumps({"type": "error", "message": "No command provided." }))
            await websocket.close()
            return

        # Stream output from the shell command executor
        async for output_line in ai_core.execute_shell_command(command_to_run, chat_id):
            # Each line from execute_shell_command is prefixed (e.g., "LOG: ", "ERROR: ")
            # We parse it and send as JSON object over WebSocket
            if output_line.startswith("LOG: "):
                await websocket.send_text(json.dumps({"type": "log", "content": output_line[len("LOG: "):].strip()}))
            elif output_line.startswith("ERROR: "):
                await websocket.send_text(json.dumps({"type": "error", "content": output_line[len("ERROR: "):].strip()}))
            elif output_line.startswith("ERROR_DETECTED: "):
                await websocket.send_text(json.dumps({"type": "error_detected", "content": output_line[len("ERROR_DETECTED: "):].strip()}))
            elif output_line.startswith("AI_SUGGESTION: "):
                await websocket.send_text(json.dumps({"type": "ai_suggestion", "content": output_line[len("AI_SUGGESTION: "):].strip()}))
            elif output_line.startswith("AI_SUGGESTION_ERROR: "):
                await websocket.send_text(json.dumps({"type": "ai_suggestion_error", "content": output_line[len("AI_SUGGESTION_ERROR: "):].strip()}))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error in websocket for chat_id {chat_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": f"Internal server error: {e}"}))
        except RuntimeError as re:
            logger.error(f"Could not send error over websocket, connection already closed: {re}")
    finally:
        await websocket.close()