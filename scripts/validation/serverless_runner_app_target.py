"""Compatibility entry point for the packaged notebook load-generator gate.

New installed-wheel callers import ``evalsurge.serverless``. Keep historical
validation imports aliased to the same module so callers and scoped diagnostics
retain one implementation, one set of globals and one Locust load engine.
"""

import sys

from evalsurge import serverless as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
