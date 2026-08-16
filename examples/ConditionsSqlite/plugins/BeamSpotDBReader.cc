// Read a BeamSpotObjects payload out of the EventSetup and check it against
// the values the writer put in.
//
// Nothing here knows the payload came from sqlite: the module just asks the
// EventSetup for a record. That indirection is the point - if this passes,
// PoolDBESSource resolved a tag, coral opened the database, and the payload
// deserialized, all through the ordinary conditions path a real job uses.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "CondFormats/BeamSpotObjects/interface/BeamSpotObjects.h"
#include "CondFormats/DataRecord/interface/BeamSpotObjectsRcd.h"

#include <cmath>
#include <iostream>

class BeamSpotDBReader : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit BeamSpotDBReader(const edm::ParameterSet& ps)
      : x_(ps.getParameter<double>("expectedX")),
        y_(ps.getParameter<double>("expectedY")),
        z_(ps.getParameter<double>("expectedZ")),
        sigmaZ_(ps.getParameter<double>("expectedSigmaZ")),
        tolerance_(ps.getParameter<double>("tolerance")) {}

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;
  void check(const char* what, double got, double expected) const;

  const double x_, y_, z_, sigmaZ_, tolerance_;
  unsigned int seen_ = 0;
};

void BeamSpotDBReader::check(const char* what, double got, double expected) const {
  if (std::abs(got - expected) > tolerance_) {
    throw cms::Exception("PayloadMismatch")
        << what << " read back as " << got << ", expected " << expected;
  }
}

void BeamSpotDBReader::analyze(const edm::Event& event, const edm::EventSetup& setup) {
  edm::ESHandle<BeamSpotObjects> handle;
  setup.get<BeamSpotObjectsRcd>().get(handle);

  const BeamSpotObjects& bs = *handle;
  check("x", bs.GetX(), x_);
  check("y", bs.GetY(), y_);
  check("z", bs.GetZ(), z_);
  check("sigmaZ", bs.GetSigmaZ(), sigmaZ_);

  ++seen_;
  std::cout << "run " << event.id().run() << " event " << event.id().event() << ": beam spot ("
            << bs.GetX() << ", " << bs.GetY() << ", " << bs.GetZ() << "), sigmaZ = " << bs.GetSigmaZ()
            << ", xError = " << bs.GetXError() << std::endl;
}

void BeamSpotDBReader::endJob() {
  if (seen_ == 0) {
    throw cms::Exception("NoEvents") << "the payload was never read - the job saw no events";
  }
  std::cout << "beam spot payload verified in " << seen_ << " events" << std::endl;
}

DEFINE_FWK_MODULE(BeamSpotDBReader);
