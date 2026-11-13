# ftqc

**Resource estimation for fault-tolerant quantum computing.**

`ftqc` turns a scheduled logical workload and hardware assumptions into a
surface-code distance, physical-qubit count, runtime, and logical-memory failure
bound. It provides a Python API, a command-line interface, hardware comparisons,
and JSON reports. Python 3.9+; no runtime dependencies.

容错量子计算资源估算工具：输入逻辑量子比特数、调度深度和硬件参数，
估算码距、物理量子比特数、运行时间与逻辑存储错误上界。

This is an alpha implementation of an explicit analytical approximation. It is
useful for exploring scaling and comparing assumptions, rather than predicting
an entire machine's performance or simulating quantum error correction.

## Install

```bash
python -m pip install ftqc
```

For a development installation, clone this repository and run
`python -m pip install .` from its root.

Source: https://github.com/ftqc/ftqc · Package: https://pypi.org/project/ftqc/

## Python API

```python
from ftqc import Hardware, Workload, estimate

report = estimate(
    Workload(logical_qubits=100, logical_steps=1_000_000,
             max_failure_probability=0.01),
    Hardware(physical_error_rate=1e-3, cycle_time_seconds=1e-6),
)
print(report.code_distance)       # 21
print(report.physical_qubits)     # 88200
print(report.runtime_seconds)     # 21.0
print(report.failure_probability_upper_bound)  # approximately 0.0021
```

`logical_steps` is **scheduled logical depth**, in time steps of `d` code cycles.
It is not gate count or T count. The package does not compile an algorithm or
infer its scheduling. `cycle_time_seconds` is the duration of one stabilizer
measurement round; all reported durations use seconds.

Compare hardware in input order:

```python
from ftqc import Hardware, Workload, compare

reports = compare(Workload(100, 1_000_000), [
    Hardware(1e-3, name="baseline"),
    Hardware(1e-4, name="lower-error"),
])
for report in reports:
    print(report.hardware.name, report.code_distance, report.physical_qubits)
# baseline 21 88200
# lower-error 9 16200
```

`report.to_dict()` includes the inputs, model parameters, units in field names,
resource totals, assumptions, schema version, and package version. Serialize
with `json.dumps(report.to_dict(), allow_nan=False)`.

## Command line

```bash
ftqc --logical-qubits 100 --logical-steps 1000000 \
  --physical-error-rate 0.001 0.0001

ftqc --logical-qubits 100 --logical-steps 1000000 \
  --physical-error-rate 0.001 --format json > estimate.json
```

`python -m ftqc` is equivalent. JSON output is always a list of reports, including
for a single hardware option. Invalid inputs exit with status 2 without emitting
a partial report. Use `ftqc --help` to inspect all parameters.

## Model and scope

For physical circuit-level error probability `p` and odd code distance `d`:

```text
p_L(d)       = A * (p / p_threshold)^((d + 1) / 2)
patches      = logical_qubits + extra_patches
code_cycles  = logical_steps * d
failure_bound = min(1, patches * code_cycles * p_L(d))
physical_qubits = ceil(patches * qubits_per_d2 * d^2)
runtime_seconds = code_cycles * cycle_time_seconds
physical_qubit_seconds = physical_qubits * runtime_seconds
```

Defaults are `A=0.1`, `p_threshold=0.01`, and `qubits_per_d2=2`. We search odd
distances from 3 through 999 and select the smallest whose failure bound is at
most the requested budget. Search uses log probabilities to avoid underflow.
Individual reported probabilities may underflow to zero for extreme inputs;
`log_failure_probability_upper_bound` retains the natural log of the bound.

The failure estimate uses a **union bound over occupied patch-rounds**. It does
not assume independent errors. However, the underlying per-round error fit is
heuristic: the bound is conditional on that fit and is not a certified hardware
reliability guarantee. A failure budget covers only these modeled memory errors.
Inputs at or above the assumed threshold are rejected. A finite distance search
that cannot meet the budget raises `ValueError`.

Space uses approximately `2*d^2` physical qubits per occupied surface-code tile,
including measurement ancillas; this is not an exact layout or chip capacity.
All patches are assumed occupied for the entire workload. `extra_patches` can
represent additional occupied area, but does not model operations on that area.

**Not included:** magic-state distillation factories or their output errors,
routing and layout synthesis, state injection, decoder latency, classical
control, spare hardware, correlated noise, leakage, or device calibration.
Adding `extra_patches` does not add factory throughput or fidelity modeling.

The fit and space factor are configurable:

```python
from ftqc import SurfaceCodeModel
model = SurfaceCodeModel(prefactor=0.1, threshold=0.01,
                         physical_qubits_per_d2=2, max_distance=1999)
# estimate(workload, hardware, model)
```

Changing the threshold is a modeling assumption, not a hardware validation.

## References and reproducible check

Daniel Litinski, *A Game of Surface Codes: Large-Scale Quantum Computing with
Lattice Surgery*, Quantum **3**, 128 (2019), DOI: 10.22331/q-2019-03-05-128,
arXiv:1808.02892. Equation (10) gives the default error fit per logical qubit per
code cycle; Sec. 2 and the discussion of measurement ancillas give the space and
time approximations. Equation (11) supplies the regression example below.

```python
report = estimate(Workload(164, 11 * 10**8), Hardware(1e-4))
assert report.code_distance == 13
assert report.physical_qubits == 55_432
# logical memory error bound ≈ 0.0023452; runtime = 14,300 s
```

The full setup in the paper includes distillation resources and error budgets
that this small reproduction does not independently calculate. This test checks
the cited memory-error calculation only.

Background: Austin G. Fowler et al., *Surface codes: Towards practical
large-scale quantum computation*, Phys. Rev. A **86**, 032324 (2012),
DOI: 10.1103/PhysRevA.86.032324, arXiv:1208.0928.

## Develop and release

```bash
python -m pip install . build twine
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

See `RELEASING.md` for the publication checklist. License: Apache-2.0.
