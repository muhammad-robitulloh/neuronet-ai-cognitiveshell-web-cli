import logging
import re
import asyncio # Added for asyncio.to_thread
from .. import config
from . import llm_utils
from . import file_utils
from . import web_utils # Import the new web_utils

logger = logging.getLogger(__name__)

async def research_and_summarize(query: str, chat_history: list = None, max_tokens: int = None, temperature: float = None):
    """
    Performs online research based on a query and summarizes the findings.
    """
    if not config.WEB_SEARCH_ENABLED:
        logger.error("[AI Services] Web search is disabled in configuration.")
        yield "message_chunk", "Web search is currently disabled. Please enable it in the settings."
        return

    logger.info(f"[AI Services] Starting online research for query: {query}")
    
    yield "status", "Searching online..."
    search_results = await web_utils.search_google(query)

    if not search_results:
        yield "message_chunk", "I couldn't find any relevant information online for your query."
        return

    yield "status", "Extracting content from top results..."
    full_content = ""
    for i, result in enumerate(search_results[:3]): # Process top 3 results
        yield "status", f"Reading {i+1}/{min(len(search_results), 3)}: {result['title']}"
        content = await web_utils.extract_content_from_url(result['link'])
        if content:
            full_content += f"\n\n--- Content from {result['title']} ({result['link']}) ---\n{content[:2000]}..." # Limit content to avoid huge prompts
        else:
            full_content += f"\n\n--- Could not extract content from {result['title']} ({result['link']}) ---"

    if not full_content.strip():
        yield "message_chunk", "I found some search results, but couldn't extract meaningful content from them."
        return

    yield "status", "Summarizing findings..."
    system_prompt = """You are an AI assistant. Summarize the provided research content concisely and answer the user's original query based on the findings. If the content is insufficient, state that.

Research Content:
"""
    messages = [
        {"role": "system", "content": system_prompt + full_content},
        {"role": "user", "content": f"Summarize the research and answer my original query: {query}"}
    ]
    if chat_history:
        messages.extend(chat_history[-5:]) # Provide some recent context

    async for chunk in llm_utils.stream_llm(messages, config.CONVERSATION_MODEL, max_tokens=max_tokens, temperature=temperature):
        yield "message_chunk", chunk

    logger.info(f"[AI Services] Online research and summarization complete for query: {query}")

async def deteksi_niat_pengguna(pesan_pengguna: str, reasoning_context: str = None, max_tokens: int = None, temperature: float = None) -> str:
    """
    Detects user intent: shell, program, conversation, direct_execution, or research.
    """
    system_prompt = '''You are an intent detector. Classify the user's message as "shell", "program", "conversation", "direct_execution", or "research". Return only one word.'''
    if reasoning_context:
        system_prompt += f"\n\nConsider the following reasoning: {reasoning_context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Detect intent for: '{pesan_pengguna}'"}
    ]

    success, niat = await asyncio.to_thread(llm_utils.call_llm, messages, config.INTENT_DETECTION_MODEL, max_tokens=max_tokens, temperature=temperature)
    logger.info(f"[AI Services] Intent detection LLM call result: Success={success}, Intent={niat}")
    niat_cleaned = niat.strip().lower()
    if success and niat_cleaned in ["shell", "program", "conversation", "direct_execution", "research"]:
        return niat_cleaned
    logger.warning(f"[AI Services] Intent detection failed or returned invalid intent: {niat_cleaned}. Defaulting to conversation.")
    return "conversation"

