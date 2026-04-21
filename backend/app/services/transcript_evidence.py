import re
from dataclasses import asdict, dataclass


CLAIM_MARKERS = [
    "improve",
    "improves",
    "improved",
    "increase",
    "increases",
    "decrease",
    "decreases",
    "reduce",
    "reduces",
    "faster",
    "better",
    "more accurate",
    "efficient",
    "effective",
    "works",
    "helps",
    "solves",
    "addresses",
]
TECH_MARKERS = [
    "fastapi",
    "next",
    "next.js",
    "react",
    "python",
    "api",
    "database",
    "sql",
    "sqlite",
    "supabase",
    "postgres",
    "model",
    "llm",
    "ai",
    "deepgram",
    "groq",
]
EVIDENCE_MARKERS = [
    "survey",
    "interview",
    "tested",
    "test",
    "measured",
    "metric",
    "metrics",
    "baseline",
    "accuracy",
    "users told us",
    "user feedback",
    "observed",
    "data",
    "results",
    "evidence",
]
TRADEOFF_MARKERS = [
    "because",
    "tradeoff",
    "trade-off",
    "compared",
    "instead",
    "rather than",
    "chosen",
    "we chose",
    "we picked",
]
VAGUE_MARKERS = [
    "better",
    "efficient",
    "useful",
    "helpful",
    "improve",
    "innovative",
    "smart",
    "easy",
    "seamless",
]


@dataclass
class TranscriptEvidence:
    summary: str
    claims: list[str]
    technicalChoices: list[str]
    metrics: list[str]
    evidenceMarkers: list[str]
    tradeoffMarkers: list[str]
    vaguePhrases: list[str]
    unansweredGaps: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _extract_marker_hits(text: str, markers: list[str], limit: int = 4) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for marker in markers:
        if marker in lowered and marker not in hits:
            hits.append(marker)
        if len(hits) >= limit:
            break
    return hits


def _clip(items: list[str], limit: int = 4) -> list[str]:
    seen: list[str] = []
    for item in items:
        trimmed = item.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.append(trimmed)
        if len(seen) >= limit:
            break
    return seen


def extract_transcript_evidence(recent_transcript: list[str], transcript_chunk: str) -> TranscriptEvidence:
    combined = " ".join([*recent_transcript[-4:], transcript_chunk]).strip()
    sentences = _normalize_sentences(combined)
    if not sentences:
        return TranscriptEvidence(
            summary="",
            claims=[],
            technicalChoices=[],
            metrics=[],
            evidenceMarkers=[],
            tradeoffMarkers=[],
            vaguePhrases=[],
            unansweredGaps=[],
        )

    claims: list[str] = []
    technical_choices: list[str] = []
    metrics: list[str] = []
    evidence_hits = _extract_marker_hits(combined, EVIDENCE_MARKERS)
    tradeoff_hits = _extract_marker_hits(combined, TRADEOFF_MARKERS)
    vague_hits = _extract_marker_hits(combined, VAGUE_MARKERS)
    unanswered_gaps: list[str] = []

    metric_regex = re.compile(r"\b\d+(?:\.\d+)?(?:%| percent| seconds| ms| users| people| tests?)\b", re.IGNORECASE)

    for sentence in sentences:
        lowered = sentence.lower()
        found_metrics = metric_regex.findall(sentence)
        metrics.extend(found_metrics)

        if _contains_any(lowered, CLAIM_MARKERS):
            claims.append(sentence)
            has_support = bool(found_metrics) or _contains_any(lowered, EVIDENCE_MARKERS)
            if not has_support:
                unanswered_gaps.append(f"Claim lacks evidence: {sentence}")

        if _contains_any(lowered, TECH_MARKERS):
            technical_choices.append(sentence)
            if not _contains_any(lowered, TRADEOFF_MARKERS):
                unanswered_gaps.append(f"Technical choice lacks justification: {sentence}")

        if ("user" in lowered or "student" in lowered or "problem" in lowered) and not _contains_any(lowered, EVIDENCE_MARKERS):
            unanswered_gaps.append(f"Problem or user need lacks support: {sentence}")

    summary = " ".join(sentences[:2])[:260]
    if vague_hits and not metrics:
        unanswered_gaps.append("Broad claims are present without concrete metrics.")

    return TranscriptEvidence(
        summary=summary,
        claims=_clip(claims),
        technicalChoices=_clip(technical_choices),
        metrics=_clip(metrics),
        evidenceMarkers=_clip(evidence_hits),
        tradeoffMarkers=_clip(tradeoff_hits),
        vaguePhrases=_clip(vague_hits),
        unansweredGaps=_clip(unanswered_gaps, limit=5),
    )
