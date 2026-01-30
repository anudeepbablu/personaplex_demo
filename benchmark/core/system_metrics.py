"""
System metrics collection for PersonaPlex benchmarks.

Collects GPU, CPU, and memory metrics during benchmark runs.
"""
import subprocess
import json
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Static GPU information."""
    index: int
    name: str
    driver_version: str
    cuda_version: str
    memory_total_mb: int
    compute_capability: str = ""


@dataclass
class GPUMetrics:
    """Dynamic GPU metrics at a point in time."""
    timestamp: float
    index: int
    memory_used_mb: int
    memory_free_mb: int
    memory_total_mb: int
    utilization_gpu_percent: float
    utilization_memory_percent: float
    temperature_c: int
    power_draw_w: float
    power_limit_w: float


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    timestamp: float
    cpu_percent: float
    memory_used_mb: int
    memory_total_mb: int
    memory_percent: float


@dataclass
class MetricsSummary:
    """Summary of collected metrics over a benchmark run."""
    # GPU info
    gpu_count: int = 0
    gpu_info: List[GPUInfo] = field(default_factory=list)

    # GPU metrics summary (per GPU)
    gpu_utilization_mean: List[float] = field(default_factory=list)
    gpu_utilization_max: List[float] = field(default_factory=list)
    gpu_memory_used_mean_mb: List[float] = field(default_factory=list)
    gpu_memory_used_max_mb: List[float] = field(default_factory=list)
    gpu_memory_percent_mean: List[float] = field(default_factory=list)
    gpu_temperature_mean_c: List[float] = field(default_factory=list)
    gpu_temperature_max_c: List[int] = field(default_factory=list)
    gpu_power_draw_mean_w: List[float] = field(default_factory=list)
    gpu_power_draw_max_w: List[float] = field(default_factory=list)

    # System metrics summary
    cpu_percent_mean: float = 0.0
    cpu_percent_max: float = 0.0
    memory_used_mean_mb: float = 0.0
    memory_used_max_mb: int = 0

    # Sample count
    sample_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "gpu_count": self.gpu_count,
            "sample_count": self.sample_count,
        }

        if self.gpu_info:
            result["gpus"] = []
            for i, gpu in enumerate(self.gpu_info):
                gpu_data = {
                    "index": gpu.index,
                    "name": gpu.name,
                    "driver_version": gpu.driver_version,
                    "cuda_version": gpu.cuda_version,
                    "memory_total_mb": gpu.memory_total_mb,
                }

                if i < len(self.gpu_utilization_mean):
                    gpu_data["utilization"] = {
                        "mean_percent": round(self.gpu_utilization_mean[i], 1),
                        "max_percent": round(self.gpu_utilization_max[i], 1),
                    }
                    gpu_data["memory"] = {
                        "total_mb": gpu.memory_total_mb,
                        "used_mean_mb": round(self.gpu_memory_used_mean_mb[i], 1),
                        "used_max_mb": round(self.gpu_memory_used_max_mb[i], 1),
                        "percent_mean": round(self.gpu_memory_percent_mean[i], 1),
                    }
                    gpu_data["temperature"] = {
                        "mean_c": round(self.gpu_temperature_mean_c[i], 1),
                        "max_c": self.gpu_temperature_max_c[i],
                    }
                    gpu_data["power"] = {
                        "draw_mean_w": round(self.gpu_power_draw_mean_w[i], 1),
                        "draw_max_w": round(self.gpu_power_draw_max_w[i], 1),
                    }

                result["gpus"].append(gpu_data)

        result["system"] = {
            "cpu_percent_mean": round(self.cpu_percent_mean, 1),
            "cpu_percent_max": round(self.cpu_percent_max, 1),
            "memory_used_mean_mb": round(self.memory_used_mean_mb, 1),
            "memory_used_max_mb": self.memory_used_max_mb,
        }

        return result


class SystemMetricsCollector:
    """
    Collects system and GPU metrics during benchmark runs.

    Uses nvidia-smi for GPU metrics and /proc for system metrics.
    """

    def __init__(self, sample_interval: float = 1.0):
        """
        Initialize metrics collector.

        Args:
            sample_interval: Seconds between metric samples
        """
        self.sample_interval = sample_interval
        self._gpu_samples: List[List[GPUMetrics]] = []  # [sample_idx][gpu_idx]
        self._system_samples: List[SystemMetrics] = []
        self._collecting = False
        self._thread: Optional[threading.Thread] = None
        self._gpu_info: List[GPUInfo] = []

    def get_gpu_info(self) -> List[GPUInfo]:
        """Get static GPU information."""
        if self._gpu_info:
            return self._gpu_info

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,driver_version,memory.total",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.warning("nvidia-smi failed, no GPU metrics available")
                return []

            # Get CUDA version
            cuda_version = ""
            cuda_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if cuda_result.returncode == 0:
                # Parse CUDA version from nvidia-smi output
                smi_output = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in smi_output.stdout.split('\n'):
                    if 'CUDA Version' in line:
                        parts = line.split('CUDA Version:')
                        if len(parts) > 1:
                            cuda_version = parts[1].strip().split()[0]
                        break

            gpus = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    # Handle [N/A] values
                    def safe_int(val, default=0):
                        try:
                            if val and val != '[N/A]' and val != 'N/A':
                                return int(float(val))
                            return default
                        except (ValueError, TypeError):
                            return default

                    gpus.append(GPUInfo(
                        index=safe_int(parts[0], 0),
                        name=parts[1] if parts[1] != '[N/A]' else 'Unknown GPU',
                        driver_version=parts[2] if parts[2] != '[N/A]' else 'N/A',
                        cuda_version=cuda_version,
                        memory_total_mb=safe_int(parts[3], 0)
                    ))

            self._gpu_info = gpus
            return gpus

        except FileNotFoundError:
            logger.warning("nvidia-smi not found, no GPU metrics available")
            return []
        except Exception as e:
            logger.warning(f"Failed to get GPU info: {e}")
            return []

    def _sample_gpu_metrics(self) -> List[GPUMetrics]:
        """Sample current GPU metrics."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,memory.used,memory.free,memory.total,"
                    "utilization.gpu,utilization.memory,temperature.gpu,"
                    "power.draw,power.limit",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return []

            timestamp = time.time()
            metrics = []

            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 9:
                    # Handle [N/A] values
                    def parse_float(val, default=0.0):
                        try:
                            return float(val) if val and val != '[N/A]' else default
                        except ValueError:
                            return default

                    def parse_int(val, default=0):
                        try:
                            return int(float(val)) if val and val != '[N/A]' else default
                        except ValueError:
                            return default

                    metrics.append(GPUMetrics(
                        timestamp=timestamp,
                        index=parse_int(parts[0]),
                        memory_used_mb=parse_int(parts[1]),
                        memory_free_mb=parse_int(parts[2]),
                        memory_total_mb=parse_int(parts[3]),
                        utilization_gpu_percent=parse_float(parts[4]),
                        utilization_memory_percent=parse_float(parts[5]),
                        temperature_c=parse_int(parts[6]),
                        power_draw_w=parse_float(parts[7]),
                        power_limit_w=parse_float(parts[8])
                    ))

            return metrics

        except Exception as e:
            logger.debug(f"Failed to sample GPU metrics: {e}")
            return []

    def _sample_system_metrics(self) -> Optional[SystemMetrics]:
        """Sample current system metrics."""
        try:
            # CPU usage from /proc/stat
            cpu_percent = 0.0
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=None)
            except ImportError:
                # Fallback: read from /proc/stat
                pass

            # Memory from /proc/meminfo
            memory_total = 0
            memory_available = 0

            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            memory_total = int(line.split()[1]) // 1024  # KB to MB
                        elif line.startswith('MemAvailable:'):
                            memory_available = int(line.split()[1]) // 1024
            except Exception:
                pass

            memory_used = memory_total - memory_available
            memory_percent = (memory_used / memory_total * 100) if memory_total > 0 else 0

            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_used_mb=memory_used,
                memory_total_mb=memory_total,
                memory_percent=memory_percent
            )

        except Exception as e:
            logger.debug(f"Failed to sample system metrics: {e}")
            return None

    def _collection_loop(self):
        """Background thread for collecting metrics."""
        while self._collecting:
            # Sample GPU metrics
            gpu_metrics = self._sample_gpu_metrics()
            if gpu_metrics:
                self._gpu_samples.append(gpu_metrics)

            # Sample system metrics
            system_metrics = self._sample_system_metrics()
            if system_metrics:
                self._system_samples.append(system_metrics)

            time.sleep(self.sample_interval)

    def start(self):
        """Start collecting metrics in background."""
        if self._collecting:
            return

        # Get GPU info first
        self.get_gpu_info()

        # Clear previous samples
        self._gpu_samples = []
        self._system_samples = []

        # Start collection thread
        self._collecting = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()

        logger.info("Started system metrics collection")

    def stop(self) -> MetricsSummary:
        """Stop collecting and return summary."""
        self._collecting = False

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info(f"Stopped metrics collection, {len(self._gpu_samples)} GPU samples, "
                   f"{len(self._system_samples)} system samples")

        return self._compute_summary()

    def _compute_summary(self) -> MetricsSummary:
        """Compute summary statistics from collected samples."""
        summary = MetricsSummary(
            gpu_count=len(self._gpu_info),
            gpu_info=self._gpu_info,
            sample_count=len(self._gpu_samples)
        )

        # Compute GPU metrics summary
        if self._gpu_samples and self._gpu_info:
            num_gpus = len(self._gpu_info)

            # Initialize per-GPU lists
            for _ in range(num_gpus):
                summary.gpu_utilization_mean.append(0.0)
                summary.gpu_utilization_max.append(0.0)
                summary.gpu_memory_used_mean_mb.append(0.0)
                summary.gpu_memory_used_max_mb.append(0.0)
                summary.gpu_memory_percent_mean.append(0.0)
                summary.gpu_temperature_mean_c.append(0.0)
                summary.gpu_temperature_max_c.append(0)
                summary.gpu_power_draw_mean_w.append(0.0)
                summary.gpu_power_draw_max_w.append(0.0)

            # Aggregate samples
            for sample in self._gpu_samples:
                for gpu_metric in sample:
                    idx = gpu_metric.index
                    if idx < num_gpus:
                        summary.gpu_utilization_mean[idx] += gpu_metric.utilization_gpu_percent
                        summary.gpu_utilization_max[idx] = max(
                            summary.gpu_utilization_max[idx],
                            gpu_metric.utilization_gpu_percent
                        )
                        summary.gpu_memory_used_mean_mb[idx] += gpu_metric.memory_used_mb
                        summary.gpu_memory_used_max_mb[idx] = max(
                            summary.gpu_memory_used_max_mb[idx],
                            gpu_metric.memory_used_mb
                        )
                        total_mem = gpu_metric.memory_total_mb or self._gpu_info[idx].memory_total_mb
                        if total_mem > 0:
                            pct = gpu_metric.memory_used_mb / total_mem * 100
                            summary.gpu_memory_percent_mean[idx] += pct
                        summary.gpu_temperature_mean_c[idx] += gpu_metric.temperature_c
                        summary.gpu_temperature_max_c[idx] = max(
                            summary.gpu_temperature_max_c[idx],
                            gpu_metric.temperature_c
                        )
                        summary.gpu_power_draw_mean_w[idx] += gpu_metric.power_draw_w
                        summary.gpu_power_draw_max_w[idx] = max(
                            summary.gpu_power_draw_max_w[idx],
                            gpu_metric.power_draw_w
                        )

            # Compute means
            n_samples = len(self._gpu_samples)
            if n_samples > 0:
                for i in range(num_gpus):
                    summary.gpu_utilization_mean[i] /= n_samples
                    summary.gpu_memory_used_mean_mb[i] /= n_samples
                    summary.gpu_memory_percent_mean[i] /= n_samples
                    summary.gpu_temperature_mean_c[i] /= n_samples
                    summary.gpu_power_draw_mean_w[i] /= n_samples

        # Compute system metrics summary
        if self._system_samples:
            cpu_values = [s.cpu_percent for s in self._system_samples]
            memory_values = [s.memory_used_mb for s in self._system_samples]

            summary.cpu_percent_mean = sum(cpu_values) / len(cpu_values)
            summary.cpu_percent_max = max(cpu_values)
            summary.memory_used_mean_mb = sum(memory_values) / len(memory_values)
            summary.memory_used_max_mb = max(memory_values)

        return summary

    def get_current_snapshot(self) -> Dict[str, Any]:
        """Get current metrics snapshot without starting collection."""
        gpu_info = self.get_gpu_info()
        gpu_metrics = self._sample_gpu_metrics()
        system_metrics = self._sample_system_metrics()

        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "gpus": [],
            "system": {}
        }

        for i, info in enumerate(gpu_info):
            gpu_data = {
                "index": info.index,
                "name": info.name,
                "driver_version": info.driver_version,
                "cuda_version": info.cuda_version,
                "memory_total_mb": info.memory_total_mb,
            }

            if i < len(gpu_metrics):
                m = gpu_metrics[i]
                gpu_data["memory_used_mb"] = m.memory_used_mb
                gpu_data["memory_free_mb"] = m.memory_free_mb
                gpu_data["utilization_gpu_percent"] = m.utilization_gpu_percent
                gpu_data["utilization_memory_percent"] = m.utilization_memory_percent
                gpu_data["temperature_c"] = m.temperature_c
                gpu_data["power_draw_w"] = m.power_draw_w
                gpu_data["power_limit_w"] = m.power_limit_w

            snapshot["gpus"].append(gpu_data)

        if system_metrics:
            snapshot["system"] = {
                "cpu_percent": system_metrics.cpu_percent,
                "memory_used_mb": system_metrics.memory_used_mb,
                "memory_total_mb": system_metrics.memory_total_mb,
                "memory_percent": system_metrics.memory_percent,
            }

        return snapshot


