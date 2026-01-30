"""
Core metrics collection for PersonaPlex benchmarking.

Metrics based on NVIDIA LLM Benchmarking standards:
- Time to First Token (TTFT)
- Inter-token Latency (ITL) / Time Per Output Token (TPOT)
- Tokens Per Second (TPS)
- End-to-End Request Latency
- Requests Per Second (RPS)

Audio-specific metrics (FullDuplexBench):
- Smooth Turn-Taking Latency
- User Interruption Latency
"""
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


# Moshi/PersonaPlex audio tokenization rates
MOSHI_SEMANTIC_TOKEN_RATE = 12.5  # Semantic tokens per second (main tokens)
MOSHI_ACOUSTIC_TOKEN_RATE = 12.5  # Acoustic tokens per second per codebook
MOSHI_SAMPLE_RATE = 24000  # Audio sample rate in Hz


def audio_to_tokens(audio_duration_seconds: float, rate: float = MOSHI_SEMANTIC_TOKEN_RATE) -> int:
    """
    Calculate input tokens from audio duration.

    Moshi uses a semantic tokenizer at ~12.5 Hz.
    For more accurate estimates, multiply by number of codebooks for acoustic tokens.

    Args:
        audio_duration_seconds: Duration of audio in seconds
        rate: Token rate (default: 12.5 Hz for semantic tokens)

    Returns:
        Estimated number of input tokens
    """
    return int(audio_duration_seconds * rate)


