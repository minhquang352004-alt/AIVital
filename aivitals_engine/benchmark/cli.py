import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from aivitals_engine.benchmark.dataset import load_dataset
from aivitals_engine.benchmark.harness import BenchmarkConfig, BenchmarkRunner, MethodFactory
from aivitals_engine.benchmark.latency import benchmark_vitals_latency
from aivitals_engine.benchmark.team_methods import TEAM_METHODS, TeamRPPGSource

DEFAULT_METHODS = "GREEN,CHROM,POS"
DEFAULT_OUTPUT_DIR = "aivitals_engine/outputs/benchmark"


def build_method_factories(method_names: Sequence[str], window_seconds: float) -> dict[str, MethodFactory]:
    unknown = [name for name in method_names if name not in TEAM_METHODS]
    if unknown:
        raise ValueError(f"Method không hỗ trợ trong CLI: {', '.join(unknown)}.")
    return {name: (lambda method_name=name: TeamRPPGSource(method_name, window_seconds)) for name in method_names}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m aivitals_engine.benchmark", description="Benchmark AIVitals Engine")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Chạy benchmark nhiều method trên cùng dataset")
    run.add_argument("--dataset", default="synthetic", help="'synthetic' hoặc thư mục chứa file .npz")
    run.add_argument("--methods", default=DEFAULT_METHODS)
    run.add_argument("--window", type=float, default=30.0)
    run.add_argument("--step", type=float, default=2.0)
    run.add_argument("--duration", type=float, default=60.0, help="Độ dài mỗi recording synthetic (giây)")
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--output", default=DEFAULT_OUTPUT_DIR)
    latency = commands.add_parser("latency", help="Đo latency của VitalsService")
    latency.add_argument("--iterations", type=int, default=50)
    latency.add_argument("--window", type=float, default=30.0)
    return parser


def run_benchmark(arguments: argparse.Namespace) -> int:
    method_names = [name.strip().upper() for name in arguments.methods.split(",") if name.strip()]
    config = BenchmarkConfig(window_seconds=arguments.window, step_seconds=arguments.step)
    recordings = load_dataset(arguments.dataset, seed=arguments.seed, duration_seconds=arguments.duration)
    report = BenchmarkRunner(build_method_factories(method_names, arguments.window), config).run(recordings)
    paths = report.write(Path(arguments.output))
    print(report.to_markdown())
    print(json.dumps({key: str(path) for key, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


def run_latency(arguments: argparse.Namespace) -> int:
    report = benchmark_vitals_latency(iterations=arguments.iterations, window_seconds=arguments.window)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = build_parser().parse_args(argv)
    handlers = {"run": run_benchmark, "latency": run_latency}
    return handlers[arguments.command](arguments)
