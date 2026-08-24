"""normalize_name 的单元测试。

每个用例都对应阶段 0 在真实数据里看到的一类"脏":大小写、空格、
法律后缀、标点、括号、& 符号、以及全是噪声词的边界情况。
"""

from matcher.normalize import normalize_name


def test_lowercases_and_strips_suffix():
    # 'Monzo Bank Ltd' 和 'Monzo Bank' 应归一成同一个结果
    assert normalize_name("Monzo Bank Ltd") == "monzo bank"


def test_strips_surrounding_whitespace():
    # 真实数据里 5.3% 的名字带多余空格
    assert normalize_name("  Deloitte LLP ") == "deloitte"


def test_drops_bracketed_qualifier():
    # 'Google (UK) Limited' -> 'google'
    assert normalize_name("Google (UK) Limited") == "google"


def test_removes_punctuation():
    # 'J.P. Morgan' 的点会被去掉,这样带点/不带点都能对上
    assert normalize_name("J.P. Morgan") == "j p morgan"


def test_all_caps_becomes_lower():
    # 真实数据里有 3.5 万条全大写
    assert normalize_name("BOLTWHIZ LIMITED") == "boltwhiz"


def test_ampersand_becomes_and():
    assert normalize_name("Smith & Jones") == "smith and jones"


def test_empty_input_returns_empty():
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def test_all_noise_words_falls_back():
    # 'UK Ltd' 全是噪声词:不能返回空串,退回保留原词
    assert normalize_name("UK Ltd") == "uk ltd"
