

### ステップ1：`uv export` による依存関係の固定

まず、開発環境にある「余計なライブラリ」を除外して、実行に必要なライブラリだけの設計図を作ります。

```powershell
# 開発用ライブラリ(pytest, black等)を除き、実行に必要なものだけを書き出す
uv export --no-dev --format requirements-txt > requirements_build.txt

```

### ステップ2：クリーンなビルド専用環境の構築

次に、別の場所（または一時フォルダ）に、ビルドのためだけの「汚れのない仮想環境」を作成します。

```powershell
# 1. ビルド用の仮想環境を作成
uv venv .build_venv

# 2. 仮想環境をアクティベート
.\.build_venv\Scripts\activate

# 3. 最小限のライブラリと、ビルドツール(Nuitka)をインストール
uv pip install -r requirements_build.txt
uv pip install nuitka zstandard

```

### ステップ3：Nuitkaによるコンパイルの実行

ここからが本番です。TkinterはPythonの標準ライブラリですが、Nuitkaでバイナリ化する際は専用のフラグを指定することで、Tcl/Tkのデータファイルを適切に処理してくれます。

以下のコマンドを実行してください。

```powershell
uv run --active python -m nuitka `
    --standalone `
    --onefile `
    --enable-plugin=tk-inter `
    --windows-console-mode=disable `
    --include-data-dir=./iRIC_DataScope/assets=iRIC_DataScope/assets `
    --output-dir=out `
    main.py
```

#### オプションの解説（Fortran開発者の視点）

* **`--standalone`**:
Fortranで言うところの「スタティックリンク」に近い考え方です。Pythonインタープリタ本体や依存DLLをすべて抽出して同梱します。
* **`--onefile`**:
`--standalone` で抽出したファイルを、最終的に一つの `.exe` にパッケージングします。
* **`--enable-plugin=tk-inter`**:
Tkinter（Tcl/Tk）特有のランタイムファイルを同梱するためのプラグインを有効にします。
* **`--enable-plugin=matplotlib`**:
matplotlib の必要ファイル（mpl-dataなど）を同梱するためのプラグインを有効にします。
* **`--windows-console-mode=disable`**:
GUIアプリとして起動し、背後のプロンプト（黒い画面）を出さないようにします。
* **`--include-data-dir=./iRIC_DataScope/assets=iRIC_DataScope/assets`**:
スプラッシュ画像などのアセットを実行ファイルへ同梱します。
* **`--output-dir=out`**:
ビルド中の中間ファイルや完成したexeを `out` フォルダにまとめます。

---

### Nuitkaでハマりやすいポイントと対策

1. **C++コンパイラの自動認識**:
Windowsの場合、Nuitkaは自動的に `Visual Studio (MSVC)` を探しに行きます。もしインストールされていない場合は、実行時に「MinGWをダウンロードしますか？」と聞かれますが、`ifort` 環境があるならそのまま MSVC を使わせるのが最も安定します。
2. **アイコンの設定**:
ユーザーに配布する際、exeのアイコンを変えたい場合は `--windows-icon-from-ico=icon.ico` を追加してください。
3. **ビルド時間の短縮**:
Nuitkaはコンパイルが非常に重いため、一度成功した後は中間ファイルを消さずに `uv pip install zstandard` を入れておくと、圧縮工程が高速化されます。

### まとめ：このフローのメリット

この **`uv export` → `uv venv` → `Nuitka**` という手順を踏むことで：

* 開発環境にある「実験的に入れたライブラリ」がexeに混入しない。
* バイナリサイズが最小限になる。
* ユーザーのPCにPythonやTkinterがインストールされていなくても、ダブルクリックだけで確実に動作する。

まずは、小さなTkinterのテストコードでこのフローを試してみてください。もしコンパイル中に「このモジュールが見つからない」といったリンカーエラーのようなメッセージが出た場合は、その内容を教えていただければ、詳細なオプションの調整をサポートします。
