import os

def main():
    """
    A quickstart script to help users set up their .env file.
    """
    print("--- NeuroNet AI Cognitive Shell Quickstart Setup ---")
    print("This script will help you create the .env file with the necessary API keys.")
    print("You can get the required values from the services mentioned below.")
    print("-" * 50)

    # Check if .env file already exists
    if os.path.exists(".env"):
        overwrite = input("An .env file already exists. Do you want to overwrite it? (y/n): ").lower()
        if overwrite != 'y':
            print("Setup cancelled. Your existing .env file has been kept.")
            return

    # Get values from user
    telegram_token = input("Enter your TELEGRAM_BOT_TOKEN (from Telegram's BotFather): ")
    telegram_chat_id = input("Enter your TELEGRAM_CHAT_ID (your personal user ID): ")
    openrouter_key = input("Enter your OPENROUTER_API_KEY (from OpenRouter.ai): ")

    # Create the .env content
    env_content = f"""# .env file for NeuroNet AI Cognitive Shell
# This file contains sensitive API keys. Do not share it.

TELEGRAM_BOT_TOKEN="{telegram_token}"
TELEGRAM_CHAT_ID="{telegram_chat_id}"
OPENROUTER_API_KEY="{openrouter_key}"
"""

    # Write to .env file
    try:
        with open(".env", "w") as f:
            f.write(env_content)
        print("\n✅ Successfully created the .env file!")
        print("You can now run the application using: neuronet-ai")
    except IOError as e:
        print(f"\n🔴 Error: Failed to write to .env file: {e}")

if __name__ == "__main__":
    main()
