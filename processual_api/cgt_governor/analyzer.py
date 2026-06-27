"""CGT Governor — Heuristic Text Analyzer

Extracts CGT input scores from (client_query, agent_response) using
pure-Python heuristics. Zero external dependencies.

Scoring philosophy:
- Decent well-written answers get scores in the 0.5-0.8 range
- Poor/empty answers get scores near 0
- The analyzer is calibrated so that a good informative answer
  produces stability >= 0.6 (rank = STABLE) via the CGT pipeline.
"""

from __future__ import annotations

import math
import re
from collections import Counter

# ── Stopword Lists ──

_EN_STOPWORDS: set[str] = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "her",
    "our",
    "their",
    "not",
    "no",
    "nor",
    "so",
    "if",
    "then",
    "than",
    "too",
    "very",
    "just",
    "about",
    "above",
    "after",
    "again",
    "all",
    "also",
    "any",
    "because",
    "before",
    "between",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "only",
    "own",
    "same",
    "into",
    "over",
    "under",
    "up",
    "out",
    "off",
    "down",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "what",
    "which",
    "who",
    "whom",
    "while",
    "during",
    "through",
    "until",
    "against",
    "within",
    "without",
    "along",
    "around",
    "among",
    "upon",
    "across",
    "behind",
    "below",
    "beneath",
    "beside",
    "beyond",
    "please",
    "let",
    "us",
    "per",
    "via",
}

_AR_STOPWORDS: set[str] = {
    "من",
    "إلى",
    "عن",
    "على",
    "في",
    "مع",
    "كان",
    "كانت",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "هنا",
    "هناك",
    "كل",
    "بعض",
    "قد",
    "لقد",
    "إن",
    "أن",
    "إنه",
    "إنها",
    "هو",
    "هي",
    "هم",
    "هن",
    "الذي",
    "التي",
    "الذين",
    "اللاتي",
    "ما",
    "لم",
    "لن",
    "سوف",
    "ثم",
    "حيث",
    "بين",
    "بعد",
    "قبل",
    "دون",
    "غير",
    "لكن",
    "ولكن",
    "أو",
    "ولا",
    "حتى",
    "إذا",
    "اذا",
    "نحو",
    "حول",
    "فقط",
    "بل",
    "أيضا",
    "أيضاً",
    "كذلك",
    "لذا",
    "لهذا",
    "عليها",
    "عنه",
    "عنها",
    "عليه",
    "لهم",
    "لها",
    "لنا",
    "له",
    "لها",
    "لهم",
    "هؤلاء",
    "ذلك",
    "و",
    "ف",
    "ب",
    "ل",
    "ك",
    "أ",
    "ال",
    "بال",
    "فل",
    "هل",
    "أم",
    "لم",
    "لن",
    "كان",
    "كانت",
    "يكون",
    "تكون",
    "يكونون",
    "ليس",
    "ليست",
    "كانوا",
    "كن",
    "كوني",
}

# ── Transition Words ──

_EN_TRANSITIONS: set[str] = {
    "because",
    "therefore",
    "thus",
    "hence",
    "consequently",
    "as a result",
    "accordingly",
    "so",
    "then",
    "furthermore",
    "moreover",
    "additionally",
    "in addition",
    "also",
    "besides",
    "likewise",
    "similarly",
    "however",
    "nevertheless",
    "nonetheless",
    "on the other hand",
    "in contrast",
    "conversely",
    "on the contrary",
    "instead",
    "meanwhile",
    "while",
    "although",
    "though",
    "even though",
    "first",
    "firstly",
    "second",
    "secondly",
    "third",
    "thirdly",
    "finally",
    "lastly",
    "next",
    "then",
    "after",
    "before",
    "for example",
    "for instance",
    "such as",
    "including",
    "in particular",
    "notably",
    "specifically",
    "especially",
    "in other words",
    "that is",
    "i.e.",
    "e.g.",
    "in summary",
    "to summarize",
    "in conclusion",
    "overall",
    "indeed",
    "certainly",
    "undoubtedly",
    "clearly",
    "additionally",
    "further",
    "moreover",
}

_AR_TRANSITIONS: set[str] = {
    "لأن",
    "لذلك",
    "بالتالي",
    "ولكن",
    "بينما",
    "على الرغم من",
    "بالرغم من",
    "بالإضافة إلى",
    "علاوة على",
    "من ناحية",
    "من جهة",
    "أولاً",
    "ثانياً",
    "أخيراً",
    "على سبيل المثال",
    "مثل",
    "كما",
    "كذلك",
    "أيضاً",
    "ومع ذلك",
    "رغم ذلك",
    "لهذا السبب",
    "بناء على",
    "خلاف ذلك",
    "بدلاً من",
    "ناهيك عن",
    "فضلاً عن",
    "إذ",
    "حيث",
    "لذا",
    "ثم",
    "التالي",
    "بالنسبة",
    "إضافة إلى",
}

_EN_HEDGES: set[str] = {
    "however",
    "although",
    "though",
    "nevertheless",
    "nonetheless",
    "it depends",
    "on the other hand",
    "in some cases",
    "arguably",
    "perhaps",
    "maybe",
    "possibly",
    "potentially",
    "might",
    "could",
    "may",
    "alternatively",
    "another approach",
    "one option",
    "it is worth noting",
    "it should be noted",
    "interestingly",
    "it is important to consider",
    "one could argue",
}

_AR_HEDGES: set[str] = {
    "ولكن",
    "على الرغم",
    "قد",
    "ربما",
    "يمكن",
    "محتمل",
    "بديل",
    "خيار آخر",
    "من الممكن",
    "في بعض الحالات",
    "تجدر الإشارة",
    "من الجدير بالذكر",
    "من ناحية أخرى",
    "أو",
    "نوعاً ما",
}

_EN_NONANSWER: set[str] = {
    "i don't know",
    "i do not know",
    "i cannot answer",
    "i can't answer",
    "i am not sure",
    "i'm not sure",
    "i have no idea",
    "i don't understand",
    "i do not understand",
    "i am unable to",
    "i'm unable to",
    "i cannot provide",
    "i can't provide",
    "insufficient information",
    "not enough information",
    "i need more information",
    "i am not able to",
    "i'm not able to",
    "i don't have enough context",
    "i do not have enough context",
    "i don't have information",
    "i'm sorry",
    "i am sorry",
    "sorry, i",
}

_AR_NONANSWER: set[str] = {
    "لا أعرف",
    "لا اعرف",
    "لا أستطيع",
    "لا استطيع",
    "لا يمكنني",
    "لا أملك",
    "لا املك",
    "ليس لدي",
    "لست متأكد",
    "لست متأكدة",
    "لا توجد معلومات",
    "معلومات غير كافية",
    "لم أفهم",
    "لم افهم",
    "لا أفهم",
    "لا افهم",
    "عذراً",
    "آسف",
    "لا يمكن الإجابة",
}

_EN_HALLUCINATION_TRIGGERS: set[str] = {
    "always",
    "never",
    "everyone",
    "nobody",
    "absolutely",
    "without question",
    "impossible",
}

_AR_HALLUCINATION_TRIGGERS: set[str] = {
    "دائماً",
    "أبداً",
    "الجميع",
    "لا أحد",
    "مستحيل",
    "بالتأكيد",
    "بلا شك",
}

_EN_BOILERPLATE: set[str] = {
    "thank you for your",
    "please find attached",
    "i hope this helps",
    "if you have any questions",
    "feel free to",
    "do not hesitate",
    "looking forward",
    "as per your request",
    "please note that",
    "i am writing to",
    "this is to inform",
    "kindly",
    "dear",
    "sincerely",
    "best regards",
    "regards",
    "i would like to",
    "we would like to",
}

