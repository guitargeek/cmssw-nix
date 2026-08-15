# Builds the real (volume-based) CMS magnetic field and probes it at a few
# points. Nothing here is a toy: the field volumes are parsed from the XML
# geometry, and the field inside each of them is interpolated from the grid
# tables of the 3.8 T map (cms-data/MagneticField-Interpolation, installed
# under MagneticField/Interpolation/data by this flake).
import FWCore.ParameterSet.Config as cms

process = cms.Process("MAGFIELD")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# the field geometry (its own XMLIdealGeometryESSource, labelled 'magfield'),
# the parametrized field used inside the tracker volume, and the volume-based
# engine reading the 'grid_160812_3_8t' tables
process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")


def _point(name, xyz, bzMin, bzMax):
    return cms.PSet(
        name=cms.string(name),
        xyz=cms.vdouble(*xyz),
        bzMin=cms.double(bzMin),
        bzMax=cms.double(bzMax),
    )


process.probe = cms.EDAnalyzer(
    "MagneticFieldProbe",
    points=cms.VPSet(
        # inside the solenoid: the nominal 3.8 T along +z
        _point("origin", (0.0, 0.0, 0.0), 3.7, 3.9),
        _point("tracker barrel (r = 50 cm)", (50.0, 0.0, 0.0), 3.7, 3.9),
        _point("tracker endcap (z = 250 cm)", (0.0, 0.0, 250.0), 3.6, 3.9),
        # the coil itself, where the field is already falling off
        _point("coil (r = 320 cm)", (320.0, 0.0, 0.0), 2.6, 3.2),
        # between cryostat and yoke the flux reverses, so the field passes
        # through zero here
        _point("coil/yoke gap (r = 420 cm)", (420.0, 0.0, 0.0), -0.3, 0.3),
        # ... and comes back through the iron pointing the other way. This is
        # the interesting one: no uniform or parametrized field reproduces it,
        # it can only come from the interpolation tables.
        _point("barrel yoke (r = 550 cm)", (550.0, 0.0, 0.0), -1.6, -1.0),
        _point("barrel yoke (r = 650 cm)", (650.0, 0.0, 0.0), -1.6, -1.0),
        _point("endcap yoke (z = 700 cm)", (0.0, 0.0, 700.0), 0.8, 1.4),
        # far outside the magnet the field has essentially died out
        _point("outside (z = 2000 cm)", (0.0, 0.0, 2000.0), -0.2, 0.2),
    ),
)

process.p = cms.Path(process.probe)
