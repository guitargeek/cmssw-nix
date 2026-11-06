# Porting notes: what changed between 10_6 and 20_1

The examples that run on both releases (all but CmsDriverChain, which is
20_1 only) use the same configuration files for both. What actually differs,
in one list:

* **Geometry.** The muon geometry builders want `MuonGeometryConstants` in
  the `IdealGeometryRecord` on top of the old `MuonNumberingRecord`; the
  tracker digi geometry gained `PTrackerAdditionalParametersPerDetRcd`.
* **Conditions consolidation.** The strip clusteriser and the HBHE
  reconstructor each read one bundled record
  (`SiStripClusterizerConditionsRcd`, `HcalChannelPropertiesRecord`)
  instead of the individual payloads; the hardcoded HCAL calibrations
  additionally want the ZDC topology.
* **Parameter renames.** `siPixelQualityLabel` →
  `siPixelQualityFromDbLabel`, the clusteriser's `QualityLabel` →
  `ConditionsLabel`, `MaxNumberOfCosmicClusters` →
  `MaxNumberOfStripClusters`; the generic pixel CPE dropped
  `PixelErrorParametrization` and `useLAAlignmentOffsets`, and
  `SiPixelRecHitConverter` dropped `VerboseLevel`.
* **NanoAOD.** The `GenPart` table gained a lepton isolation column,
  computed from miniAOD's packed gen particles; a job that starts from
  the generator drops it, as the shipped `customizeNanoGEN` does.
* **API.** The legacy `setup.get<Record>().get(handle)` is gone; the token
  `esConsumes` form works in both releases. Only `BeamSpotObjects`' renamed
  accessors and `PoolDBOutputService::writeOne` → `writeOneIOV` need
  `#ifdef CMSSW_10_6_ERA`; `PixelGeomDetUnit.h`'s moved package is handled
  by `__has_include`.
