"""与界面、Unity 无关的规范化规则，便于单独验证。"""
from __future__ import annotations

import re

# DBF LocalizedString 的序列顺序。不是按用户界面的显示顺序排列。
LOCALES = ('enus', 'dede', 'eses', 'esmx', 'frfr', 'itit', 'jajp',
           'kokr', 'plpl', 'ptbr', 'ruru', 'thth', 'zhcn', 'zhtw')
LOCALE_NAMES = dict(zip(LOCALES, ('English', 'Deutsch', 'Español (ES)', 'Español (MX)',
    'Français', 'Italiano', '日本語', '한국어', 'Polski', 'Português', 'Русский', 'ไทย', '简体中文', '繁體中文')))


def guid(value: str) -> str:
    """资源引用通常是“可读文件名:32 位 GUID”；拒绝把普通文本当资源 ID。"""
    candidate = value.rsplit(':', 1)[-1] if isinstance(value, str) else ''
    return candidate.lower() if re.fullmatch(r'[0-9a-fA-F]{32}', candidate) else ''


def localized(record: dict, field: str, locale: str = 'zhcn') -> str:
    values = record.get(field, {}).get('m_locValues', [])
    index = LOCALES.index(locale) if locale in LOCALES else 12
    return (values[index] if index < len(values) else '') or (values[0] if values else '')


def safe_name(value: str) -> str:
    """允许中文，同时规避 Windows 保留名、非法字符和尾部点空格。"""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:110] or 'asset'
    if re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', value):
        value = '_' + value
    return value


