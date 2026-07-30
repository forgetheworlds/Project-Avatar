# Project Catamaran — First Engineering Print Release

This folder is ready for slicer review and a first engineering print. It is
not yet a water-ready production release: the physical gates at the end of
`ENGINEERING_BRIEF.md` remain mandatory.

## Release artifacts

- Primary assembly: `boat_assembly.step`
- Jet-drive assembly: `jetdrive/jet_assembly.step`
- Printable meshes: `print/*.stl`
- Editable sources: the adjacent build123d `.py` files
- Automated geometry audit: `scripts/validate_design.py`

The consolidated `print/` directory contains 32 current STL files:

| Qty | STL |
| ---: | --- |
| 1 | `hull_bow.stl` |
| 1 | `hull_mid.stl` |
| 1 | `hull_stern.stl` |
| 1 | `deck_mid.stl` |
| 1 | `deck_stern.stl` |
| 1 | `electronics_house.stl` |
| 1 | `electronics_house_lid.stl` |
| 1 | `battery_tray.stl` |
| 1 | `electronics_tray.stl` |
| 1 | `pump_housing.stl` |
| 1 | `shaft_cartridge.stl` |
| 1 | `motor_adapter.stl` |
| 1 | `impeller.stl` |
| 1 | `nozzle_plate.stl` |
| 1 | `nozzle.stl` |
| 1 | `servo_bracket.stl` |
| 1 | `pump_well_cover.stl` |
| 1 | `pump_retainer.stl` |
| 1 | `hose_clip.stl` |
| 1 | `turret_base.stl` |
| 1 | `turret_platform.stl` |
| 1 | `water_cannon.stl` |
| 1 | `transom_fin_port.stl` |
| 1 | `transom_fin_starboard.stl` |
| 1 | `drain_plug.stl` |
| 1 | `foam_port_plug.stl` |
| 1 | `pushrod_gland.stl` |
| 2 | `nozzle_thrust_washer.stl` |
| 1 | `turret_thrust_washer.stl` |
| 1 | one of `nozzle_insert_2p0.stl`, `nozzle_insert_2p5.stl`, or `nozzle_insert_3p0.stl` |
| optional | the other two nozzle inserts for flow testing |

## Slicer handoff

- Use PETG, ASA, or another water-tolerant engineering filament for the hull
  and wet hardware; do not use unsealed PLA for the released wet test.
- Print the three hull sections upright on their joint bulkheads so the
  exterior shell does not require support. Add a brim and verify the selected
  printer can accommodate the 160 mm section height.
- Use at least four walls and enough top/bottom layers to make the nominal
  2.4 mm shell continuous. Prefer perimeter strength over low-density infill.
- Print the pump housing with its flat mounting/interface face on the bed.
  Keep support out of the 28 mm tunnel, seal pockets, bearing seats, and bolt
  bores.
- Print the impeller with the shaft axis vertical. Use the finest practical
  layer height, uniform cooling, and no support touching blade pressure faces.
  Dynamically balance it after installing the shaft.
- Print the shaft cartridge with the shaft axis vertical. Do not scale it:
  the 4 mm shaft, 4 x 8 x 3 seal, and bearing interfaces are dimensioned.
- Print deck and gasket faces flat. Do not sand sealing faces selectively;
  lap them on a flat surface after printing.
- Print both tracking fins flat on their broad side. Mount them with M3x8
  fasteners and removable marine sealant using the existing transom bosses.
  They are intentionally sacrificial and independently replaceable.
- Print two nozzle thrust washers even though the folder contains one washer
  STL. A PTFE/acetal washer is preferable when available.
- The pushrod gland is an epoxy-in guide and bellows retainer, not a complete
  dynamic seal; fit a purchased RC pushrod bellows over its barb.
- Do not apply global XY compensation to the whole release. Calibrate shaft,
  bearing, seal, fastener, and nozzle fits with short test coupons or the
  mating parts before committing the hull.

## Acceptance before assembly

1. Confirm every STL imports at millimetre scale and remains manifold.
2. Measure the pump bore, shaft cartridge bores, seal pockets, bearing seats,
   hull joint pins/sockets, and nozzle pivots.
3. Reject an impeller with visible blade warping, hub cracking, or excessive
   runout.
4. Dry-fit the complete jet drive outside the hull and rotate it by hand.
5. Leak-test the electronics house and shaft cartridge separately.
6. Only after those checks, bond/seal the hull and proceed through the
   physical release gates in `ENGINEERING_BRIEF.md`.

## Current digital verification

The release validator reports `PASS=122 FAIL=0 SKIP=4`. The skips are
intentional optional configurations. The primary assembly contains 38 labeled
components and includes the cannon pan turret, complete propulsion envelopes,
sealed steering linkage route, drain/fill closures, and removable tracking
fins.
