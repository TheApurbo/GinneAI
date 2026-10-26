from pathlib import Path
import re
import shutil

path = Path("verify_jobs.py")
source = path.read_text(encoding="utf-8")

start_marker = '        if re.search(r"\\$\\s?\\d+'
start = source.find(start_marker)

if start == -1:
    raise SystemExit(
        "STOP: Existing hourly-pay block not found. No changes made."
    )

end = source.find("\n\n    except HTTPError", start)
if end == -1:
    raise SystemExit(
        "STOP: Safe replacement boundary not found. No changes made."
    )

backup = path.with_name("verify_jobs.py.salary_backup")
shutil.copy2(path, backup)

replacement = r'''        # Detect hourly, monthly and annual pay mentions.
        # Detection is not proof that the employer actually pays this amount.
        pay_patterns = [
            (
                "HOURLY",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:hour|hr)\b|per\s+hour\b|per\s+hr\b|"
                r"hourly\b|an?\s+hour\b)",
            ),
            (
                "MONTHLY",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:month|mo)\b|per\s+month\b|"
                r"monthly\b|a\s+month\b)",
            ),
            (
                "ANNUAL",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:year|yr|annum)\b|per\s+(?:year|annum)\b|"
                r"annually\b|annual\b|yearly\b|a\s+year\b)",
            ),
        ]

        row["pay_type_detected"] = "UNKNOWN"
        row["pay_min_detected"] = ""
        row["pay_max_detected"] = ""
        row["pay_currency_detected"] = ""
        row["monthly_equivalent_min"] = ""
        row["monthly_equivalent_max"] = ""
        row["pay_verification_status"] = "UNVERIFIED"
        row["pay_evidence_note"] = "No supported salary pattern detected."

        for pay_type, pattern in pay_patterns:
            match = re.search(pattern, text, flags=re.I)
            if not match:
                continue

            def parse_amount(value):
                return float(value.replace(",", "")) if value else None

            low = parse_amount(match.group("low"))
            high = parse_amount(match.group("high")) or low
            currency = (match.group("currency") or "").upper()

            if currency == "$":
                currency = "USD"
            elif currency == "€":
                currency = "EUR"
            elif currency == "£":
                currency = "GBP"

            row["pay_type_detected"] = pay_type
            row["pay_min_detected"] = low if low is not None else ""
            row["pay_max_detected"] = high if high is not None else ""
            row["pay_currency_detected"] = currency
            row["pay_verification_status"] = "UNVERIFIED"
            row["pay_evidence_note"] = (
                f"{pay_type} salary pattern found in fetched page text; "
                "employer confirmation and context still required."
            )

            if pay_type == "HOURLY":
                row["pay_check"] = "HOURLY_RATE_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = ""
                row["monthly_equivalent_max"] = ""
            elif pay_type == "MONTHLY":
                row["pay_check"] = "MONTHLY_SALARY_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = low if low is not None else ""
                row["monthly_equivalent_max"] = high if high is not None else ""
            else:
                row["pay_check"] = "ANNUAL_SALARY_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = (
                    round(low / 12, 2) if low is not None else ""
                )
                row["monthly_equivalent_max"] = (
                    round(high / 12, 2) if high is not None else ""
                )

            break
        else:
            row["pay_check"] = "NO_SUPPORTED_SALARY_PATTERN_FOUND"
'''

updated = source[:start] + replacement + source[end:]

# Syntax-check before saving the modified script.
compile(updated, str(path), "exec")
path.write_text(updated, encoding="utf-8")

print("Salary detector upgraded successfully.")
print("Backup:", backup)
print("Added pay types: HOURLY, MONTHLY, ANNUAL, UNKNOWN")
print("Annual monthly equivalents are estimates.")
print("Salary verification remains UNVERIFIED.")
