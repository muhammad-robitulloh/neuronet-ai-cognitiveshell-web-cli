
import logging
import sys
import argparse
import uvicorn
import subprocess
import atexit
import os
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from ai_web_dashboard.backend.ai_core import ai_core_instance

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Frontend Process Management ---

# --- Telegram Bot Function ---






def build_frontend_for_production():
    frontend_dir = os.path.join(project_root, 'ai_web_dashboard', 'frontend')
    if not os.path.isdir(frontend_dir):
        logger.error(f"[Frontend] Directory not found: {frontend_dir}")
        return False

    logger.info(f"[Frontend] Building frontend for production in {frontend_dir}...")
    try:
        result = subprocess.run(
            ['npm', 'run', 'build'],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"[Frontend] Build successful:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[Frontend] Build failed:\n{e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"[Frontend] Failed to run npm build: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="AI Cognitive Shell")
    parser.add_argument("--web", action="store_true", help="Run the web dashboard backend with Starlette.")
    parser.add_argument("--build-frontend", action="store_true", help="Build the frontend for production.")
    parser.add_argument("--telegram", action="store_true", help="Run the Telegram bot.")
    args = parser.parse_args()

    if args.build_frontend:
        logger.info("Building frontend for production...")
        if not build_frontend_for_production():
            sys.exit(1)
        logger.info("Frontend build process completed.")
    elif args.web:
        logger.info("Starting Starlette Web Dashboard Backend...")
        
        # Point uvicorn to the 'app' instance in the new main.py
        uvicorn.run("ai_web_dashboard.backend.main:app", host="0.0.0.0", port=8002, reload=False) # Changed port to 8002
    
    else:
        parser.print_help()
        sys.exit(1)
    

if __name__ == "__main__":
    main()

