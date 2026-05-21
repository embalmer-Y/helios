"""Trigger dictionary merging with max-value semantics.

Provides the merge_triggers utility used by the main loop when collecting
Panksepp trigger vectors from multiple EventSource instances.
"""

from typing import Dict, List


def merge_triggers(trigger_dicts: List[Dict[str, float]]) -> Dict[str, float]:
    """Merge multiple Panksepp trigger dictionaries using max-value semantics.

    For overlapping system keys across sources, the maximum value is kept.
    This ensures the strongest signal for each Panksepp system is preserved.

    Args:
        trigger_dicts: List of trigger dictionaries from different EventSources.
            Each maps Panksepp system names to intensity values.

    Returns:
        Merged dictionary mapping each system key to the maximum intensity
        value across all input dictionaries.

    Examples:
        >>> merge_triggers([{"SEEKING": 0.5}, {"SEEKING": 0.8, "PANIC": 0.3}])
        {'SEEKING': 0.8, 'PANIC': 0.3}
        >>> merge_triggers([])
        {}
    """
    merged: Dict[str, float] = {}
    for triggers in trigger_dicts:
        for system, intensity in triggers.items():
            merged[system] = max(merged.get(system, 0.0), intensity)
    return merged
