"""
Direct PersonaPlex benchmark client.

Connects directly to PersonaPlex server (bypassing the backend)
to measure raw model latency without backend overhead.
"""
import asyncio
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from urllib.parse import urlencode
import numpy as np

from core.metrics import MetricsCollector, RequestMetrics, audio_to_tokens, bytes_to_audio_duration

logger = logging.getLogger(__name__)


@dataclass
class DirectConfig:
    """Configuration for direct PersonaPlex benchmark."""
    host: str = "localhost"
    port: int = 8998
    use_ssl: bool = False

    # System prompt
    text_prompt: str = "You are a helpful assistant."

    # Timeouts
    connect_timeout: float = 30.0
    response_timeout: float = 60.0

    @property
    def ws_url(self) -> str:
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.host}:{self.port}/api/chat"


class DirectBenchmarkClient:
    """
    Direct benchmark client for PersonaPlex.

    Connects directly to PersonaPlex without going through the backend,
    giving accurate measurements of the model's raw latency.
    """

    def __init__(self, config: DirectConfig):
        self.config = config
        self.ws = None
        self._connected = False
        self.opus_writer = None
        self.opus_reader = None

    async def connect(self) -> bool:
        """Connect directly to PersonaPlex with config in URL."""
        try:
            import websockets
            import sphn

            # Initialize Opus encoder/decoder
            self.opus_writer = sphn.OpusStreamWriter(24000)
            self.opus_reader = sphn.OpusStreamReader(24000)

            # Build URL with text_prompt in query params
            query_params = {'text_prompt': self.config.text_prompt}
            ws_url = f"{self.config.ws_url}?{urlencode(query_params)}"

            logger.info(f"Connecting directly to PersonaPlex at {self.config.ws_url}")

            self.ws = await asyncio.wait_for(
                websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=30
                ),
                timeout=self.config.connect_timeout
            )

            # Wait for handshake (single \x00 byte)
            logger.info("Waiting for PersonaPlex handshake...")
            handshake = await asyncio.wait_for(self.ws.recv(), timeout=30.0)

            if isinstance(handshake, bytes) and len(handshake) == 1 and handshake[0] == 0:
                logger.info("Handshake received - PersonaPlex ready")
            else:
                logger.warning(f"Unexpected handshake: {handshake}")

            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Close connection."""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        self._connected = False

    async def benchmark_audio_response(
        self,
        request_id: str,
        audio_data: bytes,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str], None]] = None
    ) -> RequestMetrics:
        """
        Benchmark a single audio request directly to PersonaPlex.

        Args:
            request_id: Unique identifier for this request
            audio_data: PCM audio bytes (24kHz, 16-bit, mono)
            on_audio: Callback for each audio chunk received
            on_text: Callback for each text token received

        Returns:
            RequestMetrics with timing data
        """
        if not self._connected or not self.ws:
            raise RuntimeError("Not connected to PersonaPlex")

        # Calculate input tokens from audio duration (Moshi uses 12.5 Hz semantic tokenizer)
        audio_duration = bytes_to_audio_duration(len(audio_data))
        prompt_tokens = audio_to_tokens(audio_duration)

        collector = MetricsCollector(
            request_id=request_id,
            prompt=f"[audio {audio_duration:.1f}s]",
            prompt_tokens=prompt_tokens
        )

        try:
            # Convert PCM to float32 for Opus encoding
            samples = np.frombuffer(audio_data, dtype=np.int16)

            # Find speech start (skip silence)
            threshold = 500
            non_silent = np.where(np.abs(samples) > threshold)[0]
            if len(non_silent) > 0:
                start_sample = max(0, non_silent[0] - 12000)
            else:
                start_sample = 0

            # Use 10 seconds of audio from speech start
            end_sample = min(start_sample + 10 * 24000, len(samples))
            speech_samples = samples[start_sample:end_sample].astype(np.float32) / 32768.0

            logger.info(f"Sending {len(speech_samples)/24000:.1f}s of audio directly to PersonaPlex")

            # Start timing
            collector.start()
            send_time = time.time()

            # Stream audio in real-time chunks (80ms = 1920 samples)
            chunk_samples = 1920
            chunk_time = chunk_samples / 24000

            first_response_time = None
            audio_chunks = 0
            text_tokens = []

            async def receive_responses():
                nonlocal first_response_time, audio_chunks, text_tokens

                while True:
                    try:
                        msg = await asyncio.wait_for(
                            self.ws.recv(),
                            timeout=self.config.response_timeout
                        )

                        now = time.time()

                        if isinstance(msg, bytes) and len(msg) > 0:
                            kind = msg[0]
                            payload = msg[1:]

                            if kind == 1 and len(payload) > 0:  # Audio
                                if first_response_time is None:
                                    first_response_time = now
                                    ttft = (now - send_time) * 1000
                                    logger.info(f"First audio at {ttft:.1f}ms")
                                    collector.record_turn_taking(send_time, now)

                                audio_chunks += 1
                                collector.record_token(f"[audio_{audio_chunks}]")

                                if on_audio and self.opus_reader:
                                    pcm = self.opus_reader.append_bytes(payload)
                                    if pcm.shape[-1] > 0:
                                        pcm_int16 = (pcm * 32767).astype(np.int16)
                                        on_audio(pcm_int16.tobytes())

                            elif kind == 2:  # Text
                                text = payload.decode('utf-8', errors='ignore')
                                if text.strip():
                                    if first_response_time is None:
                                        first_response_time = now
                                        collector.record_turn_taking(send_time, now)

                                    text_tokens.append(text)
                                    collector.record_token(text)
                                    logger.debug(f"Text: {text}")

                                    if on_text:
                                        on_text(text)

                        # Check if we have enough response
                        elapsed = now - send_time
                        if elapsed > 3.0 and (audio_chunks > 10 or len(text_tokens) > 10):
                            return True

                    except asyncio.TimeoutError:
                        logger.warning("Response timeout")
                        return False
                    except Exception as e:
                        logger.error(f"Receive error: {e}")
                        return False

            # Start receiver task
            recv_task = asyncio.create_task(receive_responses())

            # Stream audio chunks
            for i in range(0, len(speech_samples), chunk_samples):
                chunk = speech_samples[i:i+chunk_samples]
                if len(chunk) < chunk_samples:
                    chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

                opus_data = self.opus_writer.append_pcm(chunk)
                if len(opus_data) > 0:
                    await self.ws.send(b'\x01' + opus_data)

                await asyncio.sleep(chunk_time)

            user_stop_time = time.time()
            logger.info(f"Audio streaming complete after {(user_stop_time - send_time)*1000:.1f}ms")

            # Wait for responses
            success = await recv_task

            logger.info(f"Received {audio_chunks} audio chunks, {len(text_tokens)} text tokens")
            if text_tokens:
                logger.info(f"Response: {''.join(text_tokens)}")

            return collector.end(success=success)

        except Exception as e:
            logger.error(f"Direct benchmark failed: {e}")
            return collector.end(success=False, error=str(e))


async def check_personaplex_health(config: DirectConfig) -> dict:
    """Check if PersonaPlex is accessible."""
    try:
        import websockets

        ws_url = f"{config.ws_url}?text_prompt=test"
        ws = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=5.0
        )

        # Wait for handshake
        handshake = await asyncio.wait_for(ws.recv(), timeout=5.0)
        await ws.close()

        if isinstance(handshake, bytes) and len(handshake) == 1 and handshake[0] == 0:
            return {"status": "healthy", "handshake": "ok"}
        else:
            return {"status": "unhealthy", "handshake": "unexpected"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
