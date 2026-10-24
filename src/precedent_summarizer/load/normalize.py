"""Pure normalization helpers; preserve characters inside source sentences."""
from __future__ import annotations

import re
from datetime import date

BR = re.compile(r'<br\s*/?>', re.I)
TAG = re.compile(r'<[^>]+>')


def nullable(s):
    if s is None or (isinstance(s, str) and (not s.strip() or s.strip() == 'null')):
        return None
    return str(s)


def clean_text(s):
    s = nullable(s)
    if s is None:
        return None
    text = BR.sub('\n', s)
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return re.sub(r'\n{4,}', '\n\n\n', text).strip()


def other_tag_count(s):
    return len(TAG.findall(BR.sub('', nullable(s) or '')))


def parse_date(s):
    s = nullable(s)
    if s is None:
        return None, 'missing'
    s = s.strip()
    match = re.fullmatch(r'(\d{4})(\d{2})(\d{2})', s)
    if match is None:
        match = re.fullmatch(r'(\d{4})([.-])(\d{2})\2(\d{2})', s)
        if match is None:
            return None, 'missing'
        year, month, day = int(match[1]), int(match[3]), int(match[4])
    else:
        year, month, day = map(int, match.groups())
    if year < 1900:
        return None, 'placeholder'
    try:
        return date(year, month, day).isoformat(), 'ok'
    except ValueError:
        return None, 'missing'


def split_sections(clean):
    matches = list(re.finditer(r'【([^】]*)】', clean or ''))
    return [dict(header=m.group(1), header_norm=re.sub(r'\s+', '', m.group(1)),
                 start=m.start(), end=matches[i+1].start() if i+1 < len(matches) else len(clean))
            for i, m in enumerate(matches)]



def case_year(case_no):
    match = re.match(r'^\s*(\d{4})', nullable(case_no) or '')
    if match:
        year = int(match[1])
        if 1940 <= year <= date.today().year + 1:
            return year
    return None


def infer_decision_date(full_text_clean):
    tail = (full_text_clean or '')[-1000:]
    matches = list(re.finditer(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', tail))
    if not matches:
        return None
    match = matches[-1]
    year, month, day = map(int, match.groups())
    if year < 1948 or '대법관' not in tail[match.end():match.end() + 200]:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def is_summary_dismissal(full_text_clean):
    text = full_text_clean or ''
    compact = re.sub(r'\s+', '', text)
    if ('상고심절차에관한특례법제4조' not in compact
            or not ('같은법제5조에의하여' in compact or '특례법제5조' in compact)):
        return False
    reasons = [s for s in split_sections(text) if s['header_norm'] == '이유']
    return bool(reasons) and all(s['end'] - s['start'] <= 1500 for s in reasons)
