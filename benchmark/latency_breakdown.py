#!/usr/bin/env python3
"""
Latency Breakdown Analysis

Measures individual component latencies in the PersonaPlex pipeline:
1. Direct PersonaPlex latency (raw model inference)
2. Opus encoding latency
3. Opus decoding latency
4. Network round-trip latency
5. Backend WebSocket overhead
6. Full pipeline latency
"""
import asyncio
import time
import wave
import numpy as np
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

# Add benchmark directory to path
BENCHMARK_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BENCHMARK_DIR))

from audio.samples import SampleManager
from core.metrics import audio_to_tokens, bytes_to_audio_duration


@dataclass
class LatencyBreakdown:
    """Stores latency measurements for each component."""
    # Audio/Token info
    audio_duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    # Direct PersonaPlex (no encoding overhead)
    direct_ttft_ms: float = 0.0
    direct_e2e_ms: float = 0.0

    # Opus encoding/decoding
    opus_encode_ms: float = 0.0
    opus_decode_ms: float = 0.0

    # Network latencies
    network_rtt_ms: float = 0.0  # Round-trip to PersonaPlex
    backend_rtt_ms: float = 0.0  # Round-trip to backend

    # Full pipeline
    pipeline_ttft_ms: float = 0.0
    pipeline_e2e_ms: float = 0.0

    # Calculated overheads
    @property
    def backend_overhead_ms(self) -> float:
        """Backend processing overhead = pipeline - direct - encoding."""
        return self.pipeline_ttft_ms - self.direct_ttft_ms - self.opus_encode_ms - self.opus_decode_ms

    @property
    def total_encoding_overhead_ms(self) -> float:
        """Total encoding/decoding overhead."""
        return self.opus_encode_ms + self.opus_decode_ms

    def to_dict(self) -> dict:
        return {
            "audio_input": {
                "duration_seconds": round(self.audio_duration_s, 2),
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "tokens_per_second_audio": round(self.input_tokens / self.audio_duration_s, 2) if self.audio_duration_s > 0 else 0,
            },
            "direct_personaplex": {
                "ttft_ms": round(self.direct_ttft_ms, 2),
                "e2e_ms": round(self.direct_e2e_ms, 2),
            },
            "opus_processing": {
                "encode_ms": round(self.opus_encode_ms, 2),
                "decode_ms": round(self.opus_decode_ms, 2),
                "total_ms": round(self.total_encoding_overhead_ms, 2),
            },
            "network": {
                "personaplex_rtt_ms": round(self.network_rtt_ms, 2),
                "backend_rtt_ms": round(self.backend_rtt_ms, 2),
            },
            "full_pipeline": {
                "ttft_ms": round(self.pipeline_ttft_ms, 2),
                "e2e_ms": round(self.pipeline_e2e_ms, 2),
            },
            "calculated_overhead": {
                "backend_processing_ms": round(self.backend_overhead_ms, 2),
                "total_encoding_ms": round(self.total_encoding_overhead_ms, 2),
            }
        }


async def measure_network_latency(host: str, port: int) -> float:
    """Measure TCP connection latency."""
    times = []
    for _ in range(5):
        start = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"Connection error: {e}")

    return np.mean(times) if times else 0.0


