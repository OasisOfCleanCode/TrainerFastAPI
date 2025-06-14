# deploy/update_version.py

import sys
import os

from app.utils.logger import logger

new_version = sys.argv[1]

version_file = os.path.join(os.path.dirname(__file__), "version.txt")
with open(version_file, "w") as file:
    file.write(new_version)

logger.info(f"Version updated to: {new_version}")


