// Reads a real MiniAOD file: pat::Muon, pat::Jet and reco::GenParticle
// collections.

#include "FWCore/Framework/interface/global/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"

#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/HepMCCandidate/interface/GenParticle.h"

#include <iostream>
#include <vector>

class MiniAODAnalyzer : public edm::global::EDAnalyzer<> {
public:
  explicit MiniAODAnalyzer(const edm::ParameterSet& cfg)
      : muonToken_(consumes<std::vector<pat::Muon>>(edm::InputTag("slimmedMuons"))),
        jetToken_(consumes<std::vector<pat::Jet>>(edm::InputTag("slimmedJets"))),
        genToken_(consumes<std::vector<reco::GenParticle>>(edm::InputTag("prunedGenParticles"))) {}

private:
  void analyze(edm::StreamID, const edm::Event& iEvent, const edm::EventSetup&) const override {
    const auto& muons = iEvent.get(muonToken_);
    const auto& jets = iEvent.get(jetToken_);
    const auto& gens = iEvent.get(genToken_);

    std::cout << "event " << iEvent.id().event() << ": " << muons.size() << " muons, "
              << jets.size() << " jets, " << gens.size() << " gen particles" << std::endl;
    for (const auto& mu : muons) {
      std::cout << "  pat::Muon pt = " << mu.pt() << "  eta = " << mu.eta()
                << "  isGlobal = " << mu.isGlobalMuon() << std::endl;
    }
    for (size_t i = 0; i < jets.size() && i < 3; ++i) {
      std::cout << "  pat::Jet pt = " << jets[i].pt() << "  eta = " << jets[i].eta()
                << "  btag(DeepCSV) = " << jets[i].bDiscriminator("pfDeepCSVJetTags:probb")
                << std::endl;
    }
  }

  edm::EDGetTokenT<std::vector<pat::Muon>> muonToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> jetToken_;
  edm::EDGetTokenT<std::vector<reco::GenParticle>> genToken_;
};

DEFINE_FWK_MODULE(MiniAODAnalyzer);
