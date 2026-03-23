/**
 * host_stub.c — Phase C placeholder: documents linkage intent for a future host slice.
 *
 * A full host binary would compile selected Verilator --cc sources (init, sc_main, monitors)
 * with clang++, link against CUDA driver or nvcc-combined binary, and share storage layout
 * with vl_eval_batch_gpu per host_abi.h.
 *
 * Today: trivial compile check only. Run: make -C src/hybrid host_stub
 */

#include <stdio.h>
#include "host_abi.h"

int main(void) {
  printf("vl hybrid host stub — see README Roadmap Phase C and host_abi.h\n");
  printf("VL_HYBRID_DEFAULT_BLOCK = %d\n", VL_HYBRID_DEFAULT_BLOCK);
  return 0;
}