def bytes_to_audio_duration(audio_bytes: int, sample_rate: int = MOSHI_SAMPLE_RATE, bit_depth: int = 16, channels: int = 1) -> float:
    """
    Calculate audio duration from byte count.

    Args:
        audio_bytes: Number of bytes
        sample_rate: Sample rate (default: 24000 Hz)
        bit_depth: Bits per sample (default: 16)
        channels: Number of channels (default: 1)

    Returns:
        Duration in seconds
    """
    bytes_per_sample = (bit_depth // 8) * channels
    num_samples = audio_bytes / bytes_per_sample
    return num_samples / sample_rate


@dataclass
class TokenEvent:
    """Single token generation event."""
    token_id: int
    token_text: str
    timestamp: float  # Unix timestamp in seconds
    is_first: bool = False
    is_last: bool = False


@dataclass
class RequestMetrics:
    """Metrics for a single request/response cycle."""
    request_id: str
    prompt: str
    prompt_tokens: int

    # Timestamps
    request_start: float = 0.0
    first_token_time: float = 0.0
    last_token_time: float = 0.0
    request_end: float = 0.0

    # Token data
    output_tokens: int = 0
    token_events: List[TokenEvent] = field(default_factory=list)

    # Computed metrics (populated by compute_metrics())
    ttft: float = 0.0  # Time to First Token
    e2e_latency: float = 0.0  # End-to-end latency
    itl: float = 0.0  # Inter-token latency (average)
    tps: float = 0.0  # Tokens per second for this request

    # Audio-specific (if applicable)
    audio_input_duration: float = 0.0
    audio_output_duration: float = 0.0
    turn_taking_latency: float = 0.0  # Time from user stops to agent starts

    # Status
    success: bool = True
    error: Optional[str] = None

    def compute_metrics(self):
        """Compute derived metrics from raw measurements."""
        if self.request_start and self.first_token_time:
            self.ttft = self.first_token_time - self.request_start

        if self.request_start and self.request_end:
            self.e2e_latency = self.request_end - self.request_start

        # Inter-token latency: (e2e_latency - ttft) / (output_tokens - 1)
        if self.output_tokens > 1 and self.ttft > 0:
            generation_time = self.e2e_latency - self.ttft
            self.itl = generation_time / (self.output_tokens - 1)

        # Tokens per second for this request
        if self.e2e_latency > 0 and self.output_tokens > 0:
            self.tps = self.output_tokens / self.e2e_latency

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "ttft_ms": round(self.ttft * 1000, 2),
            "e2e_latency_ms": round(self.e2e_latency * 1000, 2),
            "itl_ms": round(self.itl * 1000, 2),
            "tps": round(self.tps, 2),
            "turn_taking_latency_ms": round(self.turn_taking_latency * 1000, 2) if self.turn_taking_latency else None,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class BenchmarkResult:
    """Aggregated benchmark results across multiple requests."""
    name: str
    description: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)

    # Raw request data
    requests: List[RequestMetrics] = field(default_factory=list)

    # Aggregated metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Latency statistics (in milliseconds)
    ttft_mean: float = 0.0
    ttft_median: float = 0.0
    ttft_p50: float = 0.0
    ttft_p90: float = 0.0
    ttft_p95: float = 0.0
    ttft_p99: float = 0.0
    ttft_min: float = 0.0
    ttft_max: float = 0.0

    e2e_latency_mean: float = 0.0
    e2e_latency_median: float = 0.0
    e2e_latency_p90: float = 0.0
    e2e_latency_p95: float = 0.0
    e2e_latency_p99: float = 0.0

    itl_mean: float = 0.0
    itl_median: float = 0.0
    itl_p90: float = 0.0
    itl_p95: float = 0.0

    # Throughput
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    tokens_per_second: float = 0.0
    tokens_per_minute: float = 0.0
    requests_per_second: float = 0.0

    # Audio metrics (if applicable)
    turn_taking_latency_mean: float = 0.0
    turn_taking_latency_p90: float = 0.0

    def add_request(self, request: RequestMetrics):
        """Add a request and update aggregates."""
        request.compute_metrics()
        self.requests.append(request)
        self.total_requests += 1

        if request.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def compute_aggregates(self):
        """Compute aggregate statistics from all requests."""
        self.end_time = datetime.utcnow()

        successful = [r for r in self.requests if r.success]
        if not successful:
            return

        # Extract metric arrays
        ttfts = [r.ttft * 1000 for r in successful if r.ttft > 0]  # Convert to ms
        e2e_latencies = [r.e2e_latency * 1000 for r in successful if r.e2e_latency > 0]
        itls = [r.itl * 1000 for r in successful if r.itl > 0]
        turn_taking = [r.turn_taking_latency * 1000 for r in successful if r.turn_taking_latency > 0]

        # TTFT statistics
        if ttfts:
            self.ttft_mean = statistics.mean(ttfts)
            self.ttft_median = statistics.median(ttfts)
            self.ttft_p50 = self._percentile(ttfts, 50)
            self.ttft_p90 = self._percentile(ttfts, 90)
            self.ttft_p95 = self._percentile(ttfts, 95)
            self.ttft_p99 = self._percentile(ttfts, 99)
            self.ttft_min = min(ttfts)
            self.ttft_max = max(ttfts)

        # E2E latency statistics
        if e2e_latencies:
            self.e2e_latency_mean = statistics.mean(e2e_latencies)
            self.e2e_latency_median = statistics.median(e2e_latencies)
            self.e2e_latency_p90 = self._percentile(e2e_latencies, 90)
            self.e2e_latency_p95 = self._percentile(e2e_latencies, 95)
            self.e2e_latency_p99 = self._percentile(e2e_latencies, 99)

        # ITL statistics
        if itls:
            self.itl_mean = statistics.mean(itls)
            self.itl_median = statistics.median(itls)
            self.itl_p90 = self._percentile(itls, 90)
            self.itl_p95 = self._percentile(itls, 95)

        # Turn-taking latency
        if turn_taking:
            self.turn_taking_latency_mean = statistics.mean(turn_taking)
            self.turn_taking_latency_p90 = self._percentile(turn_taking, 90)

        # Throughput calculations
        self.total_prompt_tokens = sum(r.prompt_tokens for r in successful)
        self.total_output_tokens = sum(r.output_tokens for r in successful)
        self.total_tokens = self.total_prompt_tokens + self.total_output_tokens

        # Calculate total benchmark duration
        if self.start_time and self.end_time:
            duration_seconds = (self.end_time - self.start_time).total_seconds()
            if duration_seconds > 0:
                self.tokens_per_second = self.total_output_tokens / duration_seconds
                self.tokens_per_minute = self.tokens_per_second * 60
                self.requests_per_second = self.successful_requests / duration_seconds

    def _percentile(self, data: List[float], p: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (p / 100)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "benchmark": {
                "name": self.name,
                "description": self.description,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
                "config": self.config,
            },
            "summary": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": round(self.successful_requests / self.total_requests * 100, 2) if self.total_requests > 0 else 0,
            },
            "latency_ms": {
                "ttft": {
                    "mean": round(self.ttft_mean, 2),
                    "median": round(self.ttft_median, 2),
                    "p50": round(self.ttft_p50, 2),
                    "p90": round(self.ttft_p90, 2),
                    "p95": round(self.ttft_p95, 2),
                    "p99": round(self.ttft_p99, 2),
                    "min": round(self.ttft_min, 2),
                    "max": round(self.ttft_max, 2),
                },
                "e2e": {
                    "mean": round(self.e2e_latency_mean, 2),
                    "median": round(self.e2e_latency_median, 2),
                    "p90": round(self.e2e_latency_p90, 2),
                    "p95": round(self.e2e_latency_p95, 2),
                    "p99": round(self.e2e_latency_p99, 2),
                },
                "itl": {
                    "mean": round(self.itl_mean, 2),
                    "median": round(self.itl_median, 2),
                    "p90": round(self.itl_p90, 2),
                    "p95": round(self.itl_p95, 2),
                },
                "turn_taking": {
                    "mean": round(self.turn_taking_latency_mean, 2),
                    "p90": round(self.turn_taking_latency_p90, 2),
                } if self.turn_taking_latency_mean > 0 else None,
            },
            "throughput": {
                "total_tokens": self.total_tokens,
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_output_tokens": self.total_output_tokens,
                "tokens_per_second": round(self.tokens_per_second, 2),
                "tokens_per_minute": round(self.tokens_per_minute, 2),
                "requests_per_second": round(self.requests_per_second, 4),
            },
            "requests": [r.to_dict() for r in self.requests],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def print_summary(self):
        """Print a human-readable summary."""
        print("\n" + "=" * 70)
        print(f"BENCHMARK RESULTS: {self.name}")
        print("=" * 70)
        print(f"Description: {self.description}")
        print(f"Duration: {(self.end_time - self.start_time).total_seconds():.2f}s")
        print()

        print("REQUEST SUMMARY:")
        print(f"  Total Requests:      {self.total_requests}")
        print(f"  Successful:          {self.successful_requests}")
        print(f"  Failed:              {self.failed_requests}")
        print(f"  Success Rate:        {self.successful_requests / self.total_requests * 100:.1f}%")
        print()

        print("LATENCY (milliseconds):")
        print(f"  Time to First Token (TTFT):")
        print(f"    Mean:    {self.ttft_mean:>8.2f} ms")
        print(f"    Median:  {self.ttft_median:>8.2f} ms")
        print(f"    P90:     {self.ttft_p90:>8.2f} ms")
        print(f"    P95:     {self.ttft_p95:>8.2f} ms")
        print(f"    P99:     {self.ttft_p99:>8.2f} ms")
        print()
        print(f"  End-to-End Latency:")
        print(f"    Mean:    {self.e2e_latency_mean:>8.2f} ms")
        print(f"    Median:  {self.e2e_latency_median:>8.2f} ms")
        print(f"    P90:     {self.e2e_latency_p90:>8.2f} ms")
        print(f"    P95:     {self.e2e_latency_p95:>8.2f} ms")
        print()
        print(f"  Inter-Token Latency (ITL):")
        print(f"    Mean:    {self.itl_mean:>8.2f} ms")
        print(f"    Median:  {self.itl_median:>8.2f} ms")
        print(f"    P90:     {self.itl_p90:>8.2f} ms")
        print()

        if self.turn_taking_latency_mean > 0:
            print(f"  Turn-Taking Latency:")
            print(f"    Mean:    {self.turn_taking_latency_mean:>8.2f} ms")
            print(f"    P90:     {self.turn_taking_latency_p90:>8.2f} ms")
            print()

        print("TOKEN COUNTS:")
        print(f"  Total Input Tokens:  {self.total_prompt_tokens:,}")
        print(f"  Total Output Tokens: {self.total_output_tokens:,}")
        print(f"  Total Tokens:        {self.total_tokens:,}")
        print()

        print("THROUGHPUT:")
        print(f"  Output Tokens/Second:  {self.tokens_per_second:,.2f}")
        print(f"  Output Tokens/Minute:  {self.tokens_per_minute:,.2f}")
        print(f"  Requests/Second:       {self.requests_per_second:.4f}")
        print("=" * 70)


