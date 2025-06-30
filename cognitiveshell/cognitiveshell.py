import logging
import sys
import telegram
import argparse
import uvicorn
import subprocess
import atexit
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    JobQueue
)

# Import the refactored AI core logic
from ai_web_dashboard.backend import ai_core

# --- Global variable for the frontend process ---
frontend_process = None

# State for ConversationHandler (debugging)
DEBUGGING_STATE = 1

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: CallbackContext) -> None:
    """
    Log the error and send a message to the user if it's a Telegram API conflict.
    """
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if isinstance(context.error, telegram.error.Conflict):
        error_message = (
            "*🔴 ERROR: Telegram API Conflict*\n\n"\
            "Sepertinya ada instance bot lain yang berjalan dengan token yang sama.\n"\
            "Harap pastikan hanya satu instance bot yang berjalan pada satu waktu.\n\n"\
            "Anda dapat mencoba menghentikan semua proses Python yang mungkin menjalankan bot dengan perintah:\n"\
            "`killall python` (di Termux)\n\n"\
            "Setelah itu, coba jalankan bot lagi."
        )
        if update and update.effective_chat:
            await kirim_ke_telegram(update.effective_chat.id, context, error_message)

# === Frontend Process Management ===

def start_frontend_dev_server():
    """Starts the npm start process in the frontend directory."""
    global frontend_process
    frontend_dir = os.path.join(project_root, 'ai_web_dashboard', 'frontend')
    
    if not os.path.isdir(frontend_dir):
        logger.error(f"[Frontend] Directory not found: {frontend_dir}")
        return

    logger.info(f"[Frontend] Starting 'npm start' in {frontend_dir}...")
    try:
        # Using Popen to run it as a non-blocking background process
        frontend_process = subprocess.Popen(
            ['npm', 'start'],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"[Frontend] 'npm start' process started with PID: {frontend_process.pid}")
    except FileNotFoundError:
        logger.error("[Frontend] 'npm' command not found. Please ensure Node.js and npm are installed and in your PATH.")
    except Exception as e:
        logger.error(f"[Frontend] Failed to start 'npm start': {e}")

def stop_frontend_dev_server():
    """Stops the npm start process if it's running."""
    global frontend_process
    if frontend_process and frontend_process.poll() is None:
        logger.info(f"[Frontend] Stopping 'npm start' process (PID: {frontend_process.pid})...")
        try:
            # Send SIGTERM for graceful shutdown
            frontend_process.terminate()
            frontend_process.wait(timeout=10)
            logger.info("[Frontend] 'npm start' process stopped.")
        except subprocess.TimeoutExpired:
            logger.warning("[Frontend] 'npm start' process did not terminate gracefully. Forcing kill.")
            frontend_process.kill()
            frontend_process.wait()
            logger.info("[Frontend] 'npm start' process killed.")
        except Exception as e:
            logger.error(f"Error stopping frontend process: {e}")

# Register the cleanup function to be called on script exit
atexit.register(stop_frontend_dev_server)


# === Telegram Command Handlers ===

async def start_command(update: Update, context: CallbackContext):
    """Sends a welcome message when the /start command is given."""
    chat_id = update.effective_chat.id
    system_info = ai_core.get_system_info()
    pesan_raw = f"""
*Halo! Saya AI Asisten Shell & Kode Anda.*

Saya bisa membantu Anda dengan beberapa hal:

* *⚙️ SHELL*
    Jalankan perintah sistem atau operasi file. Cukup ketik perintah Anda atau instruksi alami (misal: `tampilkan isi direktori`).
* *✨ PROGRAM*
    Hasilkan atau perbaiki kode program. Cukup berikan instruksi kode (misal: `buatkan fungsi python untuk menghitung faktorial`, `bikinin program bash simple berfungsi sebagai kalkulator`, `tulis kode javascript untuk DOM`). Saya akan mendeteksi bahasanya.
* *💬 KONVERSASI*
    Ajukan pertanyaan umum atau mulai percakapan santai.

---

*Informasi Sistem Terdeteksi:*
* *OS:* {system_info['os']}
* *Shell:* {system_info['shell']}

---

*Perintah Tambahan:*
* `/listfiles` - Melihat daftar file yang dihasilkan.
* `/deletefile <nama_file>` - Menghapus file yang dihasilkan.
* `/clear_chat` - Menghapus riwayat percakapan.

*Penting:* Pastikan bot saya berjalan di Termux dan semua variabel lingkungan sudah diatur!
    """
    await kirim_ke_telegram(chat_id, context, pesan_raw)
    logger.info(f"[Telegram] /start message sent to {chat_id}.")