_AR_BOILERPLATE: set[str] = {
    "شكرا لك",
    "شكراً لك",
    "نشكركم",
    "نشكرك",
    "يسرني",
    "يسعدني",
    "أرفق لكم",
    "مرفق لكم",
    "لطفاً",
    "يرجى",
    "نأمل منكم",
    "مع خالص التحية",
    "وتفضلوا بقبول",
    "تحياتي",
    "مع الشكر",
    "شاكرين لكم",
    "نشكر تعاونكم",
}

_EN_CONSTRAINT_VIOLATION: set[str] = {
    "i know this goes against",
    "even though you said",
    "ignoring your",
    "despite your instruction",
    "i will ignore",
    "setting aside your",
    "although you asked",
    "regardless of your",
}

_AR_CONSTRAINT_VIOLATION: set[str] = {
    "رغم تعليماتك",
    "بغض النظر عن",
    "سأتجاهل",
    "سأهمل",
    "خلافاً لتعليمات",
    "رغم أنك قلت",
}


# ── Helpers ──


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower())


def _sentences(text: str) -> list[str]:
    raw = re.split(r"[.!?\n]+", text)
    return [s.strip() for s in raw if len(s.strip()) > 3]


def _remove_stopwords(tokens: list[str], language: str) -> list[str]:
    stopwords = _AR_STOPWORDS if language == "ar" else _EN_STOPWORDS
    return [t for t in tokens if t not in stopwords]


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.5
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _scale(raw: float, per_unit: float = 0.15, baseline: float = 0.0) -> float:
    """Linear scaling: baseline + raw * per_unit, clamped to [0, 1]."""
    return _clamp(baseline + raw * per_unit)


def _count_in_text(text: str, phrases: set[str]) -> int:
    lower = text.lower()
    count = 0
    for phrase in phrases:
        count += len(re.findall(re.escape(phrase), lower))
    return count


def _unique_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.5
    return len(set(tokens)) / len(tokens)


