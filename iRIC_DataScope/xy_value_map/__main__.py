from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from iRIC_DataScope.common.logging_config import setup_logging
from .gui import XYValueMapGUI


def main(argv: list[str] | None = None):
    """
    コマンドラインから X-Y 分布画像出力ツールを直接起動する。

    使い方:
        python -m iRIC_DataScope.xy_value_map <input_path> [output_dir]

    引数:
        input_path : .ipro ファイルまたはプロジェクト/CSV フォルダ
        output_dir : 省略時は input と同じ場所を使用
    """
    setup_logging()
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Usage: python -m iRIC_DataScope.xy_value_map <input_path> [output_dir]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args[0]).expanduser().resolve()
    if len(args) >= 2:
        output_dir = Path(args[1]).expanduser().resolve()
    else:
        output_dir = input_path.parent if input_path.is_file() else input_path

    if not input_path.exists():
        print(f"入力パスが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        print(f"出力ディレクトリを作成できませんでした: {output_dir}", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()
    win = XYValueMapGUI(master=root, input_path=input_path, output_dir=output_dir)

    def on_close():
        try:
            win.destroy()
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    win.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
