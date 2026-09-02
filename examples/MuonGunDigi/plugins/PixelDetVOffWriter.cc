// Write an empty SiStripDetVOff payload as SiPixelDetVOffRcd.
//
// 20_1 only, and for the same reason plugins/PixelCablingMapWriter.cc exists:
// a record that is fetched whether or not anything needs its contents.
//
// SiPixelQualityESProducer takes a ListOfRecordToMerge VPSet that reads like
// it selects which records contribute. It does not, for this one:
//
//   SiPixelQualityESProducer.cc:57   voffToken_ = esCC.consumes();
//   SiPixelQualityESProducer.cc:83   dbptr->add(&(iRecord.get(voffToken_)));
//
// Both are unconditional, so the HV/LV-off map is required even when the
// VPSet does not mention it - and nothing in this build produces that record
// (in production it comes from the global tag). The 10_6 producer consumed it
// only when asked, which is why that era needs none of this.
//
// An empty SiStripDetVOff is the physically right payload here: IsModuleVOff
// returns false for every module, i.e. the whole detector is powered, which
// is what a simulation with no HV mask should assume.
#include "CondCore/DBOutputService/interface/PoolDBOutputService.h"
#include "CondFormats/SiStripObjects/interface/SiStripDetVOff.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/Exception.h"

class PixelDetVOffWriter : public edm::one::EDAnalyzer<> {
public:
  explicit PixelDetVOffWriter(const edm::ParameterSet& ps)
      : record_(ps.getParameter<std::string>("record")) {}

  void analyze(const edm::Event&, const edm::EventSetup&) override {}

  void endJob() override {
    edm::Service<cond::service::PoolDBOutputService> db;
    if (!db.isAvailable())
      throw cms::Exception("NoDBService") << "PoolDBOutputService is not configured";

    SiStripDetVOff payload;
    db->writeOneIOV(payload, db->beginOfTime(), record_);

    edm::LogWarning("PixelDetVOffWriter")
        << "wrote an empty SiStripDetVOff (no module off) as " << record_;
  }

private:
  const std::string record_;
};

DEFINE_FWK_MODULE(PixelDetVOffWriter);
