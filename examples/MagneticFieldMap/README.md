# MagneticFieldMap

Builds the **real CMS magnetic field** — the volume-based engine, not the
uniform 3.8 T approximation the other examples use — and probes it at a few
points.

Two ingredients come together here:

* the *field geometry*: a second `XMLIdealGeometryESSource` (labelled
  `magfield`, with an `ESPrefer` so it does not collide with the detector
  geometry) parses `MagneticFieldVolumes_160812_{1,2}.xml` into the ~2900
  volumes the field is described in,
* the *field values*: inside each volume they are interpolated from the grid
  tables of the 3.8 T map, which live in the `cms-data` external
  `MagneticField-Interpolation` and are installed by this flake under
  `MagneticField/Interpolation/data/grid_160812_3_8t/`.

Inside the tracker volume the engine uses the parametrized (`OAE_1103l_071212`)
field instead of the tables, which is what production does as well.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/magfield_cfg.py
```

Expected output:

```
origin at (0, 0, 0) cm: B = (-0, -0, 3.8112) T, |B| = 3.8112 T
tracker barrel (r = 50 cm) at (50, 0, 0) cm: B = (...) T, |B| = 3.81353 T
tracker endcap (z = 250 cm) at (0, 0, 250) cm: B = (...) T, |B| = 3.6834 T
coil (r = 320 cm) at (320, 0, 0) cm: B = (...) T, |B| = 2.93905 T
coil/yoke gap (r = 420 cm) at (420, 0, 0) cm: B = (...) T, |B| = 0.00668601 T
barrel yoke (r = 550 cm) at (550, 0, 0) cm: B = (...) T, |B| = 1.28938 T
barrel yoke (r = 650 cm) at (650, 0, 0) cm: B = (...) T, |B| = 1.28246 T
endcap yoke (z = 700 cm) at (0, 0, 700) cm: B = (...) T, |B| = 1.08801 T
outside (z = 2000 cm) at (0, 0, 2000) cm: B = (...) T, |B| = 0.000210742 T
```

The shape of that profile is the actual test. The field is 3.81 T on the
beam line, falls off through the coil, passes through **zero** in the gap
between cryostat and return yoke as the flux turns around, and comes back
through the iron with the *opposite* sign (`Bz = -1.29 T` at r = 550 cm)
before dying out far from the magnet. Neither the uniform field the other
examples use nor the parametrized tracker field reproduces that reversal —
only the interpolation tables do, so a missing or mis-installed grid file
cannot pass this test.

The analyzer throws (non-zero exit) if any probed `Bz` falls outside the
range the map is expected to give, so this doubles as a regression test for
the field geometry and the grid tables.

## Note

`edmPluginRefresh` reports a plugin library it cannot `dlopen` as an *empty*
`.edmplugincache`, not as an error — the failure then surfaces much later as
`Unable to find plugin ... Please check spelling of name`. If that happens,
`ctypes.CDLL()` the library to see the undefined symbol. Here it was the
`IdealMagneticFieldRecord` typelookup symbol, i.e. a missing link against
`MagneticFieldRecords`.
