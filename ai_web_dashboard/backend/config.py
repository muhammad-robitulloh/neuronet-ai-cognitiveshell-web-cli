import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import platform
import logging
import json

logger = logging.getLogger(__name__)

# Determine project root
try:
    PROJECT_ROOT = Path(find_dotenv()).parent.resolve()
except Exception:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Define data directories and files
GENERATED_FILES_PATH = PROJECT_ROOT / "generated_files"
FILES_STORAGE_PATH = PROJECT_ROOT / "files_storage"
CHAT_HISTORY_FILE = GENERATED_FILES_PATH / "chat_history.json"
SHELL_HISTORY_FILE = GENERATED_FILES_PATH / "shell_history.json"
TOKEN_USAGE_FILE = GENERATED_FILES_PATH / "token_usage.json"
SETTINGS_FILE = GENERATED_FILES_PATH / "settings.json" # New settings file
ENV_PATH = PROJECT_ROOT / ".env"

# Ensure data directories and essential files exist
GENERATED_FILES_PATH.mkdir(exist_ok=True)
FILES_STORAGE_PATH.mkdir(exist_ok=True)
for f in [CHAT_HISTORY_FILE, SHELL_HISTORY_FILE, TOKEN_USAGE_FILE]:
    if not f.exists():
        f.touch()
        f.write_text("[]")

# Ensure .env file exists (it might be empty)
if not ENV_PATH.exists():
    ENV_PATH.touch()

