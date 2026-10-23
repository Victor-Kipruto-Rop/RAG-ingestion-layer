"""Non-destructive worker preflight: validate DB and private object-store access only."""
import logging
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .storage import health_check

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("registry.preflight")


def main() -> int:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        log.info("Database connectivity: OK")
    except SQLAlchemyError:
        log.error("Database connectivity: FAILED (details intentionally redacted)")
        return 1

    try:
        health_check()
        log.info("Private object storage connectivity: OK")
    except Exception:
        log.error("Private object storage connectivity: FAILED (details intentionally redacted)")
        return 1

    log.info("Preflight passed. No ingestion jobs were claimed or changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
