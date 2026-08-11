"""Print all whitelisted Subsystem/Package paths from the build config."""
import sys

import yaml

with open(sys.argv[1]) as f:
    config = yaml.safe_load(f)

for subsystem, cfg in config["subsystems"].items():
    for pkg in (cfg or {}).get("whitelist", []):
        print(f"{subsystem}/{pkg}")
