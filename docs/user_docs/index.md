# ユーザ向けドキュメント

このディレクトリは、GUI の使い方を実装に合わせて整理したものです。  
アプリ内の「ヘルプ」メニューから各ページへ直接アクセスできます。

## 公式ドキュメント
- GitHub Pages: https://pckk-solvers.github.io/iRIC_DataScope/
- Notion（ランチャーのヘルプから開く）: https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73

## 対象機能
- [ランチャー](launcher.md)
- [左右岸水位抽出](lr_wse.md)
- [横断重ね合わせ図作成](cross_section.md)
- [時系列データ抽出](time_series.md)
- [X-Y 分布画像出力](xy_value_map.md)

## スクリーンショット
![ランチャー](../images/launcher.png)

## MkDocs で閲覧（任意）
この `docs/` は MkDocs で閲覧できるようにしてあります（設定: `mkdocs.yml`）。

- 例（MkDocs をインストール済みの場合）: `mkdocs serve`
- 出力先: `build_docs/site`（自動生成物のため Git 管理対象外）
