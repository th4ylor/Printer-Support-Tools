import logging
from logging.handlers import RotatingFileHandler
from .config import CONFIG

def build_logger(name = "Printer_sipport"):
    CONFIG.log_dir.mkdir(parents = True, exist_ok = True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(threadName)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        CONFIG.log_dir / "Arquivo_Logs.log",
        maxBytes = 2 * 1024 * 1024,
        backupCount = 5,
        encoding = "utf-8" ,
    )
    file_handler.setFormatter(formato)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formato)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger