"""CGT Governor — Repair Prompt Builders

Generate repair prompts for hybrid, distorted, and transient answers.
These prompts can be sent back to the LLM for a repair round.
"""

from __future__ import annotations


def build_hybrid_repair_prompt(answer: str, language: str = "en") -> str:
    """Build a repair prompt for a hybrid answer.

    A hybrid answer has a useful core but is incomplete or mixed.
    The prompt preserves the core while removing confusion.

    Args:
        answer: The LLM answer to repair.
        language: "en" for English, "ar" for Arabic.

    Returns:
        Repair prompt string in the requested language.
    """
    if language == "ar":
        return f"""الجواب التالي يحتوي نواة مفيدة لكنه غير مستقر بعد:

{answer}

أعد بناءه وفق تعليمات CGT:
1. حافظ على النواة الصحيحة.
2. أزل التداخل والالتباس.
3. فرّق بين القاعدة والاستثناء.
4. أضف حاملًا بنيويًا واضحًا: تعريف، خطوات، أو جدول.
5. اجعل النتيجة قابلة للاعتماد والتكرار."""

    return f"""The following answer has a useful core but is not yet stable:

{answer}

Rebuild it according to CGT guidelines:
1. Preserve the correct core.
2. Remove overlap and ambiguity.
3. Distinguish between the rule and the exception.
4. Add a clear structural carrier: definition, steps, or a table.
5. Make the result reliable and repeatable."""


def build_distortion_repair_prompt(answer: str, language: str = "en") -> str:
    """Build a restructure prompt for a distorted answer.

    A distorted answer has excessive structure, conceptual mixing,
    or internal contradictions.
    The prompt rebuilds from scratch with clear organization.

    Args:
        answer: The LLM answer to repair.
        language: "en" for English, "ar" for Arabic.

    Returns:
        Repair prompt string in the requested language.
    """
    if language == "ar":
        return f"""الجواب التالي مشوّه بنيويًا: فيه تركيب زائد أو اضطراب أو تداخل مفاهيمي.

{answer}

أعد بناءه من الصفر وفق الآتي:
1. ابدأ بتحديد السؤال المركزي.
2. احذف التفريعات غير الضرورية.
3. رتّب الجواب في محاور قليلة.
4. عرّف المصطلحات قبل استخدامها.
5. اجعل الخلاصة واضحة ومباشرة."""

    return (
        "The following answer is structurally distorted: excessive branching, "
        "conceptual mixing, or internal contradictions.\n\n"
        f"{answer}\n\n"
        "Rebuild from scratch as follows:\n"
        "1. Start by identifying the central question.\n"
        "2. Remove unnecessary branches.\n"
        "3. Organize the answer into a few clear axes.\n"
        "4. Define terms before using them.\n"
        "5. Make the conclusion clear and direct."
    )


def build_transient_deepen_prompt(answer: str, language: str = "en") -> str:
    """Build a deepen prompt for a transient answer.

    A transient answer is superficial or generic with insufficient carrier.
    The prompt adds depth without unnecessary length.

    Args:
        answer: The LLM answer to repair.
        language: "en" for English, "ar" for Arabic.

    Returns:
        Repair prompt string in the requested language.
    """
    if language == "ar":
        return f"""الجواب التالي عابر أو سطحي ولا يملك حاملًا كافيًا:

{answer}

عمّقه دون إطالته بلا ضرورة:
1. أضف سببًا أو تفسيرًا.
2. اربطه بسياق سؤال المستخدم.
3. أضف مثالًا أو معيارًا عمليًا.
4. اختم بصياغة مستقرة."""

    return f"""The following answer is transient or superficial and lacks sufficient carrier:

{answer}

Deepen it without unnecessary length:
1. Add a reason or explanation.
2. Connect it to the user's question context.
3. Add an example or practical criterion.
4. Conclude with a stable formulation."""
