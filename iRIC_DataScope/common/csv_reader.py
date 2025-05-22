import os
import glob
import pandas as pd

def list_csv_files(csv_dir: str) -> list[str]:
    """
    指定されたフォルダ以下を再帰的に探索し、
    'Result_*.csv' ファイルのパス一覧を返す

    Args:
        csv_dir (str): CSVファイルが格納されているディレクトリパス

    Returns:
        list[str]: 見つかったCSVファイルのパスリスト

    Raises:
        NotADirectoryError: csv_dir がディレクトリでない場合
        FileNotFoundError: Result_*.csv が一つも見つからない場合
    """
    # 1. 絶対パス化して存在チェック
    csv_dir = os.path.abspath(csv_dir)
    if not os.path.isdir(csv_dir):
        raise NotADirectoryError(f"指定パスがディレクトリではありません: {csv_dir}")

    # 2. 再帰的に Result_*.csv を検索
    pattern = os.path.join(csv_dir, '**', 'Result_*.csv')
    files = glob.glob(pattern, recursive=True)

    # 3. 見つからなければ明示的に例外
    if not files:
        raise FileNotFoundError(f"{csv_dir} 以下に Result_*.csv が見つかりません")

    return sorted(files)


def read_iric_csv(csv_path: str) -> tuple[float, pd.DataFrame]:
    """
    iRIC の出力 CSV ファイルを読み込み、
    ・最初の行からシミュレーション時刻 (float) を抽出
    ・2 行目以降を DataFrame にロード
    をタプルで返す
    """
    with open(csv_path, 'r', encoding='utf-8') as f:
        first = f.readline().strip()
    try:
        time = float(first.split('=')[1].strip())
    except Exception as e:
        raise ValueError(f"時刻取得エラー: {first}") from e

    df = pd.read_csv(csv_path, skiprows=2)
    return time, df
