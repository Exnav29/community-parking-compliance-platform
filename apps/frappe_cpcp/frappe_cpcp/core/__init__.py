# SPDX-License-Identifier: Apache-2.0
"""Framework-independent CPCP domain logic.

Nothing in this package may import ``frappe``. Keeping the rules pure makes the
safety-critical behaviour (authorization, notice clocks, charges, state machines)
unit-testable without a database and reusable by the control plane.
"""
