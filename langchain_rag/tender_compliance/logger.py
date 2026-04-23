"""
标书审核日志配置工具

提供统一的日志配置,支持控制台输出和文件输出
"""

import logging
import sys
from pathlib import Path
from typing import Optional


class UTF8StreamHandler(logging.StreamHandler):
    """处理UTF-8编码的流处理器,解决Windows控制台编码问题"""
    def __init__(self, stream=None):
        super().__init__(stream)
        # 确保输出使用UTF-8编码
        if hasattr(self.stream, 'buffer'):
            import io
            self.stream = io.TextIOWrapper(
                self.stream.buffer,
                encoding='utf-8',
                errors='backslashreplace',
                line_buffering=True
            )


def setup_logger(
    name: str = "tender_compliance",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    """
    配置标书审核日志器

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        console_output: 是否输出到控制台

    Returns:
        配置好的Logger对象
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台输出
    if console_output:
        console_handler = UTF8StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_stage_start(logger: logging.Logger, stage_name: str, stage_num: int):
    """
    记录Stage开始

    Args:
        logger: 日志器
        stage_name: Stage名称
        stage_num: Stage编号
    """
    logger.info(f"{'='*60}")
    logger.info(f"[Stage {stage_num}] {stage_name} - 开始")
    logger.info(f"{'='*60}")


def log_stage_complete(logger: logging.Logger, stage_name: str, stage_num: int, duration: float):
    """
    记录Stage完成

    Args:
        logger: 日志器
        stage_name: Stage名称
        stage_num: Stage编号
        duration: 耗时（秒）
    """
    logger.info(f"[Stage {stage_num}] {stage_name} - 完成")
    logger.info(f"  耗时: {duration:.2f}秒")
    logger.info("")


def log_progress(logger: logging.Logger, current: int, total: int, prefix: str = ""):
    """
    记录进度

    Args:
        logger: 日志器
        current: 当前进度
        total: 总数
        prefix: 前缀描述
    """
    if total > 0:
        percentage = (current / total) * 100
        logger.debug(f"{prefix}进度: {current}/{total} ({percentage:.1f}%)")
    else:
        logger.debug(f"{prefix}进度: {current}")
