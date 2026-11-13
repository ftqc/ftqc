import json
import math
import unittest
from ftqc import Hardware, SurfaceCodeModel, Workload, compare, estimate


class EstimateTests(unittest.TestCase):
    def test_published_litinski_example(self):
        # Quantum 3, 128 (2019), Sec. 4, Eqs. (10)-(11): 164 patches,
        # 11*10^8 logical time steps, p=10^-4, memory-error budget of 1%.
        report = estimate(Workload(164, 11 * 10**8), Hardware(1e-4))
        self.assertEqual(report.code_distance, 13)
        self.assertAlmostEqual(report.failure_probability_upper_bound, 0.0023452)
        self.assertEqual(report.physical_qubits, 55_432)
        self.assertEqual(report.code_cycles, 14_300_000_000)
        self.assertAlmostEqual(report.runtime_seconds, 14_300)
        self.assertAlmostEqual(report.physical_qubit_seconds, 792_677_600)

    def test_minimum_distance_and_manual_bound(self):
        model = SurfaceCodeModel()
        workload = Workload(100, 1_000_000)
        report = estimate(workload, Hardware(1e-3), model)
        self.assertEqual(report.code_distance, 21)
        rate = 0.1 * (100 * 1e-3) ** 11
        self.assertAlmostEqual(report.logical_error_per_patch_cycle, rate)
        self.assertAlmostEqual(report.failure_probability_upper_bound,
                               100 * 1_000_000 * 21 * rate)
        for distance in range(3, report.code_distance, 2):
            bound = 100 * 1_000_000 * distance * model.logical_error_rate(1e-3, distance)
            self.assertGreater(bound, workload.max_failure_probability)

    def test_monotonicity_and_comparison_order(self):
        work = Workload(100, 1_000_000)
        options = [Hardware(1e-3, name="a"), Hardware(1e-4, name="b")]
        reports = compare(work, options)
        self.assertEqual([r.hardware.name for r in reports], ["a", "b"])
        self.assertLess(reports[1].physical_qubits, reports[0].physical_qubits)
        tighter = estimate(Workload(100, 1_000_000, 1e-6), options[0])
        self.assertGreaterEqual(tighter.code_distance, reports[0].code_distance)
        slower = estimate(work, Hardware(1e-3, 2e-6))
        self.assertEqual(slower.code_distance, reports[0].code_distance)
        self.assertAlmostEqual(slower.runtime_seconds, 2 * reports[0].runtime_seconds)

    def test_extra_patches_count_towards_area_and_errors(self):
        result = estimate(Workload(10, 100, extra_patches=5), Hardware(1e-3))
        self.assertEqual(result.patches, 15)
        self.assertEqual(result.physical_qubits, 15 * 2 * result.code_distance**2)
        self.assertAlmostEqual(result.failure_probability_upper_bound,
                               15 * result.code_cycles * result.logical_error_per_patch_cycle)

    def test_low_load_uses_minimum_distance(self):
        self.assertEqual(estimate(Workload(1, 1), Hardware(1e-4)).code_distance, 3)

    def test_custom_model(self):
        model = SurfaceCodeModel(prefactor=0.2, threshold=0.02,
                                 physical_qubits_per_d2=3, min_distance=5)
        report = estimate(Workload(1, 1), Hardware(1e-4), model)
        self.assertEqual(report.code_distance, 5)
        self.assertEqual(report.physical_qubits, 75)
        self.assertAlmostEqual(model.logical_error_rate(1e-4, 5), 0.2 * 0.005**3)

    def test_log_space_preserves_extreme_budget(self):
        # Direct multiplication by a probability that underflows would return zero
        # and incorrectly accept a distance. Log-space search remains correct.
        report = estimate(Workload(1, 10**300, 1e-300), Hardware(1e-200))
        self.assertEqual(report.code_distance, 7)
        self.assertTrue(math.isfinite(report.log_failure_probability_upper_bound))
        self.assertLessEqual(report.log_failure_probability_upper_bound, math.log(1e-300))
        json.dumps(report.to_dict(), allow_nan=False)

    def test_no_supported_distance(self):
        with self.assertRaisesRegex(ValueError, "no odd code distance"):
            estimate(Workload(100, 10**6), Hardware(1e-3), SurfaceCodeModel(max_distance=3))

    def test_threshold_and_invalid_distances(self):
        for p in [0.01, 0.02]:
            with self.subTest(p=p), self.assertRaisesRegex(ValueError, "below"):
                estimate(Workload(1, 1), Hardware(p))
        for d in [0, 1, 2, 4, True, 3.0]:
            with self.subTest(d=d), self.assertRaises(ValueError):
                SurfaceCodeModel().logical_error_rate(1e-3, d)

    def test_invalid_inputs(self):
        bad_reals = [0, -1, math.nan, math.inf, -math.inf, True, "0.001"]
        for value in bad_reals:
            for factory in [lambda: Hardware(value), lambda: Hardware(1e-3, value),
                            lambda: Workload(1, 1, value),
                            lambda: SurfaceCodeModel(prefactor=value),
                            lambda: SurfaceCodeModel(threshold=value),
                            lambda: SurfaceCodeModel(physical_qubits_per_d2=value)]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    factory()
        for value in [0, -1, True, 1.5, "1"]:
            for factory in [lambda: Workload(value, 1), lambda: Workload(1, value)]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    factory()
        for factory in [lambda: Workload(1, 1, 1), lambda: Hardware(1),
                        lambda: Hardware(1e-3, name=""),
                        lambda: Workload(1, 1, extra_patches=True),
                        lambda: Workload(1, 1, extra_patches=-1),
                        lambda: SurfaceCodeModel(min_distance=4),
                        lambda: SurfaceCodeModel(min_distance=7, max_distance=3),
                        lambda: SurfaceCodeModel(threshold=1),
                        lambda: SurfaceCodeModel(prefactor=2)]:
            with self.assertRaises(ValueError):
                factory()

    def test_overflow_is_explicit(self):
        with self.assertRaisesRegex(OverflowError, "resource totals"):
            estimate(Workload(1, 10**100), Hardware(1e-4, 1e300))

    def test_json_includes_reproducibility_metadata(self):
        data = estimate(Workload(1, 10), Hardware(1e-3)).to_dict()
        encoded = json.dumps(data, allow_nan=False)
        self.assertEqual(json.loads(encoded)["schema_version"], 1)
        self.assertEqual(data["model"]["threshold"], 0.01)
        self.assertEqual(data["workload"]["logical_steps"], 10)
        self.assertTrue(data["assumptions"])
