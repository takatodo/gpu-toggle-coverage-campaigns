# AGENTS.md

このリポジトリでは、場当たり的な追加よりも責務の分離を優先する。

## 基本方針

- 最小の Python 何でもスクリプトを作らない。
- 1 ファイルに build / run / compare / trace / report を全部詰め込まない。
- 共有ロジックは import 可能な関数に寄せ、CLI は薄い entrypoint に保つ。
- 迷ったら「早く足せる形」ではなく「次の人が責務を読める形」を選ぶ。

## 迷ったときの原則

- まず責務で分け、次に言語で分け、最後に実行単位で分ける。
- CLI は入口、ライブラリは本体、生成物は結果として扱う。
- 「今回だけ動けばよい形」ではなく、「次回の変更箇所が予測できる形」を選ぶ。
- 既存構造に無理やり押し込むくらいなら、責務に沿った新しい配置を検討する。

## 配置ルール

- `src/tools/`: 単機能の開発ツール、変換、補助 CLI
- `src/runners/`: end-to-end 実行、キャンペーン、ベンチ起動
- `src/hybrid/`: C/C++ の hybrid runtime、ABI、host/GPU glue
- `src/passes/`: LLVM / Verilator pass、IR 変換
- `src/scripts/tests/`: contract test、regression test
- `docs/`: 設計メモ、roadmap、spike、運用方針
- `config/`: テンプレート、静的設定
- `work/`, `output/`: 生成物のみ。ソースコードや手書き設定を置かない

## ディレクトリ分けの判断

- 関連ファイルが 3 つ以上に増えるなら、適切な配下にサブディレクトリを切ることを検討する。
- Python と C/C++、実行系と解析系、ライブラリと CLI は雑に同居させない。
- repo root には入口スクリプトと主要ドキュメントだけを置き、単発補助スクリプトを増やさない。
- 配置に迷ったら、まず「共有ロジック」か「CLI の entrypoint」かを分け、その後に実行系・解析系・変換系を判断する。

## Python 実装ルール

- 新しい CLI を足すときは、既存の `run_*`, `build_*`, `compare_*`, `trace_*` の命名規則に合わせる。
- オプションが増えて役割が二つ以上になったら、別 CLI へ分割する。
- 一時しのぎの `misc.py`, `tmp.py`, `do_everything.py` のようなファイル名は禁止。
- 将来使うか不明な汎用化より、責務が明確な小さなモジュール分割を優先する。
- CLI は引数解析、設定ロード、入出力パスの受け渡し、ライブラリ呼び出しに留める。
- CLI に重い業務ロジック、状態管理、比較ロジック、レポート生成本体を書かない。

## 分割の目安

- 1 つの CLI が build / run / compare / trace / report のうち 2 つ以上を持ち始めたら分割を検討する。
- 1 ファイルが長大化し、複数責務を持ち始めたら分割を検討する。
- 同種の処理が複数箇所にコピペされる前に、共有モジュールへ寄せる。

## 変更時の期待値

- 新しい flow を追加したら、対応する test と docs を一緒に更新する。
- 生成 artifact を source of truth にせず、仕様は `docs/` と実装に残す。
- 既存のディレクトリ責務に合わない変更は、先に配置を見直してから実装する。
- 新しい CLI や flow を追加した場合は、少なくとも実行方法が分かる docs を更新する。

## 定量監査

上の注意事項は、少なくとも次の指標で機械監査する。

- `repo_root_python_file_count == 0`
- `banned_python_filename_count == 0`
- `cli_with_matching_test_ratio`
- `cli_with_doc_mention_ratio`
- `cli_over_300_loc_count`
- `cli_over_500_loc_count`

source of truth は `work/agents_guideline_audit.json` とし、次のコマンドで再生成する。

```bash
python3 src/tools/audit_agents_guidelines.py \
  --json-out work/agents_guideline_audit.json
```

この監査は hard gate と scoreboard を分けて扱う。

- hard gate:
  - `repo_root_python_file_count`
  - `banned_python_filename_count`
- scoreboard:
  - test/doc 追従率
  - 長大 CLI 本数

新しい CLI や flow を追加するときは、少なくとも hard gate を悪化させず、対応する test と docs mention を同じ変更で揃える。

## 一時コードと生成物

- 短命な検証コードや spike は、本流の実装や repo root に混ぜない。
- `work/` と `output/` には再生成可能な生成物だけを置く。
- 手修正が必要なファイルや、唯一の判断材料になるメモは `work/` と `output/` に置かない。
- 保持すべき知見は `docs/`、再利用すべき設定は `config/` に残す。
