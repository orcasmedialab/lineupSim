# src/utils.py

import logging
import sys

# Keep level at WARNING by default to reduce console noise
# main.py can adjust if needed via --debug or --show-game-logs
def setup_logging(level=logging.WARNING):
    """Configures basic logging to stderr."""
    logging.basicConfig(level=level,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                        # format='%(asctime)s - %(levelname)-8s - %(name)-15s - %(message)s', # Alternative more aligned format
                        stream=sys.stderr) # Changed stream to stderr
