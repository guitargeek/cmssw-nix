// Write a SiPixelLorentzAngle payload that covers the detector actually being
// simulated.
//
// Neither release can use SiPixelFakeLorentzAngleESSource here, for two
// different reasons:
//
// In 10_6 it builds its payload by looping over the DetIds listed in
// CalibTracker/SiPixelESProducers/data/PixelSkimmedGeometry.txt and assigning
// 0.106 to each. That file describes the *phase-0* pixel detector - 1440
// modules - and the 2018 geometry these examples simulate is phase-1, with
// 1856 modules and different DetIds. Nothing in the payload matches,
// SiPixelLorentzAngle::getLorentzAngle returns zero for every module in the
// job, and reconstruction applies no Lorentz correction at all.
//
// In 20_1 it does not get that far:
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
// The phase-0/phase-1 mismatch is not a subtle effect. The digitiser drifts
// the collected charge by tanLA * B * thickness/2 = 0.106 * 3.8 T * 285 um / 2,
// about 57 um, entirely in local x, because the field is along z. Left
// uncorrected that is the dominant term in the pixel residual: measured as
// 51 um against the ~15 um the sensor is capable of, and it vanishes if the
// digitiser's drift is switched off, which is how it was found.
//
// So this writes the same flat 0.106 over the DetIds of the geometry the job
// is actually running, taken from the TrackerGeometry rather than from a file
// describing some other detector.
//
// This file is deliberately identical in examples/MuonGunDigi,
// examples/TrackerLocalReco and examples/TrackingChain: each example is
// self-contained, so the writer is copied rather than shared. Keep the three
// copies byte-identical - they drifted once, into a 10_6 flavour and a 20_1
// flavour, which is what the CMSSW_10_6_ERA gate below now covers instead.
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
      // The explicit form, not the argument-less esConsumes(): 10_6 has
      // token-based esConsumes but not the deduced overload.
      : geomToken_(esConsumes<TrackerGeometry, TrackerDigiGeometryRecord>()),
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

#ifdef CMSSW_10_6_ERA
    if (db->isNewTagRequest(record_))
      db->createNewIOV<SiPixelLorentzAngle>(payload_.get(), db->beginOfTime(), db->endOfTime(), record_);
    else
      db->appendSinceTime<SiPixelLorentzAngle>(payload_.get(), db->currentTime(), record_);
    payload_.release();  // the output service takes ownership
#else
    // 20_1 collapsed createNewIOV/appendSinceTime into one call, and takes a
    // reference rather than adopting the pointer
    db->writeOneIOV(*payload_, db->beginOfTime(), record_);
#endif

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
