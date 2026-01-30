"""
Audio sample management for PersonaPlex benchmarks.

Downloads and manages test audio files from the official PersonaPlex repository.
"""
import os
import wave
import struct
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# PersonaPlex test audio files from official repository
PERSONAPLEX_TEST_FILES = {
    "input_assistant": {
        "url": "https://raw.githubusercontent.com/NVIDIA/personaplex/main/assets/test/input_assistant.wav",
        "description": "Assistant voice test input",
    },
    "input_service": {
        "url": "https://raw.githubusercontent.com/NVIDIA/personaplex/main/assets/test/input_service.wav",
        "description": "Service scenario test input",
    },
}

PERSONAPLEX_TEST_PROMPTS = {
    "prompt_service": {
        "url": "https://raw.githubusercontent.com/NVIDIA/personaplex/main/assets/test/prompt_service.txt",
        "description": "SwiftPlex Appliances service agent prompt",
    },
}

# PersonaPlex native audio format
TARGET_SAMPLE_RATE = 24000  # 24kHz
TARGET_CHANNELS = 1  # Mono
TARGET_SAMPLE_WIDTH = 2  # 16-bit


@dataclass
class AudioSample:
    """Loaded audio sample with metadata."""
    name: str
    data: bytes  # Raw PCM data
    sample_rate: int
    channels: int
    sample_width: int
    duration_seconds: float
    source_path: Optional[str] = None

    @property
    def num_samples(self) -> int:
        return len(self.data) // (self.sample_width * self.channels)


