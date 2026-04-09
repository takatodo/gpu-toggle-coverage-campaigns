# Codebase Complexity Audit

計測日: 2026-04-04  
対象: プロジェクトソースコード（`work/vl_ir_exp/` ビルド成果物・`third_party/`・`rtlmeter/venv/` 除く）

---

## スコープ

| 区分 | ファイル数 |
|---|---|
| プロジェクトソース（レビュー対象） | **326** |
| ビルド成果物 `work/vl_ir_exp/` | 1,000 |
| サードパーティ | 除外 |

Python ソース内訳：

| ディレクトリ | ファイル数 | 総 LOC |
|---|---|---|
| `src/scripts/tests/` | 53 | 8,603 |
| `src/tools/` | 35 | 6,738 |
| `src/runners/` | 25 | 15,602 |
| `src/rocm/` | 17 | — |
| `src/scripts/` | 13 | — |
| `src/grpo/` | 13 | — |
| `src/generators/` | 11 | — |
| `src/sim_accel/` | 6 | — |

---

## 問題 1 — `_threshold5` artifact の二重コミット

### 現状

`--campaign-threshold-bits 5` を渡して生成した出力 JSON/バイナリが、デフォルト (`bits=3`) 版と**並列に 19 ファイルコミットされている**。

```
output/validation/
  socket_m1_stock_hybrid_validation.json          ← bits=3
  socket_m1_stock_hybrid_validation_threshold5.json  ← bits=5
  socket_m1_cpu_baseline_validation.json
  socket_m1_cpu_baseline_validation_threshold5.json
  socket_m1_time_to_threshold_comparison.json
  socket_m1_time_to_threshold_comparison_threshold5.json
  tlul_fifo_sync_stock_hybrid_validation.json
  tlul_fifo_sync_stock_hybrid_validation_threshold5.json
  tlul_fifo_sync_cpu_baseline_validation.json
  tlul_fifo_sync_cpu_baseline_validation_threshold5.json
  tlul_fifo_sync_time_to_threshold_comparison.json
  tlul_fifo_sync_time_to_threshold_comparison_threshold5.json

work/
  campaign_speed_scoreboard.json
  campaign_speed_scoreboard_threshold5.json
  campaign_next_kpi_audit.json
  campaign_next_kpi_audit_threshold5.json

work/vl_ir_exp/*/  (さらに 7 ファイル: host_probe_report, host_init_state.bin 等)
```

- 両者の JSON スキーマは**完全に同一**（`flat_keys` 差分ゼロ）
- `_threshold5` はリポジトリが「`recommended_next_kpi=stronger_thresholds`」の根拠として保持しているが、`campaign_next_kpi_audit.json` を読めば bits=3 と bits=5 の結論が**同じ**であることが分かる
- threshold 値は CLI `--campaign-threshold-bits` で変えられるため、ファイルコピーではなくパラメータとして管理できる

### 問題点

- canonical がどちらか一見して分からない
- 将来 bits=7 を試すと 19 本がさらに増える

### 提案

`campaign_next_kpi_audit_threshold5.json` の結論が変わらない事実を 1 行 notes として `campaign_next_kpi_audit.json` に追記し、`_threshold5` 系ファイルを `.gitignore` に移す（再生成手順は `docs/README.md` のコマンドに記載済み）。

---

## 問題 2 — レガシー runner 4 本（全 runner LOC の 67%）

### 現状

```
src/runners/
  run_opentitan_tlul_slice_gpu_baseline.py        4,224 行  ─┐
  run_rtlmeter_gpu_toggle_baseline.py             2,869 行   │ 合計 10,751 行
  run_opentitan_tlul_slice_trace_gpu_sweep.py     2,406 行   │ (全 runner: 15,602 行)
  run_opentitan_tlul_slice_trace_gpu_sweep_campaign.py 1,252 行 ─┘

  残り 21 ファイルの平均: 137 行
```

