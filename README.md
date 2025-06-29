# NeuroNet AI Cognitive Shell

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An AI-powered assistant for shell commands and code generation, accessible via Telegram and a web dashboard. This tool translates natural language into executable shell commands and helps generate or debug code in various programming languages.

## Features

- **Natural Language to Shell:** Convert plain English instructions into precise shell commands.
- **Code Generation & Debugging:** Ask the AI to write new functions, programs, or help fix errors in your existing code.
- **Multi-Platform:** Interact via a Telegram Bot or a local web dashboard.
- **System-Aware:** Automatically detects your OS and default shell for tailored commands.
- **Easy Installation:** Packaged for easy distribution and installation via PyPI.

## Installation

You can install the NeuroNet AI Cognitive Shell directly from PyPI using pip.

```bash
pip install neuronet-ai-cognitiveshell
```

Before running, you need to set up your environment variables. Create a `.env` file in your home directory with the following content:

```
# Get from BotFather on Telegram
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

# Your personal Telegram user ID
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"

# Your API key from OpenRouter.ai or other compatible services
OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
```

## Usage

Once installed, you can run the assistant from your terminal.

### Start the Telegram Bot

To start the bot and the web frontend server, simply run:

```bash
neuronet-ai
```

This will:
1.  Start the React development server for the web dashboard in the background.
2.  Start the Telegram bot to listen for your commands.

### Start the Web Dashboard Backend

To run the backend API server for the web dashboard (for development or standalone use), use the `--web-dashboard` flag:

```bash
neuronet-ai --web-dashboard
```

This will start a Uvicorn server, typically on `http://localhost:8000`.

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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.