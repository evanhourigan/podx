from pathlib import Path

from podx.io import read_json, write_json


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "x.json"
    obj = {"a": 1, "b": "ok"}
    write_json(p, obj)
    assert read_json(p) == obj
