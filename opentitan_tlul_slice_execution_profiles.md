# OpenTitan TL-UL Slice Execution Profiles

| Slice | Phase | Status | Backend | nstates | gpu_reps | cpu_reps | sequential_steps |
|---|---|---|---|---:|---:|---:|---:|
| tlul_fifo_sync | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_fifo_sync | multi_step | frozen | source | 32 | 3 | 1 | 56 |
| tlul_fifo_sync | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_fifo_sync | campaign | frozen | source | 32 | 3 | 1 | 56 |
| tlul_socket_1n | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_socket_1n | multi_step | frozen | source | 32 | 3 | 1 | 56 |
| tlul_socket_1n | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_socket_1n | campaign | frozen | source | 32 | 3 | 1 | 56 |
| tlul_socket_m1 | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_socket_m1 | multi_step | frozen | circt-cubin | 32 | 3 | 1 | 56 |
| tlul_socket_m1 | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_socket_m1 | campaign | frozen | source | 32 | 3 | 1 | 56 |
| xbar_main | single_step | frozen | circt-cubin | 16 | 5 | 1 | 1 |
| xbar_main | multi_step | frozen | circt-cubin | 32 | 3 | 1 | 56 |
| xbar_main | sweep | frozen | circt-cubin | 32 | 3 | 1 | 56 |
| xbar_main | campaign | frozen | circt-cubin | 32 | 3 | 1 | 56 |
| xbar_peri | single_step | frozen | source | 16 | 5 | 1 | 1 |
| xbar_peri | multi_step | frozen | circt-cubin | 32 | 3 | 1 | 56 |
| xbar_peri | sweep | frozen | source | 32 | 3 | 1 | 56 |
| xbar_peri | campaign | frozen | source | 32 | 3 | 1 | 56 |
| tlul_fifo_async | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_fifo_async | multi_step | frozen | source | 32 | 3 | 1 | 56 |
| tlul_fifo_async | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_fifo_async | campaign | frozen | source | 32 | 3 | 1 | 56 |
| tlul_err | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_err | multi_step | frozen | source | 32 | 3 | 1 | 56 |
| tlul_err | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_err | campaign | frozen | source | 32 | 3 | 1 | 56 |
| tlul_request_loopback | single_step | frozen | source | 16 | 5 | 1 | 1 |
| tlul_request_loopback | multi_step | frozen | source | 32 | 3 | 1 | 56 |
| tlul_request_loopback | sweep | frozen | source | 32 | 3 | 1 | 56 |
| tlul_request_loopback | campaign | frozen | source | 32 | 3 | 1 | 56 |
