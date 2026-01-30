"""
Full pipeline benchmark client.

Connects to the FastAPI backend which proxies to PersonaPlex.
Tests the complete audio pipeline: Client → Backend → PersonaPlex → Backend → Client
"""
import asyncio
import json
import time
import logging
from typing import Optional, Callable, List
from dataclasses import dataclass
import httpx

from core.metrics import MetricsCollector, RequestMetrics, BenchmarkResult, audio_to_tokens, bytes_to_audio_duration

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for pipeline benchmark."""
    # Backend settings
    backend_host: str = "localhost"
    backend_port: int = 8000
    use_ssl: bool = False

    # Session settings
    restaurant_id: int = 2  # Tony's Pizzeria

    # Timeouts
    connect_timeout: float = 10.0
    response_timeout: float = 60.0  # Allow more time for PersonaPlex processing

    @property
    def base_url(self) -> str:
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.backend_host}:{self.backend_port}"

    @property
    def ws_url(self) -> str:
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.backend_host}:{self.backend_port}"


class PipelineBenchmarkClient:
    """
    Benchmark client for the full audio pipeline.

    Flow:
    1. Create session via REST API
    2. Connect to WebSocket endpoint
    3. Send audio data
    4. Receive and measure response
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.session_id: Optional[str] = None
        self.ws = None
        self._connected = False
        self._http_client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """Create session and establish WebSocket connection."""
        try:
            # Create HTTP client
            self._http_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.connect_timeout
            )

            # Create session
            response = await self._http_client.post(
                "/sessions",
                json={"restaurant_id": self.config.restaurant_id}
            )

            if response.status_code != 200:
                logger.error(f"Failed to create session: {response.status_code} {response.text}")
                return False

            data = response.json()
            self.session_id = data["session_id"]
            logger.info(f"Created session: {self.session_id}")

            # Connect to WebSocket
            import websockets

            ws_url = f"{self.config.ws_url}/ws/sessions/{self.session_id}/audio"
            logger.info(f"Connecting to WebSocket: {ws_url}")

            self.ws = await asyncio.wait_for(
                websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=30
                ),
                timeout=self.config.connect_timeout
            )

            self._connected = True
            logger.info(f"Connected to pipeline at {ws_url}")

            # Wait for initial messages (info/greeting)
            try:
                initial_msg = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                logger.debug(f"Initial message: {initial_msg[:100] if isinstance(initial_msg, str) else 'binary'}")
            except asyncio.TimeoutError:
                pass

            return True

        except Exception as e:
            logger.error(f"Failed to connect to pipeline: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Close connections."""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass

        if self._http_client:
            await self._http_client.aclose()

        if self.session_id:
            try:
                async with httpx.AsyncClient(base_url=self.config.base_url) as client:
                    await client.delete(f"/sessions/{self.session_id}")
            except:
                pass

        self._connected = False
        self.session_id = None

    async def benchmark_audio_response(
        self,
        request_id: str,
        audio_data: bytes,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str], None]] = None
    ) -> RequestMetrics:
        """
        Benchmark a single audio request through the full pipeline.

        Args:
            request_id: Unique identifier for this request
            audio_data: PCM audio bytes (24kHz, 16-bit, mono)
            on_audio: Callback for each audio chunk received
            on_text: Callback for each text token received

        Returns:
            RequestMetrics with timing data
        """
        if not self._connected or not self.ws:
            raise RuntimeError("Not connected to pipeline")

        # Calculate input tokens from audio duration (Moshi uses 12.5 Hz semantic tokenizer)
        audio_duration = bytes_to_audio_duration(len(audio_data))
        prompt_tokens = audio_to_tokens(audio_duration)

        collector = MetricsCollector(
            request_id=request_id,
            prompt=f"[audio {audio_duration:.1f}s]",
            prompt_tokens=prompt_tokens
        )

        try:
            # Start timing
            collector.start()
            send_time = time.time()

            # Send audio data in chunks (matching frontend's ScriptProcessor)
            # Frontend uses 4096 samples per chunk = 8192 bytes (24kHz, 16-bit mono)
            chunk_size = 8192  # 4096 samples * 2 bytes = 8192 bytes
            chunk_interval = 0.01  # Small delay to not overwhelm the connection

            # Find where speech starts (skip initial silence)
            import numpy as np
            samples = np.frombuffer(audio_data, dtype=np.int16)
            threshold = 500  # Amplitude threshold for speech detection
            non_silent = np.where(np.abs(samples) > threshold)[0]

            if len(non_silent) > 0:
                # Start 0.5 seconds before first speech
                start_sample = max(0, non_silent[0] - 12000)  # 0.5s buffer
                start_byte = start_sample * 2  # 16-bit = 2 bytes per sample
            else:
                start_byte = 0

            # Send 10 seconds of audio starting from speech (more context)
            audio_duration_sec = 10
            max_audio_bytes = 24000 * 2 * audio_duration_sec
            end_byte = min(start_byte + max_audio_bytes, len(audio_data))
            audio_to_send = audio_data[start_byte:end_byte]

            logger.info(f"Sending audio from {start_byte/(24000*2):.1f}s to {end_byte/(24000*2):.1f}s ({len(audio_to_send)/(24000*2):.1f}s)")
            logger.info(f"Total chunks to send: {len(audio_to_send) // chunk_size}")

            chunks_sent = 0
            for i in range(0, len(audio_to_send), chunk_size):
                chunk = audio_to_send[i:i + chunk_size]
                await self.ws.send(chunk)
                chunks_sent += 1
                if chunks_sent % 10 == 0:
                    logger.debug(f"Sent {chunks_sent} chunks ({chunks_sent * chunk_size / (24000*2):.1f}s)")
                await asyncio.sleep(chunk_interval)  # Small pacing delay

            logger.info(f"Finished sending {chunks_sent} chunks")

            # Record when we finished sending
            user_stop_time = time.time()

            # Receive response
            agent_start_time = None
            response_text = ""
            audio_chunks = 0
            text_tokens = 0

            async def receive_with_timeout():
                nonlocal agent_start_time, response_text, audio_chunks, text_tokens

                while True:
                    try:
                        message = await asyncio.wait_for(
                            self.ws.recv(),
                            timeout=self.config.response_timeout
                        )

                        now = time.time()

                        if isinstance(message, bytes):
                            # Audio response
                            logger.debug(f"Received audio chunk: {len(message)} bytes")
                            if agent_start_time is None:
                                agent_start_time = now
                                collector.record_turn_taking(user_stop_time, agent_start_time)
                                logger.info(f"First audio response at {(now - send_time)*1000:.1f}ms")

                            audio_chunks += 1
                            collector.record_token(f"[audio_chunk_{audio_chunks}]")

                            if on_audio:
                                on_audio(message)

                        elif isinstance(message, str):
                            # JSON message
                            logger.debug(f"Received JSON: {message[:200]}")
                            try:
                                data = json.loads(message)
                                msg_type = data.get("type")

                                if msg_type == "transcript":
                                    # Agent transcript
                                    text = data.get("text", "")
                                    speaker = data.get("speaker", "unknown")
                                    logger.info(f"Transcript [{speaker}]: {text[:100]}")
                                    if text and speaker == "agent":
                                        if agent_start_time is None:
                                            agent_start_time = now
                                            collector.record_turn_taking(user_stop_time, agent_start_time)

                                        text_tokens += 1
                                        collector.record_token(text)
                                        response_text += text

                                        if on_text:
                                            on_text(text)

                                elif msg_type == "end" or msg_type == "complete":
                                    logger.info("Received end/complete message")
                                    return True

                                elif msg_type == "error":
                                    logger.error(f"Error from server: {data.get('message')}")
                                    raise RuntimeError(data.get("message", "Unknown error"))

                                elif msg_type == "info":
                                    logger.info(f"Info: {data.get('message')}")

                            except json.JSONDecodeError:
                                pass

                        # Check if we've received enough response
                        elapsed = now - send_time
                        if elapsed > 3.0 and (audio_chunks > 10 or text_tokens > 10):
                            # Got substantial response, consider it done
                            logger.info(f"Response complete: {audio_chunks} audio chunks, {text_tokens} text tokens")
                            return True

                    except asyncio.TimeoutError:
                        logger.warning("Response timeout")
                        return False

            success = await receive_with_timeout()

            return collector.end(success=success)

        except Exception as e:
            logger.error(f"Pipeline benchmark failed: {e}")
            return collector.end(success=False, error=str(e))

    async def get_session_info(self) -> dict:
        """Get current session information."""
        if not self.session_id or not self._http_client:
            return {}

        try:
            response = await self._http_client.get(f"/sessions/{self.session_id}")
            if response.status_code == 200:
                return response.json()
        except:
            pass

        return {}


async def check_backend_health(config: PipelineConfig) -> dict:
    """Check if the backend is healthy and PersonaPlex is connected."""
    try:
        async with httpx.AsyncClient(base_url=config.base_url, timeout=5.0) as client:
            response = await client.get("/health")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        return {"error": str(e)}

    return {"error": "Unknown error"}
