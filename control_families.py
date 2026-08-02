# control_families.py
import re
from typing import Dict, List, Tuple

CONTROL_KEYWORDS = {
    "access_control": [
        "access control",
        "authentication",
        "authorization",
        "least privilege",
        "mfa",
        "multi-factor authentication"
    ],

    "incident_response": [
        "incident response",
        "containment",
        "eradication",
        "recovery"
    ],

    "risk_management": [
        "risk assessment",
        "risk management",
        "vulnerability assessment",
        "threat assessment"
    ],

    "network_security": [
        "electronic security perimeter",
        "firewall",
        "network segmentation",
        "remote access"
    ],

    "asset_management": [
        "asset inventory",
        "asset management",
        "critical asset"
    ],

    "monitoring_logging": [
        "audit log",
        "monitoring",
        "siem",
        "logging"
    ],

    "patch_management": [
        "patch",
        "security update",
        "vulnerability remediation"
    ],

    "business_continuity": [
        "continuity",
        "disaster recovery",
        "resilience"
    ]
}

def detect_controls(text: str):

    text = (text or "").lower()

    controls = []

    hits = {}

    for control, keywords in CONTROL_KEYWORDS.items():

        found = []

        for kw in keywords:

            if kw.lower() in text:
                found.append(kw)

        if found:
            controls.append(control)
            hits[control] = found

    return controls, hits