async def generate_reasoning(user_message: str, detected_intent: str, chat_history: list = None, max_tokens: int = None, temperature: float = None):
    """
    Generates a detailed reasoning for the AI's chosen action, streaming the output.
    """
    system_prompt = f"""You are an AI assistant. Based on the user's message and the detected intent '{detected_intent}', explain your thought process and what you plan to do next. Provide this in a structured Markdown format with the following sections:

## Thought Process
- Detail your step-by-step reasoning.
- Explain how you interpreted the user's request.
- Mention any assumptions made or ambiguities identified.

## Plan
- Outline the specific actions you will take.
- If the intent is 'shell', explain why you chose that specific shell command, considering safety and efficiency.
- If the intent is 'program', explain why you chose a particular programming language or file extension for the generated code.
- If you need to ask clarifying questions, include them here.

## Confidence
- State your confidence level in this plan (e.g., High, Medium, Low) and briefly explain why.

Be concise and clear within each section.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    if chat_history:
        messages.extend(chat_history[-5:]) # Provide some recent context

    logger.info(f"[AI Services] Starting reasoning generation for intent: {detected_intent}")
    # Stream the reasoning output
    async for chunk in llm_utils.stream_llm(messages, config.REASONING_MODEL, max_tokens=max_tokens, temperature=temperature):
        logger.debug(f"[AI Services] Reasoning chunk received from LLM: '{chunk}'")
        yield chunk

async def minta_kode(prompt: str, error_context: str = None, chat_history: list = None, target_language: str = None, max_tokens: int = None, temperature: float = None, reasoning_context: str = None) -> tuple[bool, str, str | None]:
    """
    Requests LLM to generate or fix code.
    """
    system_info_message = f"""You are an expert AI coding assistant on OS: {config.SYSTEM_INFO['os']}. Your task is to provide complete, runnable code in a single Markdown block. 

When generating code:
- Always choose the most appropriate programming language for the user's request. If the user specifies a language, adhere to it.
- Write idiomatic and clean code following best practices for the chosen language.
- Include necessary imports and setup if applicable.
- If the code requires execution, ensure it's self-contained and runnable.
- For scripts, ensure they are executable (e.g., include shebang for shell scripts).
"""
    
    messages = [{"role": "system", "content": system_info_message}]

    # Inject the reasoning context as a high-priority assistant message
    if reasoning_context:
        messages.append({
            "role": "assistant",
            "content": f"I have analyzed the user's request and prepared the following plan:\n\n{reasoning_context}\n\nNow, I will generate the code based on this plan."
        })

    if chat_history:
        messages.extend(chat_history[-5:])

    if error_context:
        messages.append({"role": "user", "content": f"Fix the following error:\n\n{error_context}"})
    else:
        messages.append({"role": "user", "content": prompt})
    
    model = config.ERROR_FIX_MODEL if error_context else config.CODE_GEN_MODEL

    logger.info(f"[AI Services] Requesting code generation from model: {model}")
    success, response_content = await asyncio.to_thread(llm_utils.call_llm, messages, model, max_tokens=max_tokens, temperature=temperature)

    if success:
        logger.info(f"[AI Services] Code generation LLM call successful.")
        cleaned_code, detected_language = llm_utils.ekstrak_kode_dari_llm(response_content, target_language)
        logger.info(f"[AI Services] Detected language for code: {detected_language}")
        return True, cleaned_code, detected_language
    else:
        logger.error(f"[AI Services] Code generation LLM call failed: {response_content}")
        return False, response_content, None


async def generate_filename(prompt: str, detected_language: str = "txt", max_tokens: int = None, temperature: float = None) -> str:
    """
    Generates a sanitized, relevant filename.
    """
    extension_map = {
        "python": ".py", "bash": ".sh", "javascript": ".js", "html": ".html", "css": ".css",
        "java": ".java", "c": ".c", "cpp": ".cpp", "txt": ".txt", "json": ".json",
        "yaml": ".yaml", "xml": ".xml", "php": ".php", "ruby": ".rb", "go": ".go",
        "rust": ".rs", "swift": ".swift", "kotlin": ".kt", "typescript": ".ts", "jsx": ".jsx",
        "tsx": ".tsx", "sql": ".sql", "markdown": ".md", "dockerfile": ".dockerfile",
        "makefile": ".makefile", "perl": ".pl", "r": ".r", "scala": ".scala", "lua": ".lua",
        "dart": ".dart", "vue": ".vue", "svelte": ".svelte", "solidity": ".sol"
    }
    messages = [
        {"role": "system", "content": f"Generate a short, descriptive, lowercase filename (no spaces, use underscores, no extension) for a '{detected_language}' file based on this prompt. Example: 'web_scraper'."},
        {"role": "user", "content": prompt}
    ]
    logger.info(f"[AI Services] Requesting filename generation from model: {config.FILENAME_GEN_MODEL}")
    success, filename = await asyncio.to_thread(llm_utils.call_llm, messages, config.FILENAME_GEN_MODEL, max_tokens=max_tokens, temperature=temperature)
    
    if not success:
        logger.warning(f"[AI Services] Filename generation failed. Using default: generated_code{extension_map.get(detected_language, '.txt')}")
        return f"generated_code{extension_map.get(detected_language, '.txt')}"

    # Sanitize the filename
    filename = re.sub(r'[^\w-]', '_', filename.strip().lower())
    logger.info(f"[AI Services] Generated and sanitized filename: {filename}{extension_map.get(detected_language, '.txt')}")
    return f"{filename}{extension_map.get(detected_language, '.txt')}"

async def konversi_ke_perintah_shell(bahasa_natural: str, chat_history: list = None, max_tokens: int = None, temperature: float = None) -> tuple[bool, str]:
    """
    Converts natural language to an executable shell command.
    """
    system_message = f"""You are a highly accurate and safe shell command translator for OS: {config.SYSTEM_INFO['os']}. Your goal is to convert natural language instructions into a single, executable shell command. 

