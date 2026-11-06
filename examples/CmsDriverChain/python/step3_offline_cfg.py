# Step 3 of the cmsDriver chain (python/chain.py), as the flake check runs
# it: cmsDriver.py writes the configuration, which is then run without
# events and without the conditions database - every module constructed,
# nothing processed (chain.offline).
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "python"))
import chain

exec(open(chain.generate(3)).read())
process = chain.offline(process)
