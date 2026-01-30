# PersonaPlex Benchmark Suite

Performance benchmarking tools for PersonaPlex speech-to-speech model.

## Metrics

Based on NVIDIA LLM benchmarking standards and FullDuplexBench methodology:

### Latency Metrics
- **TTFT (Time to First Token)**: Time from request sent to first token received
- **ITL (Inter-token Latency)**: Average time between consecutive tokens
- **E2E Latency**: Total time from request to response completion
- **Turn-Taking Latency**: Time from user stops speaking to agent starts (target: 170-270ms)

### Throughput Metrics
- **TPS (Tokens Per Second)**: Output token generation rate
- **RPS (Requests Per Second)**: Request handling rate

## Audio Test Samples

The benchmark uses **real audio files** from the official PersonaPlex repository:
- `input_assistant.wav` - 40s assistant voice test
- `input_service.wav` - 20s service scenario test
- `prompt_service.txt` - SwiftPlex Appliances service prompt

Files are automatically downloaded and cached in `audio/samples/`.

## Usage

### Download Test Samples
```bash
cd benchmark
python run_benchmark.py --download-samples
```

### Quick Test (Mock Client)
```bash
python run_benchmark.py --mock --mode text --iterations 10
```

### Text Latency Benchmark
```bash
python run_benchmark.py --mode text --iterations 100 --output reports/text_benchmark.json
```

### Audio/Turn-Taking Benchmark (Real Samples)
```bash
python run_benchmark.py --mode audio --iterations 50
python run_benchmark.py --mode turn_taking --iterations 20
```

### Audio Benchmark with Synthetic Audio
```bash
python run_benchmark.py --mode audio --iterations 50 --synthetic
```

### Full Benchmark Suite
```bash
python run_benchmark.py --mode full --iterations 100 --output reports/full_benchmark.json
```

### Throughput Benchmark
```bash
python run_benchmark.py --mode throughput --duration 60 --concurrency 4
```

## Configuration

Benchmark configurations are stored in `configs/`:
- `default.yaml` - Standard benchmark settings
- `quick_test.yaml` - Fast validation runs
- `stress_test.yaml` - Extended stress testing

## Output

Results are saved to `reports/` in JSON format with:
- Summary statistics (mean, median, percentiles)
- Per-request metrics
- Configuration details
- Timestamps

### Sample Output
```json
{
  "benchmark": {
    "name": "PersonaPlex Text Latency Benchmark",
    "duration_seconds": 45.2
  },
  "summary": {
    "total_requests": 100,
    "successful_requests": 98,
    "success_rate": 98.0
  },
  "latency_ms": {
    "ttft": {
      "mean": 152.3,
      "median": 148.5,
      "p90": 185.2,
      "p95": 210.1,
      "p99": 245.8
    },
    "itl": {
      "mean": 22.5,
      "median": 20.1,
      "p90": 35.2
    }
  },
  "throughput": {
    "tokens_per_second": 45.2,
    "requests_per_second": 2.21
  }
}
```

## Architecture

```
benchmark/
├── core/
│   ├── metrics.py          # Metrics collection classes
│   └── personaplex_client.py # WebSocket benchmark client
├── audio/
│   ├── generator.py        # Test audio generation
│   └── turn_taking.py      # Turn-taking benchmarks
├── configs/                # YAML configurations
├── reports/                # Output directory
└── run_benchmark.py        # Main CLI runner
```

## Reference

- [PersonaPlex Paper](https://research.nvidia.com/labs/adlr/personaplex/)
- [FullDuplexBench Methodology](https://arxiv.org/abs/2311.01286)
- [NVIDIA LLM Inference Benchmarking](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/perf_analyzer/genai-perf.html)
