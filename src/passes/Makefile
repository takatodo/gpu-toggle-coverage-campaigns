LLVM_CONFIG ?= llvm-config-18
CXX         ?= clang++-18

CXXFLAGS := $(shell $(LLVM_CONFIG) --cxxflags) -fPIC
LDFLAGS  := $(shell $(LLVM_CONFIG) --ldflags)

.PHONY: all clean

all: VlGpuPasses.so

VlGpuPasses.so: VlGpuPasses.cpp
	$(CXX) $(CXXFLAGS) -shared -o $@ $< $(LDFLAGS)

clean:
	rm -f VlGpuPasses.so
