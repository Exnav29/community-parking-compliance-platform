#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Turn a CycloneDX SBOM into a pinned requirements list (for pip-audit): python scripts/sbom_to_requirements.py SBOM.json > req.txt"""
import json
import sys

sbom = json.load(open(sys.argv[1], encoding="utf-8"))
for c in sbom.get("components", []):
    if c.get("version") and c["name"] != "frappe":  # frappe itself is installed from git, not PyPI
        print(f"{c['name']}=={c['version']}")