class SampleManager:
    """
    Manages audio samples for benchmarking.

    Downloads test files from PersonaPlex repository and converts
    them to the required format (24kHz, 16-bit, mono PCM).
    """

    def __init__(self, cache_dir: str = None):
        """
        Initialize sample manager.

        Args:
            cache_dir: Directory to cache downloaded files.
                       Defaults to benchmark/audio/samples/
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "samples"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._samples: dict[str, AudioSample] = {}
        self._prompts: dict[str, str] = {}

    def download_file(self, url: str, filename: str) -> Path:
        """Download a file from URL to cache directory."""
        import urllib.request

        filepath = self.cache_dir / filename
        if filepath.exists():
            logger.debug(f"Using cached file: {filepath}")
            return filepath

        logger.info(f"Downloading: {url}")
        try:
            urllib.request.urlretrieve(url, filepath)
            logger.info(f"Downloaded to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            raise

    def download_all_test_files(self) -> bool:
        """Download all PersonaPlex test files."""
        success = True

        # Download audio files
        for name, info in PERSONAPLEX_TEST_FILES.items():
            try:
                filename = f"{name}.wav"
                self.download_file(info["url"], filename)
            except Exception as e:
                logger.error(f"Failed to download {name}: {e}")
                success = False

        # Download prompt files
        for name, info in PERSONAPLEX_TEST_PROMPTS.items():
            try:
                filename = f"{name}.txt"
                self.download_file(info["url"], filename)
            except Exception as e:
                logger.error(f"Failed to download {name}: {e}")
                success = False

        return success

    def load_wav_file(self, filepath: str) -> AudioSample:
        """
        Load a WAV file and convert to PersonaPlex format.

        Args:
            filepath: Path to WAV file

        Returns:
            AudioSample with converted PCM data
        """
        filepath = Path(filepath)

        with wave.open(str(filepath), 'rb') as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            n_frames = wav.getnframes()
            raw_data = wav.readframes(n_frames)

        duration = n_frames / sample_rate

        logger.debug(
            f"Loaded {filepath.name}: {sample_rate}Hz, "
            f"{channels}ch, {sample_width * 8}bit, {duration:.2f}s"
        )

        # Convert to target format if needed
        pcm_data = self._convert_audio(
            raw_data,
            sample_rate, channels, sample_width,
            TARGET_SAMPLE_RATE, TARGET_CHANNELS, TARGET_SAMPLE_WIDTH
        )

        return AudioSample(
            name=filepath.stem,
            data=pcm_data,
            sample_rate=TARGET_SAMPLE_RATE,
            channels=TARGET_CHANNELS,
            sample_width=TARGET_SAMPLE_WIDTH,
            duration_seconds=len(pcm_data) / (TARGET_SAMPLE_RATE * TARGET_SAMPLE_WIDTH * TARGET_CHANNELS),
            source_path=str(filepath)
        )

    def _convert_audio(
        self,
        data: bytes,
        src_rate: int, src_channels: int, src_width: int,
        dst_rate: int, dst_channels: int, dst_width: int
    ) -> bytes:
        """
        Convert audio data to target format.

        Handles sample rate conversion, channel mixing, and bit depth.
        """
        import numpy as np

        # Determine source format
        if src_width == 1:
            dtype = np.uint8
            max_val = 128
            offset = 128
        elif src_width == 2:
            dtype = np.int16
            max_val = 32768
            offset = 0
        elif src_width == 4:
            dtype = np.int32
            max_val = 2147483648
            offset = 0
        else:
            raise ValueError(f"Unsupported sample width: {src_width}")

        # Convert to numpy array
        samples = np.frombuffer(data, dtype=dtype)

        # Convert to float for processing
        if src_width == 1:
            samples = (samples.astype(np.float32) - offset) / max_val
        else:
            samples = samples.astype(np.float32) / max_val

        # Reshape for channels
        if src_channels > 1:
            samples = samples.reshape(-1, src_channels)

        # Convert to mono if needed
        if src_channels > 1 and dst_channels == 1:
            samples = samples.mean(axis=1)
        elif src_channels == 1 and dst_channels > 1:
            samples = np.tile(samples.reshape(-1, 1), (1, dst_channels))

        # Ensure 1D for mono
        if dst_channels == 1:
            samples = samples.flatten()

        # Resample if needed
        if src_rate != dst_rate:
            samples = self._resample(samples, src_rate, dst_rate)

        # Convert to target bit depth
        if dst_width == 2:
            samples = (samples * 32767).clip(-32768, 32767).astype(np.int16)
        elif dst_width == 1:
            samples = ((samples * 128) + 128).clip(0, 255).astype(np.uint8)

        return samples.tobytes()

    def _resample(self, samples: 'np.ndarray', src_rate: int, dst_rate: int) -> 'np.ndarray':
        """Simple linear interpolation resampling."""
        import numpy as np

        if src_rate == dst_rate:
            return samples

        # Calculate new length
        duration = len(samples) / src_rate
        new_length = int(duration * dst_rate)

        # Linear interpolation
        old_indices = np.linspace(0, len(samples) - 1, new_length)
        new_samples = np.interp(old_indices, np.arange(len(samples)), samples)

        return new_samples.astype(samples.dtype)

    def load_personaplex_samples(self) -> dict[str, AudioSample]:
        """
        Load all PersonaPlex test samples.

        Downloads files if not cached, then loads and converts them.

        Returns:
            Dictionary of sample name -> AudioSample
        """
        # Ensure files are downloaded
        self.download_all_test_files()

        # Load each audio file
        for name in PERSONAPLEX_TEST_FILES:
            filepath = self.cache_dir / f"{name}.wav"
            if filepath.exists():
                try:
                    self._samples[name] = self.load_wav_file(filepath)
                except Exception as e:
                    logger.error(f"Failed to load {name}: {e}")

        return self._samples

    def load_personaplex_prompts(self) -> dict[str, str]:
        """Load PersonaPlex test prompts."""
        self.download_all_test_files()

        for name in PERSONAPLEX_TEST_PROMPTS:
            filepath = self.cache_dir / f"{name}.txt"
            if filepath.exists():
                self._prompts[name] = filepath.read_text()

        return self._prompts

    def get_sample(self, name: str) -> Optional[AudioSample]:
        """Get a loaded sample by name."""
        if not self._samples:
            self.load_personaplex_samples()
        return self._samples.get(name)

    def get_prompt(self, name: str) -> Optional[str]:
        """Get a loaded prompt by name."""
        if not self._prompts:
            self.load_personaplex_prompts()
        return self._prompts.get(name)

    def get_all_samples(self) -> List[AudioSample]:
        """Get all loaded samples."""
        if not self._samples:
            self.load_personaplex_samples()
        return list(self._samples.values())

    def list_available_samples(self) -> List[str]:
        """List names of available samples."""
        return list(PERSONAPLEX_TEST_FILES.keys())

    def add_custom_sample(self, name: str, filepath: str) -> AudioSample:
        """
        Add a custom audio file to the sample set.

        Args:
            name: Name to identify this sample
            filepath: Path to WAV file

        Returns:
            Loaded AudioSample
        """
        sample = self.load_wav_file(filepath)
        sample.name = name
        self._samples[name] = sample
        return sample

    def clear_cache(self):
        """Remove all cached files."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._samples.clear()
        self._prompts.clear()


def print_sample_info(sample: AudioSample):
    """Print detailed info about an audio sample."""
    print(f"\nSample: {sample.name}")
    print(f"  Source: {sample.source_path or 'generated'}")
    print(f"  Duration: {sample.duration_seconds:.2f}s")
    print(f"  Sample Rate: {sample.sample_rate}Hz")
    print(f"  Channels: {sample.channels}")
    print(f"  Bit Depth: {sample.sample_width * 8}-bit")
    print(f"  Data Size: {len(sample.data):,} bytes")
    print(f"  Num Samples: {sample.num_samples:,}")
