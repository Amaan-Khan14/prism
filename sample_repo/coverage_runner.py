"""Run the authored unittest suite under the Python stdlib line tracer."""

import json
import sys
import trace
import unittest
from pathlib import Path


repo = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(repo / "src"))
suite = unittest.defaultTestLoader.discover(str(repo / "tests"))
tracer = trace.Trace(count=True, trace=False)
result = tracer.runfunc(unittest.TextTestRunner(verbosity=1).run, suite)
counts = {}
for (filename, line), hits in tracer.results().counts.items():
    path = Path(filename)
    try:
        relative = path.relative_to(repo).as_posix()
    except ValueError:
        continue
    if relative.startswith("src/shop/"):
        counts.setdefault(relative, {})[str(line)] = hits
output.write_text(json.dumps(counts, sort_keys=True), encoding="utf-8")
sys.exit(0 if result.wasSuccessful() else 1)
