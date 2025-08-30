import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self):
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
        logger.info("Audio Service initialized")
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        return shutil.which("ffmpeg") is not None
    
    def convert_to_wav(self, input_path: Path, output_path: Path):
        """Convert audio file to WAV format."""
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", "16000", "-ac", "1", str(output_path)
        ]
        
        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"Audio converted successfully: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg conversion failed: {e}")
            raise
