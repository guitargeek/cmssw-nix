// Open a CondCore session against a frontier:// connect string and check
// that the failure comes back from the server rather than from anywhere
// closer to home.
//
// The point is the negative space. If CORAL had not been built with the
// Frontier backend, this would fail in the plugin manager with "unknown
// technology" long before any socket was opened. If the frontier client were
// missing or broken, it would fail in the transport. Getting the stub
// server's own message back means the whole chain worked - CondCore, CORAL's
// FrontierAccess, the frontier client, HTTP, and the XML response parser.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "CondCore/CondDB/interface/ConnectionPool.h"

#include <iostream>
#include <string>

class FrontierProbe : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit FrontierProbe(const edm::ParameterSet& ps)
      : connect_(ps.getParameter<std::string>("connect")),
        expectedError_(ps.getParameter<std::string>("expectedError")) {
    pool_.configure();
  }

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

  const std::string connect_;
  const std::string expectedError_;
  // Long-lived, the way PoolDBESSource holds one for the whole job. Building
  // and tearing one down inside analyze() aborts the process during static
  // destruction with a boost lock_error out of CORAL's connection service.
  cond::persistency::ConnectionPool pool_;
  bool probed_ = false;
};

void FrontierProbe::analyze(const edm::Event&, const edm::EventSetup&) {
  if (probed_)
    return;
  probed_ = true;

  std::cout << "connecting to " << connect_ << std::endl;

  std::string caught;
  {
    cond::persistency::Session session = pool_.createSession(connect_);
    try {
      session.transaction().start(true);
      // any query will do - it only has to make the client talk to the server
      session.existsDatabase();
      session.transaction().commit();
    } catch (const std::exception& e) {
      caught = e.what();
    }
    // unwind the session by hand: a transaction left open holds the
    // connection, and CORAL will not release a connection it thinks is busy
    try {
      if (session.transaction().isActive()) {
        session.transaction().rollback();
      }
      session.close();
    } catch (const std::exception& e) {
      std::cout << "(ignoring an error while closing the session: " << e.what() << ")" << std::endl;
    }
  }

  if (caught.empty()) {
    throw cms::Exception("UnexpectedSuccess")
        << "the stub server answers every query with an error, so the session "
           "should not have succeeded";
  }

  if (caught.find(expectedError_) == std::string::npos) {
    // the interesting failure mode: we got *an* error, but not the server's,
    // so something short of the server rejected the request
    throw cms::Exception("WrongError")
        << "expected the server's message (" << expectedError_ << ") but the failure was: " << caught;
  }

  std::cout << "the frontier server was reached, and answered: " << caught << std::endl;
}

void FrontierProbe::endJob() {
  if (!probed_) {
    throw cms::Exception("NoEvents") << "nothing was probed - the job saw no events";
  }

  // NB the job is not done making noise after this. cmsRun will abort at
  // exit() with a boost lock_error out of CORAL's teardown - see the README.
  // Everything above has already succeeded by then; the abort is an upstream
  // destruction-order bug and nothing this module can head off (purging
  // CORAL's connection pool here does not release the connection).
}

DEFINE_FWK_MODULE(FrontierProbe);
