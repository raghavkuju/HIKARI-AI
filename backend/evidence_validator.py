
"""
HIKARI AI v3.3
Smart Evidence Verification Engine

Features:
- Official source identification
- Historical information detection
- Source freshness assessment
- Candidate answer matching
- Conflicting evidence detection
- Confidence assessment

Important:
This module checks evidence signals.
It does not guarantee factual correctness.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from collections import defaultdict


# ============================================
# CONFIGURATION
# ============================================

STATUS_VERIFIED = "supported"
STATUS_CONFLICT = "conflicting_evidence"
STATUS_INSUFFICIENT = "insufficient_evidence"

HISTORICAL_MARKERS = (
    "former",
    "previous",
    "ex-chief minister",
    "former chief minister",
    "served as",
    "was the chief minister",
    "पूर्व मुख्यमंत्री",
    "भूतपूर्व",
)

CURRENT_MARKERS = (
    "current",
    "incumbent",
    "present",
    "currently serving",
    "मुख्यमंत्री",
)

OFFICIAL_DOMAINS = (
    ".gov.in",
    ".nic.in",
)


# ============================================
# DOMAIN UTILITIES
# ============================================

def source_domain(url):
    try:
        host = urlsplit(
            str(url or "")
        ).hostname or ""

        return host.lower().removeprefix("www.")

    except ValueError:
        return ""


def is_official_source(source):
    domain = source_domain(
        source.get("url", "")
    )

    return domain.endswith(OFFICIAL_DOMAINS)


# ============================================
# TEXT UTILITIES
# ============================================

def normalize_claim(text):
    text = str(text or "").lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def source_text(source):
    return " ".join(
        str(source.get(field) or "")
        for field in (
            "title",
            "snippet",
            "page_text",
        )
    ).strip()


def extract_years(text):
    years = re.findall(
        r"\b(?:19|20)\d{2}\b",
        str(text or ""),
    )

    return sorted(
        set(int(year) for year in years)
    )


# ============================================
# HISTORICAL DETECTION
# ============================================

def source_historical_signal(source, text=None):
    evidence = normalize_claim(
        text if text is not None
        else source_text(source)
    )

    if any(
        marker in evidence
        for marker in HISTORICAL_MARKERS
    ):
        return True

    url = str(
        source.get("url") or ""
    ).lower()

    # Known outdated government listing.
    if (
        "cgvidhansabha.gov.in/english/cm.htm" in url
        and "raman singh" in evidence
    ):
        return True

    return False


def source_current_signal(source):
    evidence = normalize_claim(
        source_text(source)
    )

    return any(
        marker in evidence
        for marker in CURRENT_MARKERS
    )


# ============================================
# SOURCE ANALYSIS
# ============================================

def analyze_source(source):
    evidence = source_text(source)

    historical = source_historical_signal(
        source,
        evidence,
    )

    return {
        "url": source.get("url", ""),
        "domain": source_domain(
            source.get("url", "")
        ),
        "official": is_official_source(source),
        "historical_signal": historical,
        "current_signal": source_current_signal(
            source
        ),
        "years": extract_years(evidence),
        "has_evidence": bool(evidence.strip()),
        "evidence_type": source.get(
            "content_type",
            "snippet",
        ),
    }


# ============================================
# CANDIDATE MATCHING
# ============================================

def candidate_in_source(candidate, source):
    candidate = normalize_claim(candidate)

    if not candidate:
        return False

    evidence = normalize_claim(
        source_text(source)
    )

    return candidate in evidence


# ============================================
# CONFLICT DETECTION
# ============================================

def detect_conflicts(
    candidate_answer,
    sources,
):
    """
    Detects only explicit conflicting signals.

    It cannot reliably infer arbitrary
    contradictions between natural-language
    claims.

    A historical mention alone is not
    automatically a contradiction.
    """

    candidate = normalize_claim(
        candidate_answer
    )

    if not candidate:
        return []

    conflicts = []

    for source in sources:
        if source_historical_signal(source):
            continue

        evidence = normalize_claim(
            source_text(source)
        )

        if not evidence:
            continue

        # Only detect explicit negation
        # near the candidate text.
        escaped = re.escape(candidate)

        patterns = [
            rf"\bnot\s+{escaped}\b",
            rf"\bno\s+longer\s+{escaped}\b",
        ]

        for pattern in patterns:
            if re.search(pattern, evidence):
                conflicts.append({
                    "url": source.get("url", ""),
                    "type": "explicit_negation",
                    "evidence": evidence[:300],
                })
                break

    return conflicts


# ============================================
# CONFIDENCE ASSESSMENT
# ============================================

def calculate_confidence(
    matching_sources,
    conflicts,
):
    """
    Returns a conservative evidence
    strength indicator.

    This is not a calibrated probability.
    """

    if conflicts:
        return "low"

    independent_domains = {
        item["domain"]
        for item in matching_sources
        if item.get("domain")
    }

    official_matches = sum(
        1
        for item in matching_sources
        if item.get("official")
    )

    if (
        len(independent_domains) >= 2
        and official_matches >= 1
    ):
        return "medium"

    return "low"


# ============================================
# MAIN EVIDENCE VALIDATOR
# ============================================

def assess_evidence(
    question,
    sources,
    candidate_answer=None,
):
    question = str(question or "").strip()
    sources = sources or []

    if not sources:
        return {
            "status": STATUS_INSUFFICIENT,
            "reason": "No web evidence was retrieved.",
            "confidence": "low",
            "sources_checked": 0,
            "claims": [],
            "conflicts": [],
        }

    analyzed = [
        analyze_source(source)
        for source in sources
    ]

    usable = [
        (source, analysis)
        for source, analysis in zip(
            sources,
            analyzed,
        )
        if analysis["has_evidence"]
        and not analysis["historical_signal"]
    ]

    historical_count = sum(
        1
        for item in analyzed
        if item["historical_signal"]
    )

    if not usable:
        return {
            "status": STATUS_INSUFFICIENT,
            "reason": (
                "No usable non-historical "
                "evidence was found."
            ),
            "confidence": "low",
            "sources_checked": len(sources),
            "historical_sources": historical_count,
            "claims": analyzed,
            "conflicts": [],
        }

    candidate = normalize_claim(
        candidate_answer
    )

    if not candidate:
        return {
            "status": STATUS_INSUFFICIENT,
            "reason": (
                "No candidate answer was "
                "provided for verification."
            ),
            "confidence": "low",
            "sources_checked": len(sources),
            "usable_sources": len(usable),
            "historical_sources": historical_count,
            "claims": analyzed,
            "conflicts": [],
        }

    matching_sources = []

    for source, analysis in usable:
        if candidate_in_source(
            candidate,
            source,
        ):
            matching_sources.append(
                analysis
            )

    conflicts = detect_conflicts(
        candidate,
        sources,
    )

    confidence = calculate_confidence(
        matching_sources,
        conflicts,
    )

    if conflicts:
        status = STATUS_CONFLICT
        reason = (
            "Explicit contradictory wording "
            "was found in retrieved evidence."
        )

    elif not matching_sources:
        status = STATUS_INSUFFICIENT
        reason = (
            "Candidate answer was not found "
            "in usable evidence."
        )

    else:
        # Matching text is not proof.
        # Do not automatically claim verification.
        status = STATUS_INSUFFICIENT
        reason = (
            "Candidate answer appears in "
            "retrieved sources, but factual "
            "verification is incomplete."
        )

    return {
        "status": status,
        "reason": reason,
        "confidence": confidence,
        "sources_checked": len(sources),
        "usable_sources": len(usable),
        "historical_sources": historical_count,
        "candidate_matches": len(
            matching_sources
        ),
        "claims": analyzed,
        "conflicts": conflicts,
        "verified_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }
