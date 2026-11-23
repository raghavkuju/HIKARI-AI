
import re
import unicodedata

QUALITY_RULES = """
You are Hikari AI.

RESPONSE QUALITY RULES:
1. Answer in the same language as the user.
2. For Roman Hindi questions, use natural Roman Hinglish.
3. Never switch to Chinese, Japanese, or Korean unless requested.
4. Do not invent locations, districts, dates, names, or statistics.
5. If uncertain about a fact, clearly say it is unverified.
6. Answer only what the user asks. Avoid unnecessary details.
7. Do not treat user corrections as verified facts automatically.
8. Prefer short, clear and accurate answers.
9. Never claim to have checked the web unless web evidence was provided.
"""

# Verified local facts for regression testing.
# This is not a replacement for live fact verification.
VERIFIED_FACTS = {
    "amarkantak": {
        "state": "Madhya Pradesh",
        "district": "Anuppur",
    }
}


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def detect_bad_language(text: str) -> bool:
    if not text:
        return False

    # Detect CJK characters in responses where not requested.
    cjk = re.findall(
        r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]",
        text
    )

    # Common replacement character from decoding failures.
    replacement = "\ufffd" in text

    # Typical mojibake patterns.
    mojibake = bool(
        re.search(r"(?:Ã.|Â.|â€|ï¼|ã[€-¿])", text)
    )

    return bool(cjk) or replacement or mojibake


def user_requested_cjk(message: str) -> bool:
    message = message.lower()
    return any(
        term in message
        for term in (
            "chinese", "mandarin", "japanese",
            "korean", "kanji", "hiragana",
            "katakana", "中文", "日本語", "한국어"
        )
    )


def fact_conflict(question: str, answer: str) -> bool:
    question_lower = question.lower()
    answer_lower = answer.lower()

    if "amarkantak" in question_lower:
        if re.search(r"\bdhar\s+district\b", answer_lower):
            return True

        if re.search(r"\bdhar\s+(?:jile|zilla|district)\b", answer_lower):
            return True

    return False


def response_has_quality_issue(
    question: str,
    answer: str
) -> bool:
    if not answer or not answer.strip():
        return True

    if (
        not user_requested_cjk(question)
        and detect_bad_language(answer)
    ):
        return True

    if fact_conflict(question, answer):
        return True

    return False


def verified_local_answer(question: str):
    q = question.lower()

    if "amarkantak" not in q:
        return None

    if any(
        term in q
        for term in ("district", "jila", "zilla", "jile")
    ):
        return (
            "Amarkantak Madhya Pradesh ke "
            "Anuppur district mein hai."
        )

    if any(
        term in q
        for term in ("state", "rajya", "pradesh")
    ):
        return "Amarkantak Madhya Pradesh mein hai."

    return None
