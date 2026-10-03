"""elohim — a gate for numerical claims."""

__all__ = [
    "cli",
    # The census half: run_census() measures, gate_verdict() decides.
    "census",
    # The mutation half, and the single home for exit policy. census.gate_verdict
    # delegates here rather than keeping a second copy that can drift.
    "mutation",
    # The mutation operator table. Both halves read it; neither redefines it.
    "sites",
    # Comparison machinery. Refuses to report agreement it did not measure, so a
    # check that matched nothing fails loudly instead of comparing equal forever.
    "compare",
]
__version__ = "0.2.0"