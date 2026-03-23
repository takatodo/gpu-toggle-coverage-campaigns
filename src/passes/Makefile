LLVM_CONFIG ?= llvm-config-18
CXX         ?= clang++-18

CXXFLAGS := $(shell $(LLVM_CONFIG) --cxxflags) -fPIC
LDFLAGS  := $(shell $(LLVM_CONFIG) --ldflags)
LIBS     := -lLLVM-18

.PHONY: all clean

all: VlGpuPasses.so vlgpugen

VlGpuPasses.so: VlGpuPasses.cpp
	$(CXX) $(CXXFLAGS) -shared -o $@ $< $(LDFLAGS)

vlgpugen: vlgpugen.cpp
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS) $(LIBS)

clean:
	rm -f VlGpuPasses.so vlgpugen
