# Project Catamaran — Marine CAD Engineering Brief

## Objective

Produce a STEP-first, source-controlled prototype of the current 480 mm
deep-V monohull that is coherent enough to print, dry-fit, seal, bench-test,
and then validate in a tethered water trial. The project name remains
“Catamaran”; the active hull geometry is a monohull.

This is a prototype engineering release, not a certified vessel design.
Hydrodynamic performance, self-righting, printed strength, watertightness,
motor loading, cavitation margin, radio range, and autonomous behavior still
require physical tests.

## Coordinate convention

- Units: millimetres.
- Hull frame: X is beam, +X starboard; Y runs bow to stern; Z is up.
- Hull origin: bow tip at Y=0, keel at Z=0.
- Segments: bow Y=0..160, mid Y=160..320, stern Y=320..480.
- Stern-local coordinates: Y=0 at the mid/stern joint and Y=160 at transom.

## Frozen prototype envelope

- Hull: 480 long, 120 chine beam, 128 deck beam, 72 moulded depth.
- Aft deadrise: 20 degrees.
- Nominal all-up design mass: 1.35 kg; allowable prototype range 1.15–1.45 kg.
- Hull construction: three upright-printed segments, 2.4 mm nominal shell,
  bolted/pinned bulkheads, epoxy-sealed wet surfaces.
- Propulsion: one 28 mm axial waterjet on centerline.
- Jet axis: stern-local Z=22, selected to improve static flooding.
- Battery: 3S 2200 mAh LiPo, nominal envelope 106 x 35 x 26.
- Steering: SG90-class servo with at least 0.5 mm clearance per body side.
- Payload: pump-fed water cannon with interchangeable nozzle inserts.

## Purchased-component design envelopes

The exact production SKU must be confirmed before the final purchase. CAD
uses conservative, replaceable interfaces rather than relying on a vendor
photo.

- Motor: Surpass KK 2838 envelope, diameter 28, body length 40, 3.175 shaft
  diameter, 15 shaft projection, M3 mounting on 16/19 mm patterns.
- Motor-to-pump coupling: 3.175-to-4 mm rigid coupler, envelope diameter 12,
  length 20.
- Pump shaft: 4 mm stainless shaft, buy 120 mm and cut after dry assembly.
- Front radial bearing: 4 mm bore sealed bearing envelope, cartridge retained.
- Aft support: MR74-class 4 x 7 x 2.5 sealed bearing in the stator hub.
- Shaft seals: two 4 x 8 x 3 rotary lip seals with a grease cavity; confirm
  shaft finish and seal material before wet operation.
- Steering servo: SG90 nominal body 22.8 x 12.2 x 22.5, flange and horn kept
  as explicit assembly envelopes.
- Cannon pump: common 5 V mini submersible pump envelope 24 x 24 x 45 with
  approximately 7 mm outlet.

## Hydrodynamic intent

- Use fair global bow curves without piecewise flat spots or polygonal stem
  faceting.
- Preserve a clean, pointed entry and add reserve buoyancy through the sheer,
  not a blunt full-width stem.
- Keep the intake flush with the external V-bottom and the internal pump
  sealing interface planar and serviceable.
- Intake mouth target: X +/-14, stern-local Y=72..132.
- Internal sealing pad: top Z=12, at least X +/-22 and Y=68..136.
- Intake transition must be monotonic in area, avoid a sharp T-junction, and
  merge into the round tunnel before the impeller approach.
- Grate projected blockage target: no more than 20 percent.
- Impeller: three connected blades, approximately 27 mm OD in a 28 mm bore.
- Stator: five vanes to avoid a 3/3 wake coincidence.
- Fixed contraction target: 28 mm to approximately 20 mm over about 32 mm.
- Steering occurs in a downstream vectoring nozzle with no overlapping sleeve
  around a fixed cylindrical stub.
- Two replaceable transom tracking fins mount at X=+/-44 using the existing
  trim-tab hardpoints. They remain downstream and outboard of the intake and
  full nozzle sweep.
- Pressurized cooling water is taken downstream of the impeller/stator from
  the fixed contraction; no suction-side cooling tap remains.

## Packaging intent

- Battery remains wholly inside the mid segment and as low as practical.
- Water cannon mounts near the forward half of the mid deck, not on the bow.
- Electronics house sits aft on the mid deck, is tapered and gasketed, and
  must not overlap the cannon reinforcement or deck fasteners.
- Wet pump, propulsion shaft, cooling water, cannon hose, servo linkage,
  high-current wiring, and sealed electronics paths remain physically
  separated and serviceable.
- Every frequently opened cover uses a gasket and machine-reusable fastening
  strategy where practical.
- The transom drain and bow foam-fill port have removable printed closures.
- The steering pushrod passes through an epoxy-in guide that retains a
  purchased RC bellows; the printed guide alone is not the dynamic seal.

## Required CAD outputs

- Parametric build123d source for each printable part.
- One closed positive-volume solid per printable part.
- Labeled STEP assembly containing printed parts and purchased-component
  envelopes.
- STEP as the primary artifact; STL files derived from the validated sources.
- A consolidated print folder with no stale duplicate geometry.

## Validation gates

1. All generators run without exceptions and return the intended solid count.
2. Hull joint pins, sockets, bolt holes, lids, and house fasteners align.
3. Pump flange, hull pad, intake aperture, and transom stack mate without
   material interference.
4. Shaft, bearings, seals, coupler, motor, impeller, and stator are coaxial.
5. Impeller has positive radial and axial clearance throughout the tunnel.
6. Vector nozzle clears its fixed outlet and pivot hardware at center and at
   +/-25 degrees.
7. Servo and pushrod clear the stern lid through the full steering range.
8. Battery, electronics, pump, tubing, and wiring envelopes remain inside
   their service volumes.
9. Pairwise assembly interference is zero except documented press fits,
   gasket compression, and fastener engagement.
10. Hydrostatic calculations cover 1.15–1.45 kg and explicitly account for
    the intake/wet-well caveat.
11. Primary STEP parts and assemblies pass CAD CLI facts/positioning checks.
12. Primary STEP assembly and section-critical parts receive reviewed
    multi-view/section snapshots before release.

## Physical release gates after printing

- Measure printed tunnel roundness and impeller runout before powered testing.
- Balance the impeller and test behind a guard at low voltage first.
- Pressure/leak-test the seal cartridge and electronics enclosure separately.
- Dry-fit every hull joint, deck, pump flange, bearing, shaft, and linkage
  before applying sealant.
- Bathtub-test displacement, trim, heel, intake flooding, and self-righting.
- Tethered pond test at a conservative firmware throttle cap; record current,
  motor temperature, thrust, steering authority, and evidence of ventilation.
- Increase throttle only after the measured current and vibration remain
  inside the selected motor, ESC, shaft, bearing, and printed-part limits.
