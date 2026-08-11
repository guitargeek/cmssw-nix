// A toy producer that puts a few reco::GsfElectron with made-up kinematics
// into the event. This stands in for the electron collections of a real
// (Mini)AOD file, so that the example is self-contained and needs no
// multi-gigabyte download from the grid.

#include "FWCore/Framework/interface/global/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"

#include "DataFormats/EgammaCandidates/interface/GsfElectron.h"

#include <cmath>
#include <memory>
#include <vector>

class MyElectronProducer : public edm::global::EDProducer<> {
public:
  explicit MyElectronProducer(const edm::ParameterSet&) { produces<std::vector<reco::GsfElectron>>(); }

private:
  void produce(edm::StreamID, edm::Event& iEvent, const edm::EventSetup&) const override;
};

void MyElectronProducer::produce(edm::StreamID, edm::Event& iEvent, const edm::EventSetup&) const {
  auto electrons = std::make_unique<std::vector<reco::GsfElectron>>();

  // a couple of fake electrons whose kinematics depend on the event number
  const auto ievt = iEvent.id().event();
  for (unsigned int i = 0; i < 1 + ievt % 3; ++i) {
    const double pt = 10.0 + 5.0 * i + 0.1 * ievt;
    const double eta = -2.0 + 0.4 * i + 0.01 * ievt;
    const double phi = 0.5 * i;
    const double m = 0.000511;
    math::PtEtaPhiMLorentzVector polarP4{pt, eta, phi, m};
    reco::GsfElectron electron;
    electron.setP4(reco::GsfElectron::P4_COMBINATION, math::XYZTLorentzVector{polarP4}, 0., true);
    electrons->push_back(electron);
  }

  iEvent.put(std::move(electrons));
}

// define this as a plug-in
DEFINE_FWK_MODULE(MyElectronProducer);
