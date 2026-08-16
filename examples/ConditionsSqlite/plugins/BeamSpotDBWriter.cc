// Write a BeamSpotObjects payload into a local sqlite conditions database
// through PoolDBOutputService.
//
// The values are deliberately unround so that reading them back proves the
// payload really made the round trip through coral's sqlite backend and the
// boost serialization in CondFormats, rather than a default-constructed
// object happening to match.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "CondCore/DBOutputService/interface/PoolDBOutputService.h"
#include "CondFormats/BeamSpotObjects/interface/BeamSpotObjects.h"

#include <iostream>

class BeamSpotDBWriter : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit BeamSpotDBWriter(const edm::ParameterSet& ps)
      : record_(ps.getParameter<std::string>("record")),
        x_(ps.getParameter<double>("x")),
        y_(ps.getParameter<double>("y")),
        z_(ps.getParameter<double>("z")),
        sigmaZ_(ps.getParameter<double>("sigmaZ")) {}

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

  const std::string record_;
  const double x_, y_, z_, sigmaZ_;
  bool written_ = false;
};

void BeamSpotDBWriter::analyze(const edm::Event& event, const edm::EventSetup&) {
  if (written_)
    return;

  BeamSpotObjects payload;
  payload.SetPosition(x_, y_, z_);
  payload.SetSigmaZ(sigmaZ_);
  payload.SetType(1);
  // a diagonal covariance, so the Get*Error() accessors have something to
  // take the square root of on the way back
  for (int i = 0; i < 7; ++i) {
    payload.SetCovariance(i, i, 1e-4);
  }

  edm::Service<cond::service::PoolDBOutputService> db;
  if (!db.isAvailable()) {
    throw cms::Exception("Configuration") << "PoolDBOutputService is not configured";
  }

  // writeOne copies the payload (storePayload takes a const reference), so
  // the stack object above is fine - it does not take ownership.
  db->writeOne(&payload, db->beginOfTime(), record_);
  written_ = true;

  std::cout << "wrote " << record_ << " for run " << event.id().run() << ": "
            << "x = " << x_ << ", y = " << y_ << ", z = " << z_ << ", sigmaZ = " << sigmaZ_ << std::endl;
}

void BeamSpotDBWriter::endJob() {
  if (!written_) {
    throw cms::Exception("NoPayload") << "no payload was written - the job saw no events";
  }
}

DEFINE_FWK_MODULE(BeamSpotDBWriter);