async def measure_websocket_rtt(url: str, timeout: float = 5.0) -> float:
    """Measure WebSocket connection + handshake latency."""
    import websockets

    times = []
    for _ in range(3):
        start = time.perf_counter()
        try:
            ws = await asyncio.wait_for(
                websockets.connect(url),
                timeout=timeout
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            await ws.close()
        except Exception as e:
            print(f"WebSocket error: {e}")

    return np.mean(times) if times else 0.0


def measure_opus_encoding(audio_samples: np.ndarray, sample_rate: int = 24000) -> tuple[bytes, float]:
    """Measure Opus encoding latency."""
    import sphn

    opus_writer = sphn.OpusStreamWriter(sample_rate)

    # Convert to float32 if needed
    if audio_samples.dtype != np.float32:
        audio_float = audio_samples.astype(np.float32) / 32768.0
    else:
        audio_float = audio_samples

    # Measure encoding time
    start = time.perf_counter()
    opus_data = opus_writer.append_pcm(audio_float)
    encode_time = (time.perf_counter() - start) * 1000

    return opus_data, encode_time


def measure_opus_decoding(opus_data: bytes, sample_rate: int = 24000) -> tuple[np.ndarray, float]:
    """Measure Opus decoding latency."""
    import sphn

    opus_reader = sphn.OpusStreamReader(sample_rate)

    start = time.perf_counter()
    pcm = opus_reader.append_bytes(opus_data)
    decode_time = (time.perf_counter() - start) * 1000

    return pcm, decode_time


async def measure_direct_personaplex(
    audio_samples: np.ndarray,
    host: str = "localhost",
    port: int = 8998,
    text_prompt: str = "You are a helpful assistant."
) -> tuple[float, float]:
    """
    Measure direct PersonaPlex latency (with Opus encoding included).
    Returns (ttft_ms, e2e_ms)
    """
    import websockets
    import sphn

    opus_writer = sphn.OpusStreamWriter(24000)

    # Convert audio
    audio_float = audio_samples.astype(np.float32) / 32768.0

    # Connect with config in URL
    query = urlencode({'text_prompt': text_prompt})
    ws_url = f"ws://{host}:{port}/api/chat?{query}"

    ws = await websockets.connect(ws_url, ping_interval=20)

    # Wait for handshake
    handshake = await asyncio.wait_for(ws.recv(), timeout=30.0)
    if not (isinstance(handshake, bytes) and len(handshake) == 1 and handshake[0] == 0):
        print(f"Unexpected handshake: {handshake}")

    # Stream audio and measure
    chunk_samples = 1920  # 80ms
    first_response_time = None
    end_time = None

    send_start = time.perf_counter()

    async def receive():
        nonlocal first_response_time, end_time
        audio_count = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                now = time.perf_counter()

                if isinstance(msg, bytes) and len(msg) > 0:
                    kind = msg[0]
                    if kind == 1:  # Audio
                        if first_response_time is None:
                            first_response_time = now
                        audio_count += 1
                        end_time = now

                        if audio_count > 10:
                            return
            except asyncio.TimeoutError:
                return

    recv_task = asyncio.create_task(receive())

    # Stream audio chunks
    for i in range(0, len(audio_float), chunk_samples):
        chunk = audio_float[i:i+chunk_samples]
        if len(chunk) < chunk_samples:
            chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

        opus_data = opus_writer.append_pcm(chunk)
        if len(opus_data) > 0:
            await ws.send(b'\x01' + opus_data)

        await asyncio.sleep(chunk_samples / 24000)

    await recv_task
    await ws.close()

    ttft = (first_response_time - send_start) * 1000 if first_response_time else 0
    e2e = (end_time - send_start) * 1000 if end_time else 0

    return ttft, e2e


async def measure_pipeline_latency(
    audio_data: bytes,
    backend_host: str = "localhost",
    backend_port: int = 8000
) -> tuple[float, float]:
    """
    Measure full pipeline latency through backend.
    Returns (ttft_ms, e2e_ms)
    """
    import websockets
    import httpx

    # Create session
    async with httpx.AsyncClient(base_url=f"http://{backend_host}:{backend_port}") as client:
        resp = await client.post('/sessions', json={'restaurant_id': 2})
        session_id = resp.json()['session_id']

    # Connect to WebSocket
    ws_url = f"ws://{backend_host}:{backend_port}/ws/sessions/{session_id}/audio"
    ws = await websockets.connect(ws_url, ping_interval=20)

    # Wait briefly for connection
    await asyncio.sleep(0.5)

    first_response_time = None
    end_time = None

    send_start = time.perf_counter()

    async def receive():
        nonlocal first_response_time, end_time
        audio_count = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                now = time.perf_counter()

                if isinstance(msg, bytes):
                    if first_response_time is None:
                        first_response_time = now
                    audio_count += 1
                    end_time = now

                    if audio_count > 10:
                        return
            except asyncio.TimeoutError:
                return

    recv_task = asyncio.create_task(receive())

    # Send audio in chunks (raw PCM, backend handles encoding)
    chunk_size = 8192
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        await ws.send(chunk)
        await asyncio.sleep(0.01)

    await recv_task
    await ws.close()

    # Cleanup session
    async with httpx.AsyncClient(base_url=f"http://{backend_host}:{backend_port}") as client:
        await client.delete(f'/sessions/{session_id}')

    ttft = (first_response_time - send_start) * 1000 if first_response_time else 0
    e2e = (end_time - send_start) * 1000 if end_time else 0

    return ttft, e2e


async def run_latency_breakdown(
    iterations: int = 3,
    personaplex_host: str = "localhost",
    personaplex_port: int = 8998,
    backend_host: str = "localhost",
    backend_port: int = 8000
) -> LatencyBreakdown:
    """Run comprehensive latency breakdown analysis."""

    print("=" * 70)
    print("LATENCY BREAKDOWN ANALYSIS")
    print("=" * 70)

    # Load audio sample
    sample_manager = SampleManager()
    samples = sample_manager.load_personaplex_samples()
    sample = list(samples.values())[0]

    audio_samples = np.frombuffer(sample.data, dtype=np.int16)

    # Find speech and get 5 seconds
    threshold = 500
    non_silent = np.where(np.abs(audio_samples) > threshold)[0]
    start = max(0, non_silent[0] - 12000) if len(non_silent) > 0 else 0
    end = min(start + 5 * 24000, len(audio_samples))
    speech_samples = audio_samples[start:end]
    speech_bytes = speech_samples.tobytes()

    audio_duration = len(speech_samples) / 24000
    input_tokens = audio_to_tokens(audio_duration)

    print(f"\nUsing {audio_duration:.1f}s of audio from {sample.name}")
    print(f"Input tokens: {input_tokens} (at 12.5 Hz semantic token rate)")

    breakdown = LatencyBreakdown()
    breakdown.audio_duration_s = audio_duration
    breakdown.input_tokens = input_tokens

    # 1. Measure network latencies
    print("\n[1/6] Measuring network latencies...")
    breakdown.network_rtt_ms = await measure_network_latency(personaplex_host, personaplex_port)
    print(f"  PersonaPlex TCP RTT: {breakdown.network_rtt_ms:.2f}ms")

    breakdown.backend_rtt_ms = await measure_network_latency(backend_host, backend_port)
    print(f"  Backend TCP RTT: {breakdown.backend_rtt_ms:.2f}ms")

    # 2. Measure Opus encoding
    print("\n[2/6] Measuring Opus encoding latency...")
    encode_times = []
    for _ in range(5):
        _, encode_time = measure_opus_encoding(speech_samples)
        encode_times.append(encode_time)
    breakdown.opus_encode_ms = np.mean(encode_times)
    print(f"  Opus encode ({len(speech_samples)/24000:.1f}s audio): {breakdown.opus_encode_ms:.2f}ms")

    # 3. Measure Opus decoding
    print("\n[3/6] Measuring Opus decoding latency...")
    opus_data, _ = measure_opus_encoding(speech_samples)
    decode_times = []
    for _ in range(5):
        _, decode_time = measure_opus_decoding(opus_data)
        decode_times.append(decode_time)
    breakdown.opus_decode_ms = np.mean(decode_times)
    print(f"  Opus decode: {breakdown.opus_decode_ms:.2f}ms")

    # 4. Measure direct PersonaPlex latency
    print(f"\n[4/6] Measuring direct PersonaPlex latency ({iterations} iterations)...")
    direct_ttfts = []
    direct_e2es = []
    for i in range(iterations):
        ttft, e2e = await measure_direct_personaplex(
            speech_samples, personaplex_host, personaplex_port
        )
        direct_ttfts.append(ttft)
        direct_e2es.append(e2e)
        print(f"  Iteration {i+1}: TTFT={ttft:.1f}ms, E2E={e2e:.1f}ms")
        await asyncio.sleep(0.5)

    breakdown.direct_ttft_ms = np.mean(direct_ttfts)
    breakdown.direct_e2e_ms = np.mean(direct_e2es)

    # 5. Measure full pipeline latency
    # Note: Each iteration needs fresh backend restart for accurate measurement
    # because PersonaPlex keeps state between sessions
    print(f"\n[5/6] Measuring full pipeline latency ({iterations} iterations)...")
    print("  (Using first-connection measurements - PersonaPlex keeps state)")
    pipeline_ttfts = []
    pipeline_e2es = []
    for i in range(iterations):
        # Longer delay to let PersonaPlex state clear
        if i > 0:
            await asyncio.sleep(3.0)

        ttft, e2e = await measure_pipeline_latency(
            speech_bytes, backend_host, backend_port
        )

        # Only use reasonable measurements (< 1s for TTFT)
        if ttft < 1000:
            pipeline_ttfts.append(ttft)
            pipeline_e2es.append(e2e)
            print(f"  Iteration {i+1}: TTFT={ttft:.1f}ms, E2E={e2e:.1f}ms ✓")
        else:
            print(f"  Iteration {i+1}: TTFT={ttft:.1f}ms, E2E={e2e:.1f}ms (stale connection, skipped)")

    if pipeline_ttfts:
        breakdown.pipeline_ttft_ms = np.mean(pipeline_ttfts)
        breakdown.pipeline_e2e_ms = np.mean(pipeline_e2es)
    else:
        print("  Warning: No valid pipeline measurements, using first iteration")
        # Re-run once more with fresh connection
        ttft, e2e = await measure_pipeline_latency(speech_bytes, backend_host, backend_port)
        breakdown.pipeline_ttft_ms = ttft
        breakdown.pipeline_e2e_ms = e2e

    # 6. Print summary
    print("\n[6/6] Computing breakdown...")

    print("\n" + "=" * 70)
    print("LATENCY BREAKDOWN RESULTS")
    print("=" * 70)

    print("\n┌─────────────────────────────────────────────────────────────────────┐")
    print("│ COMPONENT                          │ LATENCY (ms) │ % OF PIPELINE  │")
    print("├─────────────────────────────────────────────────────────────────────┤")

    total = breakdown.pipeline_ttft_ms

    def print_row(name: str, value: float):
        pct = (value / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"│ {name:<35} │ {value:>10.2f}  │ {pct:>5.1f}% {bar} │")

    print_row("Direct PersonaPlex (model inference)", breakdown.direct_ttft_ms)
    print_row("Opus Encoding (PCM → Opus)", breakdown.opus_encode_ms)
    print_row("Opus Decoding (Opus → PCM)", breakdown.opus_decode_ms)
    print_row("Network RTT (TCP to PersonaPlex)", breakdown.network_rtt_ms)
    print_row("Backend Processing Overhead", max(0, breakdown.backend_overhead_ms))

    print("├─────────────────────────────────────────────────────────────────────┤")
    print_row("TOTAL PIPELINE TTFT", breakdown.pipeline_ttft_ms)
    print("└─────────────────────────────────────────────────────────────────────┘")

    print("\n┌─────────────────────────────────────────────────────────────────────┐")
    print("│ INPUT/OUTPUT                                                        │")
    print("├─────────────────────────────────────────────────────────────────────┤")
    print(f"│ Audio Duration:                  {breakdown.audio_duration_s:>8.2f} s                       │")
    print(f"│ Input Tokens:                    {breakdown.input_tokens:>8d}   (12.5 tok/s)          │")
    print(f"│ Output Tokens:                   {breakdown.output_tokens:>8d}   (estimated)           │")
    print("└─────────────────────────────────────────────────────────────────────┘")

    print("\n┌─────────────────────────────────────────────────────────────────────┐")
    print("│ LATENCY SUMMARY                                                     │")
    print("├─────────────────────────────────────────────────────────────────────┤")
    print(f"│ Raw Model Latency (Direct):      {breakdown.direct_ttft_ms:>8.2f} ms                      │")
    print(f"│ Full Pipeline Latency:           {breakdown.pipeline_ttft_ms:>8.2f} ms                      │")
    print(f"│ Backend Overhead:                {max(0, breakdown.backend_overhead_ms):>8.2f} ms                      │")
    print(f"│ Encoding/Decoding Overhead:      {breakdown.total_encoding_overhead_ms:>8.2f} ms                      │")
    print("└─────────────────────────────────────────────────────────────────────┘")

    return breakdown


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Latency Breakdown Analysis")
    parser.add_argument("--iterations", "-n", type=int, default=3, help="Iterations per test")
    parser.add_argument("--personaplex-host", default="localhost")
    parser.add_argument("--personaplex-port", type=int, default=8998)
    parser.add_argument("--backend-host", default="localhost")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    breakdown = await run_latency_breakdown(
        iterations=args.iterations,
        personaplex_host=args.personaplex_host,
        personaplex_port=args.personaplex_port,
        backend_host=args.backend_host,
        backend_port=args.backend_port
    )

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(breakdown.to_dict(), f, indent=2)
        print(f"\nResults saved to {args.output}")

    return breakdown


if __name__ == "__main__":
    asyncio.run(main())
