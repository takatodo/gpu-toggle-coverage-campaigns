# Minimal hybrid runner (CUDA Driver API). Requires: cuda.h + libcuda
# Override: make CUDA_HOME=/path/to/cuda

CUDA_HOME ?= /usr/local/cuda

CXX      ?= g++
CXXFLAGS ?= -O2 -Wall -Wextra
INCLUDES  = -I$(CUDA_HOME)/include
LDFLAGS   = -L$(CUDA_HOME)/lib64 -Wl,-rpath,$(CUDA_HOME)/lib64
LDLIBS    = -lcuda

.PHONY: all clean

all: run_vl_hybrid host_stub

run_vl_hybrid: run_vl_hybrid.c
	@test -f $(CUDA_HOME)/include/cuda.h || (echo "Set CUDA_HOME (e.g. export CUDA_HOME=/usr/local/cuda)"; exit 1)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ $< $(LDFLAGS) $(LDLIBS)

# Phase C: no CUDA required — ABI placeholder binary
host_stub: host_stub.c host_abi.h
	$(CXX) $(CXXFLAGS) -o $@ host_stub.c

clean:
	rm -f run_vl_hybrid host_stub
