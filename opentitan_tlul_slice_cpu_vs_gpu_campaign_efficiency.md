# OpenTitan TL-UL Slice Campaign CPU vs GPU

| Slice | GPU hit/s | CPU hit/s | GPU/CPU | GPU wall s | CPU wall s | GPU hit | CPU hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| tlul_fifo_sync | 0.3419 | 0.3501 | 0.98x | 23.402 | 22.851 | 8 | 8 |
| tlul_socket_1n | 4.0106 | 4.2677 | 0.94x | 2.743 | 2.578 | 11 | 11 |
| tlul_socket_m1 | 1.7185 | 1.7493 | 0.98x | 5.237 | 5.145 | 9 | 9 |
| xbar_main | 0.7514 | 0.7201 | 1.04x | 5.323 | 5.555 | 4 | 4 |
| xbar_peri | 1.1925 | 1.2889 | 0.93x | 5.031 | 4.655 | 6 | 6 |
