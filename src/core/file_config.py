"""
文件配置读取（不依赖环境变量）。

说明：
- 本项目标准配置文件为仓库根目录的 `.env`（由 src/main.py 显式 load_dotenv）。
- 这里提供“直接读取 .env 文件”的能力：不写入 os.environ，避免环境变量配置方式。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


def _default_dotenv_path() -> Path:
    # src/core/file_config.py -> parents[0]=core, [1]=src, [2]=repo root
    return Path(__file__).resolve().parents[2] / ".env"


@lru_cache()
def _dotenv_map() -> dict[str, str]:
    path = _default_dotenv_path()
    values = dotenv_values(path) if path.exists() else {}
    return {k: v for k, v in values.items() if k and v is not None}


def get_str(key: str, default: Optional[str] = None) -> Optional[str]:
    return _dotenv_map().get(key, default)


def get_int(key: str, default: int) -> int:
    raw = _dotenv_map().get(key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default

