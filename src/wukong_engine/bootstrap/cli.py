import logging

# from wukong_engine.infrastructure.adapters.filesystem.file_loader import file_loader
from wukong_engine.infrastructure.adapters.llm.openai_client import process_prompt
from wukong_engine.infrastructure.config import config
from wukong_engine.infrastructure.logging.logger import setup_logging


def create_cli_app() -> object:
    setup_logging(level=logging.INFO)
    return None
