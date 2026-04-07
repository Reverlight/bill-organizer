import hashlib
import hmac
import logging

from app import settings
from app.db import async_sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def help_function():
    return