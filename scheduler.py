"""
Scheduler de produção para executar a automação diariamente via APScheduler.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from automacao.logging_config import setup_logging
from main import main


setup_logging()
logger = logging.getLogger(__name__)


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        logger.warning("valor_invalido_env nome=%s valor=%s usando_padrao=%s", name, raw, default)
        return default


def executar_ciclo() -> None:
    inicio = datetime.now()
    logger.info("job_iniciado timestamp=%s", inicio.isoformat())
    try:
        main(acao="download", headless=True)
        logger.info("job_concluido_com_sucesso")
    except Exception as exc:
        logger.exception("job_falhou detalhe=%s", exc)
        raise


def run_scheduler() -> None:
    timezone = os.getenv("TZ", "America/Bahia").strip()
    hour = _parse_int_env("SCHEDULE_HOUR", 8)
    minute = _parse_int_env("SCHEDULE_MINUTE", 0)

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        executar_ciclo,
        CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="logtudo_download_diario",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
        replace_existing=True,
    )

    logger.info(
        "scheduler_iniciado trigger=cron timezone=%s hour=%s minute=%s",
        timezone,
        hour,
        minute,
    )
    scheduler.start()


if __name__ == "__main__":
    run_scheduler()

