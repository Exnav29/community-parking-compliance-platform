# SPDX-License-Identifier: Apache-2.0
app_name = "frappe_cpcp"
app_title = "CPCP"
app_publisher = "Johnathan Lightfoot"
app_description = "Community Parking & Compliance Platform"
app_email = "noreply@example.invalid"
app_license = "Apache-2.0"

after_install = "frappe_cpcp.install.after_install"
after_migrate = "frappe_cpcp.install.ensure_roles"

# Every CPCP DocType is guarded by the central authorization service in addition to DocPerm.
# A list filter without a matching document check is unacceptable (PRD 30.1), so both are wired.
_DOCTYPES = [
    "CPCP Estate", "CPCP Gate", "CPCP Zone", "CPCP Unit", "CPCP Person", "CPCP Unit Membership",
    "CPCP Vehicle", "CPCP Vehicle Unit Association", "CPCP Role Assignment", "CPCP Visitor Session",
    "CPCP Visit Event", "CPCP Parking Allegation", "CPCP Allegation Receipt", "CPCP Security Work Item",
    "CPCP Notification Outbox", "CPCP Allegation Review Event", "CPCP Violation Incident",
    "CPCP Officer Evidence", "CPCP Audit Event", "CPCP Sensitive Access Event", "CPCP Policy Version",
    "CPCP Access Grant", "CPCP Communication Attempt", "CPCP Communication Event", "CPCP Warning Notice",
    "CPCP Enforcement Action", "CPCP Incident Charge", "CPCP Appeal", "CPCP Gate Shift", "CPCP Device Registration",
    "CPCP Emergency Access", "CPCP Access Review Flag", "CPCP Work Item Allegation", "CPCP Allegation Attachment",
]
has_permission = {dt: "frappe_cpcp.permissions.has_permission" for dt in _DOCTYPES}
permission_query_conditions = {dt: "frappe_cpcp.permissions.query_conditions" for dt in _DOCTYPES}

# Every request passes the sensitive-doctype guard (journals + denies); see guards.py.
before_request = ["frappe_cpcp.guards.before_request"]

scheduler_events = {
    "hourly": ["frappe_cpcp.services.access_review.run_detection_job"],
    "daily": ["frappe_cpcp.services.retention.purge_expired_access_events"],
}
