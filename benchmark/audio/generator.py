"""
Audio generation utilities for PersonaPlex benchmarks.

Generates test audio samples for latency testing.
"""
import numpy as np
import struct
from typing import Optional


class AudioGenerator:
    """
    Generate test audio data for PersonaPlex benchmarks.

    Produces PCM audio in formats compatible with PersonaPlex:
    - 24kHz sample rate (PersonaPlex native)
    - 16-bit signed PCM
    - Mono channel
    """

    SAMPLE_RATE = 24000  # PersonaPlex native sample rate
    BYTES_PER_SAMPLE = 2  # 16-bit audio
    CHANNELS = 1

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def generate_silence(self, duration_seconds: float) -> bytes:
        """Generate silent audio for specified duration."""
        num_samples = int(self.sample_rate * duration_seconds)
        samples = np.zeros(num_samples, dtype=np.int16)
        return samples.tobytes()

    def generate_tone(
        self,
        duration_seconds: float,
        frequency: float = 440.0,
        amplitude: float = 0.5
    ) -> bytes:
        """
        Generate a sine wave tone.

        Args:
            duration_seconds: Duration of audio
            frequency: Tone frequency in Hz (default 440Hz = A4)
            amplitude: Volume 0.0 to 1.0

        Returns:
            PCM audio bytes
        """
        num_samples = int(self.sample_rate * duration_seconds)
        t = np.linspace(0, duration_seconds, num_samples, dtype=np.float32)

        # Generate sine wave
        wave = np.sin(2 * np.pi * frequency * t) * amplitude

        # Convert to 16-bit PCM
        samples = (wave * 32767).astype(np.int16)
        return samples.tobytes()

    def generate_speech_like(
        self,
        duration_seconds: float,
        amplitude: float = 0.3
    ) -> bytes:
        """
        Generate speech-like audio with varying frequencies.

        Simulates speech patterns with fundamental frequency variations
        typical of human speech (100-300Hz range).

        Args:
            duration_seconds: Duration of audio
            amplitude: Volume 0.0 to 1.0

        Returns:
            PCM audio bytes
        """
        num_samples = int(self.sample_rate * duration_seconds)
        t = np.linspace(0, duration_seconds, num_samples, dtype=np.float32)

        # Simulate speech with varying fundamental frequency
        # Human speech typically ranges from 100-300Hz fundamental
        base_freq = 150.0

        # Add frequency modulation to simulate intonation
        freq_mod = base_freq + 50 * np.sin(2 * np.pi * 2 * t)  # 2Hz modulation

        # Generate waveform with harmonics (speech has harmonics)
        phase = np.cumsum(2 * np.pi * freq_mod / self.sample_rate)
        wave = np.sin(phase) * 0.6  # Fundamental
        wave += np.sin(2 * phase) * 0.3  # 2nd harmonic
        wave += np.sin(3 * phase) * 0.1  # 3rd harmonic

        # Add amplitude envelope (simulates syllables)
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)  # 4Hz syllable rate
        wave = wave * envelope * amplitude

        # Convert to 16-bit PCM
        samples = (wave * 32767).astype(np.int16)
        return samples.tobytes()

    def generate_test_utterance(
        self,
        text: str,
        words_per_minute: float = 150.0
    ) -> bytes:
        """
        Generate audio duration based on text length.

        Estimates speech duration from text and generates
        speech-like audio of appropriate length.

        Args:
            text: Text to estimate duration from
            words_per_minute: Speaking rate (default 150 WPM)

        Returns:
            PCM audio bytes
        """
        # Estimate word count and duration
        words = len(text.split())
        duration = (words / words_per_minute) * 60.0

        # Minimum duration of 0.5 seconds
        duration = max(duration, 0.5)

        return self.generate_speech_like(duration)

    def generate_burst_pattern(
        self,
        burst_duration: float = 0.3,
        silence_duration: float = 0.2,
        num_bursts: int = 5
    ) -> bytes:
        """
        Generate alternating audio/silence pattern.

        Useful for testing turn-taking detection.

        Args:
            burst_duration: Duration of each audio burst
            silence_duration: Duration of silence between bursts
            num_bursts: Number of audio bursts

        Returns:
            PCM audio bytes
        """
        audio_parts = []

        for i in range(num_bursts):
            # Add speech burst
            audio_parts.append(self.generate_speech_like(burst_duration))

            # Add silence (except after last burst)
            if i < num_bursts - 1:
                audio_parts.append(self.generate_silence(silence_duration))

        return b''.join(audio_parts)

    def add_opus_header(self, pcm_data: bytes) -> bytes:
        """
        Add PersonaPlex Moshi protocol header for audio.

        PersonaPlex expects audio with \\x01 prefix byte.
        Note: This is raw PCM, actual system would need Opus encoding.

        Args:
            pcm_data: Raw PCM audio bytes

        Returns:
            Audio bytes with protocol header
        """
        return b'\x01' + pcm_data

    def calculate_duration(self, audio_bytes: bytes) -> float:
        """Calculate duration in seconds from audio bytes."""
        num_samples = len(audio_bytes) // self.BYTES_PER_SAMPLE
        return num_samples / self.sample_rate

    @staticmethod
    def pcm_to_float(pcm_data: bytes) -> np.ndarray:
        """Convert PCM bytes to float array for analysis."""
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        return samples.astype(np.float32) / 32767.0

    @staticmethod
    def float_to_pcm(float_data: np.ndarray) -> bytes:
        """Convert float array to PCM bytes."""
        samples = (float_data * 32767).astype(np.int16)
        return samples.tobytes()