- `run_opentitan_tlul_slice_gpu_baseline.py` は `quickstart.sh`・`bootstrap_hybrid_*.py`・rocm smokeテスト 3 本・テストファイル 7 本から参照されており、**現在も生きている**
- `run_rtlmeter_gpu_toggle_baseline.py` も他 runner 6 本・rocm smokeテスト 3 本・README から参照

### 問題点

大きさの主因は sim_accel 時代の GPU kernel bundle 生成・benchmark ロジックが内包されていること。現在の stock-Verilator + ROCm flow とは分離されているが、同一ファイルに混在している。

レビュアーへの影響：diff が大きく、何を触っているのかノイズが多い。

### 提案

即時削除は不可（参照あり）。レビュー負荷の観点では最上位 2 本（`opentitan_tlul_slice_gpu_baseline`, `rtlmeter_gpu_toggle_baseline`）の **セクション分割**（Class / モジュール抽出）が有効。ただし設計判断が伴うため本 audit の scope 外。

---

## 問題 3 — `socket_m1` ドキュメント 7 本の粒度

### 現状

```
docs/
  phase_c_socket_m1_host_abi.md                  ← ABI 設計
  socket_m1_time_to_threshold_packet.md          ← 比較定義
  socket_m1_time_to_threshold_execution_packet.md  ← CC 向け実装指示
  socket_m1_campaign_schema_packet.md            ← JSON schema contract
  socket_m1_campaign_proof_matrix.md             ← reject/winner 判定ルール
  socket_m1_hybrid_schema_normalization_packet.md  ← additive migration WP0
  socket_m1_hybrid_schema_wp0_execution_packet.md  ← WP0 の CC 向け実装指示
```

7 本で合計 **1,693 行**。同様に `tlul_fifo_sync` が 4 本（1,077 行）。

- 各 `*_execution_packet.md` は「CC（Claude Code）への実装指示書」であり、実装完了後は参照されない
- `*_schema_packet.md` と `*_proof_matrix.md` は決定事項として残す価値があるが、現在は `docs/README.md` の index を読まないと辿り着けない

### 問題点

レビュアーがどのドキュメントが **現在有効** で、どれが **完了済み作業指示** かを区別できない。

### 提案

```
docs/
  active/          ← 現在 canonical な設計・contract
  archive/         ← 実装完了した execution_packet 類
```

に分類し、`docs/README.md` の「最初に読む順番」を `active/` だけに絞る。execution_packet は archive に移すだけで削除不要。

---

## 問題 4 — テスト命名の揺れ

`src/scripts/tests/` に 53 ファイルあるが、naming convention に 3 パターンが混在：

| パターン | 例 | 意味 |
|---|---|---|
| `test_run_*.py` | `test_run_socket_m1_stock_hybrid_validation.py` | runner の integration test |
| `test_*_contract.py` | `test_run_socket_m1_host_probe_contract.py` | CLI I/O contract test |
| `test_*_artifacts.py` | `test_tlul_err_tlul_sink_campaign_artifacts.py` | 出力 artifact の shape test |

3 パターンの意味は異なるが外部から区別できない。

### 提案

`conftest.py` または `README.md` に 3 カテゴリのルールを 10 行で明記する（ファイル移動は不要）。

---

## サマリ

| # | 問題 | 影響ファイル数 | 対処コスト |
|---|---|---|---|
| 1 | `_threshold5` 成果物の二重コミット | 19 | 低（.gitignore 追加 + 1 行 notes） |
| 2 | レガシー runner の肥大化 | 4（10,751 LOC） | 高（設計判断が伴う） |
| 3 | execution_packet 類の混在 | 11 | 低（ディレクトリ移動のみ） |
| 4 | テスト命名の揺れ | 53 | 低（ドキュメント追記のみ） |

優先度: **1 → 3 → 4 → 2** の順で着手するとレビュアーへの視認性が最も改善する。
