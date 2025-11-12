from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel


class SettingsConfigDict(dict):
    def __init__(
        self,
        *,
        env_file: str | None = None,
        env_file_encoding: str = "utf-8",
        env_prefix: str = "",
        case_sensitive: bool = False,
        extra: str = "ignore",
    ) -> None:
        super().__init__(
            env_file=env_file,
            env_file_encoding=env_file_encoding,
            env_prefix=env_prefix,
            case_sensitive=case_sensitive,
            extra=extra,
        )

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - debug helper
            raise AttributeError(item) from exc


def _parse_env_file(path: Path, encoding: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    content = path.read_text(encoding=encoding)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


class BaseSettings(BaseModel):
    model_config: SettingsConfigDict = SettingsConfigDict()

    def __init__(self, **values: Any) -> None:
        raw_config = getattr(self.__class__, "model_config", SettingsConfigDict())
        if isinstance(raw_config, dict):
            config = dict(raw_config)
        else:
            config = dict(raw_config.__dict__)
        env_data: Dict[str, str] = {}
        env_file = config.get("env_file")
        if env_file:
            env_data.update(_parse_env_file(Path(env_file), config.get("env_file_encoding", "utf-8")))
        env_data.update(os.environ)

        resolved: Dict[str, Any] = {}
        prefix = config.get("env_prefix", "") or ""
        case_sensitive = config.get("case_sensitive", False)
        for field_name in self.model_fields:
            env_key = prefix + (field_name if case_sensitive else field_name.upper())
            for candidate in (env_key, env_key.upper(), env_key.lower()):
                if candidate in env_data:
                    resolved[field_name] = env_data[candidate]
                    break
        resolved.update(values)
        super().__init__(**resolved)
