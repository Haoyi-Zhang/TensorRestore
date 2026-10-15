"""Validate the recorded packet-order values used by the optional plotter."""
import math
from fractions import Fraction


def checked_packet_data(rows):
    """Return the existing plot coordinates after checking every used column.

    The CSV fraction is a decimal rendering of an exact integer ratio. A small
    relative tolerance admits that serialization rounding, not a different
    measured quantity. Percentages keep the exporter's 12-significant-digit
    rendering; this function does not alter the retained data or typography.
    """
    branches, percentages = [], []
    for row in rows:
        k = int(row["branches"])
        unrestricted = math.factorial(2 * k) // 2**k
        repaired = math.factorial(k - 1) * sum(
            math.factorial(k + m) // (2**m * math.factorial(m))
            for m in range(k))
        if (int(row["unrestricted_orders"]) != unrestricted
                or int(row["repaired_orders"]) != repaired):
            raise ValueError("Recorded order counts disagree with manuscript formulas.")
        fraction = float(row["repair_retained_fraction"])
        expected = float(Fraction(repaired, unrestricted))
        if (not math.isfinite(fraction) or not 0 <= fraction <= 1
                or not math.isclose(fraction, expected, rel_tol=1e-12, abs_tol=0.0)):
            raise ValueError("Recorded retained fraction disagrees with exact order counts.")
        branches.append(k)
        percentages.append(float(format(100 * fraction, ".12g")))
    return branches, percentages
