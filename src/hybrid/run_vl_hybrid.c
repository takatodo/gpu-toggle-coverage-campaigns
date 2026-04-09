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
/* Optional stage trace to help localize runtime kills / hangs. */
#define ENV_TRACE_STAGES "RUN_VL_HYBRID_TRACE_STAGES"
/* Optional override of the requested CUDA stack limit in bytes. */
#define ENV_STACK_LIMIT_OVERRIDE "RUN_VL_HYBRID_STACK_LIMIT_OVERRIDE"
/* Optional exit after stack-limit handling, before alloc / launch. */
#define ENV_STACK_LIMIT_PROBE_ONLY "RUN_VL_HYBRID_STACK_LIMIT_PROBE_ONLY"

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

static int trace_stages_enabled(void) {
  const char *raw = getenv(ENV_TRACE_STAGES);
  return raw != NULL && raw[0] != '\0';
}

static int env_flag_enabled(const char *name) {
  const char *raw = getenv(name);
  return raw != NULL && raw[0] != '\0';
}

static int parse_size_t_env(const char *name, size_t *out) {
  const char *raw = getenv(name);
  char *end = NULL;
  unsigned long long value = 0;
  if (raw == NULL || raw[0] == '\0')
    return 0;
  value = strtoull(raw, &end, 0);
  if (end == raw || *end != '\0')
    return -1;
  *out = (size_t)value;
  return 1;
}

static void trace_stage(const char *stage) {
  if (!trace_stages_enabled())
    return;
  fprintf(stderr, "run_vl_hybrid: stage=%s\n", stage);
  fflush(stderr);
}

static void trace_function_attr(CUfunction fn, const char *kernel_name,
                                const char *attr_name,
                                CUfunction_attribute attr) {
  if (!trace_stages_enabled())
    return;
  int value = 0;
  CUresult err = cuFuncGetAttribute(&value, attr, fn);
  if (err != CUDA_SUCCESS) {
    const char *msg = NULL;
    cuGetErrorString(err, &msg);
    fprintf(stderr, "run_vl_hybrid: attr %s %s=error:%d:%s\n", kernel_name,
            attr_name, (int)err, msg ? msg : "?");
    return;
  }
  fprintf(stderr, "run_vl_hybrid: attr %s %s=%d\n", kernel_name, attr_name,
          value);
}

static void trace_function_attrs(CUfunction fn, const char *kernel_name) {
  if (!trace_stages_enabled())
    return;
  trace_function_attr(fn, kernel_name, "MAX_THREADS_PER_BLOCK",
                      CU_FUNC_ATTRIBUTE_MAX_THREADS_PER_BLOCK);
  trace_function_attr(fn, kernel_name, "NUM_REGS",
                      CU_FUNC_ATTRIBUTE_NUM_REGS);
  trace_function_attr(fn, kernel_name, "LOCAL_SIZE_BYTES",
                      CU_FUNC_ATTRIBUTE_LOCAL_SIZE_BYTES);
  trace_function_attr(fn, kernel_name, "SHARED_SIZE_BYTES",
                      CU_FUNC_ATTRIBUTE_SHARED_SIZE_BYTES);
  trace_function_attr(fn, kernel_name, "CONST_SIZE_BYTES",
                      CU_FUNC_ATTRIBUTE_CONST_SIZE_BYTES);
  trace_function_attr(fn, kernel_name, "PTX_VERSION",
                      CU_FUNC_ATTRIBUTE_PTX_VERSION);
  trace_function_attr(fn, kernel_name, "BINARY_VERSION",
                      CU_FUNC_ATTRIBUTE_BINARY_VERSION);
  trace_function_attr(fn, kernel_name, "CACHE_MODE_CA",
                      CU_FUNC_ATTRIBUTE_CACHE_MODE_CA);
#ifdef CU_FUNC_ATTRIBUTE_MAX_DYNAMIC_SHARED_SIZE_BYTES
  trace_function_attr(fn, kernel_name, "MAX_DYNAMIC_SHARED_SIZE_BYTES",
                      CU_FUNC_ATTRIBUTE_MAX_DYNAMIC_SHARED_SIZE_BYTES);
#endif
#ifdef CU_FUNC_ATTRIBUTE_PREFERRED_SHARED_MEMORY_CARVEOUT
  trace_function_attr(fn, kernel_name, "PREFERRED_SHARED_MEMORY_CARVEOUT",
                      CU_FUNC_ATTRIBUTE_PREFERRED_SHARED_MEMORY_CARVEOUT);
#endif
#ifdef CU_FUNC_ATTRIBUTE_CLUSTER_SIZE_MUST_BE_SET
  trace_function_attr(fn, kernel_name, "CLUSTER_SIZE_MUST_BE_SET",
                      CU_FUNC_ATTRIBUTE_CLUSTER_SIZE_MUST_BE_SET);
#endif
#ifdef CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_WIDTH
  trace_function_attr(fn, kernel_name, "REQUIRED_CLUSTER_WIDTH",
                      CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_WIDTH);
#endif
#ifdef CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_HEIGHT
  trace_function_attr(fn, kernel_name, "REQUIRED_CLUSTER_HEIGHT",
                      CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_HEIGHT);
#endif
#ifdef CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_DEPTH
  trace_function_attr(fn, kernel_name, "REQUIRED_CLUSTER_DEPTH",
                      CU_FUNC_ATTRIBUTE_REQUIRED_CLUSTER_DEPTH);
#endif
#ifdef CU_FUNC_ATTRIBUTE_NON_PORTABLE_CLUSTER_SIZE_ALLOWED
  trace_function_attr(fn, kernel_name, "NON_PORTABLE_CLUSTER_SIZE_ALLOWED",
                      CU_FUNC_ATTRIBUTE_NON_PORTABLE_CLUSTER_SIZE_ALLOWED);
#endif
#ifdef CU_FUNC_ATTRIBUTE_CLUSTER_SCHEDULING_POLICY_PREFERENCE
  trace_function_attr(fn, kernel_name, "CLUSTER_SCHEDULING_POLICY_PREFERENCE",
                      CU_FUNC_ATTRIBUTE_CLUSTER_SCHEDULING_POLICY_PREFERENCE);
#endif
}

