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
 * Optional future fields (not auto-filled yet): clock_bit_offset, reset_bit_offset inside each
 * state slice — use run_vl_hybrid patches at global_off = state0_off + k*storage_size for probes.
 */

#ifndef VL_HOST_ABI_H
#define VL_HOST_ABI_H

#ifdef __cplusplus
extern "C" {
#endif

/** Default block dimension matching vlgpugen kernel launch layout. */
#define VL_HYBRID_DEFAULT_BLOCK 256

#ifdef __cplusplus
}
#endif

#endif
