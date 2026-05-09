from __future__ import annotations

from avatar.sim import constants as c


def test_sih_vehicle_target_is_non_empty_ident() -> None:
    assert c.SIH_VEHICLE_TARGET
    assert c.SIH_VEHICLE_TARGET.replace("_", "").isalnum()
