# PyInstaller ビルド手順（メモ）

## エントリポイント
推奨はモジュール起動と同じ挙動になる `main.py` です。

```bash
pyinstaller ... main.py
```

これにより `iRIC_DataScope/app.py` の「直接実行用のパス調整」ロジックを避けられます。

## オプション例
過去の実行例（履歴）は `pyinstaller用.txt` を参照してください。

## よくあるエラーと対処
- `ModuleNotFoundError: No module named 'logging.handlers'`
  - `--hidden-import=logging.handlers` を追加
- `ImportError: cannot import name 'ttk' from 'tkinter'`
  - `--hidden-import=tkinter.ttk` と `--hidden-import=tkinter.filedialog` / `--hidden-import=tkinter.messagebox` を追加

## サイズを下げたい場合
- `--collect-all` はサイズが増えやすいので、まずは `--collect-submodules` を使い、足りないものだけ `--hidden-import` で追加していくのが安全です。