def print_gpu_info():
    """Print GPU information to console."""
    collector = SystemMetricsCollector()
    snapshot = collector.get_current_snapshot()

    print("\n" + "=" * 60)
    print("SYSTEM INFORMATION")
    print("=" * 60)

    if snapshot["gpus"]:
        for gpu in snapshot["gpus"]:
            print(f"\nGPU {gpu['index']}: {gpu['name']}")
            print(f"  Driver Version:  {gpu['driver_version']}")
            print(f"  CUDA Version:    {gpu.get('cuda_version', 'N/A')}")
            if gpu['memory_total_mb'] > 0:
                print(f"  Memory Total:    {gpu['memory_total_mb']:,} MB")
            else:
                print(f"  Memory Total:    N/A (unified memory architecture)")
            if 'memory_used_mb' in gpu and gpu.get('memory_total_mb', 0) > 0:
                pct = gpu['memory_used_mb'] / gpu['memory_total_mb'] * 100
                print(f"  Memory Used:     {gpu['memory_used_mb']:,} MB ({pct:.1f}%)")
            elif 'memory_used_mb' in gpu:
                print(f"  Memory Used:     {gpu['memory_used_mb']:,} MB")
            if 'utilization_gpu_percent' in gpu:
                print(f"  GPU Utilization: {gpu['utilization_gpu_percent']:.1f}%")
            if 'temperature_c' in gpu:
                print(f"  Temperature:     {gpu['temperature_c']}°C")
            if 'power_draw_w' in gpu:
                limit = gpu.get('power_limit_w', 0)
                if limit > 0:
                    print(f"  Power Draw:      {gpu['power_draw_w']:.1f}W / {limit:.1f}W")
                else:
                    print(f"  Power Draw:      {gpu['power_draw_w']:.1f}W")
    else:
        print("\nNo NVIDIA GPUs detected")

    if snapshot["system"]:
        sys = snapshot["system"]
        print(f"\nSystem:")
        print(f"  CPU Usage:       {sys['cpu_percent']:.1f}%")
        print(f"  Memory:          {sys['memory_used_mb']:,} / {sys['memory_total_mb']:,} MB ({sys['memory_percent']:.1f}%)")

    print("=" * 60)
