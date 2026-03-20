import logging
import os

_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs.txt")

logger = logging.getLogger("vcm")
logger.setLevel(logging.DEBUG)

_handler = logging.FileHandler(_log_path, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_handler)