async def handle_listfiles_command(update: Update, context: CallbackContext):
    """
    Handles the /listfiles command to display a list of generated files.
    Uses ai_core for file listing.
    """
    chat_id = update.effective_chat.id

    if str(chat_id) != ai_core.get_telegram_chat_id():
        await kirim_ke_telegram(chat_id, context, f"*❗ ACCESS DENIED* You are not authorized to use this feature. Contact the bot admin.")
        logger.warning(f"[Auth] ⚠ Unauthorized access attempt /listfiles from {chat_id}.")
        return

    files = ai_core.list_generated_files()
    
    if files:
        file_list_msg = "*📄 MY FILES* List of available program files:\n" + "\n".join([f"- `{f}`" for f in files])
    else:
        file_list_msg = "*📄 MY FILES* No program files generated by the bot."
    
    await kirim_ke_telegram(chat_id, context, file_list_msg)
    logger.info(f"[Telegram] File list sent to {chat_id}.")

async def handle_deletefile_command(update: Update, context: CallbackContext):
    """
    Handles the /deletefile command to delete a specific file.
    Uses ai_core for file deletion.
    """
    chat_id = update.effective_chat.id
    filename_to_delete = " ".join(context.args).strip()

    if str(chat_id) != ai_core.get_telegram_chat_id():
        await kirim_ke_telegram(chat_id, context, f"*❗ ACCESS DENIED* You are not authorized to use this feature. Contact the bot admin.")
        logger.warning(f"[Auth] ⚠ Unauthorized access attempt /deletefile from {chat_id}.")
        return

    if not filename_to_delete:
        await kirim_ke_telegram(chat_id, context, f"*❓ COMMAND* Please provide the filename to delete. Example: `/deletefile your_program_name.py`")
        return

    success, message = ai_core.delete_file(filename_to_delete)

    if success:
        await kirim_ke_telegram(chat_id, context, f"*✅ SUCCESS* File `{filename_to_delete}` successfully deleted.")
        logger.info(f"[File] File {filename_to_delete} deleted by {chat_id}.")
    else:
        await kirim_ke_telegram(chat_id, context, f"*🔴 ERROR* Failed to delete file `{filename_to_delete}`: `{message}`")
        logger.error(f"[File] 🔴 Failed to delete file {filename_to_delete}: {message}")

async def handle_clear_chat_command(update: Update, context: CallbackContext):
    """
    Handles the /clear_chat command to clear conversation history.
    Uses ai_core for clearing chat history.
    """
    chat_id = update.effective_chat.id
    if str(chat_id) != ai_core.get_telegram_chat_id():
        await kirim_ke_telegram(chat_id, context, f"*❗ ACCESS DENIED* You are not authorized to use this feature. Contact the bot admin.")
        logger.warning(f"[Auth] ⚠ Unauthorized access attempt /clear_chat from {chat_id}.")
        return

    success, message = ai_core.clear_all_chat_history()
    if success:
        await kirim_ke_telegram(chat_id, context, f"*✅ SUCCESS* Your conversation history has been cleared.")
        logger.info(f"[Chat] Chat history for {chat_id} cleared.")
    else:
        await kirim_ke_telegram(chat_id, context, f"*🔴 ERROR* Failed to clear chat history: {message}")
        logger.error(f"[Chat] 🔴 Failed to clear chat history for {chat_id}: {message}")


