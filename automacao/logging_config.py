"""
Configuração central de logging para execução em produção.
"""

from __future__ import annotations

import logging
import os
import sys


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "event=%(message)s | module=%(module)s | func=%(funcName)s"
)


def setup_logging() -> None:
    """
    Configura logging global da aplicação.
    Nível padrão: INFO (ajustável por LOG_LEVEL).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(os.getenv("LOG_DIR", "/app/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        handlers=handlers,
        force=True,
    )

