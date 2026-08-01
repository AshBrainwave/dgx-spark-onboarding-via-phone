"""Radio capability discovery for the AP-to-STA handoff.

NetworkManager does not expose nl80211 interface-combination limits.  ``iw phy`` is
the small, read-only exception in this project: it is querying the kernel's
NL80211 view, not configuring a network through a fragile command-line parser.
"""

from __future__ import annotations

import re


def supports_concurrent_ap_sta(iw_phy_output: str) -> bool:
    """Return whether one advertised valid combination permits AP + managed.

    The output has varied slightly across iw releases, so each combination is
    treated as a block and accepts both ``#{ AP }`` and ``#{ AP, managed }``.
    A total of two interfaces is required; a single virtual interface cannot
    keep the provisioning AP alive during association.
    """

    blocks = re.split(r"^\s*\*\s*", iw_phy_output, flags=re.MULTILINE)
    for block in blocks:
        lowered = block.lower()
        if "managed" not in lowered or "ap" not in lowered:
            continue
        total = re.search(r"total\s*<=\s*(\d+)", lowered)
        if total and int(total.group(1)) >= 2:
            return True
    return False