async def handle_text_message(update: Update, context: CallbackContext):
    """
    Handles all non-command text messages from Telegram.
    Will detect user intent and call appropriate functions using ai_core.
    """
    chat_id = update.effective_chat.id
    user_message = update.message.text.strip()
    user_context = ai_core.get_user_context(chat_id)
    
    if str(chat_id) != ai_core.get_telegram_chat_id():
        await kirim_ke_telegram(chat_id, context, f"*❗ ACCESS DENIED* You are not authorized to interact with this bot. Contact the bot admin.")
        logger.warning(f"[Auth] ⚠ Unauthorized access attempt from {chat_id}: {user_message}")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    # Use ai_core's process_user_message
    response = await ai_core.process_user_message(chat_id, user_message)
    
    if response["type"] == "shell_command":
        await kirim_ke_telegram(chat_id, context, f"*⚙️ SHELL* Translated shell command: `{response["command"]}`")
        # Call run_shell_observer_telegram and handle return value for ConversationHandler
        return await run_shell_observer_telegram(response["command"], update, context)
    elif response["type"] == "program_generated":
        await kirim_ke_telegram(chat_id, context, f"*✅ SUCCESS* *{response["language"].capitalize()}* code successfully generated and saved to `{response["filename"]}`.")
        await kirim_ke_telegram(chat_id, context, f"*You can open it in Termux with:* `nano {response["filename"]}`")
        if response["run_suggestion"]:
            await kirim_ke_telegram(chat_id, context, f"*And run with:* {response["run_suggestion"]}")
        await kirim_ke_telegram(chat_id, context, f'*📋 GENERATED CODE*\n```{response["language"]}\n{response["code"]}\n```')
    elif response["type"] == "conversation":
        await kirim_ke_telegram(chat_id, context, f"*💬 AI RESPONSE*\n{response["message"]}")
    elif response["type"] == "error":
        await kirim_ke_telegram(chat_id, context, f"*🔴 ERROR* {response["message"]}")
    elif response["type"] == "info":
        await kirim_ke_telegram(chat_id, context, f"*💬 INFO* {response["message"]}")

    return ConversationHandler.END


async def handle_unknown_command(update: Update, context: CallbackContext):
    """Responds to unknown commands (e.g., /foo bar)."""
    chat_id = update.effective_chat.id
    await kirim_ke_telegram(chat_id, context, f"*❓ UNKNOWN* Unknown command. Please use `/start` to see available commands.")
    logger.warning(f"[Command] ⚠ Unknown command from {chat_id}: {update.message.text}")

# === Debugging Conversation Handler ===
async def ask_for_debug_response(update: Update, context: CallbackContext):
    """Asks for a Yes/No response from the user for debugging."""
    chat_id = update.effective_chat.id
    user_context = ai_core.get_user_context(chat_id)
    
    if user_context["awaiting_debug_response"]:
        user_response = update.message.text.strip().lower()
        
        response = await ai_core.process_debug_request(chat_id, user_response)

        if response["type"] == "debug_fix_generated":
            await kirim_ke_telegram(chat_id, context, f"*✅ SUCCESS* AI has generated a fix/new code to `{response["filename"]}`.")
            if response["run_suggestion"]:
                await kirim_ke_telegram(chat_id, context, f'*Please review and try running again with:* {response["run_suggestion"]}\n\n*📋 FIX CODE*\n```{response["language"]}\n{response["code"]}\n```')
            else:
                await kirim_ke_telegram(chat_id, context, f'*Please review and try running again. *\n\n*📋 FIX CODE*\n```{response["language"]}\n{response["code"]}\n```')
        elif response["type"] == "error":
            await kirim_ke_telegram(chat_id, context, f"*🔴 DEBUGGING ERROR* {response["message"]}")
        elif response["type"] == "info":
            await kirim_ke_telegram(chat_id, context, f"*💬 INFO* {response["message"]}")
        
        if user_response in ["ya", "yes", "tidak", "no"]:
            user_context["last_error_log"] = None
            user_context["last_command_run"] = None
            user_context["awaiting_debug_response"] = False
            user_context["full_error_output"] = []
            return ConversationHandler.END
        else:
            return DEBUGGING_STATE
    else:
        # If not in debugging state, proceed to regular handle_text_message
        return await handle_text_message(update, context)

