/**
 * vlgpugen — Verilator merged.ll analyzer / future GPU kernel generator (Option B).
 *
 * Today: load LLVM IR, find ___024root___eval, compute reachability, classify
 * runtime vs GPU functions (same rules as vl_runtime_filter.py), report vlSymsp
 * offset from TBAA (same regex as Python).
 *
 * Full ModulePass emission (stubs + vl_eval_batch_gpu) is not implemented here;
 * use gen_vl_gpu_kernel.py + opt until Phase 3 is complete.
 */

#include "llvm/ADT/DenseSet.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/InitLLVM.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"

#include <optional>
#include <regex>
#include <string>

using namespace llvm;

static cl::OptionCategory VlGpuCat("vlgpugen options");

static cl::opt<std::string> InputFilename(cl::Positional, cl::desc("<merged.ll>"),
                                          cl::Required, cl::cat(VlGpuCat));

static cl::opt<int> StorageSize("storage-size",
                                cl::desc("Bytes per simulated state (for future kernel)"),
                                cl::init(0), cl::cat(VlGpuCat));

static cl::opt<std::string> Sm("sm", cl::desc("PTX GPU arch label"), cl::init("sm_89"),
                               cl::cat(VlGpuCat));

static cl::opt<bool> Quiet("q", cl::desc("Minimal one-line summary"), cl::init(false),
                           cl::cat(VlGpuCat));

// ---------------------------------------------------------------------------
// Match vl_runtime_filter.is_runtime (prefixes + body heuristics)
// ---------------------------------------------------------------------------

static void functionToString(const Function &F, std::string &Out) {
  raw_string_ostream OS(Out);
  F.print(OS);
}

static bool isForceInclude(StringRef Name) {
  return Name.contains("___ico_sequent") || Name.contains("___nba_comb");
}

static bool startsWithAny(StringRef Name) {
  static const char *Prefixes[] = {
      "_ZN9Verilated",  "_ZNK9Verilated", "_ZN16VerilatedContext",
      "_ZNK16VerilatedContext", "_ZN14VerilatedModel", "_ZNK14VerilatedModel",
      "_ZN9VlDeleter",  "_ZNSt",             "_ZSt",
      "_Z13sc_time_stamp", "_Z15vl_time_stamp", "__cxa_", "_ZTHN"};
  for (const char *P : Prefixes) {
    if (Name.starts_with(P))
      return true;
  }
  return false;
}

static bool isRuntimeFunction(const Function &F, const std::string &BodyStr) {
  StringRef Name = F.getName();
  if (isForceInclude(Name))
    return false;
  if (startsWithAny(Name))
    return true;
  if (BodyStr.find("@_ZGVZ") != std::string::npos)
    return true;
  if (BodyStr.find("VerilatedSyms") != std::string::npos ||
      BodyStr.find("_gpu_cov_tb__Syms") != std::string::npos)
    return true;
  return false;
}

// ---------------------------------------------------------------------------
// Match vl_runtime_filter.detect_vlsyms_offset (regex on raw .ll text)
// ---------------------------------------------------------------------------

static std::optional<int64_t> detectVlSymsOffset(StringRef FileText) {
  std::string Text = FileText.str();
  std::smatch M;
  std::regex AnyPtrRe(R"(^(!(\d+))\s*=\s*!\{!"any pointer")", std::regex_constants::multiline);
  if (!std::regex_search(Text, M, AnyPtrRe))
    return std::nullopt;
  const std::string AnyId = M.str(2);
  std::string RootPat = "^!\\d+\\s*=\\s*!\\{!\"[^\"]*_024root\".*?!" + AnyId + R"(,\s*i64\s+(\d+))";
  std::regex RootRe(RootPat, std::regex_constants::multiline);
  if (std::regex_search(Text, M, RootRe))
    return std::stoll(M.str(1));
  return std::nullopt;
}

