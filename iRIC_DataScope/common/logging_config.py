# iRIC_DataScope\common\logging_config.py
# ログ設定をまとめるファイル
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir: str = "logs"):
    """
    アプリ全体で使うログ設定を行う。
    - ログファイルはサイズベースでローテーション
      (maxBytes=1MB, backupCount=5)
    - コンソールには INFO 以上を出力

    Args:
        log_dir (str): ログディレクトリパス
    """
    
    root = logging.getLogger()
    # 既にハンドラがあれば二重登録しない
    if root.handlers:
        return
    
    # ログディレクトリ作成
    os.makedirs(log_dir, exist_ok=True)
    logfile = os.path.join(log_dir, "app.log")

    # ルートロガー設定
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # コンソールハンドラ: INFO 以上
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    # ファイルハンドラ: サイズベースローテーション
    fh = RotatingFileHandler(
        logfile,
        mode='a',
        maxBytes=1 * 1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(name)s [%(levelname)s] %(filename)s:%(lineno)d %(message)s"
    ))
    logger.addHandler(fh)
