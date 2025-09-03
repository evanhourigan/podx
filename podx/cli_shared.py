import json
import sys
from typing import Any


def read_stdin_json() -> Any:
    data = sys.stdin.read()
    if not data.strip():
        return None
    return json.loads(data)


def print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
