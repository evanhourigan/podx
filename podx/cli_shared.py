import json
import sys
from typing import Any

from .logging import get_logger, setup_logging

# Initialize logging when module is imported
setup_logging()
logger = get_logger(__name__)


def read_stdin_json() -> Any:
    """Read and parse JSON from stdin."""
    data = sys.stdin.read()
    if not data.strip():
        logger.warning("No input data received on stdin")
        return None

    try:
        parsed = json.loads(data)
        logger.debug(
            "Successfully parsed JSON from stdin",
            data_keys=list(parsed.keys()) if isinstance(parsed, dict) else "non-dict",
        )
        return parsed
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from stdin", error=str(e))
        raise


def print_json(obj: Any) -> None:
    """Print object as JSON to stdout."""
    try:
        output = json.dumps(obj, ensure_ascii=False, indent=2)
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        logger.debug("JSON output written to stdout", output_size=len(output))
    except Exception as e:
        logger.error("Failed to write JSON output", error=str(e))
        raise
