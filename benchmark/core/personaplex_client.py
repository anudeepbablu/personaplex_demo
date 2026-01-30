"""
PersonaPlex benchmark client for latency and throughput testing.

Connects to PersonaPlex server via WebSocket and measures:
- Time to First Token (TTFT)
- Inter-token Latency (ITL)
- Tokens Per Second (TPS)
- Turn-taking Latency (audio-specific)
"""
import asyncio
import json
import time
import ssl
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass

from core.metrics import MetricsCollector, RequestMetrics, BenchmarkResult

logger = logging.getLogger(__name__)


@dataclass
class PersonaPlexConfig:
    """Configuration for PersonaPlex connection."""
    host: str = "localhost"
    port: int = 8998
    use_ssl: bool = False
    ssl_verify: bool = False

    # Model configuration
    voice_id: str = "NATF1"
    text_prompt: str = "You are a helpful assistant."

    # Timeouts
    connect_timeout: float = 10.0
    response_timeout: float = 30.0

    # WebSocket endpoint path
    ws_path: str = "/api/chat"

    @property
    def ws_url(self) -> str:
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.host}:{self.port}{self.ws_path}"


class PersonaPlexBenchmarkClient:
    """
    Benchmark client for PersonaPlex server.

    Measures latency and throughput by sending text prompts and
    measuring response times for each token.
    """

    def __init__(self, config: PersonaPlexConfig):
        self.config = config
        self.ws = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish WebSocket connection to PersonaPlex."""
        try:
            import websockets

            ssl_context = None
            if self.config.use_ssl:
                ssl_context = ssl.create_default_context()
                if not self.config.ssl_verify:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            self.ws = await asyncio.wait_for(
                websockets.connect(
                    self.config.ws_url,
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=30
                ),
                timeout=self.config.connect_timeout
            )
            self._connected = True
            logger.info(f"Connected to PersonaPlex at {self.config.ws_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        self._connected = False

    async def send_config(self, text_prompt: str, voice_id: str = None):
        """Send configuration message to PersonaPlex."""
        if not self._connected or not self.ws:
            raise RuntimeError("Not connected to PersonaPlex")

        config_message = {
            "type": "config",
            "text_prompt": text_prompt,
            "voice_id": voice_id or self.config.voice_id
        }

        await self.ws.send(json.dumps(config_message))

    async def benchmark_text_response(
        self,
        request_id: str,
        text_prompt: str,
        user_input: str,
        on_token: Optional[Callable[[str], None]] = None
    ) -> RequestMetrics:
        """
        Benchmark a single text response from PersonaPlex.

        Args:
            request_id: Unique identifier for this request
            text_prompt: System prompt for the model
            user_input: User message to process
            on_token: Optional callback for each token received

        Returns:
            RequestMetrics with timing data
        """
        # Estimate prompt tokens (rough approximation: ~4 chars per token)
        prompt_tokens = len(text_prompt + user_input) // 4

        collector = MetricsCollector(
            request_id=request_id,
            prompt=user_input,
            prompt_tokens=prompt_tokens
        )

        try:
            # Send configuration
            await self.send_config(text_prompt)

            # Start timing
            collector.start()

            # Send user input as audio-like message (text simulation)
            # In real PersonaPlex, this would be audio data
            input_message = {
                "type": "text_input",
                "text": user_input
            }
            await self.ws.send(json.dumps(input_message))

            # Receive response tokens
            response_text = ""
            async for message in self.ws:
                if isinstance(message, bytes) and len(message) > 0:
                    kind = message[0]
                    payload = message[1:]

                    if kind == 2:  # Text token
                        token_text = payload.decode('utf-8', errors='ignore')
                        if token_text.strip():
                            collector.record_token(token_text)
                            response_text += token_text
                            if on_token:
                                on_token(token_text)

                elif isinstance(message, str):
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "token":
                            token_text = data.get("text", "")
                            if token_text:
                                collector.record_token(token_text)
                                response_text += token_text
                                if on_token:
                                    on_token(token_text)

                        elif msg_type == "end" or msg_type == "complete":
                            break

                        elif msg_type == "error":
                            raise RuntimeError(data.get("message", "Unknown error"))

                    except json.JSONDecodeError:
                        pass

                # Check for timeout
                if time.time() - collector.metrics.request_start > self.config.response_timeout:
                    raise TimeoutError("Response timeout exceeded")

            return collector.end(success=True)

        except Exception as e:
            logger.error(f"Benchmark request failed: {e}")
            return collector.end(success=False, error=str(e))

    async def benchmark_audio_latency(
        self,
        request_id: str,
        audio_data: bytes,
        text_prompt: str
    ) -> RequestMetrics:
        """
        Benchmark audio input/output latency.

        Measures turn-taking latency: time from end of user audio
        to start of agent audio response.

        Args:
            request_id: Unique identifier
            audio_data: PCM audio bytes (16-bit, 24kHz, mono)
            text_prompt: System prompt

        Returns:
            RequestMetrics with audio-specific timing
        """
        prompt_tokens = len(text_prompt) // 4
        collector = MetricsCollector(
            request_id=request_id,
            prompt="[audio input]",
            prompt_tokens=prompt_tokens
        )

        try:
            await self.send_config(text_prompt)
            collector.start()

            # Send audio data
            # PersonaPlex expects Opus-encoded audio with \x01 prefix
            # For benchmarking, we send raw audio and measure response time
            user_stop_time = time.time()
            await self.ws.send(audio_data)

            # Wait for first audio response
            agent_start_time = None
            token_count = 0

            async for message in self.ws:
                now = time.time()

                if isinstance(message, bytes) and len(message) > 0:
                    kind = message[0]

                    if kind == 1:  # Audio response
                        if agent_start_time is None:
                            agent_start_time = now
                            collector.record_turn_taking(user_stop_time, agent_start_time)
                        token_count += 1
                        collector.record_token(f"[audio_chunk_{token_count}]")

                    elif kind == 2:  # Text token
                        token_text = message[1:].decode('utf-8', errors='ignore')
                        if token_text.strip():
                            collector.record_token(token_text)

                # Timeout check
                if now - collector.metrics.request_start > self.config.response_timeout:
                    break

            return collector.end(success=True)

        except Exception as e:
            logger.error(f"Audio benchmark failed: {e}")
            return collector.end(success=False, error=str(e))


class MockPersonaPlexClient:
    """
    Mock client for testing benchmark infrastructure without PersonaPlex server.

    Simulates realistic latency patterns for development and testing.
    """

    def __init__(self, config: PersonaPlexConfig = None):
        self.config = config or PersonaPlexConfig()
        self._connected = False

        # Simulated latency parameters (in seconds)
        self.ttft_base = 0.15  # 150ms base TTFT
        self.ttft_variance = 0.05
        self.itl_base = 0.02  # 20ms between tokens
        self.itl_variance = 0.01

    async def connect(self) -> bool:
        await asyncio.sleep(0.1)  # Simulate connection time
        self._connected = True
        return True

    async def disconnect(self):
        self._connected = False

    async def benchmark_text_response(
        self,
        request_id: str,
        text_prompt: str,
        user_input: str,
        on_token: Optional[Callable[[str], None]] = None
    ) -> RequestMetrics:
        """Simulate a text response with realistic latency."""
        import random

        prompt_tokens = len(text_prompt + user_input) // 4
        collector = MetricsCollector(
            request_id=request_id,
            prompt=user_input,
            prompt_tokens=prompt_tokens
        )

        # Simulate response
        response_tokens = [
            "I'd", " be", " happy", " to", " help", " you", " with",
            " that", ".", " What", " would", " you", " like", " to",
            " know", "?"
        ]

        collector.start()

        # Simulate TTFT
        ttft = self.ttft_base + random.uniform(-self.ttft_variance, self.ttft_variance)
        await asyncio.sleep(ttft)

        # Generate tokens with ITL
        for token in response_tokens:
            collector.record_token(token)
            if on_token:
                on_token(token)

            itl = self.itl_base + random.uniform(-self.itl_variance, self.itl_variance)
            await asyncio.sleep(itl)

        return collector.end(success=True)

    async def benchmark_audio_latency(
        self,
        request_id: str,
        audio_data: bytes,
        text_prompt: str
    ) -> RequestMetrics:
        """Simulate audio latency benchmark."""
        import random

        collector = MetricsCollector(
            request_id=request_id,
            prompt="[audio input]",
            prompt_tokens=len(text_prompt) // 4
        )

        collector.start()
        user_stop_time = time.time()

        # Simulate turn-taking latency (170-270ms as per PersonaPlex paper)
        turn_taking = 0.17 + random.uniform(0, 0.10)
        await asyncio.sleep(turn_taking)

        agent_start_time = time.time()
        collector.record_turn_taking(user_stop_time, agent_start_time)

        # Simulate audio chunks
        for i in range(10):
            collector.record_token(f"[audio_chunk_{i}]")
            await asyncio.sleep(0.05)

        return collector.end(success=True)
