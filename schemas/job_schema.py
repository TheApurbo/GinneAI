"""Canonical job schema for Ginne AI Job Hunter."""

CANONICAL_FIELDS = [
    "job_id",
    "title",
    "company",
    "location",
    "remote_type",
    "eligible_countries",
    "country_eligibility_status",
    "pay_type",
    "pay_min",
    "pay_max",
    "currency",
    "pay_period",
    "hourly_rate_usd",
    "employment_type",
    "published_date",
    "description",
    "application_url",
    "source",
    "source_url",
    "page_status",
    "vacancy_status",
    "pay_verification_status",
    "evidence_url",
    "evidence_note",
    "match_score",
    "match_reasons",
    "final_decision",
    "collected_at",
]

UNKNOWN = "UNKNOWN"

def normalize_job(raw):
    """Map known CSV field aliases to the canonical job structure."""
    def first(*names):
        for name in names:
            value = raw.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    job = {field: "" for field in CANONICAL_FIELDS}

    job.update({
        "title": first("title"),
        "company": first("company"),
        "location": first("location"),
        "remote_type": first("remote_type", "remote"),
        "eligible_countries": first(
            "eligible_countries", "country_restrictions"
        ),
        "country_eligibility_status": first(
            "country_eligibility_status",
            "verification_status",
            "country_status",
            "bangladesh_check",
        ) or UNKNOWN,
        "pay_type": first("pay_type"),
        "pay_min": first("pay_min", "pay_min_usd", "salary_min"),
        "pay_max": first("pay_max", "salary_max"),
        "currency": first("currency"),
        "pay_period": first("pay_period", "salary_period"),
        "hourly_rate_usd": first("hourly_rate_usd"),
        "employment_type": first("employment_type"),
        "published_date": first("published_date", "published"),
        "description": first("description"),
        "application_url": first("application_url", "apply_url", "url"),
        "source": first("source"),
        "source_url": first("source_url"),
        "page_status": first("page_status", "page_check"),
        "vacancy_status": first("vacancy_status", "live_status")
            or UNKNOWN,
        "pay_verification_status": first(
            "pay_verification_status", "pay_status", "pay_check"
        ) or UNKNOWN,
        "evidence_url": first("evidence_url", "final_url"),
        "evidence_note": first(
            "evidence_note", "verification_note",
            "verification_notes", "review_hint"
        ),
        "match_score": first("match_score", "score"),
        "match_reasons": first("match_reasons", "reason"),
        "final_decision": first("final_decision") or "NEEDS_VERIFICATION",
        "collected_at": first("collected_at"),
    })

    # Never infer eligibility, open status, or verified pay from keywords.
    job["job_id"] = first("job_id") or make_job_id(job)
    return job

def make_job_id(job):
    import hashlib
    key = "|".join([
        job.get("title", "").strip().lower(),
        job.get("company", "").strip().lower(),
        job.get("application_url", "").strip().lower(),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
