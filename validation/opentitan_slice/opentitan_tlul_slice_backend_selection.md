# OpenTitan TL-UL Slice Backend Selection

| Slice | Single-step | Multi-step | Sweep | Campaign |
|---|---|---|---|---|
| tlul_fifo_sync | source | source | source | source |
| tlul_socket_1n | source | source | source | source |
| tlul_socket_m1 | source | circt-cubin | source | source |
| xbar_main | circt-cubin | circt-cubin | circt-cubin | circt-cubin |
| xbar_peri | source | circt-cubin | source | source |
