"""Configuration loader — reads from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Model settings
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
