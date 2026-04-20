SECTION_KEYWORDS = {
    "problem": ["problem", "pain point", "challenge", "issue", "struggle"],
    "solution": ["solution", "we built", "our platform", "feature", "users can"],
    "architecture": ["architecture", "stack", "database", "api", "backend", "frontend", "model"],
    "demo": ["demo", "show", "walk through", "screen", "click"],
    "evaluation": ["evaluate", "metric", "measure", "result", "testing", "improve", "faster"],
    "future_work": ["future", "next", "later", "plan to", "could add"],
    "conclusion": ["conclusion", "overall", "to summarize", "in summary"],
    "introduction": ["today", "introduce", "project is", "we are presenting"],
}


def infer_section(text: str) -> str:
    lower_text = text.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            return section
    return "unknown"

