#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Utilities/interface/EDGetToken.h"

#include "DataFormats/EgammaCandidates/interface/GsfElectron.h"

#include <iostream>

class MyAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit MyAnalyzer(const edm::ParameterSet&)
      : electronToken_(consumes<edm::View<reco::GsfElectron>>(edm::InputTag("slimmedElectrons"))) {}

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;

  const edm::EDGetTokenT<edm::View<reco::GsfElectron>> electronToken_;
};

void MyAnalyzer::analyze(const edm::Event& iEvent, const edm::EventSetup& iSetup) {
  std::cout << "event " << iEvent.id().event() << std::endl;

  auto const& electrons = iEvent.get(electronToken_);

  for (auto const& electron : electrons) {
    std::cout << "  electron pt = " << electron.pt() << "  eta = " << electron.eta() << std::endl;
  }
}

// define this as a plug-in
DEFINE_FWK_MODULE(MyAnalyzer);
