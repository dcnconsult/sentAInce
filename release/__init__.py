"""Release engineering — the community/commercial boundary (ADR-011) as executable data + gates.

This package is the ONLY authoritative definition of what ships to the public Apache-2.0 community repo. It
reads the private monorepo and writes a derived public tree; it never modifies the organism. See
``release/README.md`` and docs/ADR.md ADR-011.

(Named ``release/`` — NOT ``packaging/`` — because a top-level ``packaging/`` on ``pythonpath=["."]`` would
shadow the real ``packaging`` PyPI library that pytest/pip import.)
"""
