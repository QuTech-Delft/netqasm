class NVEprCompiler:
    """Utility methods for NV-specific compilation of EPR-related operations"""

    @classmethod
    def get_max_time_for_fidelity(cls, min_fidelity: int) -> int:
        """Convert a minimum fidelity requirement value to a maximum
        EPR generation duration in microseconds."""

        # Fidelity should be between 0 and 100.
        assert 0 <= min_fidelity <= 100

        # f = 50 -> time = 55_000 us
        # f = 80 -> time = 28_000 us
        # f = 100 -> time = 10_000 us
        return 100_000 - min_fidelity * 900
