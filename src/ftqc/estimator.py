"""A configurable phenomenological fit; not a circuit simulator.

Default fit: Litinski, Quantum 3, 128 (2019), Eq. (10).
Space and time: approximately 2*d**2 qubits per patch and d rounds per step.
The union bound budgets logical memory errors across all occupied patch-rounds.
"""
from dataclasses import asdict, dataclass, field
import math
from typing import Any, Dict, Iterable, List


def _positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _positive_real(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite positive number")
    try:
        valid = math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite positive number")


@dataclass(frozen=True)
class Workload:
    """Logical storage and sequential lattice-surgery time steps.

    logical_steps is scheduled depth, not a gate count or T count.
    Each step lasts d code cycles; all logical and extra patches remain occupied.
    max_failure_probability budgets ONLY modeled logical memory errors.
    """
    logical_qubits: int
    logical_steps: int
    max_failure_probability: float = 0.01
    extra_patches: int = 0

    def __post_init__(self) -> None:
        _positive_int("logical_qubits", self.logical_qubits)
        _positive_int("logical_steps", self.logical_steps)
        _positive_real("max_failure_probability", self.max_failure_probability)
        if self.max_failure_probability >= 1:
            raise ValueError("max_failure_probability must be less than 1")
        if (isinstance(self.extra_patches, bool)
                or not isinstance(self.extra_patches, int) or self.extra_patches < 0):
            raise ValueError("extra_patches must be a nonnegative integer")


@dataclass(frozen=True)
class Hardware:
    """Circuit-level physical error probability and stabilizer-round duration."""
    physical_error_rate: float
    cycle_time_seconds: float = 1e-6
    name: str = "hardware"

    def __post_init__(self) -> None:
        _positive_real("physical_error_rate", self.physical_error_rate)
        if self.physical_error_rate >= 1:
            raise ValueError("physical_error_rate must be less than 1")
        _positive_real("cycle_time_seconds", self.cycle_time_seconds)
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a nonempty string")


@dataclass(frozen=True)
class SurfaceCodeModel:
    """p_L = prefactor * (p / threshold)**((d + 1) / 2), per patch-round.

    Defaults reproduce a commonly used heuristic, not a hardware calibration.
    Only odd distances >= 3 and p < threshold are supported.
    """
    prefactor: float = 0.1
    threshold: float = 0.01
    physical_qubits_per_d2: float = 2.0
    min_distance: int = 3
    max_distance: int = 999

    def __post_init__(self) -> None:
        for name in ("prefactor", "threshold", "physical_qubits_per_d2"):
            _positive_real(name, getattr(self, name))
        if self.prefactor > 1 or self.threshold >= 1:
            raise ValueError("prefactor must be <= 1 and threshold must be < 1")
        for name in ("min_distance", "max_distance"):
            value = getattr(self, name)
            _positive_int(name, value)
            if value < 3 or value % 2 == 0:
                raise ValueError(f"{name} must be odd and >= 3")
        if self.max_distance < self.min_distance:
            raise ValueError("max_distance must be >= min_distance")

    def log_logical_error_rate(self, physical_error_rate: float, distance: int) -> float:
        _positive_real("physical_error_rate", physical_error_rate)
        if physical_error_rate >= self.threshold:
            raise ValueError("physical_error_rate must be below the model threshold")
        _positive_int("distance", distance)
        if distance < 3 or distance % 2 == 0:
            raise ValueError("distance must be odd and >= 3")
        # Subtract logs instead of forming a ratio, which can underflow.
        return (math.log(self.prefactor) + ((distance + 1) // 2)
                * (math.log(physical_error_rate) - math.log(self.threshold)))

    def logical_error_rate(self, physical_error_rate: float, distance: int) -> float:
        """Approximate probability per patch per code cycle (may underflow to 0)."""
        return math.exp(self.log_logical_error_rate(physical_error_rate, distance))


@dataclass(frozen=True)
class Estimate:
    hardware: Hardware
    workload: Workload
    model: SurfaceCodeModel
    code_distance: int
    patches: int
    physical_qubits: int
    code_cycles: int
    runtime_seconds: float
    logical_error_per_patch_cycle: float
    failure_probability_upper_bound: float
    log_failure_probability_upper_bound: float
    physical_qubit_seconds: float
    assumptions: tuple = field(default=(
        "All patches are occupied for the entire scheduled depth.",
        "One logical time step takes d stabilizer-measurement cycles.",
        "Physical qubits are ceil(patches * physical_qubits_per_d2 * d^2).",
        "Failure bound is patches * code_cycles * p_L, capped at 1; "
        "independence is not required, but the p_L fit is heuristic.",
        "Excludes magic-state factories and their errors, routing, state injection, "
        "decoder latency, classical control, idle hardware, and hardware-specific effects.",
        "extra_patches adds occupied storage area only, not factory throughput or fidelity.",
    ))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable report with inputs, model, units and assumptions."""
        return {"schema_version": 1, "ftqc_version": "0.1.0", **asdict(self)}


def estimate(workload: Workload, hardware: Hardware,
             model: SurfaceCodeModel = SurfaceCodeModel()) -> Estimate:
    """Find the smallest supported odd distance satisfying the union-bound budget.

    Search and budget comparisons use log probabilities to avoid underflow.
    Raises ValueError when no supported distance meets the budget.
    Raises OverflowError if resources cannot be represented as finite floats.
    """
    patches = workload.logical_qubits + workload.extra_patches
    log_budget = math.log(workload.max_failure_probability)
    for distance in range(model.min_distance, model.max_distance + 1, 2):
        cycles = workload.logical_steps * distance
        log_rate = model.log_logical_error_rate(hardware.physical_error_rate, distance)
        log_bound = math.log(patches) + math.log(cycles) + log_rate
        if log_bound <= log_budget:
            try:
                qubits = math.ceil(patches * model.physical_qubits_per_d2 * distance**2)
                runtime = cycles * hardware.cycle_time_seconds
                volume = qubits * runtime
                if not math.isfinite(runtime) or not math.isfinite(volume):
                    raise OverflowError
            except OverflowError as exc:
                raise OverflowError("resource totals exceed finite floating-point range") from exc
            return Estimate(
                hardware=hardware, workload=workload, model=model,
                code_distance=distance, patches=patches, physical_qubits=qubits,
                code_cycles=cycles, runtime_seconds=runtime,
                logical_error_per_patch_cycle=math.exp(log_rate),
                failure_probability_upper_bound=min(1.0, math.exp(log_bound)),
                log_failure_probability_upper_bound=log_bound,
                physical_qubit_seconds=volume,
            )
    raise ValueError(f"no odd code distance <= {model.max_distance} meets the failure budget; "
                     "increase max_distance or reconsider inputs")


def compare(workload: Workload, hardware_options: Iterable[Hardware],
            model: SurfaceCodeModel = SurfaceCodeModel()) -> List[Estimate]:
    """Estimate each hardware option in input order; invalid options raise ValueError."""
    return [estimate(workload, hardware, model) for hardware in hardware_options]