static size_t kernel_local_size_bytes(CUfunction fn) {
  int value = 0;
  CUresult err =
      cuFuncGetAttribute(&value, CU_FUNC_ATTRIBUTE_LOCAL_SIZE_BYTES, fn);
  if (err != CUDA_SUCCESS || value < 0)
    return 0;
  return (size_t)value;
}

static int maybe_raise_stack_limit_for_kernels(CUfunction *kfns, int nk) {
  size_t required_stack = 0;
  size_t target_stack = 0;
  for (int i = 0; i < nk; i++) {
    size_t local_size = kernel_local_size_bytes(kfns[i]);
    if (local_size > required_stack)
      required_stack = local_size;
  }
  if (required_stack == 0)
    return 0;

  target_stack = required_stack;
  {
    size_t override_stack = 0;
    int override_status = parse_size_t_env(ENV_STACK_LIMIT_OVERRIDE, &override_stack);
    if (override_status < 0) {
      fprintf(stderr, "invalid %s='%s'\n", ENV_STACK_LIMIT_OVERRIDE,
              getenv(ENV_STACK_LIMIT_OVERRIDE));
      return 2;
    }
    if (override_status > 0)
      target_stack = override_stack;
  }

  size_t current_limit = 0;
  CUDA_CHECK(cuCtxGetLimit(&current_limit, CU_LIMIT_STACK_SIZE));
  if (trace_stages_enabled()) {
    fprintf(stderr,
            "run_vl_hybrid: ctx_limit STACK_SIZE current=%zu required=%zu target=%zu\n",
            current_limit, required_stack, target_stack);
  }
  if (target_stack <= current_limit)
    return 0;
  {
    CUresult err = cuCtxSetLimit(CU_LIMIT_STACK_SIZE, target_stack);
    if (err != CUDA_SUCCESS) {
      const char *msg = NULL;
      cuGetErrorString(err, &msg);
      if (trace_stages_enabled()) {
        fprintf(stderr,
                "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=%zu err=%d:%s\n",
                target_stack, (int)err, msg ? msg : "?");
      }
      return 1;
    }
  }
  if (trace_stages_enabled()) {
    size_t updated_limit = 0;
    CUDA_CHECK(cuCtxGetLimit(&updated_limit, CU_LIMIT_STACK_SIZE));
    fprintf(stderr, "run_vl_hybrid: ctx_limit STACK_SIZE updated=%zu\n",
            updated_limit);
  }
  return 0;
}

