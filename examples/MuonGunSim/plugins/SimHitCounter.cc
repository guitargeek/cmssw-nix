// Counts the SimHits Geant4 produced and checks they are where a muon fired
// through the detector has to leave them.
//
// The point of the assertions is that they cannot pass by accident. A muon
// gun aimed into the barrel must cross the pixel and strip tracker and then
// all four DT stations, so the tracker and DT collections have to be
// non-empty; and because these hits come out of a real transport through the
// real geometry, the energy deposits have to be physical - a minimum-ionising
// particle in silicon leaves of order 100 keV, not zero and not a GeV. A
// simulation that built the wrong geometry, lost the magnetic field or failed
// to attach its sensitive detectors fails at least one of these.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"

#include "SimDataFormats/TrackingHit/interface/PSimHitContainer.h"
#include "SimDataFormats/Track/interface/SimTrackContainer.h"
#include "SimDataFormats/Vertex/interface/SimVertexContainer.h"

#include <map>
#include <string>
#include <vector>

class SimHitCounter : public edm::one::EDAnalyzer<> {
public:
  explicit SimHitCounter(const edm::ParameterSet& ps)
      : minTotalEnergy_(ps.getParameter<double>("minTotalEnergy")),
        maxTotalEnergy_(ps.getParameter<double>("maxTotalEnergy")) {
    for (const auto& tag : ps.getParameter<std::vector<edm::InputTag>>("required")) {
      required_.push_back(tag);
      tokens_.push_back(consumes<edm::PSimHitContainer>(tag));
    }
    simTracks_ = consumes<edm::SimTrackContainer>(ps.getParameter<edm::InputTag>("simTracks"));
    simVertices_ = consumes<edm::SimVertexContainer>(ps.getParameter<edm::InputTag>("simVertices"));
  }

  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<std::vector<edm::InputTag>>("required", {});
    desc.add<edm::InputTag>("simTracks", edm::InputTag("g4SimHits"));
    desc.add<edm::InputTag>("simVertices", edm::InputTag("g4SimHits"));
    desc.add<double>("minTotalEnergy", 0.0);
    desc.add<double>("maxTotalEnergy", 1.0e9);
    descriptions.addDefault(desc);
  }

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    ++events_;

    for (size_t i = 0; i < required_.size(); ++i) {
      const auto& tag = required_[i];
      edm::Handle<edm::PSimHitContainer> hits;
      event.getByToken(tokens_[i], hits);
      if (!hits.isValid()) {
        throw cms::Exception("MissingCollection")
            << "the SimHit collection " << tag.encode() << " is not in the event - "
            << "the simulation did not produce it at all";
      }
      auto& c = counts_[tag.encode()];
      c.hits += hits->size();
      for (const auto& hit : *hits) {
        c.energy += hit.energyLoss();
      }
    }

    edm::Handle<edm::SimTrackContainer> tracks;
    event.getByToken(simTracks_, tracks);
    edm::Handle<edm::SimVertexContainer> vertices;
    event.getByToken(simVertices_, vertices);
    if (tracks.isValid()) {
      nTracks_ += tracks->size();
    }
    if (vertices.isValid()) {
      nVertices_ += vertices->size();
    }
  }

  void endJob() override {
    edm::LogPrint("SimHitCounter") << "simulated " << events_ << " event(s): " << nTracks_
                                   << " SimTracks, " << nVertices_ << " SimVertices";

    bool bad = false;
    for (const auto& tag : required_) {
      const auto& c = counts_[tag.encode()];
      // energyLoss() is in GeV; report keV, which is the scale a MIP works at
      const double keV = c.energy * 1.0e6;
      edm::LogPrint("SimHitCounter")
          << "  " << tag.encode() << ": " << c.hits << " hits, " << keV << " keV deposited";

      if (c.hits == 0) {
        edm::LogPrint("SimHitCounter") << "    -> EMPTY, but a muon through this detector must hit it";
        bad = true;
        continue;
      }
      if (keV < minTotalEnergy_ || keV > maxTotalEnergy_) {
        edm::LogPrint("SimHitCounter")
            << "    -> " << keV << " keV is outside the physical range [" << minTotalEnergy_ << ", "
            << maxTotalEnergy_ << "] keV";
        bad = true;
      }
    }

    if (nTracks_ == 0) {
      edm::LogPrint("SimHitCounter") << "  no SimTracks at all - nothing was transported";
      bad = true;
    }
    if (bad) {
      throw cms::Exception("SimHitsMissing")
          << "the simulation ran but did not produce the hits a muon gun has to produce";
    }
    edm::LogPrint("SimHitCounter") << "SimHits OK";
  }

private:
  struct Count {
    unsigned long hits = 0;
    double energy = 0.0;  // GeV
  };

  std::vector<edm::InputTag> required_;
  std::vector<edm::EDGetTokenT<edm::PSimHitContainer>> tokens_;
  edm::EDGetTokenT<edm::SimTrackContainer> simTracks_;
  edm::EDGetTokenT<edm::SimVertexContainer> simVertices_;
  const double minTotalEnergy_;
  const double maxTotalEnergy_;

  std::map<std::string, Count> counts_;
  unsigned long events_ = 0;
  unsigned long nTracks_ = 0;
  unsigned long nVertices_ = 0;
};

DEFINE_FWK_MODULE(SimHitCounter);
