#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""License policy check over CycloneDX SBOMs (PRD 55.1, AC-126): fail on unknown or copyleft licences that have no recorded review.

    python scripts/license_check.py docs/legal/sbom/*.cdx.json
Policy: permissive licences pass. Weak copyleft (LGPL/MPL/EPL) passes only if listed in docs/legal/license-exceptions.json with a reason
(used as a separate library, not copied into CPCP). Strong copyleft (GPL/AGPL/SSPL/BUSL) or UNKNOWN fails unless explicitly excepted.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERMISSIVE = {"MIT", "MIT-0", "BSD-2-Clause", "BSD-3-Clause", "BSD", "ISC", "Apache-2.0", "Apache", "0BSD", "Unlicense", "CC0-1.0", "Python-2.0", "PSF-2.0",
              "BlueOak-1.0.0", "CC-BY-4.0", "CC-BY-3.0", "Zlib", "WTFPL", "BSD-1-Clause", "Artistic-2.0", "ZPL-2.1", "HPND", "MIT-CMU", "PSF"}
WEAK = {"LGPL-2.1", "LGPL-3.0", "LGPL-2.0", "LGPL", "MPL-2.0", "EPL-2.0", "EPL-1.0", "MPL-1.1", "CDDL-1.0"}
STRONG = re.compile(r"(^|[^L])GPL|AGPL|SSPL|BUSL|Commons-Clause", re.I)


def licenses_of(comp: dict) -> list[str]:
    out = []
    for entry in comp.get("licenses", []):
        lic = entry.get("license") or {}
        out.append(lic.get("id") or lic.get("name") or entry.get("expression") or "UNKNOWN")
    return out or ["UNKNOWN"]


CLASSIFIER = {
    "BSD License": "BSD", "Apache Software License": "Apache-2.0", "MIT License": "MIT", "ISC License (ISCL)": "ISC", "Python Software Foundation License": "PSF-2.0",
    "Zope Public License": "ZPL-2.1", "The Unlicense (Unlicense)": "Unlicense", "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1", "GNU Library or Lesser General Public License (LGPL)": "LGPL",
    "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0", "GNU General Public License v2 (GPLv2)": "GPL-2.0", "GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "Public Domain": "Unlicense", "Historical Permission Notice and Disclaimer (HPND)": "HPND",
}


def normalise(token: str) -> str:
    t = token.strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1]
    if t.startswith("License :: OSI Approved :: "):
        t = CLASSIFIER.get(t[len("License :: OSI Approved :: "):], t)
    t = re.sub(r"-or-later|-only|\+$", "", t)
    aliases = {"Apache License 2.0": "Apache-2.0", "Apache 2.0": "Apache-2.0", "Apache Software License": "Apache-2.0", "MIT License": "MIT", "BSD License": "BSD",
               "Python Software Foundation License": "PSF-2.0", "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1",
               "GNU Library or Lesser General Public License (LGPL)": "LGPL", "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0", "ISC License (ISCL)": "ISC",
               "Zope Public License": "ZPL-2.1", "BSD-3-Clause AND Apache-2.0": "BSD-3-Clause"}
    return aliases.get(t, t)


def classify(expr: str) -> str:
    """OR: the consumer may pick the most permissive option; AND: all parts must pass (worst wins)."""
    parts_or = re.split(r"\s+OR\s+", expr)
    results = []
    for alt in parts_or:
        worst = "permissive"
        for tok in re.split(r"\s+AND\s+|\s*/\s*", alt):
            n = normalise(tok)
            if n in PERMISSIVE or n.replace("Apache License, Version 2.0", "Apache-2.0") == "Apache-2.0":
                lvl = "permissive"
            elif n in WEAK or n.startswith(("LGPL", "MPL", "EPL")):
                lvl = "weak"
            elif STRONG.search(n):
                lvl = "strong"
            else:
                lvl = "unknown"
            order = ["permissive", "weak", "unknown", "strong"]
            worst = max(worst, lvl, key=order.index)
        results.append(worst)
    return min(results, key=["permissive", "weak", "unknown", "strong"].index)


def main(paths: list[str]) -> int:
    exceptions = {}
    ex_file = ROOT / "docs" / "legal" / "license-exceptions.json"
    if ex_file.exists():
        exceptions = json.loads(ex_file.read_text(encoding="utf-8")).get("packages", {})
    failed, review, total = [], [], 0
    for path in paths:
        sbom = json.loads(Path(path).read_text(encoding="utf-8"))
        for comp in sbom.get("components", []):
            total += 1
            name = f"{comp.get('name')}@{comp.get('version')}"
            expr = " AND ".join(licenses_of(comp))
            level = classify(expr)
            excepted = comp.get("name") in exceptions
            if level in ("weak", "unknown", "strong") and not excepted:
                (review if level == "weak" else failed).append((Path(path).name, name, expr, level))
    print(f"checked {total} components from {len(paths)} SBOM(s)")
    for f, n, e, lv in review:
        print(f"  NEEDS REVIEW (weak copyleft, record a reason in license-exceptions.json): {n} [{e}] ({f})")
    for f, n, e, lv in failed:
        print(f"  FAIL {lv}: {n} [{e}] ({f})")
    if failed or review:
        return 1
    print("license policy: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [str(p) for p in (ROOT / "docs" / "legal" / "sbom").glob("*.cdx.json")]))
