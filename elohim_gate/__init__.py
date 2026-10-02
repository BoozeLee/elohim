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
]
__version__ = "0.1.0"