Constraints:
- The command must be a single line.
- Prioritize safety: Avoid commands that could cause data loss or system instability unless explicitly requested and clearly understood.
- If the request is ambiguous, unsafe, or impossible to convert to a single shell command, respond ONLY with 'CANNOT_CONVERT'.
- If the user's instruction is already a valid shell command, return it as is.
- Consider common shell utilities and their typical usage.
- If the user asks to create a file with specific content, use `echo 'content' > filename` or `printf 'content' > filename`.
- If the user asks to create a script, provide the full script content as a single command, e.g., `echo '#!/bin/bash\nls' > script.sh && chmod +x script.sh`.

Examples:
- User: 'List all files in the current directory' -> 'ls -F'
- User: 'Create a directory called my_folder' -> 'mkdir my_folder'
- User: 'Show me the content of my_file.txt' -> 'cat my_file.txt'
- User: 'Create a python script that prints hello world' -> 'echo "print(\"Hello, World!\")" > hello.py'
- User: 'Delete all .log files' -> 'rm *.log'
- User: 'What is my IP address?' -> 'ip a'
- User: 'ls -l' -> 'ls -l'
- User: 'Open a GUI application' -> 'CANNOT_CONVERT'
- User: 'Format my hard drive' -> 'CANNOT_CONVERT'
"""
    messages = [{"role": "system", "content": system_message}]
    if chat_history:
        messages.extend(chat_history[-5:])
    messages.append({"role": "user", "content": f"Instruction: {bahasa_natural}"})

    logger.info(f"[AI Services] Requesting shell command conversion from model: {config.COMMAND_CONVERSION_MODEL}")
    success, command = await asyncio.to_thread(llm_utils.call_llm, messages, config.COMMAND_CONVERSION_MODEL, max_tokens=max_tokens, temperature=temperature)
    if success:
        # Extract the command from the Markdown code block
        match = re.search(r'```(?:bash|sh|zsh|shell)\n(.*?)\n```', command, re.DOTALL)
        if match:
            extracted_command = match.group(1).strip()
            logger.info(f"[AI Services] Extracted shell command: {extracted_command}")
            return True, extracted_command
        elif command.strip() == "CANNOT_CONVERT":
            return False, "CANNOT_CONVERT"
        else:
            # If no code block, but it's not CANNOT_CONVERT, assume it's a direct command
            logger.warning(f"[AI Services] No shell code block found, assuming direct command: {command}")
            return True, command.strip()
    else:
        logger.error(f"[AI Services] Shell command conversion LLM call failed: {command}")
        return False, command

async def generate_execution_command(prompt: str, chat_history: list = None, max_tokens: int = None, temperature: float = None) -> tuple[bool, str]:
    """
    Generates a shell command for direct execution from a user request.
    """
    system_message = f"""You are a command generator for a cognitive shell running on {config.SYSTEM_INFO['os']}.
    Your task is to convert the user's request into a single, executable shell command.
    - If the user's request is a question, provide a command to find the answer.
    - If the user's request is an action, provide the command to perform the action.
    - If the request cannot be converted to a command, respond with 'CANNOT_CONVERT'.
    - Only respond with the single command, without any explanation or formatting.
    """
    messages = [{"role": "system", "content": system_message}]
    if chat_history:
        messages.extend(chat_history[-5:])
    messages.append({"role": "user", "content": f"Request: {prompt}"})

    logger.info(f"[AI Services] Requesting execution command from model: {config.COMMAND_CONVERSION_MODEL}")
    success, command = await asyncio.to_thread(llm_utils.call_llm, messages, config.COMMAND_CONVERSION_MODEL, max_tokens=max_tokens, temperature=temperature)
    logger.info(f"[AI Services] Execution command LLM call result: Success={success}, Command={command}")
    return success, command

async def minta_jawaban_konversasi(prompt: str, chat_history: list, max_tokens: int = None, temperature: float = None):
    """
    Requests a conversational answer, maintaining context and streaming the output.
    """
    messages = [{"role": "system", "content": f"You are a helpful AI assistant on OS: {config.SYSTEM_INFO['os']}."}]
    messages.extend(chat_history[-10:])
    messages.append({"role": "user", "content": prompt})

    logger.info(f"[AI Services] Requesting conversation response from model: {config.CONVERSATION_MODEL}")
    async for chunk in llm_utils.stream_llm(messages, config.CONVERSATION_MODEL, max_tokens=max_tokens, temperature=temperature):
        yield chunk

async def analyze_execution_result(command: str, stdout: str, stderr: str, exit_code: int, max_tokens: int = None, temperature: float = None):
    """
    Analyzes the result of an executed command and suggests next steps.
    """
    system_prompt = f"""You are an AI assistant analyzing the result of a shell command executed on OS: {config.SYSTEM_INFO['os']}.

