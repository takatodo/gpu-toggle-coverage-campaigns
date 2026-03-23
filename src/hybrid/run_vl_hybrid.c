/**
 * run_vl_hybrid.c — Phase-D host: load cubin, optional per-step HtoD patches, repeat launch.
 *
 * Usage:
 *   ./run_vl_hybrid <cubin> <storage_bytes> <nstates> [block] [steps] [patch ...]
 *
 *   patch:  global_byte_offset:value  (value 0–255 decimal, or 0xNN hex)
 *   block:  0 = default 256
 *   steps:  0 = default 1; each step applies all patches then launches kernel
 *
 * Example (toggle a byte at global offset 42 before each of 8 evals):
 *   ./run_vl_hybrid m.cubin 2048 1024 256 8 42:0 42:1 42:0
 *   (three patches per step — use one patch per step instead: run with steps=8 and one patch
 *    per step requires multiple invocations; here all patches run each step in order.)
 */

#include <cuda.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Set to force one cuCtxSynchronize per step (slower wall clock; old behavior). */
#define ENV_SYNC_EACH_STEP "RUN_VL_HYBRID_SYNC_EACH_STEP"
/* Optional untimed launch after init to absorb first-launch / driver latency. */
#define ENV_WARMUP "RUN_VL_HYBRID_WARMUP"

static void cuda_fail(const char *file, int line, CUresult err, const char *what) {
  const char *msg = NULL;
  cuGetErrorString(err, &msg);
  fprintf(stderr, "%s:%d CUDA error %d: %s (%s)\n", file, line, (int)err,
          msg ? msg : "?", what);
  /* CUDA_ERROR_NO_DEVICE == 100 */
  if ((int)err == 100) {
    fprintf(stderr,
            "Hint: if nvidia-smi works but this fails, on WSL2 try:\n"
            "  export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH\n"
            "Also check CUDA_VISIBLE_DEVICES and that libcuda is not a stub-only link.\n");
  }
  exit(1);
}

#define CUDA_CHECK(stmt)                                                       \
  do {                                                                         \
    CUresult _err = (stmt);                                                    \
    if (_err != CUDA_SUCCESS) {                                                \
      const char *_msg = NULL;                                                 \
      cuGetErrorString(_err, &_msg);                                           \
      fprintf(stderr, "%s:%d CUDA error %d: %s\n", __FILE__, __LINE__,        \
              (int)_err, _msg ? _msg : "?");                                    \
      exit(1);                                                                 \
    }                                                                          \
  } while (0)

#define MAX_PATCHES 64
typedef struct {
  size_t global_off;
  unsigned char val;
} Patch;

static int parse_byte(const char *s, unsigned char *out) {
  if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X'))
    return sscanf(s + 2, "%hhx", out) == 1 ? 0 : -1;
  unsigned v;
  if (sscanf(s, "%u", &v) != 1 || v > 255)
    return -1;
  *out = (unsigned char)v;
  return 0;
}

