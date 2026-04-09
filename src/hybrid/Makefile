# Minimal hybrid runner (CUDA Driver API). Requires: cuda.h + libcuda
# Override: make CUDA_HOME=/path/to/cuda
#           make CUDA_INCLUDE_DIR=/path/to/include CUDA_LIB_DIR=/path/to/lib

CUDA_HOME ?= /usr/local/cuda
CUDA_INCLUDE_DIR ?=
CUDA_LIB_DIR ?=

CXX      ?= g++
CXXFLAGS ?= -O2 -Wall -Wextra

ifeq ($(strip $(CUDA_INCLUDE_DIR)),)
  ifneq ($(wildcard $(CUDA_HOME)/include/cuda.h),)
    CUDA_INCLUDE_DIR := $(CUDA_HOME)/include
  else ifneq ($(wildcard /usr/lib/cuda/include/cuda.h),)
    CUDA_INCLUDE_DIR := /usr/lib/cuda/include
  else ifneq ($(wildcard /usr/include/cuda.h),)
    CUDA_INCLUDE_DIR := /usr/include
  endif
endif

ifeq ($(strip $(CUDA_LIB_DIR)),)
  ifneq ($(wildcard $(CUDA_HOME)/lib64/libcuda.so),)
    CUDA_LIB_DIR := $(CUDA_HOME)/lib64
  else ifneq ($(wildcard /usr/lib/wsl/lib/libcuda.so),)
    CUDA_LIB_DIR := /usr/lib/wsl/lib
  else ifneq ($(wildcard /usr/lib/x86_64-linux-gnu/libcuda.so),)
    CUDA_LIB_DIR := /usr/lib/x86_64-linux-gnu
  endif
endif

INCLUDES  = -I$(CUDA_INCLUDE_DIR)
LDFLAGS   = -L$(CUDA_LIB_DIR) -Wl,-rpath,$(CUDA_LIB_DIR)
LDLIBS    = -lcuda

.PHONY: all clean

all: run_vl_hybrid host_stub

run_vl_hybrid: run_vl_hybrid.c
	@test -n "$(CUDA_INCLUDE_DIR)" -a -f $(CUDA_INCLUDE_DIR)/cuda.h || \
		(echo "Set CUDA_HOME or CUDA_INCLUDE_DIR so cuda.h is available"; exit 1)
	@test -n "$(CUDA_LIB_DIR)" -a -e $(CUDA_LIB_DIR)/libcuda.so || \
		(echo "Set CUDA_LIB_DIR so libcuda.so is available"; exit 1)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ $< $(LDFLAGS) $(LDLIBS)

# Phase C: no CUDA required — ABI placeholder binary
host_stub: host_stub.c host_abi.h
	$(CXX) $(CXXFLAGS) -o $@ host_stub.c

clean:
	rm -f run_vl_hybrid host_stub