# === Function: Send Telegram notification ===
async def kirim_ke_telegram(chat_id: int, context: CallbackContext, pesan_raw: str):
    """
    Sends a message to Telegram. Removes ANSI colors and applies MarkdownV2 escaping
    to the entire message content, specifically handling code blocks by not escaping their internal content.
    """
    if not ai_core.get_telegram_bot_token() or not ai_core.get_telegram_chat_id():
        logger.warning(f"[Telegram] ⚠ Telegram BOT Token or Chat ID not found. Notification not sent.")
        return

    # Remove ANSI color codes first
    pesan_bersih_tanpa_ansi = ai_core.re.sub(r'\033\[[0-9;]*m', '', pesan_raw)
    
    final_message_parts = []
    
    # 1. Separate by multiline code blocks (```)
    multiline_split = ai_core.re.split(r'(```(?:\w+)?\n.*?```)', pesan_bersih_tanpa_ansi, flags=ai_core.re.DOTALL)
    
    for ml_part in multiline_split:
        if ml_part.startswith('```') and ml_part.endswith('```'):
            # This is a multiline code block, add as is (content inside is not escaped)
            final_message_parts.append(ml_part)
        else:
            # This is a text part outside multiline code blocks, now check for inline code blocks (`)
            inline_split = ai_core.re.split(r'(`[^`]+`)', ml_part) # Capture `...`
            for il_part in inline_split:
                if il_part.startswith('`') and il_part.endswith('`'):
                    # This is an inline code block, add as is (content inside is not escaped)
                    final_message_parts.append(il_part)
                else:
                    # This is plain text, apply MarkdownV2 escaping using the new function
                    final_message_parts.append(ai_core._escape_plaintext_markdown_v2(il_part))
            
    pesan_final = "".join(final_message_parts)

    try:
        await context.bot.send_message(chat_id=chat_id, text=pesan_final, parse_mode=ParseMode.MARKDOWN_V2)
        logger.info(f"[Telegram] Notification successfully sent to {chat_id}.")
    except Exception as e:
        logger.error(f"[Telegram] 🔴 Failed to send message to Telegram: {e}")

# === Mode Function: Shell Observation and Error Correction (for Telegram) ===
async def run_shell_observer_telegram(command_to_run: str, update: Update, context: CallbackContext):
    """
    Runs a shell command, monitors output, and sends logs/error suggestions to Telegram.
    Non-interactive.
    """
    chat_id = update.effective_chat.id
    user_context = ai_core.get_user_context(chat_id)
    user_context["last_command_run"] = command_to_run
    user_context["full_error_output"] = []
    
    telegram_log_buffer = [] 
    async def send_telegram_chunk():
        nonlocal telegram_log_buffer
        if telegram_log_buffer:
            escaped_log_content = "\n".join(telegram_log_buffer)
            message = f"```log\n{escaped_log_content}\n```" 
            await kirim_ke_telegram(chat_id, context, message)
            telegram_log_buffer = []

    # Initial message when running the command. Command_to_run is inserted directly into backticks.
    await kirim_ke_telegram(chat_id, context, f"*⚙️ SHELL* Starting command: `{command_to_run}`")
    logger.info(f"[Shell] Running command: `{command_to_run}`")

    user_context["last_error_log"] = None

    # Use ai_core.execute_shell_command to get output
    async for output_line_raw in ai_core.execute_shell_command(command_to_run, chat_id):
        # output_line_raw is like "LOG: content" or "ERROR: content"
        if output_line_raw.startswith("LOG: "):
            cleaned_line = output_line_raw[len("LOG: "):].strip()
            logger.info(f"[Shell Log] {cleaned_line}")
            telegram_log_buffer.append(cleaned_line)
            if len(telegram_log_buffer) >= 10:
                await send_telegram_chunk()
        elif output_line_raw.startswith("ERROR_DETECTED: "):
            error_content = output_line_raw[len("ERROR_DETECTED: "):].strip()
            user_context["last_error_log"] = error_content
            await send_telegram_chunk() # Send any buffered logs before error message
            await kirim_ke_telegram(chat_id, context, f"*❗ ERROR* Error detected in last execution. Do you want to debug this program with AI assistance? (Yes/No)")
            user_context["awaiting_debug_response"] = True
            return DEBUGGING_STATE
        elif output_line_raw.startswith("AI_SUGGESTION: "):
            saran = output_line_raw[len("AI_SUGGESTION: "):].strip()
            saran_lang = ai_core.deteksi_bahasa_pemrograman_dari_konten(saran)
            telegram_msg = f"""*💡 AI SUGGESTION*
```
{saran_lang}
{saran}
```
"""
            await kirim_ke_telegram(chat_id, context, telegram_msg)
        elif output_line_raw.startswith("AI_SUGGESTION_ERROR: "):
            error_msg = output_line_raw[len("AI_SUGGESTION_ERROR: "):].strip()
            await kirim_ke_telegram(chat_id, context, f"*🔴 AI ERROR* Failed to get AI suggestion: {error_msg}")
        elif output_line_raw.startswith("ERROR: "):
            error_msg = output_line_raw[len("ERROR: "):].strip()
            await kirim_ke_telegram(chat_id, context, f"*❗ SHELL ERROR* {error_msg}")
            logger.error(f"[Shell] Error: {error_msg}")
            return ConversationHandler.END # End conversation on critical shell error

    await send_telegram_chunk() # Send any remaining buffered logs
    await kirim_ke_telegram(chat_id, context, f"*⚙️ SHELL* Shell command finished.")
    
    if user_context["last_error_log"]:
        await kirim_ke_telegram(chat_id, context, f"*❗ ERROR* Error detected in last execution. Do you want to debug this program with AI assistance? (Yes/No)")
        user_context["awaiting_debug_response"] = True
        return DEBUGGING_STATE

    return ConversationHandler.END

