// Write a SiPixelLorentzAngle payload covering the geometry this job runs.
//
// CMSSW_20_1 has exactly one producer of SiPixelLorentzAngleRcd,
// SiPixelFakeLorentzAngleESSource, and it cannot be used here:
//
//   SiPixelFakeLorentzAngleESSource.cc:273
//   desc.add<edm::FileInPath>("file",
//       edm::FileInPath("SLHCUpgradeSimulations/Geometry/data/PhaseI/
//                        PixelSkimmedGeometry_phase1.txt"))
//
// The edm::FileInPath constructor runs when the *description* is built, which
// happens during validation whatever the configuration says, so overriding the
// parameter does not help. The file lives in a data-only package that is not a
// dependency of this one and is not in the build, so the job dies before any
// module is constructed.
//
// The payload itself is not hard to produce: a flat tan(theta_L) per module
// over the DetIds of the geometry actually loaded. That is what the fake
// source would have done, and doing it from the TrackerGeometry has the
// additional virtue of always matching the detector in the job - the same
// technique fixes a real phase-0/phase-1 mismatch in
// examples/MuonGunDigi, where the fake source silently supplied nothing.
#include "CondCore/DBOutputService/interface/PoolDBOutputService.h"
#include "CondFormats/SiPixelObjects/interface/SiPixelLorentzAngle.h"
#include "DataFormats/DetId/interface/DetId.h"
#include "DataFormats/SiPixelDetId/interface/PixelSubdetector.h"
#include "FWCore/Utilities/interface/ESGetToken.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/Exception.h"
// GeomDet comes in through TrackerGeometry.h. Including it directly would
// need a release-dependent path: Geometry/CommonDetUnit in 10_6,
// Geometry/CommonTopologies in 20_1.
#include "Geometry/Records/interface/TrackerDigiGeometryRecord.h"
#include "Geometry/TrackerGeometryBuilder/interface/TrackerGeometry.h"

class PixelLorentzAngleWriter : public edm::one::EDAnalyzer<> {
public:
  explicit PixelLorentzAngleWriter(const edm::ParameterSet& ps)
      : geomToken_(esConsumes()),
        record_(ps.getParameter<std::string>("record")),
        value_(static_cast<float>(ps.getParameter<double>("tanLorentzAnglePerTesla"))) {}

  void analyze(const edm::Event&, const edm::EventSetup& es) override {
    if (payload_)
      return;

    const TrackerGeometry& geom = es.getData(geomToken_);
    payload_ = std::make_unique<SiPixelLorentzAngle>();
    for (const auto* unit : geom.detUnits()) {
      const DetId id = unit->geographicalId();
      if (id.subdetId() != PixelSubdetector::PixelBarrel &&
          id.subdetId() != PixelSubdetector::PixelEndcap)
        continue;
      if (!payload_->putLorentzAngle(id.rawId(), value_))
        throw cms::Exception("DuplicateDetId")
            << "module " << id.rawId() << " is in the geometry twice";
      ++modules_;
    }
    if (modules_ == 0)
      throw cms::Exception("NoPixelModules")
          << "the tracker geometry has no pixel det units - wrong geometry loaded?";
  }

  void endJob() override {
    if (!payload_)
      throw cms::Exception("NoPayload") << "no event was processed, so no geometry was seen";

    edm::Service<cond::service::PoolDBOutputService> db;
    if (!db.isAvailable())
      throw cms::Exception("NoDBService") << "PoolDBOutputService is not configured";

    // 20_1 collapsed createNewIOV/appendSinceTime into one call
    db->writeOneIOV(*payload_, db->beginOfTime(), record_);

    edm::LogWarning("PixelLorentzAngleWriter")
        << "wrote tanLorentzAnglePerTesla = " << value_ << " for " << modules_
        << " pixel modules as " << record_;
  }

private:
  const edm::ESGetToken<TrackerGeometry, TrackerDigiGeometryRecord> geomToken_;
  const std::string record_;
  // putLorentzAngle takes a float&, so keep it as one
  float value_;
  std::unique_ptr<SiPixelLorentzAngle> payload_;
  unsigned int modules_ = 0;
};

DEFINE_FWK_MODULE(PixelLorentzAngleWriter);