def _avg_sentence_length(sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _coeff_variation(sentences: list[str]) -> float:
    lengths = [len(s.split()) for s in sentences if s]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return math.sqrt(var) / mean


# ── Public API ──


def analyze_cgt(
    client_query: str,
    agent_response: str,
    language: str = "en",
) -> dict[str, float]:
    """Analyze an agent response and return CGT input scores.

    Args:
        client_query: The user's original question/query.
        agent_response: The agent's generated answer.
        language: 'en' for English, 'ar' for Arabic.

    Returns:
        dict with all 12 CGT score keys + 'speed'.
    """
    q_tokens = _tokenize(client_query)
    a_tokens = _tokenize(agent_response)
    a_sentences = _sentences(agent_response)

    q_clean = _remove_stopwords(q_tokens, language)
    a_clean = _remove_stopwords(a_tokens, language)

    q_set = set(q_clean)
    a_set = set(a_clean)

    n_words = len(a_tokens) or 1
    n_sents = len(a_sentences) or 1

    # ── Compatibility ──
    # How well does the answer address the topic of the query?
    # Primary: what fraction of query keywords appear in the answer
    query_covg = 0.0
    if q_clean:
        hits = sum(1 for w in q_clean if w in a_set)
        query_covg = hits / len(q_clean)
    compatibility = _scale(query_covg, per_unit=0.55, baseline=0.25)

    # ── Coherence ──
    # Internal consistency: transitions + sentence length consistency + vocab reuse
    n_transitions = _count_in_text(
        agent_response,
        _EN_TRANSITIONS if language == "en" else _AR_TRANSITIONS,
    )
    transitions_per_sent = n_transitions / n_sents
    cv = _coeff_variation(a_sentences)
    # Only penalize extreme sentence length variation
    # Moderate variation (CV < 0.5) is natural in good writing
    cv_penalty = _clamp((cv - 0.30) * 1.2)

    coherence = (
        _scale(transitions_per_sent, per_unit=0.35, baseline=0.38) * 0.40
        + _scale(1.0 - cv_penalty, per_unit=0.50, baseline=0.35) * 0.20
        + _scale(_unique_ratio(a_tokens), per_unit=0.60, baseline=0.35) * 0.40
    )

    # ── Structural Support ──
    n_paragraphs = len(re.findall(r"\n\s*\n", agent_response.strip())) + 1
    n_list_items = len(re.findall(r"(?:^|\n)\s*(?:\d+\.|[-*•])\s", agent_response))
    n_headings = len(re.findall(r"(?:^|\n)[A-Z\u0600-\u06FF][^.!?\n]*[:\n]", agent_response))
    n_code_blocks = len(re.findall(r"```", agent_response))

    has_multiple_sentences = 1.0 if n_sents >= 2 else 0.0
    has_paragraphs = 1.0 if n_paragraphs >= 2 else 0.0
    has_list = 1.0 if n_list_items >= 1 else 0.0
    has_headings = 1.0 if n_headings >= 1 else 0.0
    has_code = 1.0 if n_code_blocks >= 1 else 0.0

    structural_support = (
        0.25  # baseline
        + has_multiple_sentences * 0.30
        + has_paragraphs * 0.25
        + has_list * 0.20
        + has_headings * 0.15
        + has_code * 0.10
    )

    # ── Usefulness ──
    n_numbers = len(re.findall(r"\b\d+\b", agent_response))
    n_urls = len(re.findall(r"https?://\S+", agent_response))
    n_action_verbs = len(
        re.findall(
            r"\b(use|run|install|configure|create|build|do|follow|check|ensure|"
            r"provide|implement|apply|setup|deploy|define|explain|"
            r"describe|demonstrate|show|illustrate|"
            r"require|enable|allow|form|contain|include|consist|comprise|"
            r"connect|link|store|broadcast|validate|process|add|form|ensure|"
            r"أستخدم|شغل|ثبت|اضبط|أنشئ|ابن|اتبع|تحقق|تأكد|وفر|طبق|اشرح|"
            r"وصف|يوضح|يبين|يشرح|يتطلب|يمكن|يسمح|يحتوي|يشمل|يربط|يخزن|"
            r"يضمن|يضيف|يكون)\b",
            agent_response.lower(),
        )
    )
    data_density = _scale(n_numbers, per_unit=0.04, baseline=0.0)
    url_score = _scale(n_urls, per_unit=0.10, baseline=0.0)
    verb_score = _scale(n_action_verbs, per_unit=0.05, baseline=0.0)
    length_score = _scale(n_words, per_unit=0.008, baseline=0.0)

    usefulness = _clamp(
        0.35  # baseline
        + data_density * 0.12
        + url_score * 0.08
        + verb_score * 0.20
        + length_score * 0.30
    )

    # ── Complexity ──
    avg_sl = _avg_sentence_length(a_sentences)
    norm_avg_sl = _clamp(avg_sl / 30.0)
    vocab_diversity = 1.0 - _unique_ratio(a_tokens) if a_tokens else 0.3
    long_word_ratio = sum(1 for w in a_tokens if len(w) > 8) / n_words

    complexity = (
        _scale(norm_avg_sl, per_unit=0.35, baseline=0.0) * 0.35
        + _scale(vocab_diversity, per_unit=0.40, baseline=0.0) * 0.35
        + _scale(long_word_ratio, per_unit=0.40, baseline=0.0) * 0.30
    )

    # ── Fatigue ──
    boilerplate_count = _count_in_text(
        agent_response,
        _EN_BOILERPLATE if language == "en" else _AR_BOILERPLATE,
    )
    repeats = sum(c - 1 for c in Counter(a_tokens).values() if c > 3)
    fatigue = _scale(boilerplate_count, per_unit=0.06, baseline=0.0) + _scale(
        repeats / n_words, per_unit=0.30, baseline=0.0
    )

    # ── Shock ──
    n_excl = agent_response.count("!")
    n_caps_words = len(re.findall(r"\b[A-Z]{3,}\b", agent_response))
    shock = _scale(n_excl, per_unit=0.05, baseline=0.0) + _scale(n_caps_words, per_unit=0.03, baseline=0.0)

    # ── Lift (corrigibility) ──
    n_hedges = _count_in_text(
        agent_response,
        _EN_HEDGES if language == "en" else _AR_HEDGES,
    )
    hedges_per_sent = n_hedges / n_sents
    is_not_terse = 1.0 if n_words >= 20 else 0.0  # very short answers lack lift
    lift = _scale(hedges_per_sent, per_unit=0.15, baseline=0.10) * 0.45 + (1.0 - fatigue) * 0.30 + is_not_terse * 0.25

    # ── Novelty ──
    # Words in the answer not found in the query
    unique_to_answer = a_set - q_set
    novelty_ratio = len(unique_to_answer) / max(len(a_set), 1) if a_set else 0.0
    novelty = _scale(novelty_ratio, per_unit=0.50, baseline=0.15)

    # ── No Answer ──
    nonanswer_count = _count_in_text(
        agent_response,
        _EN_NONANSWER if language == "en" else _AR_NONANSWER,
    )
    too_short = 1.0 if n_words < 8 else 0.0
    no_answer = _scale(nonanswer_count, per_unit=0.15, baseline=0.0) + too_short * 0.60

    # ── Hallucination ──
    lower = agent_response.lower()
    hallucination_score = 0.0

    # Unsupported numbers (3+ digits without source)
    big_numbers = re.findall(r"\b\d{3,}\b", agent_response)
    if big_numbers:
        sourced = len(
            re.findall(
                r"\d+.*?(according to|source|report|study|research|"
                r"data from|found that|بحث|دراسة|تقرير|حسب)",
                lower,
            )
        )
        unsupported_ratio = (len(big_numbers) - sourced) / len(big_numbers)
        if unsupported_ratio > 0.5 and len(big_numbers) >= 2:
            hallucination_score += unsupported_ratio * 0.15

    # Extreme absolute claims
    absolutes = _count_in_text(
        lower,
        _EN_HALLUCINATION_TRIGGERS if language == "en" else _AR_HALLUCINATION_TRIGGERS,
    )
    hallucination_score += _scale(absolutes, per_unit=0.04, baseline=0.0)

    # No evidence markers — a good answer cites or references
    evidence_markers = len(
        re.findall(
            r"\b(because|since|according to|research|study|data|"
            r"بعرض|حسب|وفقاً|لأن|بناء على|تشير)\b",
            lower,
        )
    )
    if n_words >= 30 and evidence_markers == 0:
        hallucination_score += 0.05  # small penalty for long unsourced answers

    hallucination = _clamp(hallucination_score)

    # ── Constraint Failure ──
    constraint_phrases = _EN_CONSTRAINT_VIOLATION if language == "en" else _AR_CONSTRAINT_VIOLATION
    n_constraint = _count_in_text(agent_response, constraint_phrases)
    constraint_failure = _scale(n_constraint, per_unit=0.15, baseline=0.0)

    return {
        "compatibility": round(_clamp(compatibility), 4),
        "coherence": round(_clamp(coherence), 4),
        "structural_support": round(_clamp(structural_support), 4),
        "usefulness": round(_clamp(usefulness), 4),
        "complexity": round(_clamp(complexity), 4),
        "fatigue": round(_clamp(fatigue), 4),
        "shock": round(_clamp(shock), 4),
        "lift": round(_clamp(lift), 4),
        "novelty": round(_clamp(novelty), 4),
        "no_answer": round(_clamp(no_answer), 4),
        "hallucination": round(_clamp(hallucination), 4),
        "constraint_failure": round(_clamp(constraint_failure), 4),
        "speed": 0.5,
    }
