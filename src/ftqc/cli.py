"""Command-line interface for the same model exposed by the Python API."""
import argparse
import json
from typing import Optional, Sequence
from . import __version__
from .estimator import Hardware, SurfaceCodeModel, Workload, compare


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Surface-code resource estimation")
    parser.add_argument("--version", action="version", version=f"ftqc {__version__}")
    parser.add_argument("--logical-qubits", type=int, required=True)
    parser.add_argument("--logical-steps", type=int, required=True,
                        help="scheduled logical depth; each step lasts d code cycles")
    parser.add_argument("--physical-error-rate", type=float, required=True, nargs="+",
                        help="one or more circuit-level error rates to compare")
    parser.add_argument("--cycle-time-seconds", type=float, default=1e-6)
    parser.add_argument("--max-failure-probability", type=float, default=0.01)
    parser.add_argument("--extra-patches", type=int, default=0)
    parser.add_argument("--prefactor", type=float, default=0.1)
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument("--physical-qubits-per-d2", type=float, default=2.0)
    parser.add_argument("--max-distance", type=int, default=999)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        workload = Workload(args.logical_qubits, args.logical_steps,
                            args.max_failure_probability, args.extra_patches)
        model = SurfaceCodeModel(args.prefactor, args.threshold,
                                 args.physical_qubits_per_d2, max_distance=args.max_distance)
        options = [Hardware(p, args.cycle_time_seconds, f"p={p:g}")
                   for p in args.physical_error_rate]
        reports = compare(workload, options, model)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(json.dumps([report.to_dict() for report in reports], indent=2, allow_nan=False))
    else:
        print("hardware       distance    physical_qubits    runtime_s    failure_bound")
        for report in reports:
            print(f"{report.hardware.name:<14} {report.code_distance:>8} "
                  f"{report.physical_qubits:>18,} {report.runtime_seconds:>12.6g} "
                  f"{report.failure_probability_upper_bound:>16.6g}")
        print("\nModel: p_L=A*(p/p_th)^((d+1)/2) per patch-cycle; "
              "failure_bound <= patches*cycles*p_L.")
        for assumption in reports[0].assumptions:
            print(f"- {assumption}")
        print("Use --format json for inputs, fitted parameters and full resource totals.")
    return 0
