def _update_env_file(updates: dict):
    """
    A utility function to update the .env file.
    """
    env_path = os.path.join(os.getcwd(), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except IOError as e:
            logger.error(f"Error reading .env file: {e}")
            # Decide if you want to return or continue with an empty dict
            return False, f"Error reading .env file: {e}"

    
    for key, value in updates.items():
        env_vars[key] = value

    try:
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f'{key}="{value}"\n') # Enclose values in quotes
        
        load_dotenv(override=True) # Reload environment variables
        return True, "Configuration updated successfully."
    except IOError as e:
        logger.error(f"Error writing to .env file: {e}")
        return False, f"Error writing to .env file: {e}"
