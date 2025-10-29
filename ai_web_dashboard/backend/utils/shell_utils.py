import asyncio
import logging
import re
from .. import config

logger = logging.getLogger(__name__)

BLACKLISTED_COMMANDS = ["rm -rf /", "mkfs"]

def is_safe_command(command: str) -> bool:
    """
    Checks if a command is safe to execute.
    """
    # Prevent potentially dangerous commands
    for blacklisted in BLACKLISTED_COMMANDS:
        if blacklisted in command:
            return False

    # Add more safety checks here, e.g., for dangerous characters or patterns
    if re.search(r'[;&|`]', command):
        # This is a simple check. A more robust solution might be needed.
        # For now, we allow these characters but will log a warning.
        logger.warning(f"[Shell Util] Executing command with potentially dangerous characters: {command}")

    return True

async def execute_command_sync(command: str, timeout: int = 300) -> dict:
    """
    Executes a shell command synchronously and returns all its output at once.
    """
    if not is_safe_command(command):
        logger.error(f"[Shell Util] Unsafe command blocked: {command}")
        return {"stdout": "", "stderr": f"Unsafe command blocked: {command}", "exit_code": -1}

    logger.info(f"[Shell Util] Executing command synchronously: {command}")
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.PROJECT_ROOT
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        logger.info(f"[Shell Util] Command '{command}' finished with exit code {process.returncode}")
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "exit_code": process.returncode
        }
    except asyncio.TimeoutError:
        logger.warning(f"[Shell Util] Command '{command}' timed out after {timeout} seconds.")
        if process.returncode is None:
            process.kill()
            await process.wait()
        return {"stdout": "", "stderr": f"Command timed out after {timeout} seconds.", "exit_code": -1}
    except Exception as e:
        logger.error(f"[Shell Util] Error executing sync command '{command}': {e}")
        return {"stdout": "", "stderr": f"An unexpected error occurred: {e}", "exit_code": -1}

async def execute_and_stream_command(command: str, timeout: int = 300):
    """
    Executes a shell command and streams its stdout and stderr using asyncio.Queue.
    Yields chunks of output as they become available.
    """
    if not is_safe_command(command):
        logger.error(f"[Shell Util] Unsafe command blocked: {command}")
        yield {"type": "shell_error", "content": f"Unsafe command blocked: {command}"}
        return

    logger.info(f"[Shell Util] Executing command: {command}")
    process = None
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.PROJECT_ROOT
        )

        stdout_queue = asyncio.Queue()
        stderr_queue = asyncio.Queue()

        async def enqueue_stream(stream, queue, stream_type):
            while True:
                line = await stream.readline()
                if not line:
                    logger.debug(f"[Shell Util] {stream_type} stream for command '{command}' ended.")
                    break
                await queue.put({"type": stream_type, "content": line.decode().strip()})
            await queue.put(None) # Sentinel to signal end of stream

        stdout_producer_task = asyncio.create_task(enqueue_stream(process.stdout, stdout_queue, "shell_output"))
        stderr_producer_task = asyncio.create_task(enqueue_stream(process.stderr, stderr_queue, "shell_error"))
        process_wait_task = asyncio.create_task(process.wait())

        active_tasks = {stdout_producer_task, stderr_producer_task, process_wait_task}

        while active_tasks:
            logger.debug(f"[Shell Util] Active tasks: {[t.get_name() for t in active_tasks if not t.done()]}")
            # Create tasks for queue.get() only if producers are still active
            current_get_tasks = set()
            if not stdout_producer_task.done():
                current_get_tasks.add(asyncio.create_task(stdout_queue.get(), name="stdout_get"))
            if not stderr_producer_task.done():
                current_get_tasks.add(asyncio.create_task(stderr_queue.get(), name="stderr_get"))
            
            logger.debug(f"[Shell Util] Current get tasks: {[t.get_name() for t in current_get_tasks if not t.done()]}")
            
            # Combine all tasks to wait on
            tasks_to_wait = active_tasks.union(current_get_tasks)

            if not tasks_to_wait:
                break # No more active tasks or items to get

            try:
                done, pending = await asyncio.wait(
                    tasks_to_wait,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"[Shell Util] Command output stream timed out after {timeout} seconds. Terminating process.")
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                yield {"type": "shell_error", "content": f"Command output stream timed out after {timeout} seconds and was terminated."}
                break # Exit if timed out

            for task in done:
                if task in active_tasks:
                    active_tasks.remove(task)

                if task is process_wait_task:
                    # Process finished, cancel producers and drain queues
                    stdout_producer_task.cancel()
                    stderr_producer_task.cancel()
                    # Ensure producers are removed from active_tasks if they were there
                    active_tasks.discard(stdout_producer_task)
                    active_tasks.discard(stderr_producer_task)
                    # Drain remaining items from queues
                    while not stdout_queue.empty():
                        yield await stdout_queue.get()
                    while not stderr_queue.empty():
                        yield await stderr_queue.get()
                    break # Exit main loop
                elif task in current_get_tasks: # It's a queue.get() task
                    item = task.result()
                    if item is None: # Sentinel
                        pass # Stream ended, producer task will be done soon
                    else:
                        yield item

            # Cancel any pending get tasks if the loop is breaking or producers are done
            for task in pending:
                if task in current_get_tasks:
                    task.cancel()

            if process.returncode is not None: # Process has finished
                break # Exit main loop

        # Ensure all tasks are cancelled if still running
        for task in active_tasks:
            task.cancel()
        try:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        await process.wait() # Ensure process has truly finished
        yield {"type": "shell_exit_code", "content": process.returncode}

    except Exception as e:
        logger.error(f"[Shell Util] Error executing command '{command}': {e}")
        yield {"type": "shell_error", "content": f"Error executing command: {e}"}
    finally:
        if process and process.returncode is None:
            process.kill() # Ensure process is terminated if still running
            await process.wait()
        logger.info(f"[Shell Util] Command execution finished: {command}")
