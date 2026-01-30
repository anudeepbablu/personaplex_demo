#!/usr/bin/env python3
"""
PersonaPlex Benchmark Runner

Comprehensive benchmark suite for measuring PersonaPlex performance:
- Time to First Token (TTFT)
- Inter-token Latency (ITL)
- Tokens Per Second (TPS)
- Turn-Taking Latency (Full-Duplex specific)
- End-to-End Request Latency

Usage:
    python run_benchmark.py --mode text --iterations 100
    python run_benchmark.py --mode audio --iterations 50
    python run_benchmark.py --mode full --output report.json
    python run_benchmark.py --mock  # Use mock client for testing
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add benchmark directory to path for imports
BENCHMARK_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BENCHMARK_DIR))

from core import (
    PersonaPlexConfig,
    PersonaPlexBenchmarkClient,
    MockPersonaPlexClient,
    BenchmarkResult,
    SystemMetricsCollector,
    print_gpu_info,
    PipelineConfig,
    PipelineBenchmarkClient,
    check_backend_health,
    DirectConfig,
    DirectBenchmarkClient,
    check_personaplex_health,
)
from audio import TurnTakingBenchmark, AudioGenerator, SampleManager, print_sample_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Test prompts for text benchmarking
TEST_PROMPTS = [
    "Hello, I'd like to make a reservation.",
    "What time do you open tomorrow?",
    "Do you have any vegetarian options on the menu?",
    "I need a table for 4 people at 7 PM.",
    "What's your most popular dish?",
    "Can I modify my existing reservation?",
    "Do you have outdoor seating available?",
    "What are your specials today?",
    "Is there parking available nearby?",
    "Can you accommodate food allergies?",
]

SYSTEM_PROMPT = """You are a friendly restaurant receptionist for Tony's Pizzeria.
Help customers with reservations, menu questions, and general inquiries.
Keep responses concise and helpful."""


async def run_text_benchmark(
    client,
    num_iterations: int,
    prompts: list = None
) -> BenchmarkResult:
    """
    Run text-based latency benchmark.

    Measures TTFT, ITL, and TPS for text responses.
    """
    prompts = prompts or TEST_PROMPTS

    result = BenchmarkResult(
        name="PersonaPlex Text Latency Benchmark",
        description=f"Text response latency over {num_iterations} requests",
        start_time=datetime.utcnow(),
        config={
            "num_iterations": num_iterations,
            "num_prompts": len(prompts),
            "system_prompt_length": len(SYSTEM_PROMPT),
        }
    )

    logger.info(f"Starting text benchmark with {num_iterations} iterations")

    for i in range(num_iterations):
        prompt = prompts[i % len(prompts)]

        logger.info(f"Request {i + 1}/{num_iterations}: {prompt[:50]}...")

        metrics = await client.benchmark_text_response(
            request_id=f"text_{i}",
            text_prompt=SYSTEM_PROMPT,
            user_input=prompt,
            on_token=lambda t: None  # Suppress token output
        )

        result.add_request(metrics)

        if metrics.success:
            logger.info(
                f"  TTFT: {metrics.ttft * 1000:.1f}ms, "
                f"Tokens: {metrics.output_tokens}, "
                f"TPS: {metrics.tps:.1f}"
            )
        else:
            logger.warning(f"  Request failed: {metrics.error}")

    result.compute_aggregates()
    return result


async def run_audio_benchmark(
    client,
    num_iterations: int,
    use_real_samples: bool = True
) -> BenchmarkResult:
    """
    Run audio-based latency benchmark.

    Measures turn-taking latency and audio response times.
    Uses real audio samples from PersonaPlex repository when available.

    Args:
        client: Benchmark client
        num_iterations: Number of test iterations
        use_real_samples: If True, download and use PersonaPlex test audio files
    """
    audio_gen = AudioGenerator()
    sample_manager = SampleManager()

    # Try to load real audio samples
    real_samples = []
    system_prompt = SYSTEM_PROMPT

    if use_real_samples:
        logger.info("Loading PersonaPlex test audio samples...")
        try:
            samples = sample_manager.load_personaplex_samples()
            real_samples = list(samples.values())

            # Load the service prompt if available
            prompts = sample_manager.load_personaplex_prompts()
            if "prompt_service" in prompts:
                system_prompt = prompts["prompt_service"]
                logger.info("Using PersonaPlex service prompt")

            if real_samples:
                logger.info(f"Loaded {len(real_samples)} real audio samples:")
                for sample in real_samples:
                    print_sample_info(sample)
            else:
                logger.warning("No real samples loaded, falling back to synthetic audio")

        except Exception as e:
            logger.warning(f"Failed to load real samples: {e}")
            logger.info("Falling back to synthetic audio generation")

    result = BenchmarkResult(
        name="PersonaPlex Audio Latency Benchmark",
        description=f"Audio turn-taking latency over {num_iterations} requests",
        start_time=datetime.utcnow(),
        config={
            "num_iterations": num_iterations,
            "sample_rate": 24000,
            "use_real_samples": bool(real_samples),
            "num_real_samples": len(real_samples),
        }
    )

    logger.info(f"Starting audio benchmark with {num_iterations} iterations")

    for i in range(num_iterations):
        # Use real sample if available, otherwise generate synthetic
        if real_samples:
            sample = real_samples[i % len(real_samples)]
            audio_data = sample.data
            audio_duration = sample.duration_seconds
            sample_name = sample.name
        else:
            audio_duration = 1.5 + (i % 3) * 0.5  # Vary duration
            audio_data = audio_gen.generate_speech_like(audio_duration)
            sample_name = "synthetic"

        logger.info(f"Request {i + 1}/{num_iterations}: {sample_name} ({audio_duration:.2f}s)")

        metrics = await client.benchmark_audio_latency(
            request_id=f"audio_{i}",
            audio_data=audio_data,
            text_prompt=system_prompt
        )

        result.add_request(metrics)

        if metrics.success:
            logger.info(
                f"  Turn-taking: {metrics.turn_taking_latency * 1000:.1f}ms, "
                f"Tokens: {metrics.output_tokens}"
            )
        else:
            logger.warning(f"  Request failed: {metrics.error}")

    result.compute_aggregates()
    return result


async def run_turn_taking_benchmark(client, num_iterations: int) -> dict:
    """Run dedicated turn-taking benchmark."""
    benchmark = TurnTakingBenchmark(client)
    results = await benchmark.run_full_benchmark(
        smooth_iterations=num_iterations,
        interrupt_iterations=num_iterations // 2
    )
    benchmark.print_report()
    return results


async def run_pipeline_benchmark(
    config: PipelineConfig,
    num_iterations: int,
    collect_system_metrics: bool = True
) -> dict:
    """
    Run full pipeline benchmark through the backend.

    Tests: Client → Backend → PersonaPlex → Backend → Client
    Uses real audio samples from PersonaPlex repository.
    """
    sample_manager = SampleManager()
    system_collector = None

    # Check backend health first
    logger.info("Checking backend health...")
    health = await check_backend_health(config)
    logger.info(f"Backend health: {health}")

    if health.get("error"):
        logger.error(f"Backend not available: {health['error']}")
        return {"error": health["error"]}

    # Load real audio samples
    logger.info("Loading PersonaPlex test audio samples...")
    samples = sample_manager.load_personaplex_samples()
    real_samples = list(samples.values())

    if not real_samples:
        logger.error("No audio samples available")
        return {"error": "No audio samples"}

    logger.info(f"Loaded {len(real_samples)} audio samples")
    for sample in real_samples:
        print_sample_info(sample)

    # Initialize system metrics collector
    if collect_system_metrics:
        system_collector = SystemMetricsCollector(sample_interval=0.5)
        print_gpu_info()
        initial_snapshot = system_collector.get_current_snapshot()

    # Create benchmark result
    result = BenchmarkResult(
        name="PersonaPlex Full Pipeline Benchmark",
        description=f"End-to-end pipeline latency over {num_iterations} requests",
        start_time=datetime.utcnow(),
        config={
            "num_iterations": num_iterations,
            "backend_url": config.base_url,
            "personaplex_connected": health.get("personaplex_running", False),
            "mode": health.get("mode", "unknown"),
            "num_samples": len(real_samples),
        }
    )

    results = {
        "benchmark": "pipeline",
        "start_time": datetime.utcnow().isoformat(),
        "backend_health": health,
    }

    if collect_system_metrics and initial_snapshot:
        results["system_info"] = {
            "gpus": initial_snapshot.get("gpus", []),
            "initial_state": initial_snapshot
        }

    # Start metrics collection
    if system_collector:
        system_collector.start()

    # Create client and run benchmark
    client = PipelineBenchmarkClient(config)

    try:
        connected = await client.connect()
        if not connected:
            logger.error("Failed to connect to pipeline")
            return {"error": "Connection failed"}

        logger.info(f"\nStarting pipeline benchmark with {num_iterations} iterations")
        logger.info("=" * 60)

        for i in range(num_iterations):
            # Cycle through available samples
            sample = real_samples[i % len(real_samples)]

            logger.info(f"Request {i + 1}/{num_iterations}: {sample.name} ({sample.duration_seconds:.1f}s)")

            metrics = await client.benchmark_audio_response(
                request_id=f"pipeline_{i}",
                audio_data=sample.data,
                on_text=lambda t: None  # Suppress output
            )

            result.add_request(metrics)

            if metrics.success:
                ttl = metrics.turn_taking_latency * 1000 if metrics.turn_taking_latency else 0
                logger.info(
                    f"  Turn-taking: {ttl:.1f}ms, "
                    f"TTFT: {metrics.ttft * 1000:.1f}ms, "
                    f"Tokens: {metrics.output_tokens}"
                )
            else:
                logger.warning(f"  Request failed: {metrics.error}")

        result.compute_aggregates()
        results["benchmark_results"] = result.to_dict()

        # Print summary
        result.print_summary()

    finally:
        await client.disconnect()

        # Stop metrics collection
        if system_collector:
            metrics_summary = system_collector.stop()
            results["system_metrics"] = metrics_summary.to_dict()
            print_system_metrics_summary(metrics_summary)

    results["end_time"] = datetime.utcnow().isoformat()

    return results


async def run_direct_benchmark(
    config: DirectConfig,
    num_iterations: int = 5,
    collect_system_metrics: bool = True
) -> dict:
    """
    Run direct PersonaPlex benchmark (bypassing backend).

    Connects directly to PersonaPlex to measure raw model latency
    without backend overhead.
    """
    sample_manager = SampleManager()
    system_collector = None

    # Check PersonaPlex health
    logger.info("Checking PersonaPlex health...")
    health = await check_personaplex_health(config)
    logger.info(f"PersonaPlex health: {health}")

    if health.get("status") != "healthy":
        logger.error(f"PersonaPlex not healthy: {health}")
        return {"error": health.get("error", "PersonaPlex unhealthy")}

    # Load audio samples
    logger.info("Loading PersonaPlex test audio samples...")
    samples = sample_manager.load_personaplex_samples()
    real_samples = list(samples.values())

    if not real_samples:
        logger.error("No audio samples available")
        return {"error": "No audio samples"}

    logger.info(f"Loaded {len(real_samples)} audio samples")
    for sample in real_samples:
        print_sample_info(sample)

    # Initialize system metrics
    if collect_system_metrics:
        system_collector = SystemMetricsCollector(sample_interval=0.5)
        print_gpu_info()
        initial_snapshot = system_collector.get_current_snapshot()

    # Create benchmark result
    result = BenchmarkResult(
        name="PersonaPlex Direct Benchmark",
        description=f"Direct PersonaPlex latency (no backend) over {num_iterations} requests",
        start_time=datetime.utcnow(),
        config={
            "num_iterations": num_iterations,
            "personaplex_url": config.ws_url,
            "mode": "direct",
            "num_samples": len(real_samples),
        }
    )

    results = {
        "benchmark": "direct",
        "start_time": datetime.utcnow().isoformat(),
        "personaplex_health": health,
    }

    if collect_system_metrics and initial_snapshot:
        results["system_info"] = {
            "gpus": initial_snapshot.get("gpus", []),
            "initial_state": initial_snapshot
        }

    # Start metrics collection
    if system_collector:
        system_collector.start()

    # Create direct client
    client = DirectBenchmarkClient(config)

    try:
        connected = await client.connect()
        if not connected:
            logger.error("Failed to connect to PersonaPlex")
            return {"error": "Connection failed"}

        logger.info(f"\nStarting direct benchmark with {num_iterations} iterations")
        logger.info("=" * 60)

        for i in range(num_iterations):
            sample = real_samples[i % len(real_samples)]

            logger.info(f"Request {i + 1}/{num_iterations}: {sample.name} ({sample.duration_seconds:.1f}s)")

            metrics = await client.benchmark_audio_response(
                request_id=f"direct_{i}",
                audio_data=sample.data,
                on_text=lambda t: None
            )

            result.add_request(metrics)

            if metrics.success:
                ttl = metrics.turn_taking_latency * 1000 if metrics.turn_taking_latency else 0
                logger.info(
                    f"  Turn-taking: {ttl:.1f}ms, "
                    f"TTFT: {metrics.ttft * 1000:.1f}ms, "
                    f"Tokens: {metrics.output_tokens}"
                )
            else:
                logger.warning(f"  Request failed: {metrics.error}")

            # Reconnect for next iteration (PersonaPlex needs fresh connection)
            await client.disconnect()
            if i < num_iterations - 1:
                await asyncio.sleep(0.5)
                await client.connect()

        result.compute_aggregates()
        results["benchmark_results"] = result.to_dict()

        result.print_summary()

    finally:
        await client.disconnect()

        if system_collector:
            metrics_summary = system_collector.stop()
            results["system_metrics"] = metrics_summary.to_dict()
            print_system_metrics_summary(metrics_summary)

    results["end_time"] = datetime.utcnow().isoformat()

    return results


async def run_throughput_benchmark(
    client,
    duration_seconds: int = 60,
    concurrency: int = 1
) -> dict:
    """
    Run throughput benchmark.

    Measures sustained tokens per second over a time period.
    """
    logger.info(f"Starting throughput benchmark: {duration_seconds}s, concurrency={concurrency}")

    results = {
        "benchmark": "throughput",
        "duration_seconds": duration_seconds,
        "concurrency": concurrency,
        "start_time": datetime.utcnow().isoformat(),
    }

    start_time = datetime.utcnow()
    total_tokens = 0
    total_requests = 0
    request_id = 0

    end_time = asyncio.get_event_loop().time() + duration_seconds

    async def worker():
        nonlocal total_tokens, total_requests, request_id

        while asyncio.get_event_loop().time() < end_time:
            prompt = TEST_PROMPTS[request_id % len(TEST_PROMPTS)]
            metrics = await client.benchmark_text_response(
                request_id=f"throughput_{request_id}",
                text_prompt=SYSTEM_PROMPT,
                user_input=prompt
            )

            if metrics.success:
                total_tokens += metrics.output_tokens
                total_requests += 1

            request_id += 1

    # Run concurrent workers
    workers = [worker() for _ in range(concurrency)]
    await asyncio.gather(*workers)

    elapsed = (datetime.utcnow() - start_time).total_seconds()

    results["end_time"] = datetime.utcnow().isoformat()
    results["actual_duration_seconds"] = elapsed
    results["total_requests"] = total_requests
    results["total_tokens"] = total_tokens
    results["tokens_per_second"] = total_tokens / elapsed if elapsed > 0 else 0
    results["tokens_per_minute"] = results["tokens_per_second"] * 60
    results["requests_per_second"] = total_requests / elapsed if elapsed > 0 else 0

    logger.info(f"Throughput results:")
    logger.info(f"  Requests: {total_requests}")
    logger.info(f"  Tokens: {total_tokens}")
    logger.info(f"  TPS: {results['tokens_per_second']:.2f}")
    logger.info(f"  RPS: {results['requests_per_second']:.4f}")

    return results


async def run_full_benchmark(
    client,
    text_iterations: int,
    audio_iterations: int,
    collect_system_metrics: bool = True
) -> dict:
    """Run complete benchmark suite with system metrics collection."""
    # Initialize system metrics collector
    system_collector = None
    if collect_system_metrics:
        system_collector = SystemMetricsCollector(sample_interval=1.0)

        # Print GPU info at start
        print_gpu_info()

        # Get initial system snapshot
        initial_snapshot = system_collector.get_current_snapshot()

    results = {
        "benchmark_suite": "PersonaPlex Full Benchmark",
        "start_time": datetime.utcnow().isoformat(),
    }

    # Add initial system info
    if collect_system_metrics and initial_snapshot:
        results["system_info"] = {
            "gpus": initial_snapshot.get("gpus", []),
            "initial_state": initial_snapshot
        }

    # Start metrics collection
    if system_collector:
        system_collector.start()

    try:
        # Text benchmark
        logger.info("\n" + "=" * 60)
        logger.info("RUNNING TEXT BENCHMARK")
        logger.info("=" * 60)
        text_result = await run_text_benchmark(client, text_iterations)
        results["text_benchmark"] = text_result.to_dict()

        # Audio benchmark
        logger.info("\n" + "=" * 60)
        logger.info("RUNNING AUDIO BENCHMARK")
        logger.info("=" * 60)
        audio_result = await run_audio_benchmark(client, audio_iterations)
        results["audio_benchmark"] = audio_result.to_dict()

        # Turn-taking benchmark
        logger.info("\n" + "=" * 60)
        logger.info("RUNNING TURN-TAKING BENCHMARK")
        logger.info("=" * 60)
        turn_taking_result = await run_turn_taking_benchmark(client, audio_iterations)
        results["turn_taking_benchmark"] = turn_taking_result

    finally:
        # Stop metrics collection and get summary
        if system_collector:
            metrics_summary = system_collector.stop()
            results["system_metrics"] = metrics_summary.to_dict()

            # Print system metrics summary
            print_system_metrics_summary(metrics_summary)

    results["end_time"] = datetime.utcnow().isoformat()

    return results


def print_system_metrics_summary(summary):
    """Print system metrics summary to console."""
    print("\n" + "=" * 60)
    print("SYSTEM METRICS SUMMARY")
    print("=" * 60)

    if summary.gpu_info:
        for i, gpu in enumerate(summary.gpu_info):
            print(f"\nGPU {gpu.index}: {gpu.name}")
            print(f"  Memory Total:      {gpu.memory_total_mb:,} MB")

            if i < len(summary.gpu_utilization_mean):
                print(f"  GPU Utilization:   {summary.gpu_utilization_mean[i]:.1f}% (mean), "
                      f"{summary.gpu_utilization_max[i]:.1f}% (max)")
                print(f"  Memory Used:       {summary.gpu_memory_used_mean_mb[i]:,.0f} MB (mean), "
                      f"{summary.gpu_memory_used_max_mb[i]:,.0f} MB (max)")
                print(f"  Memory Utilization: {summary.gpu_memory_percent_mean[i]:.1f}% (mean)")
                print(f"  Temperature:       {summary.gpu_temperature_mean_c[i]:.1f}°C (mean), "
                      f"{summary.gpu_temperature_max_c[i]}°C (max)")
                print(f"  Power Draw:        {summary.gpu_power_draw_mean_w[i]:.1f}W (mean), "
                      f"{summary.gpu_power_draw_max_w[i]:.1f}W (max)")
    else:
        print("\nNo GPU metrics collected")

    print(f"\nSystem:")
    print(f"  CPU Usage:         {summary.cpu_percent_mean:.1f}% (mean), "
          f"{summary.cpu_percent_max:.1f}% (max)")
    print(f"  Memory Used:       {summary.memory_used_mean_mb:,.0f} MB (mean), "
          f"{summary.memory_used_max_mb:,} MB (max)")
    print(f"  Samples Collected: {summary.sample_count}")
    print("=" * 60)


def save_results(results: dict, output_path: str):
    """Save benchmark results to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Results saved to: {path}")


