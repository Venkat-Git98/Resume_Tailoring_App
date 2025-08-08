from typing import List


GENERIC_STOP_TERMS = {
    'benefits','connections','check','exp','experience','position','role','company','remote','hybrid',
    'full-time','team','looking','seeking','hiring','Responsibilities'.lower(), 'qualification','qualifications',
    'preferred','required','industry','media','software','hardware','tv','roku','advertising','platforms',
    'consumer','electronics','digital','entertainment','video','streaming'
}


def filter_ats_keywords(keywords: List[str]) -> List[str]:
    filtered: List[str] = []
    seen = set()
    for kw in keywords:
        k = (kw or '').strip()
        if not k:
            continue
        low = k.lower()
        if low in seen:
            continue
        if any(ch.isalpha() for ch in low) is False:
            continue
        if len(low) < 3:
            continue
        if low in GENERIC_STOP_TERMS:
            continue
        # allow important bigrams/phrases
        filtered.append(k)
        seen.add(low)
        if len(filtered) >= 25:
            break
    return filtered


def compact_summary(text: str, max_chars: int = 450) -> str:
    if not text:
        return text
    t = text.strip()
    if len(t) <= max_chars:
        return t
    # naive sentence split
    parts = [p.strip() for p in t.replace('\n', ' ').split('. ') if p.strip()]
    out = ''
    for p in parts:
        candidate = (out + (' ' if out else '') + p).strip()
        if len(candidate) + 1 > max_chars:
            break
        out = candidate
    if out and not out.endswith('.'):
        out += '.'
    if not out:
        out = t[:max_chars]
    return out.strip()


def compact_cover_letter(text: str, max_chars: int = 1300) -> str:
    if not text:
        return text
    t = text.strip()
    if len(t) <= max_chars:
        return t
    paras = [p.strip() for p in t.split('\n\n') if p.strip()]
    out_paras: List[str] = []
    total = 0
    for p in paras:
        # trim each paragraph to ~300 chars
        p_trim = p
        if len(p_trim) > 300:
            # cut at last sentence boundary within 300
            sub = p_trim[:300]
            idx = max(sub.rfind('. '), sub.rfind('; '), sub.rfind(', '))
            if idx > 100:
                p_trim = sub[:idx+1]
            else:
                p_trim = sub
        if total + len(p_trim) + (2 if out_paras else 0) > max_chars:
            break
        out_paras.append(p_trim)
        total += len(p_trim) + (2 if out_paras else 0)
    return '\n\n'.join(out_paras).strip()


