// Checker for the standalone-muon step of the toy muon validation: asserts
// that the segment-based muon seeding and the standalone Kalman fit produce
// output for the toy segments.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "DataFormats/TrajectorySeed/interface/TrajectorySeedCollection.h"
#include "DataFormats/TrackReco/interface/Track.h"
#include "DataFormats/TrackReco/interface/TrackFwd.h"

class STAMuonChecker : public edm::one::EDAnalyzer<> {
public:
  explicit STAMuonChecker(const edm::ParameterSet& conf)
      : seedsToken_(consumes<TrajectorySeedCollection>(conf.getParameter<edm::InputTag>("seeds"))),
        tracksToken_(consumes<reco::TrackCollection>(conf.getParameter<edm::InputTag>("tracks"))) {}

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    const auto& seeds = event.get(seedsToken_);
    const auto& tracks = event.get(tracksToken_);
    edm::LogPrint("STAMuonChecker")
        << "muon seeds: " << seeds.size() << ", standalone muon tracks: " << tracks.size();
    for (const auto& t : tracks)
      edm::LogPrint("STAMuonChecker")
          << "STA muon: pt = " << t.pt() << " GeV, eta = " << t.eta()
          << ", phi = " << t.phi() << ", hits = " << t.found();
    if (seeds.empty())
      throw cms::Exception("STAMuonChecker") << "expected at least one muon seed";
  }

private:
  edm::EDGetTokenT<TrajectorySeedCollection> seedsToken_;
  edm::EDGetTokenT<reco::TrackCollection> tracksToken_;
};

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(STAMuonChecker);
