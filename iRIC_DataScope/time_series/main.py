#!/usr/bin/env python3
# iRIC_DataScope\time_series\main.py
"""
時系列抽出ツールのエントリポイント
- GUIの構築と配置は gui_components に委譲
"""
import os
import sys
import logging

# スクリプト直接実行時にパッケージを解決
if __name__ == "__main__" and __package__ is None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, project_root)
    __package__ = "iRIC_DataScope.time_series"

from iRIC_DataScope.common.logging_config import setup_logging
from .gui_components import launch_time_series_gui

logger = logging.getLogger(__name__)

def main():
    """エントリポイント: ロギング設定後、GUIを起動する"""
    setup_logging()
    logger.info("時系列抽出ツール起動")
    launch_time_series_gui()

if __name__ == "__main__":
    main()
