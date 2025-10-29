import requests
import json
import re
import logging
import time
import asyncio
from .. import config

logger = logging.getLogger(__name__)

def call_llm(messages: list, model: str, max_tokens: int = None, temperature: float = None, extra_headers: dict = None) -> tuple[bool, str]:
    """
    Generic function to send requests to an LLM model.
    """
    if not config.OPENROUTER_API_KEY or not config.LLM_BASE_URL:
        logger.error("[LLM ERROR] API Key or LLM Base URL not set.")
        return False, "API Key or LLM Base URL not set. Please check configuration."

    # Use global defaults if not provided
    actual_max_tokens = max_tokens if max_tokens is not None else config.DEFAULT_MAX_TOKENS
    actual_temperature = temperature if temperature is not None else config.DEFAULT_TEMPERATURE

    payload = {"model": model, "messages": messages, "max_tokens": actual_max_tokens, "temperature": actual_temperature}
    headers = {"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    if extra_headers: headers.update(extra_headers)

    try:
        res = requests.post(config.LLM_BASE_URL, json=payload, headers=headers, timeout=300)
        res.raise_for_status()
        data = res.json()
        if "choices" in data and data["choices"]:
            usage = data.get("usage", {})
            log_token_usage(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), usage.get("total_tokens", 0))
            return True, data["choices"][0]["message"]["content"]
        else:
            logger.error(f"[LLM] Response format error: {data}")
            return False, f"LLM response not in expected format. Debug: {data}"
    except requests.exceptions.RequestException as e:
        logger.error(f"[LLM] API request failed: {e}")
        return False, f"An unexpected error occurred: {e}"

def _sync_stream_llm_lines(messages: list, model: str, max_tokens: int = None, temperature: float = None, extra_headers: dict = None):
    """
    Synchronous helper to stream raw lines from LLM API.
    This function runs in a separate thread.
    """
    if not config.OPENROUTER_API_KEY or not config.LLM_BASE_URL:
        logger.error("[LLM ERROR] API Key or LLM Base URL not set.")
        # Yield bytes as expected by iter_lines consumer
        yield b"data: API Key or LLM Base URL not set. Please check configuration.\n"
        return

    actual_max_tokens = max_tokens if max_tokens is not None else config.DEFAULT_MAX_TOKENS
    actual_temperature = temperature if temperature is not None else config.DEFAULT_TEMPERATURE

    payload = {"model": model, "messages": messages, "max_tokens": actual_max_tokens, "temperature": actual_temperature, "stream": True}
    headers = {"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    if extra_headers: headers.update(extra_headers)

    logger.debug(f"[LLM] Sending streaming request to {config.LLM_BASE_URL} with payload: {payload}")

    try:
        with requests.post(config.LLM_BASE_URL, json=payload, headers=headers, stream=True, timeout=300) as res:
            res.raise_for_status()
            for line in res.iter_lines():
                yield line
    except requests.exceptions.RequestException as e:
        logger.error(f"[LLM] API streaming request failed: {e}")
        yield f"data: Failed to connect to LLM API for streaming: {e}\n".encode()
    except Exception as e:
        logger.error(f"[LLM] Unexpected error during streaming: {e}")
        yield f"data: An unexpected error occurred during streaming: {e}\n".encode()

async def stream_llm(messages: list, model: str, max_tokens: int = None, temperature: float = None, extra_headers: dict = None):
    """
    Streams responses from an LLM model.
    This is an async generator that uses _sync_stream_llm_lines in a thread.
    """
    # The initial checks are already done in _sync_stream_llm_lines, but keeping for clarity
    if not config.OPENROUTER_API_KEY or not config.LLM_BASE_URL:
        logger.error("[LLM ERROR] API Key or LLM Base URL not set.")
        yield "API Key or LLM Base URL not set. Please check configuration."
        return

    try:
        # Get the synchronous generator object by awaiting asyncio.to_thread
        sync_generator = await asyncio.to_thread(_sync_stream_llm_lines, messages, model, max_tokens, temperature, extra_headers)

        while True:
            try:
                # Get the next line from the synchronous generator, running next() in a thread
                line = await asyncio.to_thread(next, sync_generator)
                logger.debug(f"[LLM] Raw stream line: {line}")
                if line:
                    # OpenRouter sends data in the format: data: {json_payload}
                    # And a [DONE] message at the end
                    if line.startswith(b"data:"):
                        json_str = line.decode('utf-8')[len("data:"):]
                        if json_str.strip() == "[DONE]":
                            logger.info("[LLM] Stream finished with [DONE] signal.")
                            break
                        try:
                            json_data = json.loads(json_str)
                            logger.debug(f"[LLM] Parsed JSON data: {json_data}")
                            if "choices" in json_data and json_data["choices"]:
                                delta = json_data["choices"][0]["delta"]
                                if "content" in delta:
                                    yield delta["content"]
                                else:
                                    logger.warning(f"[LLM] 'content' key missing in delta: {delta}")
                            else:
                                logger.warning(f"[LLM] 'choices' key missing or empty in JSON data: {json_data}")
                        except json.JSONDecodeError:
                            logger.warning(f"[LLM] Could not decode JSON from stream: {json_str}")
                            continue
                    else:
                        # Handle non-data lines, e.g., comments or empty lines
                        logger.debug(f"[LLM] Non-data line received: {line.decode('utf-8')}")
            except StopIteration:
                # The synchronous generator has finished
                break
            except Exception as e:
                logger.error(f"[LLM] Error getting next line from synchronous generator: {e}")
                yield f"An error occurred during streaming: {e}"
                break
    except requests.exceptions.RequestException as e:
        logger.error(f"[LLM] API streaming request failed: {e}")
        yield f"Failed to connect to LLM API for streaming: {e}"
    except Exception as e:
        logger.error(f"[LLM] Unexpected error during streaming: {e}")
        yield f"An unexpected error occurred during streaming: {e}"

def ekstrak_kode_dari_llm(text_response: str, target_language: str = None) -> tuple[str, str]:
    """
    Extracts Markdown code blocks from LLM responses.
    """
    code_block_pattern = r"```(?P<lang>\w+)?\n(?P<content>.*?)```"
    matches = re.findall(code_block_pattern, text_response, re.DOTALL)

    if matches:
        # Prefer the target language if specified
        if target_language:
            for lang, content in matches:
                if lang and lang.lower() == target_language.lower():
                    return content.strip(), lang.lower()
        # Otherwise, take the first valid language block
        for lang, content in matches:
            if lang:
                return content.strip(), lang.lower()
        # Fallback to the first block if no language is specified
        return matches[0][1].strip(), "unknown"

    return text_response.strip(), "unknown"

def log_token_usage(model: str, prompt: int, completion: int, total: int):
    try:
        from .file_utils import get_token_usage_data, save_token_usage_data
        usage_data = get_token_usage_data()
        usage_data.append({"timestamp": time.time(), "model": model, "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total})
        save_token_usage_data(usage_data)
    except Exception as e:
        logger.error(f"[Core] Failed to log token usage: {e}")