def main():
    """Main function to start the Telegram bot or web dashboard."""
    # Start the frontend dev server regardless of the mode
    start_frontend_dev_server()

    parser = argparse.ArgumentParser(description="AI Shell & Code Assistant Bot/Web Dashboard")
    parser.add_argument("--web-dashboard", action="store_true", help="Start the web dashboard backend instead of the Telegram bot.")
    args = parser.parse_args()

    try:
        if args.web_dashboard:
            logger.info("Starting AI Web Dashboard Backend...")
            # Ensure the current working directory is added to sys.path for uvicorn to find the app
            sys.path.insert(0, os.path.join(project_root, 'ai_web_dashboard', 'backend'))
            uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[os.path.join(project_root, 'ai_web_dashboard', 'backend')])
        else:
            logger.info(f"Starting Telegram Bot...")
            if not ai_core.get_telegram_bot_token():
                logger.error(f"ERROR: TELEGRAM_BOT_TOKEN is not set. Please set the environment variable or enter it directly.")
                return
            if not ai_core.get_telegram_chat_id():
                logger.error(f"ERROR: TELEGRAM_CHAT_ID is not set. Please set the environment variable or enter it directly.")
                return
            if not ai_core.get_openrouter_api_key():
                logger.error(f"ERROR: OPENROUTER_API_KEY is not set. Please set the environment variable or enter it directly.")
                return

            logger.info(f"Using TOKEN: {'*' * (len(ai_core.get_telegram_bot_token()) - 5) + ai_core.get_telegram_bot_token()[-5:] if len(ai_core.get_telegram_bot_token()) > 5 else ai_core.get_telegram_bot_token()}")
            logger.info(f"Allowed Chat ID: {ai_core.get_telegram_chat_id()}")

            application = Application.builder().token(ai_core.get_telegram_bot_token()).job_queue(JobQueue()).build()

            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("listfiles", handle_listfiles_command))
            application.add_handler(CommandHandler("deletefile", handle_deletefile_command))
            application.add_handler(CommandHandler("clear_chat", handle_clear_chat_command))
            
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

            conv_handler = ConversationHandler(
                entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, ask_for_debug_response)],
                states={
                    DEBUGGING_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_for_debug_response)],
                },
                fallbacks=[CommandHandler('cancel', lambda update, context: ConversationHandler.END)]
            )
            application.add_handler(conv_handler)
            
            application.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))

            # Add error handler
            application.add_error_handler(error_handler)

            logger.info(f"Bot is running. Press Ctrl+C to stop.")
            application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        stop_frontend_dev_server()
        logger.info("Application shut down.")

if __name__ == "__main__":
    main()