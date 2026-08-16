// Checks the generated event content of the NanoGen example: finds the two
// hardest opposite-charge status-1 muons and requires their invariant mass to
// sit near the Z peak often enough over the run. Together with the PyROOT
// readback of the nanoAOD file (nanogen_cfg_check.py) this validates the
// whole generation chain, not just that files got written.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "DataFormats/HepMCCandidate/interface/GenParticle.h"

class GenZmumuChecker : public edm::one::EDAnalyzer<> {
public:
  explicit GenZmumuChecker(const edm::ParameterSet& conf)
      : genParticlesToken_(consumes<reco::GenParticleCollection>(
            conf.getParameter<edm::InputTag>("genParticles"))),
        minZFraction_(conf.getParameter<double>("minZFraction")) {}

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    const auto& genParticles = event.get(genParticlesToken_);

    const reco::GenParticle* muPlus = nullptr;
    const reco::GenParticle* muMinus = nullptr;
    for (const auto& p : genParticles) {
      if (p.status() != 1 || std::abs(p.pdgId()) != 13)
        continue;
      auto& slot = p.pdgId() == -13 ? muPlus : muMinus;
      if (!slot || p.pt() > slot->pt())
        slot = &p;
    }

    ++nEvents_;
    if (muPlus && muMinus) {
      const double mass = (muPlus->p4() + muMinus->p4()).M();
      if (std::abs(mass - 91.19) < 15.)
        ++nZ_;
      if (nEvents_ <= 5)
        edm::LogPrint("GenZmumuChecker") << "event " << nEvents_ << ": m(mumu) = " << mass << " GeV";
    }
  }

  void endJob() override {
    const double fraction = nEvents_ ? double(nZ_) / nEvents_ : 0.;
    edm::LogPrint("GenZmumuChecker") << nZ_ << " of " << nEvents_
                                     << " events with m(mumu) within 15 GeV of the Z peak";
    if (fraction < minZFraction_)
      throw cms::Exception("GenZmumuChecker")
          << "only " << fraction << " of events look like Z->mumu (expected >= " << minZFraction_ << ")";
  }

private:
  edm::EDGetTokenT<reco::GenParticleCollection> genParticlesToken_;
  const double minZFraction_;
  unsigned int nEvents_ = 0;
  unsigned int nZ_ = 0;
};

DEFINE_FWK_MODULE(GenZmumuChecker);