static int parse_patch(const char *arg, Patch *p) {
  const char *colon = strchr(arg, ':');
  if (!colon)
    return -1;
  char *end = NULL;
  unsigned long long off = strtoull(arg, &end, 0);
  if (end != colon || colon[1] == '\0')
    return -1;
  unsigned char b;
  if (parse_byte(colon + 1, &b) != 0)
    return -1;
  p->global_off = (size_t)off;
  p->val = b;
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr,
            "Usage: %s <cubin> <storage_bytes> <nstates> [block] [steps] "
            "[global_off:byte ...]\n",
            argv[0]);
    return 1;
  }

  const char *cubin_path = argv[1];
  unsigned long long storage_ull = strtoull(argv[2], NULL, 0);
  unsigned nstates = (unsigned)strtoul(argv[3], NULL, 0);

  unsigned block = 256U;
  unsigned steps = 1U;
  Patch patches[MAX_PATCHES];
  int npatch = 0;

  int pi = 4;
  if (argc > 4 && strchr(argv[4], ':') == NULL && strlen(argv[4]) > 0) {
    unsigned b = (unsigned)strtoul(argv[4], NULL, 0);
    if (b > 0U && b <= 1024U)
      block = b;
    pi++;
  }
  if (argc > pi && strchr(argv[pi], ':') == NULL && strlen(argv[pi]) > 0) {
    unsigned s = (unsigned)strtoul(argv[pi], NULL, 0);
    if (s > 0U)
      steps = s;
    pi++;
  }
  for (; pi < argc; pi++) {
    if (npatch >= MAX_PATCHES) {
      fprintf(stderr, "too many patches (max %d)\n", MAX_PATCHES);
      return 1;
    }
    if (parse_patch(argv[pi], &patches[npatch]) != 0) {
      fprintf(stderr, "bad patch '%s' (want global_offset:byte)\n", argv[pi]);
      return 1;
    }
    npatch++;
  }

  if (storage_ull == 0ULL || storage_ull > (1ULL << 40)) {
    fprintf(stderr, "invalid storage_bytes\n");
    return 1;
  }
  if (nstates == 0U) {
    fprintf(stderr, "nstates must be >= 1\n");
    return 1;
  }

  size_t storage = (size_t)storage_ull;
  size_t total = storage * (size_t)nstates;

  {
    CUresult err = cuInit(0);
    if (err != CUDA_SUCCESS)
      cuda_fail(__FILE__, __LINE__, err, "cuInit");
  }

  CUdevice dev;
  {
    CUresult err = cuDeviceGet(&dev, 0);
    if (err != CUDA_SUCCESS)
      cuda_fail(__FILE__, __LINE__, err, "cuDeviceGet");
  }

  char name[256];
  CUDA_CHECK(cuDeviceGetName(name, sizeof(name), dev));
  printf("device 0: %s\n", name);

  CUcontext ctx;
  CUDA_CHECK(cuCtxCreate(&ctx, 0, dev));

  CUmodule mod;
  CUDA_CHECK(cuModuleLoad(&mod, cubin_path));

  CUfunction kfn;
  CUDA_CHECK(cuModuleGetFunction(&kfn, mod, "vl_eval_batch_gpu"));

  CUdeviceptr d_storage = 0;
  CUDA_CHECK(cuMemAlloc(&d_storage, total));
  CUDA_CHECK(cuMemsetD8(d_storage, 0, total));

  int nstates_i = (int)nstates;
  void *params[] = {&d_storage, &nstates_i};
  unsigned grid = (nstates + block - 1) / block;

  CUevent ev_start, ev_stop;
  CUDA_CHECK(cuEventCreate(&ev_start, CU_EVENT_DEFAULT));
  CUDA_CHECK(cuEventCreate(&ev_stop, CU_EVENT_DEFAULT));

  struct timespec wall0, wall1;
  clock_gettime(CLOCK_MONOTONIC, &wall0);

  float gpu_kernel_ms_sum = 0.f;
  const int sync_each_step = getenv(ENV_SYNC_EACH_STEP) != NULL;

  if (getenv(ENV_WARMUP) != NULL) {
    CUDA_CHECK(cuLaunchKernel(kfn, grid, 1, 1, block, 1, 1, 0, 0, params,
                              NULL));
    CUDA_CHECK(cuCtxSynchronize());
  }

  if (sync_each_step) {
    for (unsigned step = 0; step < steps; step++) {
      for (int i = 0; i < npatch; i++) {
        if (patches[i].global_off >= total) {
          fprintf(stderr, "patch offset %zu >= total %zu\n",
                  patches[i].global_off, total);
          return 1;
        }
        CUDA_CHECK(cuMemcpyHtoD(d_storage + patches[i].global_off,
                                &patches[i].val, 1));
      }
      CUDA_CHECK(cuEventRecord(ev_start, 0));
      CUDA_CHECK(cuLaunchKernel(kfn, grid, 1, 1, block, 1, 1, 0, 0, params,
                                NULL));
      CUDA_CHECK(cuEventRecord(ev_stop, 0));
      CUDA_CHECK(cuCtxSynchronize());
      float step_ms = 0.f;
      CUDA_CHECK(cuEventElapsedTime(&step_ms, ev_start, ev_stop));
      gpu_kernel_ms_sum += step_ms;
    }
  } else {
    /* One sync after all work: much lower wall latency when steps > 1. */
    int recorded_start = 0;
    for (unsigned step = 0; step < steps; step++) {
      for (int i = 0; i < npatch; i++) {
        if (patches[i].global_off >= total) {
          fprintf(stderr, "patch offset %zu >= total %zu\n",
                  patches[i].global_off, total);
          return 1;
        }
        CUDA_CHECK(cuMemcpyHtoD(d_storage + patches[i].global_off,
                                &patches[i].val, 1));
      }
      if (!recorded_start) {
        CUDA_CHECK(cuEventRecord(ev_start, 0));
        recorded_start = 1;
      }
      CUDA_CHECK(cuLaunchKernel(kfn, grid, 1, 1, block, 1, 1, 0, 0, params,
                                NULL));
    }
    CUDA_CHECK(cuEventRecord(ev_stop, 0));
    CUDA_CHECK(cuCtxSynchronize());
    CUDA_CHECK(cuEventElapsedTime(&gpu_kernel_ms_sum, ev_start, ev_stop));
  }

  clock_gettime(CLOCK_MONOTONIC, &wall1);
  double wall_ms =
      (wall1.tv_sec - wall0.tv_sec) * 1000.0 +
      (wall1.tv_nsec - wall0.tv_nsec) / 1e6;

  CUDA_CHECK(cuEventDestroy(ev_start));
  CUDA_CHECK(cuEventDestroy(ev_stop));

  double ms_per_launch =
      steps > 0 ? (double)gpu_kernel_ms_sum / (double)steps : 0.0;
  double us_per_state =
      (nstates > 0) ? (ms_per_launch / (double)nstates) * 1000.0 : 0.0;

  printf("ok: steps=%u patches_per_step=%d grid=%u block=%u nstates=%u "
         "storage=%zu B\n",
         steps, npatch, grid, block, nstates, storage);
  if (sync_each_step) {
    printf("gpu_kernel_time_ms: total=%.6f  per_launch=%.6f  (per-step CUDA "
           "events; kernels only)\n",
           gpu_kernel_ms_sum, ms_per_launch);
  } else if (steps <= 1U) {
    printf("gpu_kernel_time_ms: total=%.6f  per_launch=%.6f  (CUDA events, "
           "kernels only; HtoD patches before launch excluded)\n",
           gpu_kernel_ms_sum, ms_per_launch);
  } else {
    printf("gpu_kernel_time_ms: total=%.6f  per_launch=%.6f  (CUDA events, "
           "default stream: first kernel → last kernel; includes HtoD "
           "between steps)\n",
           gpu_kernel_ms_sum, ms_per_launch);
  }
  printf("gpu_kernel_time: per_state=%.3f us  (per_launch / nstates)\n",
         us_per_state);
  printf("wall_time_ms: %.3f  (host; one GPU sync unless %s=1)\n", wall_ms,
         ENV_SYNC_EACH_STEP);

  CUDA_CHECK(cuMemFree(d_storage));
  CUDA_CHECK(cuCtxDestroy(ctx));
  return 0;
}
