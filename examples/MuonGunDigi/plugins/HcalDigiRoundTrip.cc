// Check that the HCAL digis survive the trip through the raw data format.
//
// The digis were written into FED buffers by HcalDigiToRaw, carried through a
// streamer file, and read back by HcalRawToDigi. Both copies are in the
// event: the simulated ones (the streamer file kept them) and the unpacked
// ones. Every simulated channel the electronics map knows has to come back
// with the same number of samples and, sample by sample, the same ADC count
// and capacitor id. Those are the numbers the reconstruction reads; the
// fiber and channel bits are not compared, because only the unpacker sets
// them (from the electronics map), and the digitiser leaves them zero.
//
// A channel can be lost legitimately in one way: the packer drops digis
// whose channel has no entry in the electronics map. Those are counted
// separately and must stay a small fraction.
#include <map>
#include <string>

#include "DataFormats/HcalDigi/interface/HcalDigiCollections.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"

class HcalDigiRoundTrip : public edm::one::EDAnalyzer<> {
public:
  explicit HcalDigiRoundTrip(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  struct Tally {
    unsigned long original = 0;   // simulated digis
    unsigned long unpacked = 0;   // digis the unpacker produced
    unsigned long matched = 0;    // ... identical in every compared sample
    unsigned long missing = 0;    // simulated, not unpacked
    unsigned long different = 0;  // unpacked, but not identical
  };

  template <typename Collection>
  void compare(const edm::Event&,
               const edm::EDGetTokenT<Collection>& original,
               const edm::EDGetTokenT<Collection>& unpacked,
               Tally&);

  const edm::EDGetTokenT<HBHEDigiCollection> hbheOriginal_, hbheUnpacked_;
  const edm::EDGetTokenT<HODigiCollection> hoOriginal_, hoUnpacked_;
  const double maxMissingFraction_;
  std::map<std::string, Tally> tallies_;
};

HcalDigiRoundTrip::HcalDigiRoundTrip(const edm::ParameterSet& ps)
    : hbheOriginal_(consumes<HBHEDigiCollection>(ps.getParameter<edm::InputTag>("original"))),
      hbheUnpacked_(consumes<HBHEDigiCollection>(ps.getParameter<edm::InputTag>("unpacked"))),
      hoOriginal_(consumes<HODigiCollection>(ps.getParameter<edm::InputTag>("original"))),
      hoUnpacked_(consumes<HODigiCollection>(ps.getParameter<edm::InputTag>("unpacked"))),
      maxMissingFraction_(ps.getParameter<double>("maxMissingFraction")) {}

template <typename Collection>
void HcalDigiRoundTrip::compare(const edm::Event& event,
                                const edm::EDGetTokenT<Collection>& originalToken,
                                const edm::EDGetTokenT<Collection>& unpackedToken,
                                Tally& tally) {
  const auto& original = event.get(originalToken);
  const auto& unpacked = event.get(unpackedToken);
  tally.original += original.size();
  tally.unpacked += unpacked.size();
  for (const auto& digi : original) {
    auto it = unpacked.find(digi.id());
    if (it == unpacked.end()) {
      ++tally.missing;
      continue;
    }
    bool same = it->size() == digi.size();
    for (int i = 0; same && i < digi.size(); ++i)
      same = it->sample(i).adc() == digi.sample(i).adc() && it->sample(i).capid() == digi.sample(i).capid();
    if (same) {
      ++tally.matched;
    } else {
      ++tally.different;
      edm::LogWarning("HcalDigiRoundTrip") << "different after the round trip: " << digi.id() << "\n  simulated " << digi
                                           << "\n  unpacked  " << *it;
    }
  }
}

void HcalDigiRoundTrip::analyze(const edm::Event& event, const edm::EventSetup&) {
  compare(event, hbheOriginal_, hbheUnpacked_, tallies_["HBHE"]);
  compare(event, hoOriginal_, hoUnpacked_, tallies_["HO"]);
}

void HcalDigiRoundTrip::endJob() {
  for (const auto& [name, t] : tallies_) {
    edm::LogPrint("HcalDigiRoundTrip") << name << ": " << t.original << " simulated, " << t.unpacked << " unpacked, "
                                       << t.matched << " identical, " << t.different << " different, " << t.missing
                                       << " not unpacked";
    if (t.original == 0)
      throw cms::Exception("HcalDigiRoundTrip") << "no simulated " << name << " digis to compare";
    if (t.different > 0)
      throw cms::Exception("HcalDigiRoundTrip") << t.different << " " << name << " digis changed in the round trip";
    if (t.missing > maxMissingFraction_ * t.original)
      throw cms::Exception("HcalDigiRoundTrip")
          << t.missing << " of " << t.original << " " << name << " digis were not unpacked";
  }
}

DEFINE_FWK_MODULE(HcalDigiRoundTrip);