# Load environment variables from .env file
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Create settings.json with default values if it doesn't exist
if not SETTINGS_FILE.exists():
    default_settings = {
        "OPENROUTER_API_KEY": "",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1/chat/completions",
        "CODE_GEN_MODEL": "moonshotai/kimi-dev-72b:free",
        "ERROR_FIX_MODEL": "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "CONVERSATION_MODEL": "mistralai/mistral-small-3.2-24b-instruct",
        "COMMAND_CONVERSION_MODEL": "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "FILENAME_GEN_MODEL": "mistralai/mistral-small-3.2-24b-instruct",
        "INTENT_DETECTION_MODEL": "mistralai/mistral-small-3.2-24b-instruct",
        "WEB_EXTRACTION_MODEL": "mistralai/mistral-small-3.2-24b-instruct",
        "REASONING_ENABLED": False,
        "REASONING_MODEL": "mistralai/mistral-small-3.2-24b-instruct", # Default to conversation model
        "REASONING_MAX_TOKENS": 200,
        "REASONING_TEMPERATURE": 0.7,
        "REASONING_APPLY_TO_MODELS": [
            "CODE_GEN_MODEL",
            "ERROR_FIX_MODEL",
            "CONVERSATION_MODEL",
            "COMMAND_CONVERSION_MODEL",
            "FILENAME_GEN_MODEL",
            "INTENT_DETECTION_MODEL"
        ],
        "TELEGRAM_ENABLED": False,
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "DEFAULT_MAX_TOKENS": 1000, # New global setting
        "DEFAULT_TEMPERATURE": 0.7, # New global setting
        "WEB_SEARCH_ENABLED": False,
        "GOOGLE_API_KEY": "",
        "GOOGLE_CSE_ID": "",
        "SERPER_API_KEY": "",
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(default_settings, f, indent=4)

# Global variables for settings
OPENROUTER_API_KEY = ""
LLM_BASE_URL = ""
CODE_GEN_MODEL = ""
ERROR_FIX_MODEL = ""
CONVERSATION_MODEL = ""
COMMAND_CONVERSION_MODEL = ""
FILENAME_GEN_MODEL = ""
INTENT_DETECTION_MODEL = ""
WEB_EXTRACTION_MODEL = ""
REASONING_ENABLED = False
REASONING_MODEL = ""
REASONING_MAX_TOKENS = 0
REASONING_TEMPERATURE = 0.0
REASONING_APPLY_TO_MODELS = []
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
DEFAULT_MAX_TOKENS = 0
DEFAULT_TEMPERATURE = 0.0
WEB_SEARCH_ENABLED = False
GOOGLE_API_KEY = ""
GOOGLE_CSE_ID = ""

def _load_settings():
    """Loads settings from settings.json into global variables."""
    global OPENROUTER_API_KEY, LLM_BASE_URL, CODE_GEN_MODEL, ERROR_FIX_MODEL,            CONVERSATION_MODEL, COMMAND_CONVERSION_MODEL, FILENAME_GEN_MODEL,            INTENT_DETECTION_MODEL, WEB_EXTRACTION_MODEL, REASONING_ENABLED, REASONING_MODEL,            REASONING_MAX_TOKENS, REASONING_TEMPERATURE, REASONING_APPLY_TO_MODELS,            TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,            DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, WEB_SEARCH_ENABLED,            GOOGLE_API_KEY, GOOGLE_CSE_ID, SERPER_API_KEY

    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)

        OPENROUTER_API_KEY = settings.get("OPENROUTER_API_KEY", "")
        LLM_BASE_URL = settings.get("LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
        CODE_GEN_MODEL = settings.get("CODE_GEN_MODEL", "moonshotai/kimi-dev-72b:free")
        ERROR_FIX_MODEL = settings.get("ERROR_FIX_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")
        CONVERSATION_MODEL = settings.get("CONVERSATION_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
        COMMAND_CONVERSION_MODEL = settings.get("COMMAND_CONVERSION_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")
        FILENAME_GEN_MODEL = settings.get("FILENAME_GEN_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
        INTENT_DETECTION_MODEL = settings.get("INTENT_DETECTION_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
        WEB_EXTRACTION_MODEL = settings.get("WEB_EXTRACTION_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
        
        REASONING_ENABLED = settings.get("REASONING_ENABLED", False)
        REASONING_MODEL = settings.get("REASONING_MODEL", CONVERSATION_MODEL)
        REASONING_MAX_TOKENS = settings.get("REASONING_MAX_TOKENS", 200)
        REASONING_TEMPERATURE = settings.get("REASONING_TEMPERATURE", 0.7)
        REASONING_APPLY_TO_MODELS = settings.get("REASONING_APPLY_TO_MODELS", [
            "CODE_GEN_MODEL",
            "ERROR_FIX_MODEL",
            "CONVERSATION_MODEL",
            "COMMAND_CONVERSION_MODEL",
            "FILENAME_GEN_MODEL",
            "INTENT_DETECTION_MODEL"
        ])

        TELEGRAM_ENABLED = settings.get("TELEGRAM_ENABLED", False)
        TELEGRAM_BOT_TOKEN = settings.get("TELEGRAM_BOT_TOKEN", "")
        TELEGRAM_CHAT_ID = settings.get("TELEGRAM_CHAT_ID", "")

        DEFAULT_MAX_TOKENS = settings.get("DEFAULT_MAX_TOKENS", 1000)
        DEFAULT_TEMPERATURE = settings.get("DEFAULT_TEMPERATURE", 0.7)

        WEB_SEARCH_ENABLED = settings.get("WEB_SEARCH_ENABLED", False)
        GOOGLE_API_KEY = settings.get("GOOGLE_API_KEY", "")
        GOOGLE_CSE_ID = settings.get("GOOGLE_CSE_ID", "")
        SERPER_API_KEY = settings.get("SERPER_API_KEY", "")

    except Exception as e:
        logger.error(f"Failed to load settings from {SETTINGS_FILE}: {e}")
        # Fallback to defaults if loading fails
        OPENROUTER_API_KEY = ""
        LLM_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
        CODE_GEN_MODEL = "moonshotai/kimi-dev-72b:free"
        ERROR_FIX_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"
        CONVERSATION_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
        COMMAND_CONVERSION_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1:free"
        FILENAME_GEN_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
        INTENT_DETECTION_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
        WEB_EXTRACTION_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
        REASONING_ENABLED = False
        REASONING_MODEL = CONVERSATION_MODEL
        REASONING_MAX_TOKENS = 200
        REASONING_TEMPERATURE = 0.7
        REASONING_APPLY_TO_MODELS = []
        TELEGRAM_ENABLED = False
        TELEGRAM_BOT_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        DEFAULT_MAX_TOKENS = 1000
        DEFAULT_TEMPERATURE = 0.7
        WEB_SEARCH_ENABLED = False
        GOOGLE_API_KEY = ""
        GOOGLE_CSE_ID = ""
        SERPER_API_KEY = ""

def _save_settings():
    """Saves current global settings to settings.json."""
    settings = {
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "LLM_BASE_URL": LLM_BASE_URL,
        "CODE_GEN_MODEL": CODE_GEN_MODEL,
        "ERROR_FIX_MODEL": ERROR_FIX_MODEL,
        "CONVERSATION_MODEL": CONVERSATION_MODEL,
        "COMMAND_CONVERSION_MODEL": COMMAND_CONVERSION_MODEL,
        "FILENAME_GEN_MODEL": FILENAME_GEN_MODEL,
        "INTENT_DETECTION_MODEL": INTENT_DETECTION_MODEL,
        "WEB_EXTRACTION_MODEL": WEB_EXTRACTION_MODEL,
        "REASONING_ENABLED": REASONING_ENABLED,
        "REASONING_MODEL": REASONING_MODEL,
        "REASONING_MAX_TOKENS": REASONING_MAX_TOKENS,
        "REASONING_TEMPERATURE": REASONING_TEMPERATURE,
        "REASONING_APPLY_TO_MODELS": REASONING_APPLY_TO_MODELS,
        "TELEGRAM_ENABLED": TELEGRAM_ENABLED,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "DEFAULT_MAX_TOKENS": DEFAULT_MAX_TOKENS,
        "DEFAULT_TEMPERATURE": DEFAULT_TEMPERATURE,
        "WEB_SEARCH_ENABLED": WEB_SEARCH_ENABLED,
        "GOOGLE_API_KEY": GOOGLE_API_KEY,
        "GOOGLE_CSE_ID": GOOGLE_CSE_ID,
        "SERPER_API_KEY": SERPER_API_KEY,
    }
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save settings to {SETTINGS_FILE}: {e}")

# Load settings on module import
_load_settings()

# System information (initialized once)
def _get_system_info():
    try:
        system = platform.system()
        if system == "Linux":
            if os.environ.get("TERMUX_VERSION"):
                os_name = "Termux"
            else:
                try:
                    with open("/etc/os-release") as f:
                        lines = f.readlines()
                        info = dict(line.strip().split('=', 1) for line in lines if '=' in line)
                        os_name = info.get('PRETTY_NAME', 'Linux').strip('"')
                except FileNotFoundError:
                    os_name = f"Linux ({platform.release()})"
        else:
            os_name = f"{system} ({platform.release()})"

        shell = os.environ.get("SHELL", "Unknown")
        
        info = {"os": os_name, "shell": shell}
        logger.info(f"System Info Detected: {info}")
        return info

    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return {"os": "Unknown", "shell": "Unknown"}

SYSTEM_INFO = _get_system_info()
