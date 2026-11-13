"""Run after installing ftqc: python examples/compare_hardware.py."""
import json
from ftqc import Hardware, Workload, compare

workload = Workload(logical_qubits=100, logical_steps=1_000_000)
reports = compare(workload, [
    Hardware(physical_error_rate=1e-3, name="baseline"),
    Hardware(physical_error_rate=1e-4, name="lower-error"),
])
print(json.dumps([report.to_dict() for report in reports], indent=2, allow_nan=False))
