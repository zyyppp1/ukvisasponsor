"""公司名归一化:把写法各异的公司名压成一个统一、可比较的形式。

匹配的第一步。用户在 LinkedIn 看到的 'Google (UK) Limited' 和名单里的
'Google' 只有归一化成同一个字符串后,才谈得上"精确匹配"。
"""

import re
import unicodedata

# 法律实体后缀和无助于识别公司的填充词。归一化时去掉它们,
# 这样 'Monzo Bank Ltd' 和 'Monzo Bank' 会归一成同一个结果。
_NOISE_WORDS = {
    "ltd", "limited", "plc", "llp", "llc", "inc", "incorporated",
    "co", "company", "group", "holdings", "holding", "uk",
}


def normalize_name(name: str) -> str:
    """把一个公司名归一化成小写、去后缀、去标点的形式。

    例:
        'Google (UK) Limited' -> 'google'
        '  Deloitte LLP '     -> 'deloitte'
        'J.P. Morgan'         -> 'j p morgan'
        'Smith & Jones'       -> 'smith and jones'
    """
    if not name:
        return ""

    # 1) 去掉重音符号:café -> cafe
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))

    # 2) 全部转小写
    name = name.lower()

    # 3) '&' 统一成 'and'
    name = name.replace("&", " and ")

    # 4) 逗号或左括号之后的内容通常是分部/地点/法律细节,丢掉
    name = re.split(r"[(,\[]", name)[0]

    # 5) 所有非字母数字字符换成空格(去掉 . - / 等标点)
    name = re.sub(r"[^a-z0-9]+", " ", name)

    # 6) 切成单词,去掉噪声词
    tokens = name.split()
    words = [w for w in tokens if w not in _NOISE_WORDS]

    # 7) 边界情况:如果整个名字全是噪声词(如 'UK Ltd'),
    #    去噪后会变空 —— 这时保留原始单词,总比返回空串好。
    if not words:
        words = tokens

    # 8) 用单空格重新拼起来
    return " ".join(words)