def print_summary(result: BenchmarkResult):
    """Print benchmark summary."""
    result.print_summary()


async def main():
    parser = argparse.ArgumentParser(
        description="PersonaPlex Performance Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_benchmark.py --mode text --iterations 100
  python run_benchmark.py --mode audio --iterations 50
  python run_benchmark.py --mode full --output results/benchmark.json
  python run_benchmark.py --mock --mode text  # Test with mock client
  python run_benchmark.py --mode pipeline --iterations 10  # Full pipeline test
        """
    )

    parser.add_argument(
        "--mode",
        choices=["text", "audio", "turn_taking", "throughput", "full", "pipeline", "direct"],
        default="text",
        help="Benchmark mode. 'direct' connects directly to PersonaPlex (no backend), 'pipeline' goes through backend."
    )

    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=10,
        help="Number of iterations (default: 10)"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="PersonaPlex server host (default: localhost)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8998,
        help="PersonaPlex server port (default: 8998)"
    )

    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Backend server port for pipeline mode (default: 8000)"
    )

    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Use SSL/TLS connection"
    )

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock client (for testing without server)"
    )

    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path for JSON results"
    )

    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=1,
        help="Concurrency level for throughput tests (default: 1)"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds for throughput tests (default: 60)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic audio instead of real PersonaPlex test samples"
    )

    parser.add_argument(
        "--download-samples",
        action="store_true",
        help="Download PersonaPlex test audio samples and exit"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle download-samples command
    if args.download_samples:
        logger.info("Downloading PersonaPlex test audio samples...")
        sample_manager = SampleManager()
        if sample_manager.download_all_test_files():
            logger.info("All samples downloaded successfully!")
            samples = sample_manager.load_personaplex_samples()
            for sample in samples.values():
                print_sample_info(sample)
        else:
            logger.error("Some downloads failed")
            sys.exit(1)
        return

    # Handle pipeline mode separately (uses backend, not direct PersonaPlex)
    if args.mode == "pipeline":
        logger.info("Running full pipeline benchmark through backend")

        pipeline_config = PipelineConfig(
            backend_host=args.host,
            backend_port=args.backend_port,
            use_ssl=args.ssl,
        )

        result = await run_pipeline_benchmark(
            pipeline_config,
            num_iterations=args.iterations,
            collect_system_metrics=True
        )

        if args.output:
            save_results(result, args.output)
        else:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            save_results(result, f"reports/pipeline_benchmark_{timestamp}.json")

        logger.info("Pipeline benchmark complete!")
        return

    # Handle direct mode (connects directly to PersonaPlex, bypassing backend)
    if args.mode == "direct":
        logger.info("Running direct PersonaPlex benchmark (no backend)")

        direct_config = DirectConfig(
            host=args.host,
            port=args.port,
            use_ssl=args.ssl,
            text_prompt=SYSTEM_PROMPT,
        )

        result = await run_direct_benchmark(
            direct_config,
            num_iterations=args.iterations,
            collect_system_metrics=True
        )

        if args.output:
            save_results(result, args.output)
        else:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            save_results(result, f"reports/direct_benchmark_{timestamp}.json")

        logger.info("Direct benchmark complete!")
        return

    # Create client for other PersonaPlex benchmarks
    config = PersonaPlexConfig(
        host=args.host,
        port=args.port,
        use_ssl=args.ssl,
    )

    if args.mock:
        logger.info("Using mock client")
        client = MockPersonaPlexClient(config)
    else:
        logger.info(f"Connecting to PersonaPlex at {config.ws_url}")
        client = PersonaPlexBenchmarkClient(config)

    # Connect
    connected = await client.connect()
    if not connected and not args.mock:
        logger.error("Failed to connect to PersonaPlex server")
        logger.info("Use --mock to test with mock client")
        sys.exit(1)

    try:
        # Run benchmark based on mode
        if args.mode == "text":
            result = await run_text_benchmark(client, args.iterations)
            print_summary(result)
            if args.output:
                save_results(result.to_dict(), args.output)

        elif args.mode == "audio":
            result = await run_audio_benchmark(
                client,
                args.iterations,
                use_real_samples=not args.synthetic
            )
            print_summary(result)
            if args.output:
                save_results(result.to_dict(), args.output)

        elif args.mode == "turn_taking":
            result = await run_turn_taking_benchmark(client, args.iterations)
            if args.output:
                save_results(result, args.output)

        elif args.mode == "throughput":
            result = await run_throughput_benchmark(
                client,
                duration_seconds=args.duration,
                concurrency=args.concurrency
            )
            if args.output:
                save_results(result, args.output)

        elif args.mode == "full":
            result = await run_full_benchmark(
                client,
                text_iterations=args.iterations,
                audio_iterations=args.iterations // 2
            )
            if args.output:
                save_results(result, args.output)
            else:
                # Save to default location
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                save_results(result, f"reports/benchmark_{timestamp}.json")

    finally:
        await client.disconnect()

    logger.info("Benchmark complete!")


if __name__ == "__main__":
    asyncio.run(main())