int main(int argc, char **argv) {
  if (trace_stages_enabled())
    setvbuf(stderr, NULL, _IONBF, 0);

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

  trace_stage("before_cuInit");
  {
    CUresult err = cuInit(0);
    if (err != CUDA_SUCCESS)
      cuda_fail(__FILE__, __LINE__, err, "cuInit");
  }
  trace_stage("after_cuInit");

  CUdevice dev;
  {
    trace_stage("before_cuDeviceGet");
    CUresult err = cuDeviceGet(&dev, 0);
    if (err != CUDA_SUCCESS)
      cuda_fail(__FILE__, __LINE__, err, "cuDeviceGet");
  }
  trace_stage("after_cuDeviceGet");

  char name[256];
  CUDA_CHECK(cuDeviceGetName(name, sizeof(name), dev));
  printf("device 0: %s\n", name);
  fflush(stdout);

  trace_stage("before_cuCtxCreate");
  CUcontext ctx;
  CUDA_CHECK(cuCtxCreate(&ctx, 0, dev));
  trace_stage("after_cuCtxCreate");

  trace_stage("before_cuModuleLoad");
  CUmodule mod;
  CUDA_CHECK(cuModuleLoad(&mod, cubin_path));
  trace_stage("after_cuModuleLoad");

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
      trace_function_attrs(kfns[nk], tok);
      nk++;
    }
    free(buf);
  } else {
    CUDA_CHECK(cuModuleGetFunction(&kfns[0], mod, "vl_eval_batch_gpu"));
    trace_function_attrs(kfns[0], "vl_eval_batch_gpu");
    nk = 1;
  }
  if (nk < 1) {
    fprintf(stderr, "no kernels to launch\n");
    return 1;
  }
  {
    int stack_limit_status = maybe_raise_stack_limit_for_kernels(kfns, nk);
    if (env_flag_enabled(ENV_STACK_LIMIT_PROBE_ONLY))
      return stack_limit_status;
    if (stack_limit_status != 0) {
      fprintf(stderr, "stack-limit setup failed with status=%d\n", stack_limit_status);
      return stack_limit_status;
    }
  }
  trace_stage("after_kernel_resolution");

  CUdeviceptr d_storage = 0;
  trace_stage("before_cuMemAlloc");
  CUDA_CHECK(cuMemAlloc(&d_storage, total));
  CUDA_CHECK(cuMemsetD8(d_storage, 0, total));
  trace_stage("after_cuMemAlloc");

  {
    const char *init_state_path = getenv(ENV_INIT_STATE);
    if (init_state_path && init_state_path[0] != '\0') {
      trace_stage("before_init_state_upload");
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
      trace_stage("after_init_state_upload");
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
  trace_stage("before_launch_loop");

  float gpu_kernel_ms_sum = 0.f;
  const int sync_each_step = getenv(ENV_SYNC_EACH_STEP) != NULL;

  if (getenv(ENV_WARMUP) != NULL) {
    trace_stage("before_warmup");
    for (int k = 0; k < nk; k++) {
      CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0, params,
                                NULL));
    }
    CUDA_CHECK(cuCtxSynchronize());
    trace_stage("after_warmup");
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
      if (step == 0U)
        trace_stage("before_first_kernel_launch");
      for (int k = 0; k < nk; k++) {
        CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0,
                                  params, NULL));
      }
      if (step == 0U)
        trace_stage("after_first_kernel_launch");
      CUDA_CHECK(cuEventRecord(ev_stop, 0));
      if (step == 0U)
        trace_stage("before_first_step_sync");
      CUDA_CHECK(cuCtxSynchronize());
      if (step == 0U)
        trace_stage("after_first_step_sync");
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
      if (step == 0U)
        trace_stage("before_first_kernel_launch");
      for (int k = 0; k < nk; k++) {
        CUDA_CHECK(cuLaunchKernel(kfns[k], grid, 1, 1, block, 1, 1, 0, 0,
                                  params, NULL));
      }
      if (step == 0U)
        trace_stage("after_first_kernel_launch");
    }
    CUDA_CHECK(cuEventRecord(ev_stop, 0));
    trace_stage("before_final_sync");
    CUDA_CHECK(cuCtxSynchronize());
    trace_stage("after_final_sync");
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
  trace_stage("after_launch_loop");

  const char *dump_path = getenv(ENV_DUMP_STATE);
  if (dump_path && dump_path[0] != '\0') {
    trace_stage("before_dump_state");
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
    trace_stage("after_dump_state");
  }

  trace_stage("before_cleanup");
  CUDA_CHECK(cuMemFree(d_storage));
  CUDA_CHECK(cuCtxDestroy(ctx));
  trace_stage("after_cleanup");
  return 0;
}
