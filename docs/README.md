# Docs Index

現在の主要ドキュメントは次の 4 本。

- `roadmap_tasks.md`
  プロジェクト全体の目標、到達点、優先タスク
- `phase_b_ico_nba_spike.md`
  Phase B の調査結果、compare artifact、受け入れ条件
- `phase_b_splitter_redesign.md`
  guarded `_eval_nba` segment split へ切り替えた設計メモ
- `phase_c_socket_m1_host_abi.md`
  最初の supported target `tlul_socket_m1` の ABI と host->GPU flow

最初に読む順番:

1. `roadmap_tasks.md`
2. `phase_c_socket_m1_host_abi.md`
3. 必要に応じて `phase_b_ico_nba_spike.md`
4. splitter の背景が必要なら `phase_b_splitter_redesign.md`

現時点の supported entrypoint:

- `./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite`
- `python3 src/runners/run_socket_m1_stock_hybrid_validation.py --mdir work/vl_ir_exp/socket_m1_vl --nstates 64 --steps 1`