// ---------------------------------------------------------------------------
// Eval + reachability (direct calls; strip pointer casts)
// ---------------------------------------------------------------------------

static Function *findEvalFunction(Module &M) {
  for (Function &F : M) {
    if (F.isDeclaration())
      continue;
    StringRef N = F.getName();
    if (N.contains("___024root___eval") && !N.contains("___eval_"))
      return &F;
  }
  for (Function &F : M) {
    if (F.isDeclaration())
      continue;
    if (F.getName().contains("_eval") && F.getFunctionType()->getNumParams() >= 1)
      return &F;
  }
  return nullptr;
}

static Function *getCallee(CallBase *CB) {
  Value *Op = CB->getCalledOperand()->stripPointerCasts();
  return dyn_cast<Function>(Op);
}

static void collectReachable(Function *Root, DenseSet<Function *> &Out) {
  SmallVector<Function *, 64> Stack;
  Stack.push_back(Root);
  while (!Stack.empty()) {
    Function *F = Stack.pop_back_val();
    if (!Out.insert(F).second)
      continue;
    for (BasicBlock &BB : *F)
      for (Instruction &I : BB) {
        auto *CB = dyn_cast<CallBase>(&I);
        if (!CB)
          continue;
        if (Function *Callee = getCallee(CB)) {
          if (!Callee->isDeclaration())
            Stack.push_back(Callee);
        }
      }
  }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main(int argc, char **argv) {
  InitLLVM X(argc, argv);
  cl::HideUnrelatedOptions(VlGpuCat);
  cl::ParseCommandLineOptions(
      argc, argv,
      "Analyze Verilator merged.ll: find eval, reachability, runtime vs GPU (Option B scaffold).\n"
      "IR emission (stubs + kernel) remains in gen_vl_gpu_kernel.py until Phase 3.\n");

  LLVMContext Ctx;
  SMDiagnostic Err;
  std::unique_ptr<Module> M = parseIRFile(InputFilename, Err, Ctx);
  if (!M) {
    Err.print(argv[0], errs());
    return 1;
  }

  // Raw file text for TBAA offset (same as Python)
  ErrorOr<std::unique_ptr<MemoryBuffer>> BufOr =
      MemoryBuffer::getFile(InputFilename);
  std::optional<int64_t> VlOff;
  if (BufOr) {
    StringRef Raw = BufOr.get()->getBuffer();
    VlOff = detectVlSymsOffset(Raw);
  }

  Function *Eval = findEvalFunction(*M);
  if (!Eval) {
    errs() << "error: no ___024root___eval-like function found\n";
    return 1;
  }

  DenseSet<Function *> Reach;
  collectReachable(Eval, Reach);

  unsigned Gpu = 0, Runtime = 0;
  for (Function *F : Reach) {
    std::string Body;
    functionToString(*F, Body);
    if (isRuntimeFunction(*F, Body))
      ++Runtime;
    else
      ++Gpu;
  }

  if (!Quiet) {
    outs() << "vlgpugen (analysis only — IR emission still via gen_vl_gpu_kernel.py)\n";
    outs() << "  input:           " << InputFilename << "\n";
    outs() << "  eval:            " << Eval->getName() << '\n';
    outs() << "  reachable:       " << Reach.size() << " function(s)\n";
    outs() << "  gpu (non-rt):    " << Gpu << "\n";
    outs() << "  runtime (stub):  " << Runtime << "\n";
    if (VlOff)
      outs() << "  vlSymsp offset:  " << *VlOff << " bytes (TBAA)\n";
    else
      outs() << "  vlSymsp offset:  (not detected)\n";
    if (StorageSize > 0)
      outs() << "  --storage-size:  " << StorageSize << " (reserved for kernel gen)\n";
    outs() << "  --sm:            " << Sm << "\n";
  } else {
    outs() << Eval->getName().str() << ' ' << Reach.size() << ' ' << Gpu << ' '
           << Runtime << '\n';
  }

  return 0;
}
