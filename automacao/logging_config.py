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

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )

