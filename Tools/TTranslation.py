#!/usr/bin/env python
#-*- coding: utf-8 -*-

import TUtilLog

# 已经提示过的缺失词条，避免同一个词条刷满整个log
_warned = set()

def get_tl(s):
    lang = TARGET_LANG or zhCN
    try:
        return lang[s]
    except KeyError:
        if s not in _warned:
            _warned.add(s)
            TUtilLog.warning("缺失翻译：{}".format(s))
        return s
en = {
    "选择语言/Select Language": "Select Language",
    "1 - 简体中文 (Default)": "1 - Simplified Chinese (Default)",
    "MAS 已经安装": "MAS is already installed",
    "未安装 MAS": "MAS is not installed",
    "准备安装MAS...": "Preparing to install MAS..."
}

# 中文词条就是原文，缺了会刷一堆"缺失翻译"警告，所以在这里显式列出来
zhCN = {
    "选择语言/Select Language": "选择语言/Select Language",
    "1 - 简体中文 (Default)": "1 - 简体中文 (Default)",
    "MAS 已经安装": "MAS 已经安装",
    "未安装 MAS": "未安装 MAS",
    "准备安装MAS...": "准备安装MAS..."
}

TARGET_LANG = None
