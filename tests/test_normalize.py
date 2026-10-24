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


from datetime import date
from precedent_summarizer.load.normalize import case_year, infer_decision_date, is_summary_dismissal


@pytest.mark.parametrize('text,expected', [('2023두57982',2023), (' 2024다1',2024),
    ('64도126',None), ('',None), (None,None), ('1939다1',None), ('9999다1',None), ('다2023',None)])
def test_case_year(text, expected):
    assert case_year(text) == expected


def test_case_year_upper_bound():
    assert case_year(str(date.today().year+1)+'다1') == date.today().year+1
    assert case_year(str(date.today().year+2)+'다1') is None


@pytest.mark.parametrize('text,expected', [
    ('주문과 같이 판결한다.\n2010. 3. 11.\n재판장 대법관 홍길동', '2010-03-11'),
    ('2010. 3. 11. 서명 없음', None),
    ('2010. 3. 11. 대법관'+'가'*1100, None),
    ('2023. 2. 30. 대법관', None),
    ('1947. 1. 1. 대법관', None),
    ('1948. 1. 1. 대법관', '1948-01-01'),
    ('2010. 3. 11. 대법관 2020. 4. 2. 대법관', '2020-04-02'),
    ('2010. 3. 11. 대법관 2020. 4. 2. 서명없음', None),
    ('2010. 3. 11.'+'가'*201+'대법관', None),
    (None, None),
])
def test_infer_signature_date(text, expected):
    assert infer_decision_date(text) == expected


@pytest.mark.parametrize('article5', ['같은 법 제5조에 의하여', '특례법 제5조'])
def test_summary_dismissal_pattern_and_long_reason(article5):
    text = '【주 문】상고 기각【이    유】상고심절차에 관한 특례법 제4조 '+article5+' 상고를 기각한다.'
    assert is_summary_dismissal(text)
    assert not is_summary_dismissal(text+'가'*1500)
    assert not is_summary_dismissal(text.replace('제4조','제3조'))
    assert not is_summary_dismissal(text.replace('【이    유】',''))
    assert not is_summary_dismissal(None)
    # A long order does not count toward the reasons section length.
    assert is_summary_dismissal(text.replace('상고 기각', '가'*1600))
