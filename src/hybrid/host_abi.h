/**
 * host_abi.h — Phase C: documented ABI between host driver and vl_eval_batch_gpu cubin.
 *
 * The GPU kernel expects:
 *   - void vl_eval_batch_gpu(uint8_t *storage_base, int32_t nstates);
 *   - Per-thread state at storage_base + (blockIdx.x*blockDim.x + threadIdx.x) * STORAGE_STRIDE
 *     when thread index < nstates.
 *
 * Build metadata (vl_batch_gpu.meta.json next to cubin) supplies:
 *   - schema_version, storage_size (stride in bytes), sm, kernel name
 *
 * First supported target (2026-04-03): tlul_socket_m1.
 * These offsets were probed from the socket_m1 root header under work/vl_ir_exp/socket_m1_vl/
 * and are treated as the
 * initial executable ABI for the minimal CPU slice:
 *   - cfg_valid_i @ 0
 *   - done_o @ 1
 *   - clk_i @ 2
 *   - rst_ni @ 3
 *   - cfg_reset_cycles_i @ 172
 *   - cfg_signature_o @ 196
 *   - toggle_bitmap_word[0..2]_o @ 296, 300, 304
 *   - vlSymsp @ 2040
 *
 * Host/GPU ownership for the minimal supported flow:
 *   - Host owns byte-level initialization and CPU-side mutation of config / reset fields.
 *   - The serialized root image still exposes clk_i, but the first supported tlul_socket_m1 flow
 *     keeps the timed clock coroutine already present in tlul_socket_m1_gpu_cov_tb rather than
 *     requiring a host-driven clock top.
 *   - GPU owns in-place mutation of the root storage during kernel launches.
 *   - GPU writes a fake vlSymsp pointer before each launch; any future CPU slice must rebind
 *     vlSymsp before calling host-side Verilator helpers.
 *   - Toggle bitmap words are GPU-produced outputs; host may read them back after each launch
 *     sequence and zero / reinitialize state between campaigns.
 *   - Fatal / error handling is process-fatal for the first supported flow: CUDA or host-side
 *     Verilator failures abort the run rather than attempting recovery.
 */

#ifndef VL_HOST_ABI_H
#define VL_HOST_ABI_H

#ifdef __cplusplus
extern "C" {
#endif

/** Default block dimension matching vlgpugen kernel launch layout. */
#define VL_HYBRID_DEFAULT_BLOCK 256

/** Canonical first supported target: tlul_socket_m1. */
#define VL_SOCKET_M1_STORAGE_SIZE 2112
#define VL_SOCKET_M1_OFF_CFG_VALID_I 0
#define VL_SOCKET_M1_OFF_DONE_O 1
#define VL_SOCKET_M1_OFF_CLK_I 2
#define VL_SOCKET_M1_OFF_RST_NI 3
#define VL_SOCKET_M1_OFF_CFG_RESET_CYCLES_I 172
#define VL_SOCKET_M1_OFF_CFG_SIGNATURE_O 196
#define VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD0_O 296
#define VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD1_O 300
#define VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD2_O 304
#define VL_SOCKET_M1_OFF_VLSYMS 2040

#ifdef __cplusplus
}
#endif

#endif
