import pytest
from precedent_summarizer.load.normalize import clean_text, parse_date, split_sections, nullable


@pytest.mark.parametrize('tag', ['<br/>', '<br>', '<br />', '<BR/>', '<Br >'])
def test_br_preserves_internal_characters(tag):
    assert clean_text('  앞  문장  '+tag+'다음 &amp; 문장  ') == '앞  문장\n다음 &amp; 문장'


def test_blank_lines_other_tags_and_null():
    assert clean_text('첫 줄\n \n\n\n\n마지막') == '첫 줄\n\n\n마지막'
    assert clean_text('<b>강조</b>') == '<b>강조</b>'
    for value in (None, '', '  ', 'null', ' null '):
        assert clean_text(value) is None and nullable(value) is None


@pytest.mark.parametrize('value', ['20250102', '2025.01.02', '2025-01-02'])
def test_date_formats(value):
    assert parse_date(value) == ('2025-01-02', 'ok')


@pytest.mark.parametrize('value,status', [('0001.01.01', 'placeholder'), ('18991231', 'placeholder'),
    ('', 'missing'), ('null', 'missing'), ('bad', 'missing'), ('20250230', 'missing'), ('2025.01-02', 'missing')])
def test_missing_dates(value, status):
    assert parse_date(value) == (None, status)


def test_section_offsets():
    text = '머리말\n【주    문】\n상고 기각\n【이 유】\n원문  그대로'
    sections = split_sections(text)
    assert [s['header_norm'] for s in sections] == ['주문', '이유']
    assert sections[0]['header'] == '주    문'
    assert text[sections[0]['start']:sections[0]['end']] == '【주    문】\n상고 기각\n'
    assert text[sections[1]['start']:sections[1]['end']] == '【이 유】\n원문  그대로'
    assert split_sections(None) == []
