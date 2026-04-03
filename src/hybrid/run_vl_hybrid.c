/**
 * run_vl_hybrid.c — Phase-D host: load cubin, optional per-step HtoD patches, repeat launch.
 *
 * If RUN_VL_HYBRID_KERNELS is set (comma-separated names), each step launches that sequence
 * instead of a single vl_eval_batch_gpu (see vl_batch_gpu.meta.json launch_sequence).
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

/* Comma-separated kernel names; Verilator phase order (see vl_batch_gpu.meta.json launch_sequence). */
#define ENV_KERNEL_CHAIN "RUN_VL_HYBRID_KERNELS"
#define MAX_KERNEL_CHAIN 16

/* Optional binary dump of device storage after the last launch sequence. */
#define ENV_DUMP_STATE "RUN_VL_HYBRID_DUMP_STATE"
/* Optional raw state image copied into device storage before patches/launches. */
#define ENV_INIT_STATE "RUN_VL_HYBRID_INIT_STATE"

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

  CUfunction kfns[MAX_KERNEL_CHAIN];
  int nk = 0;
  const char *kchain = getenv(ENV_KERNEL_CHAIN);
  if (kchain && kchain[0] != '\0') {
    char *buf = strdup(kchain);
    if (!buf) {
      fprintf(stderr, "strdup failed\n");
      return 1;
    }
    for (char *tok = strtok(buf, ","); tok != NULL; tok = strtok(NULL, ",")) {
      while (*tok == ' ' || *tok == '\t')
        tok++;
      size_t L = strlen(tok);
      while (L > 0 && (tok[L - 1] == ' ' || tok[L - 1] == '\t'))
        tok[--L] = '\0';
      if (tok[0] == '\0')
        continue;
      if (nk >= MAX_KERNEL_CHAIN) {
        fprintf(stderr, "too many kernels in %s (max %d)\n", ENV_KERNEL_CHAIN,
                MAX_KERNEL_CHAIN);
        free(buf);
        return 1;
      }
      CUresult gr = cuModuleGetFunction(&kfns[nk], mod, tok);
      if (gr != CUDA_SUCCESS) {
        const char *em = NULL;
        cuGetErrorString(gr, &em);
        fprintf(stderr, "cuModuleGetFunction(%s): %d %s\n", tok, (int)gr,
                em ? em : "?");
        free(buf);
        return 1;
      }
      nk++;
    }
    free(buf);
  } else {
    CUDA_CHECK(cuModuleGetFunction(&kfns[0], mod, "vl_eval_batch_gpu"));
    nk = 1;
  }
  if (nk < 1) {
    fprintf(stderr, "no kernels to launch\n");
    return 1;
  }

  CUdeviceptr d_storage = 0;
  CUDA_CHECK(cuMemAlloc(&d_storage, total));
  CUDA_CHECK(cuMemsetD8(d_storage, 0, total));

  {
    const char *init_state_path = getenv(ENV_INIT_STATE);
    if (init_state_path && init_state_path[0] != '\0') {
      FILE *fp = fopen(init_state_path, "rb");
      if (!fp) {
        fprintf(stderr, "failed to open %s=%s\n", ENV_INIT_STATE, init_state_path);
        return 1;
      }
      if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        fprintf(stderr, "failed to seek %s\n", init_state_path);
        return 1;
      }
      long file_size_long = ftell(fp);
      if (file_size_long < 0) {
        fclose(fp);
        fprintf(stderr, "failed to stat %s\n", init_state_path);
        return 1;
      }
      if (fseek(fp, 0, SEEK_SET) != 0) {
        fclose(fp);
        fprintf(stderr, "failed to rewind %s\n", init_state_path);
        return 1;
      }
      size_t file_size = (size_t)file_size_long;
      if (!(file_size == storage || file_size == total)) {
        fclose(fp);
        fprintf(stderr,
                "%s size %zu does not match storage_size %zu or total bytes %zu\n",
                init_state_path, file_size, storage, total);
        return 1;
      }
      unsigned char *buf = (unsigned char *)malloc(file_size ? file_size : 1);
      if (!buf) {
        fclose(fp);
        fprintf(stderr, "malloc failed for init state\n");
        return 1;
      }
      if (file_size && fread(buf, 1, file_size, fp) != file_size) {
        free(buf);
        fclose(fp);
        fprintf(stderr, "failed to read %s\n", init_state_path);
        return 1;
      }
      fclose(fp);
      if (file_size == total) {
        CUDA_CHECK(cuMemcpyHtoD(d_storage, buf, total));
      } else {
        for (unsigned state = 0; state < nstates; state++) {
          CUDA_CHECK(cuMemcpyHtoD(d_storage + ((size_t)state * storage), buf, storage));
        }
      }
      free(buf);
    }
  }

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
    for (int k = 0; k < nk; k++) {
      CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0, params,
                                NULL));
    }
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
      for (int k = 0; k < nk; k++) {
        CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0,
                                  params, NULL));
      }
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
      for (int k = 0; k < nk; k++) {
        CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0,
                                  params, NULL));
      }
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

  printf("ok: steps=%u kernels_per_step=%d patches_per_step=%d grid=%u block=%u "
         "nstates=%u storage=%zu B\n",
         steps, nk, npatch, grid, block, nstates, storage);
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

  const char *dump_path = getenv(ENV_DUMP_STATE);
  if (dump_path && dump_path[0] != '\0') {
    unsigned char *host = (unsigned char *)malloc(total);
    if (!host) {
      fprintf(stderr, "malloc failed for %zu-byte state dump\n", total);
      return 1;
    }
    CUDA_CHECK(cuMemcpyDtoH(host, d_storage, total));
    FILE *fp = fopen(dump_path, "wb");
    if (!fp) {
      fprintf(stderr, "fopen(%s) failed\n", dump_path);
      free(host);
      return 1;
    }
    size_t nw = fwrite(host, 1, total, fp);
    fclose(fp);
    free(host);
    if (nw != total) {
      fprintf(stderr, "short write to %s: wrote %zu / %zu bytes\n", dump_path,
              nw, total);
      return 1;
    }
    printf("state_dump: %s (%zu bytes)\n", dump_path, total);
  }

  CUDA_CHECK(cuMemFree(d_storage));
  CUDA_CHECK(cuCtxDestroy(ctx));
  return 0;
}
