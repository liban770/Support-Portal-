import os
import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import SiteSettings

# File signatures ("magic bytes") for allowed types; extension alone is not trusted.
SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".docx": [b"PK\x03\x04"],
}

# Known junk, test, or placeholder phrases
JUNK_PHRASES = {
    "test", "testing", "asdf", "asdfghjk", "qwerty", "none", "n/a", "na",
    "null", "nothing", "dummy", "fake", "junk", "sample", "example",
    "xxx", "zzz", "aaa", "bbb", "ccc", "bla", "blah", "random", "check",
    "idk", "dont know", "don't know", "whatever", "lorem", "ipsum", "asdasd",
    "abc", "xyz", "qwe", "qwert", "qwertz", "pass", "fail", "no reason",
}


def validate_upload(uploaded):
    """Validate extension, size and file signature of an uploaded attachment."""
    if not uploaded:
        return
    ext = os.path.splitext(uploaded.name)[1].lower()
    allowed = settings.ATU_ALLOWED_UPLOAD_EXTENSIONS
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(e.lstrip('.').upper() for e in allowed)}."
        )
    max_mb = SiteSettings.load().max_upload_mb
    if uploaded.size > max_mb * 1024 * 1024:
        raise ValidationError(f"File is too large. Maximum size is {max_mb} MB.")
    if uploaded.size == 0:
        raise ValidationError("The uploaded file is empty.")
    head = uploaded.read(16)
    uploaded.seek(0)
    if not any(head.startswith(sig) for sig in SIGNATURES.get(ext, [])):
        raise ValidationError("The file content does not match its extension.")


def validate_meaningful_text(text, field_label="Description", min_length=15, min_words=2):
    """
    Validates user text to prevent sending empty, spam, repeated gibberish, or joke content.
    Ensures legitimate academic and administrative information is provided.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValidationError(f"{field_label} is required and cannot be empty.")

    if len(cleaned) < min_length:
        raise ValidationError(
            f"{field_label} is too short (minimum {min_length} characters). Please provide specific details."
        )

    # Check for keyboard smash or repeated single character (e.g. "aaaaaaaa", ".....", "1111111")
    letters_and_digits = re.sub(r"\s+", "", cleaned.lower())
    if len(letters_and_digits) >= 5 and len(set(letters_and_digits)) <= 2:
        raise ValidationError(
            f"Please provide meaningful text in {field_label.lower()}, not repeated characters."
        )

    # Check for pure symbols or punctuation
    alphanumeric = re.sub(r"[^\w\s]", "", cleaned)
    if len(alphanumeric.strip()) < 3:
        raise ValidationError(f"{field_label} must contain letters or numbers, not just symbols.")

    # Extract alphanumeric words
    words = [w.lower() for w in re.findall(r"\b[A-Za-z0-9]+\b", cleaned)]
    if len(words) < min_words:
        raise ValidationError(
            f"Please write a complete explanation in {field_label.lower()} (at least {min_words} words)."
        )

    # Check if text is a known single junk pattern
    norm = " ".join(words)
    if norm in JUNK_PHRASES or all(w in JUNK_PHRASES for w in words):
        raise ValidationError(
            f"Please enter genuine, specific details. Placeholder or test values like '{cleaned}' are not accepted."
        )

    # Check for excessive repeated words (e.g. "please please please please")
    if len(words) >= 4 and len(set(words)) == 1:
        raise ValidationError(f"Please provide constructive details rather than repeating the same word.")

    return cleaned


def validate_course_identifier(course):
    """Ensures course title or code has valid academic formatting."""
    cleaned = (course or "").strip()
    if not cleaned or len(cleaned) < 3:
        raise ValidationError("Please provide a valid course code or title (at least 3 characters, e.g. 'CS-201' or 'Calculus I').")

    alphanumeric = re.sub(r"[^\w\s]", "", cleaned)
    if len(alphanumeric.strip()) < 2:
        raise ValidationError("Course identifier must include letters or numbers.")

    if cleaned.lower() in JUNK_PHRASES:
        raise ValidationError("Please enter a valid university course code or title.")

    return cleaned


def validate_absence_dates(start_date, end_date, max_past_days=45, max_future_days=90):
    """Ensures absence dates are realistic, within semester policy, and ordered properly."""
    today = timezone.localdate()
    if start_date:
        earliest_allowed = today - timedelta(days=max_past_days)
        if start_date < earliest_allowed:
            raise ValidationError(
                f"Start date cannot be more than {max_past_days} days in the past ({earliest_allowed:%b %d, %Y}). "
                "Late excuses require formal petition via the Registrar's Office."
            )
        latest_allowed = today + timedelta(days=max_future_days)
        if start_date > latest_allowed:
            raise ValidationError(
                f"Start date cannot be scheduled more than {max_future_days} days in advance ({latest_allowed:%b %d, %Y})."
            )

    if start_date and end_date:
        if end_date < start_date:
            raise ValidationError("End date cannot be earlier than the start date.")
        duration = (end_date - start_date).days + 1
        if duration > 120:
            raise ValidationError(
                f"Selected duration ({duration} days) exceeds maximum portal limit (120 days). "
                "Extended leaves of absence must be processed directly with the Academic Registrar."
            )
