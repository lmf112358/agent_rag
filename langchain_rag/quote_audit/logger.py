"""
报价审核日志工具

处理Windows控制台UTF-8编码问题
"""

import sys
import io
import logging
from typing import Optional


class UTF8StreamHandler(logging.StreamHandler):
    """处理UTF-8编码的流处理器，解决Windows控制台编码问题"""

    def __init__(self, stream=None):
        super().__init__(stream)
        if hasattr(self.stream, 'buffer'):
            self.stream = io.TextIOWrapper(
                self.stream.buffer,
                encoding='utf-8',
                errors='backslashreplace',
                line_buffering=True,
            )


def setup_logger(
    name: str = "quote_audit",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    """配置报价审核日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    if console_output:
        console_handler = UTF8StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
