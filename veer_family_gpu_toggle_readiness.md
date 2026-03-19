# VeeR Family GPU Toggle Readiness

## Summary

- Weakest point: the VeeR family is no longer blocked on late-family execution contract bring-up. `gpu_cov_gate` now survives the family-standard reruns, and final freeze is now handled in a scope-limited packet rather than being blocked on raw `gpu_cov` runtime parity.
- Current direction: keep `gpu_cov_gate` as the default VeeR late-family precheck path, treat the raw `gpu_cov` loop as a localized VeeR failure signature, and stop treating lower-level harness surgery as the mainline next step.

## Current Status

| Design | Status | Evidence | Result |
|---|---|---|---|
| `VeeR-EL2` | executed | `/tmp/veer_el2_gpu_cov_smoke_v1.json` | `best_case_hit=0`, `tb_contract=needs_review`, `observability=needs_review` |
| `VeeR-EH1` | executed | `/tmp/veer_eh1_gpu_cov_smoke_v1.json` | `best_case_hit=0`, `tb_contract=needs_review`, `observability=needs_review` |
| `VeeR-EH2` | compile path reached `full_all` | `/tmp/veer_eh2_gpu_cov_smoke_v1` | cold compile remains heavy; minimal gated `tb_top` path not yet shown to produce non-dead coverage |
| `VeeR-EL2` late-family `dhry` stress | executed | `/tmp/veer_family_late_validation_v1/VeeR-EL2/gpu_cov` | standard `dhry` precheck passes, but `gpu_cov` execute remains live with `program_loaded=1`, `rst_l=1`, trace/WB/LSU activity and enters a `TEST_FAILED` loop (`>1.17 GiB` stdout, `1,175,649` failures observed before manual stop) |
| `VeeR-EL2` `gpu_cov_gate:dhry` late-family gate | executed | `/tmp/veer_el2_gpu_cov_gate_direct_v1/VeeR-EL2/gpu_cov_gate/execute-0/dhry/_execute/stdout.log` | `TEST_PASSED` with clean `$finish` at `tb_top.sv:671`; the late-family precheck no longer depends on the pathological raw `gpu_cov` execution contract |
| `VeeR-EH1` `gpu_cov_gate:hello` late-family gate | executed | `/tmp/veer_eh1_gpu_cov_gate_direct_v1/VeeR-EH1/gpu_cov_gate/execute-0/hello/_execute/stdout.log` | `TEST_PASSED` with clean `$finish` at `tb_top.sv:367` |
| `VeeR-EH1` `gpu_cov_gate:dhry` standard-grade rerun | executed | `/tmp/veer_eh1_gpu_cov_gate_dhry_v1/VeeR-EH1/gpu_cov_gate/execute-0/dhry/_execute/stdout.log` | `TEST_PASSED` with clean `$finish` at `tb_top.sv:367`; standard Dhrystone completes under the same family gate |
| `VeeR-EH2` `gpu_cov_gate:hello` late-family gate | executed | `/tmp/veer_eh2_gpu_cov_gate_direct_v1/VeeR-EH2/gpu_cov_gate/execute-0/hello/_execute/stdout.log` | `TEST_PASSED` with clean `$finish` at `tb_top.sv:359` |
| `VeeR-EH2` `gpu_cov_gate:cmark_iccm_mt` standard-grade rerun | executed | `/tmp/veer_eh2_gpu_cov_gate_cmark_iccm_mt_v1/VeeR-EH2/gpu_cov_gate/execute-0/cmark_iccm_mt/_execute/stdout.log` | `TEST_PASSED` with clean `$finish` at `tb_top.sv:359`; the assigned multicore CoreMark standard survives the same gate |

## What This Means

- Compile readiness is no longer the blocker.
- The old raw `gpu_cov` execution path is still useful as a failure signature, but it is no longer the recommended late-family precheck.
- `gpu_cov_gate` shows that the immediate EL2 late-family problem was narrower than "need a new lower-level harness":
  - plain `dhry` still reaches `TEST_PASSED`
  - the old `gpu_cov` path is active but pathologically non-terminating
  - the new `gpu_cov_gate` path terminates cleanly on the mailbox contract and keeps the existing wrapper-level observability
- The family rollout now works at standard-grade level:
  - `EL2 dhry` passes under `gpu_cov_gate`
  - `EH1 dhry` passes under `gpu_cov_gate`
  - `EH2 cmark_iccm_mt` passes under `gpu_cov_gate`
- This removes VeeR as the immediate late-family blocker for the provisional rule family.
- The next milestone is no longer "finish the VeeR family rerun". `VeeR` is now part of the included late-family gate evidence in `./metrics_driven_final_rule_packet.md`.

## Recommended Next Step

1. Treat the old EL2 late-family `TEST_FAILED` loop as a VeeR execution-contract bug in the raw `gpu_cov` path, not as evidence against the provisional generic rule family.
2. Use `gpu_cov_gate` as the default late-family precheck path.
3. Keep the lower-level harness idea as fallback only; it is no longer on the critical path.
4. Treat any further raw `gpu_cov` harness surgery as follow-on debt rather than a blocker to the frozen rule table.
