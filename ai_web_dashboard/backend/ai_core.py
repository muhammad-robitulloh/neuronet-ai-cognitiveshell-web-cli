import json
import logging
import asyncio
import uuid # Import uuid

from . import config
from .utils import llm_utils, ai_services, file_utils, shell_utils

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Main Class for Web Backend Core Logic ---

class AICore:
    """
    Encapsulates all core logic required for the web dashboard backend.
    Orchestrates calls to various utility modules.
    """
    def __init__(self):
        """Initializes in-memory stores for session data."""
        self.user_contexts: dict = {}
        self.chat_histories: dict = {}
        self.auto_debug_requests: dict = {} # Store auto-debug requests
        logger.info(f"AICore initialized. Project root: {config.PROJECT_ROOT}")

    def get_user_context(self, chat_id: int) -> dict:
        """Retrieves user context, initializing if absent."""
        if chat_id not in self.user_contexts:
            self.user_contexts[chat_id] = {}
        return self.user_contexts[chat_id]

    def get_chat_history(self, chat_id: int) -> list:
        """Retrieves chat history, initializing if absent."""
        if chat_id not in self.chat_histories:
            self.chat_histories[chat_id] = []
        return self.chat_histories[chat_id]

    async def process_chat_stream(self, chat_id: int, message: str, attached_file_path: str = None, is_telegram_chat: bool = False):
        """
        Main generator to handle a chat request and stream back responses.
        """
        logger.info(f"[Core] Chat stream started for chat_id {chat_id} (Telegram: {is_telegram_chat}): '{message}'")
        yield self._format_stream_chunk("status", "Thinking...")

        current_chat_history = self.get_chat_history(chat_id)
        file_content = None
        reasoning_full_text = "" # Initialize reasoning_full_text
        shell_output_full_text = "" # Initialize shell_output_full_text
        generated_code_full_text = "" # Initialize generated_code_full_text

        if attached_file_path:
            read_result = file_utils.read_file(attached_file_path)
            if read_result.get("error"):
                yield self._format_stream_chunk("error", f"Failed to read attached file: {read_result["error"]}", format="error")
                yield self._format_stream_chunk("done", "")
                return
            file_content = read_result["content"]
            logger.info(f"Attached file content read from {attached_file_path}")
            # Add file content to the message for AI processing
            message_with_file = f"{message}\n\nAttached File ({attached_file_path}):\n```\n{file_content}\n```"
        else:
            message_with_file = message

        niat_initial = None
        try:
            niat_initial = await ai_services.deteksi_niat_pengguna(message_with_file, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)
            logger.info(f"[Core] Detected initial intent: {niat_initial}")
            yield self._format_stream_chunk("intent_update", f"Initial Intent: {niat_initial}")
        except Exception as e:
            logger.error(f"[Core] Error detecting initial intent: {e}")
            yield self._format_stream_chunk("error", f"Failed to detect initial intent: {e}", format="error")
            yield self._format_stream_chunk("done", "")
            return

        niat_final = niat_initial # Default to initial intent

        # --- Agentic Workflow --- 
        if niat_final == "shell" or niat_final == "direct_execution":
            yield self._format_stream_chunk("status", "Planning command...")
            if niat_final == "shell":
                success, command = await ai_services.konversi_ke_perintah_shell(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)
            else: # direct_execution
                success, command = await ai_services.generate_execution_command(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)

            if not success or command == "CANNOT_CONVERT":
                logger.error(f"[Core] Command conversion failed: {command}")
                yield self._format_stream_chunk("error", "Could not convert to a valid command.", format="error")
            else:
                logger.info(f"[Core] Proposed command: {command}")
                # Yield for user approval instead of executing directly
                yield self._format_stream_chunk("agent_request_approval", {"command": command})
            yield self._format_stream_chunk("done", "")
            return
        # --- End Agentic Workflow ---

        # Conditionally generate and stream reasoning
        logger.info(f"[Core] Reasoning Enabled: {config.REASONING_ENABLED}, Apply to Models: {config.REASONING_APPLY_TO_MODELS}")
        intent_to_model_map = {
            "shell": "COMMAND_CONVERSION_MODEL",
            "program": "CODE_GEN_MODEL",
            "conversation": "CONVERSATION_MODEL",
            "error_fix": "ERROR_FIX_MODEL", # Assuming error_fix is an intent
            "filename_gen": "FILENAME_GEN_MODEL", # Assuming filename_gen is an intent
            "intent_detection": "INTENT_DETECTION_MODEL", # Assuming intent_detection is an intent
            "direct_execution": "COMMAND_CONVERSION_MODEL",
            "research": "CONVERSATION_MODEL" # Research intent will use conversation model for summarization
        }
        # Get the model key corresponding to the detected intent
        model_key_for_intent = intent_to_model_map.get(niat_initial)

        if config.REASONING_ENABLED and model_key_for_intent and model_key_for_intent in config.REASONING_APPLY_TO_MODELS:
            yield self._format_stream_chunk("status", "Generating reasoning...")
            reasoning_full_text = ""
            try:
                async for chunk in ai_services.generate_reasoning(message_with_file, niat_initial, chat_history=current_chat_history, max_tokens=config.REASONING_MAX_TOKENS, temperature=config.REASONING_TEMPERATURE):
                    reasoning_full_text += chunk
                    yield self._format_stream_chunk("reasoning_chunk", chunk, format="markdown")
                    logger.debug(f"[Core] Yielded reasoning chunk: {chunk}")
            except Exception as e:
                logger.error(f"[Core] Error during reasoning generation: {e}")
                yield self._format_stream_chunk("error", f"Reasoning generation failed: {e}", format="error")
                # If reasoning fails, we should still proceed with initial intent or handle gracefully
                # For now, let's just log and continue with niat_initial

            # After reasoning, re-evaluate intent with reasoning context
            if reasoning_full_text:
                yield self._format_stream_chunk("status", "Re-evaluating intent with reasoning...")
                try:
                    niat_final = await ai_services.deteksi_niat_pengguna(
                        message_with_file,
                        reasoning_context=reasoning_full_text,
                        max_tokens=config.DEFAULT_MAX_TOKENS,
                        temperature=config.DEFAULT_TEMPERATURE
                    )
                    logger.info(f"[Core] Detected final intent with reasoning: {niat_final}")
                    yield self._format_stream_chunk("intent_update", f"Final Intent (with reasoning): {niat_final}")
                except Exception as e:
                    logger.error(f"[Core] Error re-detecting intent with reasoning: {e}")
                    yield self._format_stream_chunk("error", f"Failed to re-detect intent with reasoning: {e}. Proceeding with initial intent.", format="error")
                    niat_final = niat_initial # Fallback to initial intent if re-detection fails

        if niat_final == "shell":
            # Check if the message is already a direct shell command
            direct_command_prefixes = (
                "python ", "bash ", "sh ", "ls ", "cd ", "mkdir ", "rm ", "touch ", "cat ", "echo ",
                "pip ", "npm ", "git ", "docker ", # Common commands
                "python", "bash", "sh", "ls", "cd", "mkdir", "rm", "touch", "cat", "echo",
                "pip", "npm", "git", "docker" # For commands without arguments
            )
            
            command = None
            success = False

            if message_with_file.strip().startswith(direct_command_prefixes):
                command = message_with_file.strip()
                success = True
                logger.info(f"[Core] Direct shell command detected: {command}")
            else:
                yield self._format_stream_chunk("status", "Converting to shell command...")
                try:
                    success, command = await ai_services.konversi_ke_perintah_shell(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)
                except Exception as e:
                    logger.error(f"[Core] Error converting to shell command: {e}")
                    yield self._format_stream_chunk("error", f"Failed to convert to shell command: {e}", format="error")
                    yield self._format_stream_chunk("done", "")
                    return
            
            if not success or command == "CANNOT_CONVERT":
                logger.error(f"[Core] Shell command conversion failed: {command}")
                yield self._format_stream_chunk("error", "Could not convert to a shell command.", format="error")
            else:
                logger.info(f"[Core] Generated shell command: {command}")
                yield self._format_stream_chunk("command", command, format="code")
                yield self._format_stream_chunk("status", "Executing shell command...")
                try:
                    async for chunk in shell_utils.execute_and_stream_command(command):
                        if chunk is None: # Sentinel for end of stream
                            continue
                        if chunk["type"] == "shell_output":
                            shell_output_full_text += chunk["content"]
                            yield self._format_stream_chunk(chunk["type"], chunk["content"], format="code")
                        elif chunk["type"] == "shell_error":
                            # Trigger auto-debug if a shell error occurs
                            request_id = str(uuid.uuid4())
                            self.auto_debug_requests[request_id] = {
                                "original_message": message_with_file,
                                "error_details": chunk["content"],
                                "shell_command": command,
                                "full_shell_output": shell_output_full_text,
                                "chat_history": current_chat_history,
                                "intent": niat_final
                            }
                            yield self._format_stream_chunk("auto_debug_request", {"request_id": request_id, "error_details": chunk["content"]})
                            return # Stop further processing until debug is handled
                        elif chunk["type"] == "shell_exit_code":
                            # Optionally, you can yield the exit code or handle it
                            # For now, we just log it and let the stream continue to 'done'
                            logger.info(f"[Core] Shell command exited with code: {chunk['content']}")
                    # After shell command execution, add to chat history
                    current_chat_history.append({"role": "user", "content": message})
                    current_chat_history.append({
                        "role": "assistant",
                        "content": f"Executed command: `{command}`",
                        "reasoning": reasoning_full_text,
                        "shell_output": shell_output_full_text
                    })
                    self.chat_histories[chat_id] = current_chat_history
                except Exception as e:
                    logger.error(f"[Core] Error executing shell command: {e}")
                    yield self._format_stream_chunk("error", f"Error executing shell command: {e}", format="error")
                

        elif niat_final == "program":
            yield self._format_stream_chunk("status", "Generating program code...")
            # Attempt to detect target language from the message for better filename generation
            target_language = None
            if "python" in message_with_file.lower():
                target_language = "python"
            elif "javascript" in message_with_file.lower() or "js" in message_with_file.lower():
                target_language = "javascript"
            elif "bash" in message_with_file.lower() or "shell script" in message_with_file.lower():
                target_language = "bash"
            # Add more language detections as needed

            try:
                success, code, lang = await ai_services.minta_kode(
                    message_with_file, 
                    chat_history=current_chat_history, 
                    target_language=target_language, 
                    max_tokens=config.DEFAULT_MAX_TOKENS, 
                    temperature=config.DEFAULT_TEMPERATURE,
                    reasoning_context=reasoning_full_text # Pass the reasoning context
                )
            except Exception as e:
                logger.error(f"[Core] Error requesting code: {e}")
                yield self._format_stream_chunk("error", f"Failed to request code: {e}", format="error")
                yield self._format_stream_chunk("done", "")
                return

            if success:
                logger.info(f"[Core] Code generated successfully for language: {lang}")
                try:
                    filename = await ai_services.generate_filename(message_with_file, lang, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)
                except Exception as e:
                    logger.error(f"[Core] Error generating filename: {e}")
                    yield self._format_stream_chunk("error", f"Failed to generate filename: {e}", format="error")
                    yield self._format_stream_chunk("done", "")
                    return
                logger.info(f"[Core] Generated filename: {filename}")
                file_path_full = f"generated_files/{filename}"
                write_result = file_utils.write_file(file_path_full, code)
                if write_result.get("error"):
                    logger.error(f"[Core] Failed to write file {filename}: {write_result['error']}")
                    yield self._format_stream_chunk("error", f"Failed to save generated code: {write_result['error']}", format="error")
                else:
                    logger.info(f"[Core] File {filename} written successfully.")
                    generated_code_full_text = code # Store the generated code
                    yield self._format_stream_chunk("generated_code", {"filename": filename, "language": lang, "code": code}, format="code_block")

                    # Execute the generated program
                    execution_command = ""
                    if lang == "python":
                        execution_command = f"python {file_path_full}"
                    elif lang == "bash":
                        # Make script executable before running
                        execution_command = f"chmod +x {file_path_full} && bash {file_path_full}"
                    elif lang == "javascript":
                        execution_command = f"node {file_path_full}"
                    # Add more execution commands for other languages as needed

                    if execution_command:
                        yield self._format_stream_chunk("status", f"Executing generated {lang} program...")
                        try:
                            async for chunk in shell_utils.execute_and_stream_command(execution_command):
                                if chunk is None: # Sentinel for end of stream
                                    continue
                                if chunk["type"] == "shell_output":
                                    shell_output_full_text += chunk["content"]
                                    yield self._format_stream_chunk(chunk["type"], chunk["content"], format="code")
                                elif chunk["type"] == "shell_error":
                                    # Trigger auto-debug if a program execution error occurs
                                    request_id = str(uuid.uuid4())
                                    self.auto_debug_requests[request_id] = {
                                        "command": execution_command,
                                        "error_output": chunk["content"],
                                        "code": code,
                                        "language": lang,
                                        "chat_history": current_chat_history,
                                        "message": message
                                    }
                                    yield self._format_stream_chunk("auto_debug_request", {"request_id": request_id, "error_details": chunk["content"]})
                                    return # Stop further processing until debug is handled
                                elif chunk["type"] == "shell_exit_code":
                                    logger.info(f"[Core] Program execution exited with code: {chunk['content']}")
                        except Exception as e:
                            logger.error(f"[Core] Error executing generated program: {e}")
                            yield self._format_stream_chunk("error", f"Error executing generated program: {e}", format="error")
                    else:
                        yield self._format_stream_chunk("status", "No direct execution command for this language.")

                    # After program generation and optional execution, add to chat history
                    current_chat_history.append({"role": "user", "content": message})
                    assistant_message_content = f"Generated {lang} code:\n```\n{generated_code_full_text}\n```"
                    if shell_output_full_text:
                        assistant_message_content += f"\n\nExecution Output:\n```\n{shell_output_full_text}\n```"
                    current_chat_history.append({
                        "role": "assistant",
                        "content": assistant_message_content,
                        "reasoning": reasoning_full_text,
                        "shell_output": shell_output_full_text # Include shell output for program execution
                    })
                    self.chat_histories[chat_id] = current_chat_history
            else:
                logger.error(f"[Core] Code generation failed: {code}")
                yield self._format_stream_chunk("error", "Failed to generate code.", format="error")

        elif niat_final == "direct_execution":
            yield self._format_stream_chunk("status", "Generating execution command...")
            try:
                success, command = await ai_services.generate_execution_command(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE)
            except Exception as e:
                logger.error(f"[Core] Error generating execution command: {e}")
                yield self._format_stream_chunk("error", f"Failed to generate execution command: {e}", format="error")
                yield self._format_stream_chunk("done", "")
                return

            if not success or command == "CANNOT_CONVERT":
                logger.error(f"[Core] Execution command generation failed: {command}")
                yield self._format_stream_chunk("error", "Could not generate an execution command.", format="error")
            else:
                logger.info(f"[Core] Generated execution command: {command}")
                yield self._format_stream_chunk("command", command, format="code")
                yield self._format_stream_chunk("status", "Executing command...")
                try:
                    async for chunk in shell_utils.execute_and_stream_command(command):
                        if chunk is None: # Sentinel for end of stream
                            continue
                        if chunk["type"] == "shell_output":
                            shell_output_full_text += chunk["content"]
                            yield self._format_stream_chunk(chunk["type"], chunk["content"], format="code")
                        elif chunk["type"] == "shell_error":
                            # Trigger auto-debug if a shell error occurs
                            request_id = str(uuid.uuid4())
                            self.auto_debug_requests[request_id] = {
                                "command": command,
                                "error_output": chunk["content"],
                                "chat_history": current_chat_history, # Provide context
                                "message": message # Original user message
                            }
                            logger.info(f"[Core] Stored auto_debug_request for ID: {request_id}. Current requests: {list(self.auto_debug_requests.keys())}")
                            yield self._format_stream_chunk("auto_debug_request", {"request_id": request_id, "error_details": chunk["content"]})
                            return # Stop further processing until debug is handled
                        elif chunk["type"] == "shell_exit_code":
                            logger.info(f"[Core] Direct execution command exited with code: {chunk['content']}")
                    # After shell command execution, add to chat history
                    current_chat_history.append({"role": "user", "content": message})
                    current_chat_history.append({
                        "role": "assistant",
                        "content": f"Executed command: `{command}`",
                        "reasoning": reasoning_full_text,
                        "shell_output": shell_output_full_text
                    })
                    self.chat_histories[chat_id] = current_chat_history
                except Exception as e:
                    logger.error(f"[Core] Error executing command: {e}")
                    yield self._format_stream_chunk("error", f"Error executing command: {e}", format="error")

        elif niat_final == "research":
            if not config.WEB_SEARCH_ENABLED:
                yield self._format_stream_chunk("error", "Web search is not enabled in settings.", format="error")
                yield self._format_stream_chunk("done", "")
                return
            yield self._format_stream_chunk("status", "Starting online research...")
            full_response_content = ""
            try:
                async for type, content in ai_services.research_and_summarize(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE):
                    if type == "status":
                        yield self._format_stream_chunk("status", content)
                    elif type == "message_chunk":
                        full_response_content += content
                        yield self._format_stream_chunk("conversation_chunk", content, format="markdown")
            except Exception as e:
                logger.error(f"[Core] Error during research and summarization: {e}")
                yield self._format_stream_chunk("error", f"Research failed: {e}", format="error")
                return
            
            logger.info(f"[Core] Online research and summarization complete.")
            current_chat_history.append({"role": "user", "content": message})
            current_chat_history.append({"role": "assistant", "content": full_response_content, "reasoning": reasoning_full_text})
            self.chat_histories[chat_id] = current_chat_history

        else: # Conversation
            yield self._format_stream_chunk("status", "Generating conversation response...")
            full_response_content = ""
            try:
                async for chunk in ai_services.minta_jawaban_konversasi(message_with_file, chat_history=current_chat_history, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE):
                    full_response_content += chunk
                    yield self._format_stream_chunk("conversation_chunk", chunk, format="markdown")
                    logger.debug(f"[Core] Yielded conversation message chunk: {chunk}")
            except Exception as e:
                logger.error(f"[Core] Error during conversation response generation: {e}")
                yield self._format_stream_chunk("error", f"Conversation response failed: {e}", format="error")
                return

            logger.info(f"[Core] Conversation response generated.")
            current_chat_history.append({"role": "user", "content": message})
            current_chat_history.append({"role": "assistant", "content": full_response_content, "reasoning": reasoning_full_text})
            self.chat_histories[chat_id] = current_chat_history

        yield self._format_stream_chunk("done", "")

    async def execute_and_analyze_stream(self, chat_id: int, command: str):
        """
        Executes the command, streams the output, and then streams the AI analysis.
        """
        logger.info(f"[Core] User approved command for chat_id {chat_id}: {command}")
        yield self._format_stream_chunk("status", f"Executing: {command}")

        # 1. Execute the command and get the full result
        execution_result = await shell_utils.execute_command_sync(command)
        stdout = execution_result["stdout"]
        stderr = execution_result["stderr"]
        exit_code = execution_result["exit_code"]

        # 2. Stream the raw output to the user
        yield self._format_stream_chunk("shell_output", stdout, format="code")
        if stderr:
            yield self._format_stream_chunk("shell_error", stderr, format="code")
        yield self._format_stream_chunk("shell_exit_code", exit_code)

        # 3. Analyze the result and stream the analysis
        yield self._format_stream_chunk("status", "Analyzing result...")
        analysis_full_text = ""
        try:
            async for chunk in ai_services.analyze_execution_result(command, stdout, stderr, exit_code, max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE):
                analysis_full_text += chunk
                yield self._format_stream_chunk("agent_analysis_chunk", chunk, format="markdown")
        except Exception as e:
            logger.error(f"[Core] Error during execution analysis: {e}")
            yield self._format_stream_chunk("error", f"Result analysis failed: {e}", format="error")

        # 4. Update chat history
        current_chat_history = self.get_chat_history(chat_id)
        # We might need to find the original user message that led to this command
        # For now, we'll add a system message.
        current_chat_history.append({
            "role": "assistant",
            "content": f"Executed command: `{command}`\n\n**Output**:\n```\n{stdout}\n{stderr}\n```\n\n**Analysis**:\n{analysis_full_text}"
        })
        self.chat_histories[chat_id] = current_chat_history

        yield self._format_stream_chunk("done", "")

    async def process_auto_debug_request(self, request_id: str):
        """
        Processes an auto-debug request, using LLM to analyze the error
        and suggest a fix, streaming the thought process.
        """
        logger.info(f"[Core] Processing auto-debug request_id: {request_id}. Current requests before pop: {list(self.auto_debug_requests.keys())}")
        if request_id is None:
            logger.error("[Core] Received auto-debug request with no request_id.")
            yield self._format_stream_chunk("error", "Auto-debug request missing ID.", format="error")
            yield self._format_stream_chunk("done", "")
            return
        request_data = self.auto_debug_requests.pop(request_id, None)

        if not request_data:
            logger.error(f"[Core] Auto-debug request_id {request_id} not found. Requests after pop: {list(self.auto_debug_requests.keys())}")
            yield self._format_stream_chunk("error", "Auto-debug request not found or expired.", format="error")
            yield self._format_stream_chunk("done", "")
            return

        command = request_data.get("command", "N/A")
        error_output = request_data.get("error_output", "N/A")
        code = request_data.get("code", "N/A")
        language = request_data.get("language", "N/A")
        chat_history = request_data.get("chat_history", [])
        original_message = request_data.get("message", "N/A")

        yield self._format_stream_chunk("status", "Analyzing error with AI...")
        yield self._format_stream_chunk("thought_process_start", "")

        full_thought_process = ""
        try:
            async for chunk in ai_services.analyze_and_fix_error(
                command=command,
                error_output=error_output,
                code=code,
                language=language,
                chat_history=chat_history,
                original_message=original_message,
                max_tokens=config.DEFAULT_MAX_TOKENS,
                temperature=config.DEFAULT_TEMPERATURE
            ):
                full_thought_process += chunk
                yield self._format_stream_chunk("thought_process_chunk", chunk, format="markdown")
        except Exception as e:
            logger.error(f"[Core] Error during auto-debug analysis: {e}")
            yield self._format_stream_chunk("error", f"Auto-debug analysis failed: {e}", format="error")
            yield self._format_stream_chunk("done", "")
            return

        yield self._format_stream_chunk("thought_process_end", full_thought_process)
        yield self._format_stream_chunk("status", "Auto-debug complete.")
        yield self._format_stream_chunk("final_debug_response", full_thought_process)
        yield self._format_stream_chunk("done", "")

    def _format_stream_chunk(self, type: str, content: any, format: str = None):
        """Helper to format a JSON chunk for streaming responses."""
        chunk_data = {"type": type, "content": content}
        if format:
            chunk_data["format"] = format
        return json.dumps(chunk_data) + '\n'

# --- Create a single instance for the application to use ---
ai_core_instance = AICore()
