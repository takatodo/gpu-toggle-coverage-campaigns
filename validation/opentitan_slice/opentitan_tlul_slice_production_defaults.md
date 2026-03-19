# OpenTitan TL-UL Slice Production Defaults

| Slice | Status | Single backend | Multi backend | Campaign backend | Best hit | Hit/s | Wall s | Candidate count | Shards | Stop |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| tlul_err | needs_review | source | source | source | 0 | 0.0000 | 0.000 | 0 | 0 | no |
| tlul_fifo_async | needs_review | source | source | source | 0 | 0.0000 | 0.000 | 512 | 2 | yes |
| tlul_fifo_sync | frozen | source | source | source | 8 | 5.2660 | 1.519 | 0 | 0 | no |
| tlul_request_loopback | needs_review | source | source | source | 0 | 0.0000 | 0.000 | 0 | 0 | no |
| tlul_socket_1n | frozen | source | source | source | 11 | 24.3253 | 0.452 | 0 | 0 | no |
| tlul_socket_m1 | frozen | source | circt-cubin | source | 9 | 17.2710 | 0.521 | 0 | 0 | no |
| xbar_main | frozen | circt-cubin | circt-cubin | circt-cubin | 4 | 5.6406 | 0.709 | 0 | 0 | no |
| xbar_peri | frozen | source | circt-cubin | source | 6 | 12.2988 | 0.488 | 0 | 0 | no |
