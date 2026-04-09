# Test Naming Conventions

`test_*.py` ファイルは次の 3 パターンに分類する。

| サフィックス | 意味 | 例 |
|---|---|---|
| `_contract` | CLI の入出力 contract（引数・終了コード・JSON スキーマ）を固定するテスト | `test_run_socket_m1_host_probe_contract.py` |
| `_artifacts` | 生成済み成果物の shape・フィールド存在を確認するテスト | `test_tlul_err_tlul_sink_campaign_artifacts.py` |
| `_validation` | runner/flow の end-to-end 動作を検証するテスト | `test_run_socket_m1_stock_hybrid_validation.py` |

上記 3 パターンに当てはまらないテストは `other` 扱い。新規テストを追加するときは
できるだけいずれかのパターンに合わせてファイル名をつけること。
