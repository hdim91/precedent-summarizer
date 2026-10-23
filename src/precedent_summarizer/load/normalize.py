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
