# NeuroNet AI Cognitive Shell

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An AI-powered assistant for shell commands and code generation, accessible via Telegram and a web dashboard. This tool translates natural language into executable shell commands and helps generate or debug code in various programming languages.

## Features

- **Natural Language to Shell:** Convert plain English instructions into precise shell commands.
- **Code Generation & Debugging:** Ask the AI to write new functions, programs, or help fix errors in your existing code.
- **File Attachment & Analysis:** Attach files to chat messages for AI analysis. Supports text-based files (code, logs, configs) for deeper insights. Files are stored in `files_storage` and are accessible by the AI and shell execution model.
- **Multi-Platform (Web & Telegram):** Interact via a local web dashboard or a configurable Telegram Bot. The Telegram bot can now be enabled and configured directly from the web dashboard settings.
- **System-Aware:** Automatically detects your OS and default shell for tailored commands.
- **Easy Installation:** Packaged for easy distribution and installation via PyPI.

## Installation

You can install the NeuroNet AI Cognitive Shell directly from PyPI using pip.

```bash
pip install neuronet-ai-cognitiveshell
```

Before running, you need to set up your environment variables. Create a `.env` file in your home directory with the following content:

```
# Your API key from OpenRouter.ai or other compatible services
OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"

# Optional: Set these if you want to enable Telegram bot from .env
# Otherwise, configure via web dashboard settings
# TELEGRAM_ENABLED="true"
# TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
# TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"
```

## Usage

Once installed, you can run the assistant from your terminal.

### Start the Web Dashboard Backend

To run the backend API server for the web dashboard, use the `--web` flag:

```bash
python cognitiveshell/cognitiveshell.py --web
```

This will start a Uvicorn server, typically on `http://localhost:8001`. The backend now manages the Telegram bot's lifecycle based on settings.

### Build the Frontend for Production

If you need to build the frontend for production (e.g., for deployment), use the `--build-frontend` flag:

```bash
python cognitiveshell/cognitiveshell.py --build-frontend
```

## Development

To contribute to the project, clone the repository and install the dependencies.

```bash
git clone https://github.com/muhammad-robitulloh/neuronet-ai-cognitiveshell-web-cli.git
cd neuronet-ai-cognitiveshell-web-cli

# Install Python dependencies
pip install -e .

# Install frontend dependencies
cd ai_web_dashboard/frontend
npm install
```

## Verification

After refactoring, you can verify the application's functionality:

1.  **Build the Frontend (if not already built):**
    ```bash
    python cognitiveshell/cognitiveshell.py --build-frontend
    ```
2.  **Start the Backend:**
    ```bash
    python cognitiveshell/cognitiveshell.py --web
    ```
3.  **Access the Web Dashboard:** Open your web browser and navigate to `http://localhost:3000` (or the port indicated by the React development server).
4.  **Test Features:**
    *   **Terminal:** Try running some shell commands (e.g., `ls -la`, `pwd`).
    *   **Chat:** Interact with the AI, ask it to generate code, or convert natural language to shell commands.
    *   **File Attachment:** Test attaching a text file to a chat message and ask the AI to analyze its content.
    *   **History:** Check if chat and shell history are being recorded.
    *   **Analytics:** See if token usage data is displayed.
    *   **Settings:**
        *   Verify that you can update API keys and other LLM configurations.
        *   **Telegram Bot Settings:** Enable the Telegram bot, enter your token and optional chat ID, save settings, and verify the bot starts/stops correctly. Test sending messages to the bot and receiving AI responses.
    *   **File Manager:** Check if generated files and uploaded files are listed and can be viewed/deleted.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.