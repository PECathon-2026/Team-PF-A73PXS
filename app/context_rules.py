import re

from app.models import Finding

_NAME = r"[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2}"

CONTEXT_RULES = [
    ("NAME", re.compile(rf"(?i:my name is)\s+({_NAME})"), "name introduced in a sentence", 1),
    ("ADDRESS", re.compile(r"(?i:address)\s*[:\-]\s*([^\n]{10,120})"), "text after the word address", 1),
    ("DOB", re.compile(r"(?i:dob|date of birth|born on)\s*[:\-]?\s*"
                       r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2} [A-Z][a-z]+ \d{4})"),
     "date of birth", 1),
    ("ACCOUNT", re.compile(r"(?i:account\s*(?:no\.?|number|#))\s*[:\-]?\s*(\d[\d \-]{5,20}\d)"),
     "number after the words account number", 1),
    ("MEDICAL", re.compile(r"(?i:diagnos(?:is|ed with)|prescri(?:ption|bed)|blood group|medication|allergic to)"
                           r"\s*(?:is|are|:)?\s*([^.,;\n]{3,40})"),
     "health detail after a medical word", 1),
]


def find_contextual(text: str) -> list[Finding]:
    found = []
    for type_, rx, reason, group in CONTEXT_RULES:
        for m in rx.finditer(text):
            s, e = m.span(group)
            found.append(Finding(type_, s, e, text[s:e], reason, "context"))
    return found
