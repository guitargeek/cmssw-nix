// Write an empty SiPixelFedCablingMap, because the pixel digitiser insists on
// having one and never looks at it.
//
// SiPixelDigitizerAlgorithm::initializeEvent does
//
//   es.get<SiPixelFedCablingMapRcd>().get(map_);   // line 128
//
// unconditionally - there is no switch beside the use_deadmodule_DB_ and
// use_LorentzAngle_DB_ guards on the lines above it, so the record has to
// exist or the job dies on the first event. The two places that actually
// dereference the handle are both behind conditions that are off here:
//
//   line 1737   inside `if (eff.PixelFEDChannelCollection_ != nullptr)`,
//               which is only filled when KillBadFEDChannels is set
//   line 2243   inside `if (SiPixelBadModule_->IsRocBad(detID, j))`, which
//               never fires against a fake quality payload that marks
//               nothing bad
//
// A real map cannot be built here in any case. SiPixelFedCablingMapBuilder
// needs an ASCII module-to-link description, and the only ones in the release
// are phase-0 (three barrel layers, in CalibTracker/SiPixelConnectivity/test,
// which this build does not install). The phase-1 file the 2018 detector
// would need, pixelToLNK.ascii_phase1_v1, is named by the release's own
// writer configuration and is not shipped with it.
//
// So the choice is between an empty map and a phase-0 map describing a
// detector this job is not simulating. Empty is the honest one: it cannot be
// mistaken for a real cabling description, and if either guarded branch above
// were ever reached, pathToDetUnit returns an empty vector and the loops that
// follow do nothing rather than reading a map for the wrong geometry.
#include "CondCore/DBOutputService/interface/PoolDBOutputService.h"
#include "CondFormats/SiPixelObjects/interface/SiPixelFedCablingMap.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/Exception.h"

class PixelCablingMapWriter : public edm::one::EDAnalyzer<> {
public:
  explicit PixelCablingMapWriter(const edm::ParameterSet& ps)
      : record_(ps.getParameter<std::string>("record")),
        version_(ps.getParameter<std::string>("version")) {}

  void analyze(const edm::Event&, const edm::EventSetup&) override {}

  void endJob() override {
    edm::Service<cond::service::PoolDBOutputService> db;
    if (!db.isAvailable())
      throw cms::Exception("NoDBService") << "PoolDBOutputService is not configured";

    SiPixelFedCablingMap payload(version_);
    if (db->isNewTagRequest(record_))
      db->createNewIOV<SiPixelFedCablingMap>(&payload, db->beginOfTime(), db->endOfTime(), record_);
    else
      db->appendSinceTime<SiPixelFedCablingMap>(&payload, db->currentTime(), record_);

    edm::LogWarning("PixelCablingMapWriter")
        << "wrote an empty SiPixelFedCablingMap (version '" << version_ << "') as " << record_;
  }

private:
  const std::string record_;
  const std::string version_;
};

DEFINE_FWK_MODULE(PixelCablingMapWriter);
