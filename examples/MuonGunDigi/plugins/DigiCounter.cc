// Check that digitisation turned the simulated hits into readout digis.
//
// The interesting assertion here is not that digis exist - a digitiser that
// wrote noise into every channel would satisfy that. It is that the modules
// carrying digis are the modules the muon actually crossed. So the analyzer
// reads both the PSimHits and the digis, and requires that most of the
// modules with a SimHit also produced a digi: a minimum-ionising particle
// deposits of order 100 keV in a silicon sensor, far above any sensible
// zero-suppression threshold, so a module that was hit and stayed silent
// means the digitiser and the geometry disagree about which module is which.
//
// The converse is deliberately not required. The strip digitiser adds noise
// and can produce digis in modules with no hit at all, which is correct
// behaviour and not something to assert against.
#include <map>
#include <set>
#include <string>
#include <vector>

#include "DataFormats/Common/interface/DetSetVector.h"
#include "DataFormats/SiPixelDigi/interface/PixelDigi.h"
#include "DataFormats/SiStripDigi/interface/SiStripDigi.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "SimDataFormats/TrackingHit/interface/PSimHitContainer.h"

class DigiCounter : public edm::one::EDAnalyzer<> {
public:
  explicit DigiCounter(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<edm::DetSetVector<PixelDigi>> pixelDigis_;
  const edm::EDGetTokenT<edm::DetSetVector<SiStripDigi>> stripDigis_;
  std::vector<edm::EDGetTokenT<edm::PSimHitContainer>> pixelHits_;
  std::vector<edm::EDGetTokenT<edm::PSimHitContainer>> stripHits_;
  const double minMatchFraction_;
  // a detector configured with an empty InputTag is not checked
  const bool checkPixel_;

  // per-detector tallies, summed over events
  struct Tally {
    unsigned long digis = 0;
    unsigned long adcSum = 0;
    unsigned long zeroAdc = 0;
    unsigned long hitModules = 0;      // modules with a SimHit
    unsigned long matchedModules = 0;  // ... that also produced a digi
  };
  Tally pixel_, strip_;
  unsigned long events_ = 0;
};

DigiCounter::DigiCounter(const edm::ParameterSet& ps)
    : pixelDigis_(consumes<edm::DetSetVector<PixelDigi>>(ps.getParameter<edm::InputTag>("pixelDigis"))),
      stripDigis_(consumes<edm::DetSetVector<SiStripDigi>>(ps.getParameter<edm::InputTag>("stripDigis"))),
      minMatchFraction_(ps.getParameter<double>("minMatchFraction")),
      checkPixel_(!ps.getParameter<edm::InputTag>("pixelDigis").label().empty()) {
  for (const auto& tag : ps.getParameter<std::vector<edm::InputTag>>("pixelSimHits"))
    pixelHits_.push_back(consumes<edm::PSimHitContainer>(tag));
  for (const auto& tag : ps.getParameter<std::vector<edm::InputTag>>("stripSimHits"))
    stripHits_.push_back(consumes<edm::PSimHitContainer>(tag));
}

namespace {
  // the set of modules the simulation left a hit in
  std::set<unsigned int> hitModules(const edm::Event& ev,
                                    const std::vector<edm::EDGetTokenT<edm::PSimHitContainer>>& tokens) {
    std::set<unsigned int> dets;
    for (const auto& t : tokens) {
      edm::Handle<edm::PSimHitContainer> h;
      ev.getByToken(t, h);
      if (!h.isValid())
        continue;
      for (const auto& hit : *h)
        dets.insert(hit.detUnitId());
    }
    return dets;
  }
}  // namespace

void DigiCounter::analyze(const edm::Event& ev, const edm::EventSetup&) {
  ++events_;

  edm::Handle<edm::DetSetVector<PixelDigi>> pix;
  ev.getByToken(pixelDigis_, pix);
  std::set<unsigned int> pixelDigiDets;
  if (pix.isValid()) {
    for (const auto& ds : *pix) {
      pixelDigiDets.insert(ds.detId());
      for (const auto& d : ds) {
        ++pixel_.digis;
        pixel_.adcSum += d.adc();
        if (d.adc() == 0)
          ++pixel_.zeroAdc;
      }
    }
  }

  edm::Handle<edm::DetSetVector<SiStripDigi>> str;
  ev.getByToken(stripDigis_, str);
  std::set<unsigned int> stripDigiDets;
  if (str.isValid()) {
    for (const auto& ds : *str) {
      stripDigiDets.insert(ds.detId());
      for (const auto& d : ds) {
        ++strip_.digis;
        strip_.adcSum += d.adc();
        if (d.adc() == 0)
          ++strip_.zeroAdc;
      }
    }
  }

  for (auto det : hitModules(ev, pixelHits_)) {
    ++pixel_.hitModules;
    if (pixelDigiDets.count(det))
      ++pixel_.matchedModules;
  }
  for (auto det : hitModules(ev, stripHits_)) {
    ++strip_.hitModules;
    if (stripDigiDets.count(det))
      ++strip_.matchedModules;
  }
}

void DigiCounter::endJob() {
  // A detector configured with an empty InputTag is not checked - see the
  // README on why the pixel digitiser needs a conditions database here.
  auto report = [&](const char* what, const Tally& t) {
    const double frac = t.hitModules ? double(t.matchedModules) / double(t.hitModules) : 0.0;
    const double meanAdc = t.digis ? double(t.adcSum) / double(t.digis) : 0.0;
    edm::LogWarning("DigiCounter") << "  " << what << ": " << t.digis << " digis, mean ADC " << meanAdc << ", "
                                   << t.matchedModules << "/" << t.hitModules << " hit modules digitised ("
                                   << 100.0 * frac << "%)";

    if (t.digis == 0)
      throw cms::Exception("NoDigis") << what << ": the digitiser produced nothing, but the simulation left "
                                      << t.hitModules << " modules hit";
    if (t.hitModules == 0)
      throw cms::Exception("NoSimHits") << what << ": no SimHits to digitise - the simulation half of this job "
                                        << "did not run, so the digis prove nothing";
    if (t.zeroAdc == t.digis)
      throw cms::Exception("ZeroAdc") << what << ": every one of the " << t.digis << " digis has ADC 0";
    if (frac < minMatchFraction_)
      throw cms::Exception("DigisNotWhereHitsAre")
          << what << ": only " << t.matchedModules << " of " << t.hitModules
          << " modules with a SimHit produced a digi (" << 100.0 * frac << "%, required "
          << 100.0 * minMatchFraction_ << "%). A minimum-ionising particle cannot cross a silicon sensor "
          << "without leaving one, so the digitiser and the geometry disagree about module identity.";
  };

  edm::LogWarning("DigiCounter") << "digitised " << events_ << " event(s):";
  if (checkPixel_)
    report("pixel", pixel_);
  report("strip", strip_);
  edm::LogWarning("DigiCounter") << "digis OK";
}

DEFINE_FWK_MODULE(DigiCounter);
