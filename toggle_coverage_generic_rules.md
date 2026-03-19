# Toggle Coverage Generic Rules

| Rule | Evidence | Campaign backend | Campaign nstates | Candidate count | Region budget | Notes |
|---|---|---|---:|---:|---|---|
| deep_fifo_source | tlul_fifo_async | source | 512 | 512 | reqfifo_storage_upper=2, response_payload=2, rspfifo_storage_upper=2 | recommended_campaign_candidate_count >= 512; recommended_stop == true; campaign_backend == source; best_case_hit <= 8 |
| compact_socket_source | tlul_socket_1n | source | 256 | 0 | reqfifo_storage_upper=6, response_payload=8, rspfifo_storage_upper=6 | campaign_backend == source; recommended_campaign_candidate_count <= 96; best_case_hit >= 10 |
| mixed_source_campaign_circt_multistep | tlul_socket_m1, xbar_peri | source | 512 | 0 | reqfifo_storage_upper=4, response_payload=6, rspfifo_storage_upper=4 | campaign_backend == source; multi_step_backend == circt-cubin; recommended_campaign_candidate_count <= 160; best_case_hit between 6 and 10 |
| dense_xbar_circt | xbar_main | circt-cubin | 512 | 0 | reqfifo_storage_upper=3, response_payload=6, rspfifo_storage_upper=3 | campaign_backend == circt-cubin; single_step_backend == circt-cubin; multi_step_backend == circt-cubin |
| balanced_source_general | tlul_fifo_sync, tlul_err, tlul_request_loopback | source | 512 | 0 | reqfifo_storage_upper=4, response_payload=1, rspfifo_storage_upper=3 | fallback |
