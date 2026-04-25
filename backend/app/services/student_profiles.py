import re

from app.models.request_models import StudentProfile
from app.models.response_models import Slide

_KNOWN_MAJORS = [
    "computer science",
    "mechanical engineering",
    "electrical engineering",
    "bioengineering",
    "civil engineering",
    "computer engineering",
    "aerospace engineering",
    "chemical engineering",
    "information science",
    "data science",
]

_INTEREST_PATTERNS = [
    "software",
    "ai",
    "machine learning",
    "cybersecurity",
    "robotics",
    "research",
    "startup",
    "product",
    "data",
    "systems",
]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _infer_major(text: str) -> str | None:
    lowered = _normalize(text)
    for major in _KNOWN_MAJORS:
        if major in lowered:
            return major.title()

    major_match = re.search(r"\b(?:i am|i'm|as a|as an)\s+(?:a |an )?([a-z\s]{3,40})\s+major\b", lowered)
    if major_match:
        return " ".join(part.capitalize() for part in major_match.group(1).split())
    return None


def _infer_interests(text: str) -> list[str]:
    lowered = _normalize(text)
    found: list[str] = []
    for interest in _INTEREST_PATTERNS:
        if interest in lowered and interest not in found:
            found.append(interest)
    return [item.title() if item != "ai" else "AI" for item in found]


def _profile_owner(current_slide: Slide | None) -> str | None:
    if current_slide and current_slide.slideCategory == "individual_lesson" and current_slide.slideAuthor:
        return current_slide.slideAuthor
    return None


def update_student_profiles(
    existing_profiles: dict[str, StudentProfile],
    transcript_chunk: str,
    current_slide: Slide | None,
) -> dict[str, StudentProfile]:
    owner = _profile_owner(current_slide)
    if not owner:
        return existing_profiles

    major = _infer_major(transcript_chunk)
    interests = _infer_interests(transcript_chunk)
    if major is None and not interests:
        return existing_profiles

    updated = dict(existing_profiles)
    previous = updated.get(owner, StudentProfile())
    merged_interests = [*previous.interests]
    for interest in interests:
        if interest not in merged_interests:
            merged_interests.append(interest)

    merged_evidence = [*previous.evidence]
    clipped_evidence = " ".join(transcript_chunk.split())
    if clipped_evidence and clipped_evidence not in merged_evidence:
        merged_evidence.append(clipped_evidence[:180])

    updated[owner] = StudentProfile(
        major=major or previous.major,
        interests=merged_interests,
        evidence=merged_evidence[-4:],
    )
    return updated


def profile_hint(student_profiles: dict[str, StudentProfile], student_name: str | None) -> str | None:
    if not student_name:
        return None
    profile = student_profiles.get(student_name)
    if not profile:
        return None

    parts: list[str] = []
    if profile.major:
        parts.append(profile.major)
    if profile.interests:
        parts.append(", ".join(profile.interests[:2]))
    if not parts:
        return None
    return " | ".join(parts)
