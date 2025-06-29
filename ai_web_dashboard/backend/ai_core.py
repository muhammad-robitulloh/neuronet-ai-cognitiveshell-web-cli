import pexpect
import requests
import re
import os
import time
import subprocess
import logging
import shlex
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === Global Configuration ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "") # Keep for compatibility, though not used by web
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "") # Keep for compatibility, though not used by web

# Configure LLM models for various tasks
CODE_GEN_MODEL = os.getenv("CODE_GEN_MODEL", "moonshotai/kimi-dev-72b:free")
ERROR_FIX_MODEL = os.getenv("ERROR_FIX_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")
CONVERSATION_MODEL = os.getenv("CONVERSATION_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
COMMAND_CONVERSION_MODEL = os.getenv("COMMAND_CONVERSION_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")
FILENAME_GEN_MODEL = os.getenv("FILENAME_GEN_MODEL", "mistralai/mistral-small-3.2-24b-instruct")
INTENT_DETECTION_MODEL = os.getenv("INTENT_DETECTION_MODEL", "mistralai/mistral-small-3.2-24b-instruct")

# ANSI colors for Termux console output (for internal logs only)
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_PURPLE = "\033[95m"
COLOR_RESET = "\033[0m"

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Global Variables for System Information ---
SYSTEM_INFO = {
    "os": "Unknown",
    "shell": "Unknown",
    "neofetch_output": "Not available"
}

# --- Global Functions for Context Storage ---
user_contexts: dict = {}
chat_histories: dict = {}

def get_user_context(chat_id: int) -> dict:
    """Retrieves user context. Initializes if not already present."""
    if chat_id not in user_contexts:
        user_contexts[chat_id] = {
            "last_error_log": None,
            "last_command_run": None,
            "last_generated_code": None,
            "awaiting_debug_response": False,
            "full_error_output": [],
            "last_user_message_intent": None,
            "last_ai_response_type": None,
            "last_generated_code_language": None
        }
    return user_contexts[chat_id]

def get_chat_history(chat_id: int) -> list:
    """Retrieves user chat history. Initializes if not already present."""
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    return chat_histories[chat_id]

# === General Function: Call LLM ===
def call_llm(messages: list, model: str, api_key: str, max_tokens: int = 512, temperature: float = 0.7, extra_headers: dict = None) -> tuple[bool, str]:
    """
    Generic function to send requests to an LLM model (OpenRouter).
    Returns a tuple: (True, result) on success, (False, error_message) on failure.
    """
    if not api_key or not LLM_BASE_URL:
        logger.error("[LLM ERROR] API Key or LLM Base URL not set.")
        return False, "API Key or LLM Base URL not set. Please check configuration."

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if extra_headers:
        headers.update(extra_headers)

    try:
        res = requests.post(LLM_BASE_URL, json=payload, headers=headers, timeout=300)
        res.raise_for_status()
        data = res.json()
        if "choices" in data and data["choices"]:
            return True, data["choices"][0]["message"]["content"]
        else:
            logger.error(f"[LLM] LLM response does not contain 'choices'. Debug response: {data}")
            return False, f"LLM response not in expected format. Debug response: {data}"
    except requests.exceptions.Timeout:
        logger.error(f"[LLM] LLM API request timed out ({LLM_BASE_URL}).")
        return False, f"LLM API request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error(f"[LLM] Failed to connect to LLM API ({LLM_BASE_URL}): {e}")
        return False, f"Failed to connect to LLM API: {e}"
    except KeyError as e:
        logger.error(f"[LLM] LLM response not in expected format (no 'choices' or 'message'): {e}. Debug response: {data}")
        return False, f"LLM response not in expected format: {e}. Debug response: {data}"
    except Exception as e:
        logger.error(f"[LLM] An unexpected error occurred while calling LLM: {e}")
        return False, f"An unexpected error occurred while calling LLM: {e}"

# === Function: Extract Code from LLM Response ===
def ekstrak_kode_dari_llm(text_response: str, target_language: str = None) -> tuple[str, str]:
    """
    Extracts Markdown code blocks from LLM responses.
    Returns a tuple: (cleaned_code, detected_language)
    """
    code_block_pattern = r"```(?P<lang>\w+)?\n(?P<content>.*?)```"
    matches = re.findall(code_block_pattern, text_response, re.DOTALL)
    
    if matches:
        if target_language:
            for lang, content in matches:
                if lang and lang.lower() == target_language.lower():
                    logger.info(f"{COLOR_GREEN}[LLM] ✔ {target_language} code detected and extracted.{COLOR_RESET}")
                    return content.strip(), lang.lower()
        
        for lang, content in matches:
            if lang and lang.lower() in ["python", "bash", "javascript", "js", "sh", "py", "node"]:
                logger.info(f"{COLOR_GREEN}[LLM] ✔ {lang} code detected and extracted.{COLOR_RESET}")
                return content.strip(), lang.lower().replace("js", "javascript").replace("sh", "bash").replace("py", "python")
        
        if matches:
            logger.info(f"{COLOR_YELLOW}[LLM] ⚠ Markdown code block found without specific language indicator. Extracting and trying to guess language.{COLOR_RESET}")
            first_content = matches[0][1].strip()
            detected_lang = deteksi_bahasa_pemrograman_dari_konten(first_content)
            return first_content, detected_lang
    
    logger.warning(f"{COLOR_YELLOW}[LLM] ⚠ No Markdown code block detected. Performing aggressive text cleaning.{COLOR_RESET}")
    lines = text_response.strip().split('\n')
    cleaned_lines = []
    in_potential_code_block = False
    
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith(('#', 'import ', 'from ', 'function ', 'def ', 'const ', 'let ', 'var ', 'echo ', '#!/')):
            cleaned_lines.append(line)
            in_potential_code_block = True
        elif re.match(r'^(def|class|if|for|while|try|with|function|const|let|var)\s+', stripped_line):
            cleaned_lines.append(line)
            in_potential_code_block = True
        elif any(char in stripped_line for char in ['=', '(', ')', '{', '}', '[', ']']) and not stripped_line.startswith('- '):
            cleaned_lines.append(line)
            in_potential_code_block = True
        elif in_potential_code_block and not stripped_line:
            cleaned_lines.append(line)
        elif len(stripped_line) > 0 and not re.match(r'^[a-zA-Z\s,;.:-]*$', stripped_line):
             cleaned_lines.append(line)
             in_potential_code_block = True
        else:
            if in_potential_code_block and stripped_line:
                break 
            pass

    final_code = "\n".join(cleaned_lines).strip()
    final_code = re.sub(r'```(.*?)```', r'\1', final_code, flags=re.DOTALL)
    
    detected_lang = deteksi_bahasa_pemrograman_dari_konten(final_code)
    logger.info(f"{COLOR_YELLOW}[LLM] ⚠ Code extracted with aggressive cleaning. Detected language: {detected_lang}{COLOR_RESET}")
    return final_code.strip(), detected_lang


# === Function: Detect Programming Language from Code Content ===
def deteksi_bahasa_pemrograman_dari_konten(code_content: str) -> str:
    """
    Detects programming language from code content based on heuristics.
    """
    if not code_content:
        return "txt"

    code_content_lower = code_content.lower()

    if "import" in code_content_lower or "def " in code_content_lower or "class " in code_content_lower or ".py" in code_content_lower:
        return "python"
    if "bash" in code_content_lower or "#!/bin/bash" in code_content or "#!/bin/sh" in code_content or "echo " in code_content_lower or ".sh" in code_content_lower:
        return "bash"
    if "function" in code_content_lower or "console.log" in code_content_lower or "const " in code_content_lower or "let " in code_content_lower or "var " in code_content_lower or ".js" in code_content_lower:
        return "javascript"
    if "<html" in code_content_lower or "<body" in code_content_lower or "<div" in code_content_lower:
        return "html"
    if "body {" in code_content_lower or "background-color" in code_content_lower or "color:" in code_content_lower:
        return "css"
    if "<?php" in code_content_lower or (re.search(r'\becho\b', code_content_lower) and not re.search(r'\bbash\b', code_content_lower)):
        return "php"
    if "public class" in code_content_lower or "public static void main" in code_content_lower or ".java" in code_content_lower:
        return "java"
    if "#include <" in code_content_lower or "int main()" in code_content_lower or ".c" in code_content_lower or ".cpp" in code_content_lower:
        return "c"
    return "txt"


# === Function: Detect User Intent ===
def deteksi_niat_pengguna(pesan_pengguna: str) -> str:
    """
    Detects user intent (run shell command, create program, or general conversation).
    Returns string: "shell", "program", or "conversation".
    """
    messages = [
        {"role": "system", "content": """You are an intent detector. Identify whether the user's message intends to:
- "shell": If the user wants to run a system command or perform file operations (e.g., "delete file", "list directory", "run", "open", "install", "compress").
- "program": If the user wants to create or fix code (e.g., "create a python function", "write javascript code", "fix this error", "write a program").
- "conversation": For all other types of questions or interactions that are not direct commands or code generation.

Return only one word from the categories above. Do not provide additional explanations.
"""},
        {"role": "user", "content": f"Detect intent for: '{pesan_pengguna}'"}
    ]
    logger.info(f"{COLOR_BLUE}[AI] Detecting user intent for '{pesan_pengguna}' ({INTENT_DETECTION_MODEL})...{COLOR_RESET}\n")
    
    success, niat = call_llm(messages, INTENT_DETECTION_MODEL, OPENROUTER_API_KEY, max_tokens=10, temperature=0.0)
    
    if success:
        niat_cleaned = niat.strip().lower()
        if not niat_cleaned:
            logger.warning(f"[AI] Empty intent from LLM. Defaulting to 'conversation'.")
            return "conversation"
        elif niat_cleaned in ["shell", "program", "conversation"]:
            return niat_cleaned
        else:
            logger.warning(f"[AI] Unknown intent from LLM: '{niat_cleaned}'. Defaulting to 'conversation'.")
            return "conversation"
    else:
        logger.error(f"[AI] Failed to detect intent: {niat}. Defaulting to 'conversation'.")
        return "conversation"

# === Function: Detect Programming Language requested in Prompt ===
def deteksi_bahasa_dari_prompt(prompt: str) -> str | None:
    """
    Detects the programming language requested in the user's prompt.
    Returns language string (e.g., "python", "bash", "javascript") or None if not specific.
    """
    prompt_lower = prompt.lower()
    if "python" in prompt_lower or "python script" in prompt_lower or "python function" in prompt_lower:
        return "python"
    elif "bash" in prompt_lower or "shell" in prompt_lower or "shell script" in prompt_lower or "sh program" in prompt_lower:
        return "bash"
    elif "javascript" in prompt_lower or "js" in prompt_lower or "nodejs" in prompt_lower:
        return "javascript"
    elif "html" in prompt_lower or "web page" in prompt_lower:
        return "html"
    elif "css" in prompt_lower or "stylesheet" in prompt_lower:
        return "css"
    elif "php" in prompt_lower:
        return "php"
    elif "java" in prompt_lower:
        return "java"
    elif "c++" in prompt_lower or "cpp" in prompt_lower:
        return "cpp"
    elif "c#" in prompt_lower or "csharp" in prompt_lower:
        return "csharp"
    elif "ruby" in prompt_lower or "rb" in prompt_lower:
        return "ruby"
    elif "go lang" in prompt_lower or "golang" in prompt_lower or "go " in prompt_lower:
        return "go"
    elif "swift" in prompt_lower:
        return "swift"
    elif "kotlin" in prompt_lower:
        return "kotlin"
    elif "rust" in prompt_lower:
        return "rust"
    return None


# === Function: Request Code from LLM ===
def minta_kode(prompt: str, error_context: str = None, chat_id: int = None, target_language: str = None) -> tuple[bool, str, str | None]:
    """
    Requests LLM to generate code based on prompt in a specific language.
    If error_context is provided, this is a debugging request.
    Includes recent conversation context if available.
    """
    messages = []
    
    history = get_chat_history(chat_id) if chat_id else []
    recent_history = history[-10:]
    for msg in recent_history:
        messages.append(msg)

    # Add system information to the system message
    system_info_message = (
        f"You are an AI coding assistant proficient in various programming languages. "
        f"The system runs on OS: {SYSTEM_INFO['os']}, Shell: {SYSTEM_INFO['shell']}. "
        f"Neofetch output: \n```\n{SYSTEM_INFO['neofetch_output']}\n```\n"
        f"Code results *must* be Markdown code blocks with appropriate language tags "
        f"(e.g., ```python, ```bash, ```javascript, ```html, ```css, ```php, ```java, etc.). "
        f"DO NOT add explanations, intros, conclusions, or extra text outside the Markdown code block. "
        f"Include all necessary imports/dependencies within the code block. "
        f"If any part requires user input, provide clear comments within the code."
    )

    if error_context:
        messages.append({
                "role": "system", 
                "content": system_info_message + " You are fixing code. Based on the error log and provided conversation history, provide *only* the complete fixed code or new code. Ensure the code is directly runnable."
            })
        messages.append({
                "role": "user",
                "content": f"There was an error running the code/command:\n\n{error_context}\n\nFix it or provide complete new code. Focus on {target_language if target_language else 'relevant'} language."
            })
        logger.info(f"{COLOR_BLUE}[AI] Requesting fix/new code ({target_language if target_language else 'universal'}) from AI model ({CODE_GEN_MODEL}) based on error...{COLOR_RESET}\n")
    else:
        messages.append({
                "role": "system", 
                "content": system_info_message
            })
        prompt_with_lang = f"Instruction: {prompt}"
        if target_language:
            prompt_with_lang += f" (in {target_language} language)"
        messages.append({
                "role": "user",
                "content": prompt_with_lang
            })
        logger.info(f"{COLOR_BLUE}[AI] Requesting code ({target_language if target_language else 'universal'}) from AI model ({CODE_GEN_MODEL})...{COLOR_RESET}\n")
    
    success, response_content = call_llm(messages, CODE_GEN_MODEL, OPENROUTER_API_KEY, max_tokens=2048, temperature=0.7)

    if success:
        cleaned_code, detected_language = ekstrak_kode_dari_llm(response_content, target_language)
        return True, cleaned_code, detected_language
    else:
        return False, response_content, None

# === Function: Generate Filename ===
def generate_filename(prompt: str, detected_language: str = "txt") -> str:
    """
    Generates a relevant filename based on user prompt and detected language.
    """
    extension_map = {
        "python": ".py", "bash": ".sh", "javascript": ".js", "html": ".html",
        "css": ".css", "php": ".php", "java": ".java", "c": ".c",
        "cpp": ".cpp", "csharp": ".cs", "ruby": ".rb", "go": ".go",
        "swift": ".swift", "kotlin": ".kt", "rust": ".rs", "txt": ".txt"
    }
    
    messages = [
        {"role": "system", "content": f"You are a filename generator. Provide a single short, relevant, and descriptive filename (no spaces, use underscores, all lowercase, no extension) based on the following code description and language '{detected_language}'. Example: 'factorial_function' or 'cli_calculator'. No explanation, just the filename."},
        {"role": "user", "content": f"Code description: {prompt}"}
    ]
    logger.info(f"{COLOR_BLUE}[AI] Generating filename for '{prompt}' ({FILENAME_GEN_MODEL}) with language {detected_language}...{COLOR_RESET}\n")
    
    success, filename = call_llm(messages, FILENAME_GEN_MODEL, OPENROUTER_API_KEY, max_tokens=20, temperature=0.5)
    
    if not success:
        logger.warning(f"[AI] Failed to generate filename from LLM: {filename}. Using default name.")
        return f"generated_code{extension_map.get(detected_language, '.txt')}"

    filename = filename.strip()
    filename = re.sub(r'[^\w-]', '', filename).lower().replace(' ', '_')
    
    for ext in extension_map.values():
        if filename.endswith(ext):
            filename = filename[:-len(ext)]
            break
            
    if not filename:
        filename = "generated_code"
        
    return filename + extension_map.get(detected_language, '.txt')


# === Function: Convert Natural Language to Shell Command ===
def konversi_ke_perintah_shell(bahasa_natural: str, chat_id: int = None) -> tuple[bool, str]:
    """
    Converts user's natural language into an executable shell command.
    Includes recent conversation context if available.
    """
    messages = []

    history = get_chat_history(chat_id) if chat_id else []
    recent_history = history[-10:] 
    for msg in recent_history:
        messages.append(msg)

    # Add system information to the system message
    system_message_content = (
        f"You are a natural language to shell command translator. "
        f"The system runs on OS: {SYSTEM_INFO['os']}, Shell: {SYSTEM_INFO['shell']}. "
        f"Convert the following natural language instruction into the most relevant single-line Linux Termux shell command. "
        f"Do not provide explanations, just the command. "
        f"If the instruction is unclear or cannot be converted into a shell command, respond with 'CANNOT_CONVERT'."
    )
    messages.append({"role": "system", "content": system_message_content})
    messages.append({"role": "user", "content": f"Convert this to a shell command: {bahasa_natural}"})

    logger.info(f"{COLOR_BLUE}[AI] Converting natural language to shell command ({COMMAND_CONVERSION_MODEL})...{COLOR_RESET}\n")
    return call_llm(messages, COMMAND_CONVERSION_MODEL, OPENROUTER_API_KEY, max_tokens=128, temperature=0.3)


# === Function: Send Error to LLM for Suggestion ===
def kirim_error_ke_llm_for_suggestion(log_error: str, chat_id: int = None) -> tuple[bool, str]:
    """
    Sends error log to LLM to get suggested fixes.
    Includes recent conversation context if available.
    """
    messages = []

    history = get_chat_history(chat_id) if chat_id else []
    recent_history = history[-10:] 
    for msg in recent_history:
        messages.append(msg)

    # Add system information to the system message
    system_message_content = (
        f"You are an AI debugger. "
        f"The system runs on OS: {SYSTEM_INFO['os']}, Shell: {SYSTEM_INFO['shell']}. "
        f"Consider this system information when analyzing errors and providing suggestions. "
        f"Provide suggestions in a runnable shell format if possible, or in a Markdown code block. "
        f"Otherwise, provide a brief explanation."
    )

    messages.append({"role": "system", "content": system_message_content})
    messages.append({"role": "user", "content": f"The following error occurred:\n\n{log_error}\n\nWhat is the best suggestion to fix it in a Linux Termux system context? "})
    
    headers = {"HTTP-Referer": "[https://t.me/dseAI_bot](https://t.me/dseAI_bot)"}
    
    logger.info(f"{COLOR_BLUE}[AI] Sending error to AI model ({ERROR_FIX_MODEL}) for suggestions...{COLOR_RESET}\n")
    return call_llm(messages, ERROR_FIX_MODEL, OPENROUTER_API_KEY, max_tokens=512, temperature=0.7, extra_headers=headers)

# === Function: Request General Conversation Answer from LLM ===
def minta_jawaban_konversasi(chat_id: int, prompt: str) -> tuple[bool, str]:
    """
    Requests a general conversational answer from LLM, while maintaining history
    and including references from previous interactions (code, commands).
    """
    history = get_chat_history(chat_id)
    user_context = get_user_context(chat_id)
    
    system_context_messages = []

    # Add system information to the beginning of the system message
    system_context_messages.append(
        {"role": "system", "content": f"System runs on OS: {SYSTEM_INFO['os']}, Shell: {SYSTEM_INFO['shell']}. Neofetch information:\n```\n{SYSTEM_INFO['neofetch_output']}\n```"}
    )

    if user_context["last_command_run"] and user_context["last_ai_response_type"] == "shell":
        system_context_messages.append(
            {"role": "system", "content": f"User just ran a shell command: `{user_context['last_command_run']}`. Consider this context in your answer."}
        )
    if user_context["last_generated_code"] and user_context["last_ai_response_type"] == "program":
        lang_display = user_context["last_generated_code_language"] if user_context["last_generated_code_language"] else "code"
        system_context_messages.append(
            {"role": "system", "content": f"User just received {lang_display} code:\n```{lang_display}\n{user_context['last_generated_code']}\n```. Consider this context in your answer."}
        )
    if user_context["last_error_log"] and user_context["last_user_message_intent"] == "shell":
        system_context_messages.append(
            {"role": "system", "content": f"User encountered an error after running a command: `{user_context['last_command_run']}` with error log:\n```\n{user_context['full_error_output'][-500:]}\n```. Consider this in your answer."}
        )
    elif user_context["last_error_log"] and user_context["last_user_message_intent"] == "program":
         system_context_messages.append(
            {"role": "system", "content": f"User encountered an error after interacting with a program:\n```\n{user_context['full_error_output'][-500:]}\n```. Consider this in your answer."}
        )

    messages_to_send = []
    messages_to_send.extend(system_context_messages)

    max_history_length = 10
    recent_history = history[-max_history_length:]
    messages_to_send.extend(recent_history)
    
    messages_to_send.append({"role": "user", "content": prompt})

    logger.info(f"{COLOR_BLUE}[AI] Requesting conversational answer from AI model ({CONVERSATION_MODEL})...{COLOR_RESET}\n")
    success, response = call_llm(messages_to_send, CONVERSATION_MODEL, OPENROUTER_API_KEY, max_tokens=256, temperature=0.7)

    if success:
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": response})
        chat_histories[chat_id] = history
    return success, response


# === Function: Save to file ===
def simpan_ke_file(nama_file: str, isi: str) -> bool:
    """
    Saves string content to a file.
    Returns True on success, False on failure.
    """
    try:
        with open(nama_file, "w") as f:
            f.write(isi)
        logger.info(f"{COLOR_GREEN}[FILE] ✅ Code successfully saved to file: {nama_file}{COLOR_RESET}")
        return True
    except IOError as e:
        logger.error(f"[FILE] 🔴 Failed to save file {nama_file}: {e}")
        return False

# === Function: Detect shell commands in AI suggestions ===
def deteksi_perintah_shell(saran_ai: str) -> str | None:
    """
    Detects shell command lines from AI suggestions, including those in
    Markdown code blocks or inline quotes.
    Priority: Markdown code blocks > Inline quotes > Regular Regex patterns
    """
    code_block_pattern = r"```(?:bash|sh|zsh|\w+)?\n(.*?)```"
    inline_code_pattern = r"`([^`]+)`"

    code_blocks = re.findall(code_block_pattern, saran_ai, re.DOTALL)
    for block in code_blocks:
        lines_in_block = [line.strip() for line in block.split('\n') if line.strip()]
        if lines_in_block:
            first_line = lines_in_block[0]
            if any(first_line.startswith(kw) for kw in ["sudo", "apt", "pkg", "pip", "python", "bash", "sh", "./", "chmod", "chown", "mv", "cp", "rmdir", "mkdir", "cd", "ls", "git", "curl", "wget", "tar", "unzip", "zip", "export"]):
                return first_line

    inline_codes = re.findall(inline_code_pattern, saran_ai)
    for code in inline_codes:
        code = code.strip()
        if code and any(code.startswith(kw) for kw in ["sudo", "apt", "pkg", "pip", "python", "bash", "sh", "./", "chmod", "chown", "mv", "cp", "rmdir", "mkdir", "cd", "ls", "git", "curl", "wget", "tar", "unzip", "zip", "export"]):
            return code

    shell_command_patterns = [
        r"^(sudo|apt|pkg|dpkg|pip|python|bash|sh|./|chmod|chown|mv|cp|rmdir|mkdir|cd|ls|grep|find|nano|vi|vim|git|curl|wget|tar|unzip|zip|export|alias)\s+",
        r"^(\S+\.sh)\s+",
        r"^\S+\s+(--\S+|\S+)+",
    ]
    lines = saran_ai.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for pattern in shell_command_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return line
                
    return None

# === Security Function: Filter Dangerous Commands ===
def is_command_dangerous(command: str) -> bool:
    """
    Checks if a shell command contains forbidden keywords.
    """
    command_lower = command.lower()
    
    dangerous_patterns = [
        r'\brm\b\s+-rf',
        r'\brm\b\s+/\s*',
        r'\bpkg\s+uninstall\b',
        r'\bmv\b\s+/\s*',
        r'\bchown\b\s+root',
        r'\bchmod\b\s+\d{3}\s+/\s*',
        r'\bsu\b',
        r'\bsudo\b\s+poweroff',
        r'\breboot\b',
        r'\bformat\b',
        r'\bmkfs\b',
        r'\bdd\b',
        r'\bfdisk\b',
        r'\bparted\b',
        r'\bwipefs\b',
        r'\bcrontab\b\s+-r',
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command_lower):
            logger.warning(f"[SECURITY] ❗ Dangerous command detected: {command}")
            return True
    return False

# === Function to check system info with neofetch ===
def check_system_info():
    """
    Checks for neofetch availability and retrieves system information.
    If neofetch is not available, it attempts to install it based on the OS.
    """
    global SYSTEM_INFO

    def install_neofetch(install_command):
        """Attempts to install neofetch using the given command."""
        logger.info(f"{COLOR_YELLOW}[INFO SISTEM] Neofetch tidak ditemukan. Mencoba menginstal dengan: '{' '.join(install_command)}'...{COLOR_RESET}")
        try:
            # Try to install silently
            subprocess.run(install_command, check=True, capture_output=True)
            logger.info(f"{COLOR_GREEN}[INFO SISTEM] Neofetch berhasil diinstal.{COLOR_RESET}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"{COLOR_RED}🔴 ERROR: Gagal menginstal neofetch. Output error:\n{e.stderr.strip()}{COLOR_RESET}")
            return False
        except FileNotFoundError:
            logger.error(f"{COLOR_RED}🔴 ERROR: Perintah instalasi '{install_command[0]}' tidak ditemukan.{COLOR_RESET}")
            return False

    # First, try to detect the OS
    detected_os = "Unknown"
    try:
        if os.path.exists("/data/data/com.termux/files/usr/bin/pkg"):
            detected_os = "Termux"
        elif os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                os_release_content = f.read()
                if "ID=debian" in os_release_content or "ID=ubuntu" in os_release_content:
                    detected_os = "Debian/Ubuntu"
                elif "ID_LIKE=arch" in os_release_content:
                    detected_os = "Arch Linux"
                elif "ID=fedora" in os_release_content:
                    detected_os = "Fedora"
                # Add more OS detection as needed
    except Exception as e:
        logger.warning(f"[INFO SISTEM] Gagal mendeteksi OS secara detail: {e}. Menggunakan deteksi default.")
    
    SYSTEM_INFO["os"] = detected_os
    logger.info(f"[INFO SISTEM] OS yang terdeteksi: {SYSTEM_INFO['os']}")

    # Check if neofetch is installed
    try:
        subprocess.run(["which", "neofetch"], check=True, capture_output=True)
        neofetch_installed = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        neofetch_installed = False

    if not neofetch_installed:
        if detected_os == "Termux":
            success_install = install_neofetch(["pkg", "install", "-y", "neofetch"])
        elif detected_os == "Debian/Ubuntu":
            success_install = install_neofetch(["sudo", "apt", "install", "-y", "neofetch"])
            if not success_install: # Fallback if sudo isn't configured for current user
                 success_install = install_neofetch(["apt", "install", "-y", "neofetch"])
        elif detected_os == "Arch Linux":
            success_install = install_neofetch(["sudo", "pacman", "-S", "--noconfirm", "neofetch"])
        elif detected_os == "Fedora":
            success_install = install_neofetch(["sudo", "dnf", "install", "-y", "neofetch"])
        else:
            logger.warning(f"{COLOR_YELLOW}[INFO SISTEM] Neofetch tidak ditemukan dan OS tidak dikenal untuk instalasi otomatis. Coba instal neofetch secara manual.{COLOR_RESET}")
            success_install = False
        
        if not success_install:
            logger.error(f"{COLOR_RED}🔴 ERROR: Neofetch tidak terinstal dan gagal menginstalnya secara otomatis. Tidak dapat melanjutkan tanpa neofetch.{COLOR_RESET}")
            exit(1) # Exit if installation fails

    try:
        # Run neofetch and capture its output
        result = subprocess.run(["neofetch", "--off", "--config", "none", "--stdout"], capture_output=True, text=True, check=True)
        neofetch_output = result.stdout.strip()
        SYSTEM_INFO["neofetch_output"] = neofetch_output
        logger.info(f"{COLOR_GREEN}[INFO SISTEM] Neofetch successfully executed.{COLOR_RESET}")

        # Parse neofetch output to get OS and Shell
        os_match = re.search(r"OS:\s*(.*?)\n", neofetch_output)
        shell_match = re.search(r"Shell:\s*(.*?)\n", neofetch_output)

        if os_match:
            SYSTEM_INFO["os"] = os_match.group(1).strip()
        if shell_match:
            SYSTEM_INFO["shell"] = shell_match.group(1).strip()
        
        logger.info(f"[INFO SISTEM] Detected OS: {SYSTEM_INFO['os']}")
        logger.info(f"[INFO SISTEM] Detected Shell: {SYSTEM_INFO['shell']}")

    except subprocess.CalledProcessError as e:
        logger.error(f"{COLOR_RED}🔴 ERROR: Failed to run neofetch even after installation attempt. Error output:\n{e.stderr.strip()}{COLOR_RESET}")
        logger.error(f"{COLOR_RED}Please check neofetch installation and your PATH manually.{COLOR_RESET}")
        logger.error(f"{COLOR_RED}Program will stop. Please fix neofetch installation to continue.{COLOR_RESET}")
        exit(1)
    except FileNotFoundError:
        # This case should ideally not happen if install_neofetch worked
        logger.error(f"{COLOR_RED}🔴 ERROR: 'neofetch' command not found after installation attempt.{COLOR_RESET}")
        logger.error(f"{COLOR_RED}Program will stop. Please fix neofetch installation to continue.{COLOR_RESET}")
        exit(1)
    except Exception as e:
        logger.error(f"{COLOR_RED}🔴 ERROR: An unexpected error occurred while checking system information: {e}{COLOR_RESET}")
        logger.error(f"{COLOR_RED}Program will stop.{COLOR_RESET}")
        exit(1)

# Call check_system_info once when this module is imported
check_system_info()

# === Shell Execution Function (for web backend) ===
async def execute_shell_command(command_to_run: str, chat_id: int = 0):
    """
    Executes a shell command and yields output line by line.
    chat_id is used for context management, default to 0 for web.
    """
    user_context = get_user_context(chat_id)
    user_context["last_command_run"] = command_to_run
    user_context["full_error_output"] = []
    user_context["last_error_log"] = None

    logger.info(f"\n{COLOR_BLUE}[Shell] 🟢 Running command: `{command_to_run}`{COLOR_RESET}\n")

    safe_command_to_run = shlex.quote(command_to_run)

    try:
        child = pexpect.spawn(f"bash -c {safe_command_to_run}", encoding='utf-8', timeout=None)
    except pexpect.exceptions.ExceptionPexpect as e:
        error_msg = f"Failed to run command: `{str(e)}`. Ensure the command is valid, bash is available, and pexpect is installed correctly."
        logger.error(f"[Shell] 🔴 Failed to run command: {e}")
        yield f"ERROR: {error_msg}\n"
        return

    error_detected_in_stream = False

    while True:
        try:
            line = await asyncio.to_thread(child.readline)

            if not line:
                if child.eof():
                    logger.info(f"{COLOR_GREEN}[Shell] ✅ Shell process finished.{COLOR_RESET}")
                    if user_context["last_error_log"]:
                        yield f"ERROR_DETECTED: {user_context['last_error_log']}\n"
                    break
                continue

            cleaned_line = line.strip()
            logger.info(f"{COLOR_YELLOW}[Shell Log] {cleaned_line}{COLOR_RESET}")
            yield f"LOG: {cleaned_line}\n"
            
            user_context["full_error_output"].append(cleaned_line)

            is_program_execution_command = bool(re.match(r"^(python|sh|bash|node|\./)\s+\S+\.(py|sh|js|rb|pl|php)", command_to_run, re.IGNORECASE))
            
            if is_program_execution_command and any(keyword in cleaned_line.lower() for keyword in ["error", "exception", "not found", "failed", "permission denied", "command not found", "no such file or directory", "segmentation fault", "fatal"]):
                if not error_detected_in_stream:
                    error_detected_in_stream = True
                    user_context["last_error_log"] = "\n".join(user_context["full_error_output"])
                    logger.info(f"{COLOR_RED}[AI] Error detected. Sending context to model...{COLOR_RESET}\n")
                    
                    success_saran, saran = kirim_error_ke_llm_for_suggestion(user_context["last_error_log"], chat_id)
                    if success_saran:
                        yield f"AI_SUGGESTION: {saran}\n"
                    else:
                        yield f"AI_SUGGESTION_ERROR: {saran}\n"

        except pexpect.exceptions.EOF:
            logger.info(f"{COLOR_GREEN}[Shell] ✅ Shell process finished.{COLOR_RESET}")
            if user_context["last_error_log"]:
                yield f"ERROR_DETECTED: {user_context['last_error_log']}\n"
            break
        except Exception as e:
            error_msg = f"An unexpected error occurred in `execute_shell_command`: `{str(e)}`"
            logger.error(f"[Shell] 🔴 Unexpected error: {e}")
            yield f"ERROR: {error_msg}\n"
            if child.isalive():
                child.close()
            break


# === File Management Functions ===
def list_generated_files() -> list[str]:
    """
    Lists files generated by the AI.
    """
    allowed_extensions = [
        '.py', '.sh', '.js', '.html', '.css', '.php', '.java', '.c', '.cpp',
        '.cs', '.rb', '.go', '.swift', '.kt', '.rs', '.txt'
    ]
    # Exclude the current script itself
    current_script_name = os.path.basename(__file__)
    files = [
        f for f in os.listdir('.') 
        if os.path.isfile(f) and any(f.endswith(ext) for ext in allowed_extensions) 
        and f != current_script_name
    ]
    return files

def read_file_content(filename: str) -> tuple[bool, str]:
    """
    Reads the content of a specified file.
    """
    allowed_extensions = [
        '.py', '.sh', '.js', '.html', '.css', '.php', '.java', '.c', '.cpp',
        '.cs', '.rb', '.go', '.swift', '.kt', '.rs', '.txt'
    ]
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        return False, "File type not allowed."

    try:
        with open(filename, 'r') as f:
            content = f.read()
        return True, content
    except FileNotFoundError:
        return False, "File not found."
    except Exception as e:
        return False, f"Error reading file: {e}"

def delete_file(filename: str) -> tuple[bool, str]:
    """
    Deletes a specified file.
    """
    allowed_extensions = [
        '.py', '.sh', '.js', '.html', '.css', '.php', '.java', '.c', '.cpp',
        '.cs', '.rb', '.go', '.swift', '.kt', '.rs', '.txt'
    ]
    current_script_name = os.path.basename(__file__)

    if not any(filename.endswith(ext) for ext in allowed_extensions) or filename == current_script_name:
        return False, "Deletion of this file type or the bot's own file is not allowed."

    try:
        if os.path.exists(filename) and os.path.isfile(filename):
            os.remove(filename)
            logger.info(f"[File] File {filename} deleted.")
            return True, "File deleted successfully."
        else:
            return False, "File not found."
    except Exception as e:
        logger.error(f"[File] 🔴 Failed to delete file {filename}: {e}")
        return False, f"Failed to delete file: {e}"

# Expose configuration for settings management
def get_llm_config():
    return {
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "LLM_BASE_URL": LLM_BASE_URL,
        "CODE_GEN_MODEL": CODE_GEN_MODEL,
        "ERROR_FIX_MODEL": ERROR_FIX_MODEL,
        "CONVERSATION_MODEL": CONVERSATION_MODEL,
        "COMMAND_CONVERSION_MODEL": COMMAND_CONVERSION_MODEL,
        "FILENAME_GEN_MODEL": FILENAME_GEN_MODEL,
        "INTENT_DETECTION_MODEL": INTENT_DETECTION_MODEL,
    }

def update_llm_config(new_config: dict):
    global OPENROUTER_API_KEY, LLM_BASE_URL, CODE_GEN_MODEL, ERROR_FIX_MODEL, CONVERSATION_MODEL, COMMAND_CONVERSION_MODEL, FILENAME_GEN_MODEL, INTENT_DETECTION_MODEL
    
    # Update in-memory variables
    OPENROUTER_API_KEY = new_config.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    LLM_BASE_URL = new_config.get("LLM_BASE_URL", LLM_BASE_URL)
    CODE_GEN_MODEL = new_config.get("CODE_GEN_MODEL", CODE_GEN_MODEL)
    ERROR_FIX_MODEL = new_config.get("ERROR_FIX_MODEL", ERROR_FIX_MODEL)
    CONVERSATION_MODEL = new_config.get("CONVERSATION_MODEL", CONVERSATION_MODEL)
    COMMAND_CONVERSION_MODEL = new_config.get("COMMAND_CONVERSION_MODEL", COMMAND_CONVERSION_MODEL)
    FILENAME_GEN_MODEL = new_config.get("FILENAME_GEN_MODEL", FILENAME_GEN_MODEL)
    INTENT_DETECTION_MODEL = new_config.get("INTENT_DETECTION_MODEL", INTENT_DETECTION_MODEL)

    # Update .env file (simplified for demonstration, consider a more robust solution for production)
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    for key, value in new_config.items():
        env_vars[key] = value

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables to ensure consistency
    return True, "Configuration updated successfully."


# Expose SYSTEM_INFO
def get_system_info():
    return SYSTEM_INFO

# Function to clear chat history (for web dashboard)
def clear_all_chat_history():
    chat_histories.clear()
    user_contexts.clear()
    logger.info("[Chat] All chat histories and user contexts cleared.")
    return True, "All chat histories and user contexts cleared."


# Main handler for processing user messages (for web backend)
async def process_user_message(chat_id: int, user_message: str):
    user_context = get_user_context(chat_id)
    
    niat = deteksi_niat_pengguna(user_message)
    user_context["last_user_message_intent"] = niat
    logger.info(f"[Intent] User {chat_id} -> Intent: {niat}")

    if niat == "shell":
        logger.info(f"[Shell] Intent detected: Shell Command. Translating instruction: `{user_message}`")
        success_konversi, perintah_shell = konversi_ke_perintah_shell(user_message, chat_id)
        perintah_shell = perintah_shell.strip()

        if not success_konversi:
            return {"type": "error", "message": f"CONVERSION ERROR: An issue occurred while converting the command: {perintah_shell}"}
        elif perintah_shell == "CANNOT_CONVERT":
            return {"type": "info", "message": "UNCLEAR COMMAND: Sorry, I cannot convert that instruction into a clear shell command. Please provide more specific instructions."}

        if is_command_dangerous(perintah_shell):
            return {"type": "error", "message": f"PROHIBITED: This command is not allowed to be executed: `{perintah_shell}`. Please use another command."}
        
        user_context["last_ai_response_type"] = "shell"
        user_context["last_command_run"] = perintah_shell
        user_context["last_generated_code"] = None
        user_context["last_generated_code_language"] = None
        
        # For shell commands, we will stream the output via WebSocket, so we return a special type
        return {"type": "shell_command", "command": perintah_shell}

    elif niat == "program":
        logger.info(f"[Program] Intent detected: Program Creation. Starting code generation for: `{user_message}`")
        
        target_lang_from_prompt = deteksi_bahasa_dari_prompt(user_message)

        success_code, kode_tergenerasi, detected_language = minta_kode(user_message, chat_id=chat_id, target_language=target_lang_from_prompt)

        if not success_code:
            return {"type": "error", "message": f"CODE GENERATION ERROR: An issue occurred while generating code: {kode_tergenerasi}"}
        
        generated_file_name = generate_filename(user_message, detected_language)
        simpan_ok = simpan_ke_file(generated_file_name, kode_tergenerasi)

        if simpan_ok:
            user_context["last_generated_code"] = kode_tergenerasi
            user_context["last_generated_code_language"] = detected_language
            user_context["last_ai_response_type"] = "program"
            user_context["last_command_run"] = None

            run_command_suggestion = ""
            if detected_language == "python":
                run_command_suggestion = f"`python {generated_file_name}`"
            elif detected_language == "bash":
                run_command_suggestion = f"`bash {generated_file_name}` or `chmod +x {generated_file_name} && ./{generated_file_name}`"
            elif detected_language == "javascript":
                run_command_suggestion = f"`node {generated_file_name}` (ensure Node.js is installed)"
            elif detected_language == "html":
                run_command_suggestion = f"Open this file in your web browser."
            elif detected_language == "php":
                run_command_suggestion = f"`php {generated_file_name}` (ensure PHP is installed)"
            elif detected_language == "java":
                run_command_suggestion = f"Compile with `javac {generated_file_name}` then run with `java {generated_file_name.replace('.java', '')}`"
            elif detected_language in ["c", "cpp"]:
                run_command_suggestion = f"Compile with `gcc {generated_file_name} -o a.out` then run with `./a.out`"
            
            return {
                "type": "program_generated",
                "message": f"SUCCESS: {detected_language.capitalize()} code successfully generated and saved to `{generated_file_name}`.",
                "filename": generated_file_name,
                "code": kode_tergenerasi,
                "language": detected_language,
                "run_suggestion": run_command_suggestion
            }
        else:
            return {"type": "error", "message": "FILE ERROR: Failed to save generated code to file."}
            

    else: # niat == "conversation"
        logger.info(f"[Conversation] Intent detected: General Conversation. Requesting AI answer...")
        success_response, jawaban_llm = minta_jawaban_konversasi(chat_id, user_message)
        user_context["last_ai_response_type"] = "conversation"
        user_context["last_command_run"] = None
        user_context["last_generated_code"] = None
        user_context["last_generated_code_language"] = None
        
        if not success_response:
            return {"type": "error", "message": f"AI ERROR: An issue occurred while processing the conversation: {jawaban_llm}"}
        else:
            return {"type": "conversation", "message": jawaban_llm}

async def process_debug_request(chat_id: int, user_response: str):
    user_context = get_user_context(chat_id)
    
    if user_response.lower() in ["ya", "yes"]:
        logger.info(f"[Debug] Starting debugging for {chat_id}")
        
        error_log = user_context["last_error_log"]
        last_command = user_context["last_command_run"]
        last_generated_code_lang = user_context["last_generated_code_language"]

        if error_log:
            logger.info(f"[Debug] Requesting LLM to analyze error and provide fix/new code...")
            success_debug, debug_saran, debug_lang = minta_kode(prompt="", error_context=error_log, chat_id=chat_id, target_language=last_generated_code_lang)
            
            if not success_debug:
                return {"type": "error", "message": f"DEBUGGING ERROR: An issue occurred during debugging: {debug_saran}"}
            else:
                debug_file_name = None
                if last_command:
                    match = re.search(r"^(python|sh|bash|node|php|\./)\s+(\S+\.(py|sh|js|rb|pl|php|java|c|cpp|html|css|txt))", last_command, re.IGNORECASE)
                    if match:
                        debug_file_name = match.group(2)
                
                if not debug_file_name:
                    debug_file_name = generate_filename("bug_fix", debug_lang)

                simpan_ok = simpan_ke_file(debug_file_name, debug_saran)
                if simpan_ok:
                    user_context["last_generated_code"] = debug_saran
                    user_context["last_generated_code_language"] = debug_lang
                    user_context["last_ai_response_type"] = "program"
                    
                    run_command_suggestion = ""
                    if debug_lang == "python":
                        run_command_suggestion = f"`python {debug_file_name}`"
                    elif debug_lang == "bash":
                        run_command_suggestion = f"`bash {debug_file_name}` or `chmod +x {debug_file_name} && ./{debug_file_name}`"
                    elif debug_lang == "javascript":
                        run_command_suggestion = f"`node {debug_file_name}` (ensure Node.js is installed)"
                    elif debug_lang == "html":
                        run_command_suggestion = f"Open this file in your web browser."
                    elif debug_lang == "php":
                        run_command_suggestion = f"`php {debug_file_name}` (ensure PHP is installed)"
                    elif debug_lang == "java":
                        run_command_suggestion = f"Compile with `javac {debug_file_name}` then run with `java {debug_file_name.replace('.java', '')}`"
                    elif debug_lang in ["c", "cpp"]:
                        run_command_suggestion = f"Compile with `gcc {debug_file_name} -o a.out` then run with `./a.out`"

                    return {
                        "type": "debug_fix_generated",
                        "message": f"SUCCESS: AI has generated a fix/new code to `{debug_file_name}`.",
                        "filename": debug_file_name,
                        "code": debug_saran,
                        "language": debug_lang,
                        "run_suggestion": run_command_suggestion
                    }
                else:
                    return {"type": "error", "message": "FILE ERROR: Failed to save generated fix code to file."}
        else:
            return {"type": "info", "message": "No error log available for debugging."}
        
    elif user_response.lower() in ["tidak", "no"]:
        logger.info(f"[Debug] Debugging canceled by {chat_id}")
        return {"type": "info", "message": "Debugging canceled."}
    else:
        return {"type": "info", "message": "INVALID RESPONSE: Please answer 'Yes' or 'No'."}


# Function to get current LLM model names
def get_current_llm_models():
    return {
        "CODE_GEN_MODEL": CODE_GEN_MODEL,
        "ERROR_FIX_MODEL": ERROR_FIX_MODEL,
        "CONVERSATION_MODEL": CONVERSATION_MODEL,
        "COMMAND_CONVERSION_MODEL": COMMAND_CONVERSION_MODEL,
        "FILENAME_GEN_MODEL": FILENAME_GEN_MODEL,
        "INTENT_DETECTION_MODEL": INTENT_DETECTION_MODEL,
    }

# Function to update LLM model names
def set_llm_models(new_models: dict):
    global CODE_GEN_MODEL, ERROR_FIX_MODEL, CONVERSATION_MODEL, COMMAND_CONVERSION_MODEL, FILENAME_GEN_MODEL, INTENT_DETECTION_MODEL
    
    CODE_GEN_MODEL = new_models.get("CODE_GEN_MODEL", CODE_GEN_MODEL)
    ERROR_FIX_MODEL = new_models.get("ERROR_FIX_MODEL", ERROR_FIX_MODEL)
    CONVERSATION_MODEL = new_models.get("CONVERSATION_MODEL", CONVERSATION_MODEL)
    COMMAND_CONVERSION_MODEL = new_models.get("COMMAND_CONVERSION_MODEL", COMMAND_CONVERSION_MODEL)
    FILENAME_GEN_MODEL = new_models.get("FILENAME_GEN_MODEL", FILENAME_GEN_MODEL)
    INTENT_DETECTION_MODEL = new_models.get("INTENT_DETECTION_MODEL", INTENT_DETECTION_MODEL)

    # Update .env file
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    for key, value in new_models.items():
        env_vars[key] = value

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables
    return True, "LLM models updated successfully."


# Function to get and set OPENROUTER_API_KEY
def get_openrouter_api_key():
    return OPENROUTER_API_KEY

def set_openrouter_api_key(api_key: str):
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = api_key
    
    # Update .env file
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    env_vars["OPENROUTER_API_KEY"] = api_key

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables
    return True, "OpenRouter API Key updated successfully."


# Function to get and set LLM_BASE_URL
def get_llm_base_url():
    return LLM_BASE_URL

def set_llm_base_url(base_url: str):
    global LLM_BASE_URL
    LLM_BASE_URL = base_url
    
    # Update .env file
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    env_vars["LLM_BASE_URL"] = base_url

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables
    return True, "LLM Base URL updated successfully."


# Function to get and set TELEGRAM_CHAT_ID (for reference, not directly used by web)
def get_telegram_chat_id():
    return TELEGRAM_CHAT_ID

def set_telegram_chat_id(chat_id: str):
    global TELEGRAM_CHAT_ID
    TELEGRAM_CHAT_ID = chat_id
    
    # Update .env file
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    env_vars["TELEGRAM_CHAT_ID"] = chat_id

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables
    return True, "Telegram Chat ID updated successfully."


# Function to get and set TELEGRAM_BOT_TOKEN (for reference, not directly used by web)
def get_telegram_bot_token():
    return TELEGRAM_BOT_TOKEN

def set_telegram_bot_token(token: str):
    global TELEGRAM_BOT_TOKEN
    TELEGRAM_BOT_TOKEN = token
    
    # Update .env file
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    env_vars["TELEGRAM_BOT_TOKEN"] = token

    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    load_dotenv(override=True) # Reload environment variables
    return True, "Telegram Bot Token updated successfully."