Your task is to:
1.  **Summarize the outcome**: Briefly explain what the command did and whether it succeeded or failed.
2.  **Analyze the output**: Interpret the `stdout` and `stderr`. If there's a list of files, point out potentially important ones. If there's an error, explain it simply.
3.  **Suggest next steps**: Based on the output, propose 2-3 relevant, actionable next steps. Frame them as questions to the user.

**Example 1: Successful `ls -l`**
*   **User Request**: `ls -l`
*   **Analysis**: The command `ls -l` was executed successfully, showing a detailed list of files in the current directory. I see a `README.md` which might contain important information, and a Python script `main.py`.
*   **Suggestions**:
    - "Would you like me to read the contents of `README.md`?"
    - "Should I try to run the `main.py` script?"

**Example 2: Failed `python script.py`**
*   **User Request**: `python script.py`
*   **Analysis**: The command `python script.py` failed with an error. The error message `FileNotFoundError: [Errno 2] No such file or directory: 'script.py'` indicates that the script does not exist.
*   **Suggestions**:
    - "Would you like me to list the files in the current directory to check if the file exists?"
    - "Would you like me to create a new file named `script.py`?"

Provide only the 'Analysis' and 'Suggestions' sections in your response.
"""

    analysis_prompt = f"""**Command Executed**: `{command}`
**Exit Code**: {exit_code}

**STDOUT**:
```
{stdout or '(empty)'}
```

**STDERR**:
```
{stderr or '(empty)'}
```"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": analysis_prompt}
    ]

    logger.info(f"[AI Services] Starting execution result analysis for command: {command}")
    async for chunk in llm_utils.stream_llm(messages, config.CONVERSATION_MODEL, max_tokens=max_tokens, temperature=temperature):
        yield chunk

async def analyze_and_fix_error(command: str, error_output: str, code: str = None, language: str = None, chat_history: list = None, original_message: str = None, max_tokens: int = None, temperature: float = None):
    """
    Analyzes an error and suggests a fix, streaming the thought process.
    """
    system_prompt = f"""You are an expert debugging AI assistant on OS: {config.SYSTEM_INFO['os']}. Your task is to analyze the provided error, explain its likely cause, and suggest a fix. 

Provide your thought process step-by-step. If the error is from a shell command, suggest a corrected command. If it's from a program, suggest corrected code. 

Format your response as a thought process, leading to a suggested solution. If suggesting code, provide it in a Markdown code block. If suggesting a shell command, provide it directly.
"""

    user_message_parts = [
        f"I encountered an error.\n\nOriginal Command/Request: {command}",
        f"Error Output:\n```\n{error_output}\n```"
    ]

    if code and language:
        user_message_parts.append(f"\nProblematic Code ({language}):\n```\n{code}\n```")
    if original_message:
        user_message_parts.append(f"\nOriginal User Message: {original_message}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_message_parts)}
    ]

    if chat_history:
        messages.extend(chat_history[-5:]) # Provide some recent context

    logger.info(f"[AI Services] Starting error analysis and fix generation.")
    async for chunk in llm_utils.stream_llm(messages, config.ERROR_FIX_MODEL, max_tokens=max_tokens, temperature=temperature):
        logger.debug(f"[AI Services] Error fix chunk received from LLM: '{chunk}'")
        yield chunk
