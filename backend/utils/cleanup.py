import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

def cleanup_files(*paths: Union[str, Path]):
    """Clean up temporary files."""
    for p in paths:
        try:
            path = Path(p)
            if path.exists():
                path.unlink()
                logger.debug(f"Cleaned up file: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {p}: {e}")