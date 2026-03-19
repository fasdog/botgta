from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from .models import DEFAULT_STATE


class StateStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict[str, dict[str, Any]]:
        if not os.path.exists(self.path):
            self.save(deepcopy(DEFAULT_STATE))
            return deepcopy(DEFAULT_STATE)

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self.save(deepcopy(DEFAULT_STATE))
            return deepcopy(DEFAULT_STATE)

        merged = deepcopy(DEFAULT_STATE)
        for key, value in data.items():
            if key in merged and isinstance(value, dict):
                merged[key].update(value)
        return merged

    def save(self, state: dict[str, dict[str, Any]]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
