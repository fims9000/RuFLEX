import unittest

from certificates import (
    audit_reference, binary_threshold_certificate, exact_one_sided_lower,
    min_perfect_runs, multiclass_margin_certificate,
)


class ReproducibilityCertificateTests(unittest.TestCase):
    def test_all_agreeing_lower_bound(self):
        self.assertAlmostEqual(exact_one_sided_lower(19, 19, .05), .05 ** (1 / 19))
        self.assertEqual(exact_one_sided_lower(0, 100, .05), 0.0)

    def test_perfect_run_budget(self):
        self.assertEqual(min_perfect_runs(.95, .05), 59)

    def test_multiclass_margin(self):
        self.assertTrue(multiclass_margin_certificate([.8, .2], .29))
        self.assertFalse(multiclass_margin_certificate([.8, .2], .31))

    def test_binary_threshold(self):
        self.assertTrue(binary_threshold_certificate(.8, .5, .29))
        self.assertFalse(binary_threshold_certificate(.8, .5, .31))

    def test_fresh_seed_reuse_rejected(self):
        with self.assertRaises(ValueError):
            audit_reference({'a': '1'}, {'a': {9: '1'}},
                            declared_seeds=[9], reference_seed=9)

    def test_missing_audit_run_rejected(self):
        with self.assertRaises(ValueError):
            audit_reference({'a': '1'}, {'a': {10: '1'}},
                            declared_seeds=[10, 11], reference_seed=9)

    def test_familywise_wider_than_pointwise(self):
        ref = {'a': '1', 'b': '0'}
        calibration = {k: {s: v for s in range(100)} for k, v in ref.items()}
        pointwise = audit_reference(ref, calibration, declared_seeds=list(range(100)),
                                    correction='none', reference_seed=9000)
        familywise = audit_reference(ref, calibration, declared_seeds=list(range(100)),
                                     correction='bonferroni', reference_seed=9000)
        for p, f in zip(pointwise, familywise):
            self.assertGreaterEqual(p['one_sided_lower_bound'],
                                    f['one_sided_lower_bound'])


if __name__ == '__main__':
    unittest.main()
