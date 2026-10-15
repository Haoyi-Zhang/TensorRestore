"""Standard-library regressions for the optional plotter's numeric consumer."""
import copy
import csv
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "owned_packet_plot_data", ROOT / "scripts" / "packet_plot_data.py")
DATA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DATA)


class PacketPlotData(unittest.TestCase):
    def row(self, fraction="0.8333333333333334"):
        return {"branches": "2", "unrestricted_orders": "6",
                "repaired_orders": "5", "repair_retained_fraction": fraction}

    def test_retained_coordinates_are_unchanged(self):
        with (ROOT / "results" / "packets.csv").open(
                encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        before = copy.deepcopy(rows)
        branches, percentages = DATA.checked_packet_data(rows)
        self.assertEqual(branches, [int(row["branches"]) for row in rows])
        self.assertEqual(percentages, [
            float(format(100 * float(row["repair_retained_fraction"]), ".12g"))
            for row in rows])
        self.assertEqual(rows, before)

    def test_correct_counts_do_not_license_a_wrong_fraction(self):
        with self.assertRaisesRegex(ValueError, "retained fraction"):
            DATA.checked_packet_data([self.row("0.5")])

    def test_nonfinite_or_out_of_range_fraction_is_rejected(self):
        for fraction in ("nan", "inf", "-inf", "-0.1", "1.1"):
            with self.subTest(fraction=fraction):
                with self.assertRaises(ValueError):
                    DATA.checked_packet_data([self.row(fraction)])

    def test_exact_count_guard_is_retained(self):
        row = self.row()
        row["repaired_orders"] = "4"
        with self.assertRaisesRegex(ValueError, "order counts"):
            DATA.checked_packet_data([row])


if __name__ == "__main__":
    unittest.main()