class MetricsCollector:
    """Real-time metrics collector for streaming responses."""

    def __init__(self, request_id: str, prompt: str, prompt_tokens: int = 0):
        self.metrics = RequestMetrics(
            request_id=request_id,
            prompt=prompt,
            prompt_tokens=prompt_tokens
        )
        self._token_count = 0

    def start(self):
        """Mark the start of the request."""
        self.metrics.request_start = time.time()

    def record_token(self, token_text: str, token_id: int = 0):
        """Record a token generation event."""
        now = time.time()
        self._token_count += 1

        is_first = self._token_count == 1
        if is_first:
            self.metrics.first_token_time = now

        self.metrics.token_events.append(TokenEvent(
            token_id=token_id,
            token_text=token_text,
            timestamp=now,
            is_first=is_first
        ))
        self.metrics.output_tokens = self._token_count
        self.metrics.last_token_time = now

    def end(self, success: bool = True, error: Optional[str] = None):
        """Mark the end of the request."""
        self.metrics.request_end = time.time()
        self.metrics.success = success
        self.metrics.error = error

        if self.metrics.token_events:
            self.metrics.token_events[-1].is_last = True

        self.metrics.compute_metrics()
        return self.metrics

    def record_turn_taking(self, user_stop_time: float, agent_start_time: float):
        """Record turn-taking latency for audio benchmarks."""
        self.metrics.turn_taking_latency = agent_start_time - user_stop_time
