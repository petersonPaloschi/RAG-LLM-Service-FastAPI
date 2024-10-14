# main.py

import logging
import os

import uvicorn

from api.server import app
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 1))
    log_level = "debug" if config.DEBUG else "info"

    logger.info(
        "Iniciando o servidor na porta %d com %d worker(s)", port, workers
    )

    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=config.DEBUG,
        log_level=log_level,
        workers=workers,
    )

    logger.info("Servidor parado.")
