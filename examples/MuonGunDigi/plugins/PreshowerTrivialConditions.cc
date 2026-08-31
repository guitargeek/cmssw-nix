// The four preshower conditions the ECAL digitiser fetches but does not use.
//
// EcalDigiProducer builds its preshower digitiser unconditionally - both the
// old and the fast variant are constructed in the initialiser list, before
// anything looks at doES - and then fetches ESGain, ESMIPToGeVConstant,
// ESPedestals and ESIntercalibConstants from the EventSetup every time the
// geometry changes. Only the *use* of those payloads is behind the switch.
// With doES off, as it is here, the values are read and then discarded.
//
// Nothing in the release provides them without a conditions database:
// EcalTrivialConditionRetriever covers the barrel and the endcap but not the
// preshower, and grepping the release for producers of ESGainRcd finds only
// consumers. So this ESProducer exists to make four fetches succeed. The
// values are nominal, and no number in this example depends on them: the
// preshower is at |eta| > 1.65 and this gun fires into |eta| < 0.8.
//
// This is the same shape as three things MuonIdProducer does in
// python/muon_gun_nano_cfg.py - work happening before the switch that is
// supposed to control it - and it is worth noticing how often it recurs.
#include <memory>

#include "CondFormats/DataRecord/interface/ESGainRcd.h"
#include "CondFormats/DataRecord/interface/ESIntercalibConstantsRcd.h"
#include "CondFormats/DataRecord/interface/ESMIPToGeVConstantRcd.h"
#include "CondFormats/DataRecord/interface/ESPedestalsRcd.h"
#include "CondFormats/ESObjects/interface/ESGain.h"
#include "CondFormats/ESObjects/interface/ESIntercalibConstants.h"
#include "CondFormats/ESObjects/interface/ESMIPToGeVConstant.h"
#include "CondFormats/ESObjects/interface/ESPedestals.h"
#include "FWCore/Framework/interface/ESProducer.h"
#include "FWCore/Framework/interface/ModuleFactory.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"

class PreshowerTrivialConditions : public edm::ESProducer {
public:
  explicit PreshowerTrivialConditions(const edm::ParameterSet& ps)
      : gain_(ps.getParameter<double>("gain")),
        mipToGeVLow_(ps.getParameter<double>("mipToGeVLow")),
        mipToGeVHigh_(ps.getParameter<double>("mipToGeVHigh")) {
    setWhatProduced(this, &PreshowerTrivialConditions::produceGain);
    setWhatProduced(this, &PreshowerTrivialConditions::produceMipToGeV);
    setWhatProduced(this, &PreshowerTrivialConditions::producePedestals);
    setWhatProduced(this, &PreshowerTrivialConditions::produceIntercalibConstants);
  }

  std::unique_ptr<ESGain> produceGain(const ESGainRcd&) {
    return std::make_unique<ESGain>(gain_);
  }

  std::unique_ptr<ESMIPToGeVConstant> produceMipToGeV(const ESMIPToGeVConstantRcd&) {
    return std::make_unique<ESMIPToGeVConstant>(mipToGeVLow_, mipToGeVHigh_);
  }

  // Empty channel containers. The digitiser only hands these to the preshower
  // electronics simulation when doES is on, and it is not.
  std::unique_ptr<ESPedestals> producePedestals(const ESPedestalsRcd&) {
    return std::make_unique<ESPedestals>();
  }

  std::unique_ptr<ESIntercalibConstants> produceIntercalibConstants(
      const ESIntercalibConstantsRcd&) {
    return std::make_unique<ESIntercalibConstants>();
  }

private:
  const float gain_;
  const float mipToGeVLow_;
  const float mipToGeVHigh_;
};

DEFINE_FWK_EVENTSETUP_MODULE(PreshowerTrivialConditions);
