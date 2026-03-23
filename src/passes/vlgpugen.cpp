/**
 * vlgpugen — Verilator merged.ll → NVPTX GPU kernel generator.
 *
 * Replaces gen_vl_gpu_kernel.py (Phase 3 of C++ pass migration).
 *
 * Analysis layer  (always runs):
 *   - findEvalFunction, collectReachable, isRuntimeFunction  (mirrors Python)
 *   - detectVlSymsOffset via C++ regex on raw .ll text       (same as Python)
 *
 * Generation layer (activated by --out <path> --storage-size=N):
 *   - stub runtime functions and extern calls
 *   - remove host-only globals (vtable, typeinfo, annotations)
 *   - inject @fake_syms_buf and @vl_eval_batch_gpu kernel
 *   - retarget module to NVPTX and write output .ll
 *
 * Usage:
 *   vlgpugen <merged.ll>                               # analysis only
 *   vlgpugen <merged.ll> --analyze-phases              # Phase B: ico/nba reachability
 *   vlgpugen <merged.ll> --storage-size=N --out=...    # generation
 *
 * Build:
 *   make -C src/passes
 */

#include "llvm/ADT/DenseSet.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/GlobalAlias.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"
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

static cl::opt<std::string> InputFilename(cl::Positional, cl::desc("<merged.ll>"), cl::init(""));
static cl::opt<uint64_t> StorageSize("storage-size", cl::desc("sizeof(root struct) in bytes"), cl::init(0));
static cl::opt<std::string> OutFile("out", cl::desc("Output .ll (enables generation mode)"), cl::init(""));
static cl::opt<std::string> Sm("sm", cl::desc("PTX GPU arch label"), cl::init("sm_89"));
static cl::opt<bool> Quiet("q", cl::desc("Minimal output"), cl::init(false));
static cl::opt<bool> AnalyzePhases(
    "analyze-phases",
    cl::desc("Phase B: report ___ico_sequent / ___nba_* reachability from eval, then exit"),
    cl::init(false));
static cl::opt<bool> NoDeclRuntimeMerge(
    "no-decl-runtime-merge",
    cl::desc("Phase E: disable decl-callee expansion of runtime function set (default: merge on)"),
    cl::init(false));

static constexpr StringLiteral NVPTX_TRIPLE    = "nvptx64-nvidia-cuda";
static constexpr StringLiteral NVPTX_DATALAYOUT = "e-i64:64-i128:128-v16:16-v32:32-n16:32:64";

// ---------------------------------------------------------------------------
// Analysis: isRuntimeFunction — mirrors vl_runtime_filter.py
// ---------------------------------------------------------------------------

static void functionToString(const Function &F, std::string &Out) {
    raw_string_ostream OS(Out);
    F.print(OS);
}

static bool isForceInclude(StringRef Name) {
    return Name.contains("___ico_sequent") || Name.contains("___nba_comb");
}

static bool isRuntimeFunction(const Function &F, const std::string &BodyStr) {
    StringRef Name = F.getName();
    if (isForceInclude(Name)) return false;
    static const char *Prefixes[] = {
        "_ZN9Verilated",  "_ZNK9Verilated",
        "_ZN16VerilatedContext", "_ZNK16VerilatedContext",
        "_ZN14VerilatedModel",   "_ZNK14VerilatedModel",
        "_ZN9VlDeleter",  "_ZNSt", "_ZSt",
        "_Z13sc_time_stamp", "_Z15vl_time_stamp", "__cxa_", "_ZTHN",
    };
    for (const char *P : Prefixes)
        if (Name.starts_with(P)) return true;
    if (BodyStr.find("@_ZGVZ")           != std::string::npos) return true;
    if (BodyStr.find("VerilatedSyms")     != std::string::npos) return true;
    if (BodyStr.find("_gpu_cov_tb__Syms") != std::string::npos) return true;
    return false;
}

// ---------------------------------------------------------------------------
// Analysis: detectVlSymsOffset — same regex as detect_vlsyms_offset()
// C++ regex is more version-stable than LLVM TBAA metadata API.
// ---------------------------------------------------------------------------

static std::optional<int64_t> detectVlSymsOffset(StringRef FileText) {
    std::string Text = FileText.str();
    std::smatch M;
    std::regex AnyPtrRe(R"(^(!(\d+))\s*=\s*!\{!"any pointer")",
                        std::regex_constants::multiline);
    if (!std::regex_search(Text, M, AnyPtrRe)) return std::nullopt;
    const std::string AnyId = M.str(2);
    std::string RootPat = R"(^!\d+\s*=\s*!\{!"[^"]*_024root".*?!)"
                          + AnyId + R"(,\s*i64\s+(\d+))";
    std::regex RootRe(RootPat, std::regex_constants::multiline);
    if (std::regex_search(Text, M, RootRe))
        return std::stoll(M.str(1));
    return std::nullopt;
}

// ---------------------------------------------------------------------------
// Analysis: eval function + reachable BFS
// ---------------------------------------------------------------------------

static Function *findEvalFunction(Module &M) {
    for (auto &F : M) {
        if (F.isDeclaration()) continue;
        StringRef N = F.getName();
        if (N.contains("___024root___eval") && !N.contains("___eval_"))
            return &F;
    }
    for (auto &F : M) {
        if (F.isDeclaration()) continue;
        if (F.getName().contains("_eval") && F.getFunctionType()->getNumParams() >= 1)
            return &F;
    }
    return nullptr;
}

static bool hostLikeDecl(const Function *F) {
    if (!F || !F->isDeclaration())
        return false;
    StringRef N = F->getName();
    if (N.starts_with("llvm."))
        return false;
    static const char *Pfx[] = {
        "_ZN9Verilated",  "_ZNK9Verilated", "_ZN16VerilatedContext",
        "_ZNK16VerilatedContext", "_ZN14VerilatedModel", "_ZNK14VerilatedModel",
        "_ZN9VlDeleter",  "_ZNSt", "_ZSt", "__cxa_", "_Z13sc_time_stamp",
        "_Z15vl_time_stamp", "_ZTHN"};
    for (const char *P : Pfx)
        if (N.starts_with(P))
            return true;
    return false;
}

/// Phase E: any function in Reach that directly calls a host-like declare is treated as runtime
/// (conservative; complements body-string isRuntimeFunction).
static void mergeRuntimeViaDeclCalls(const DenseSet<Function *> &Reach,
                                     DenseSet<Function *> &RuntimeFuncs) {
    bool Changed = true;
    while (Changed) {
        Changed = false;
        for (Function *F : Reach) {
            if (RuntimeFuncs.count(F))
                continue;
            for (BasicBlock &BB : *F)
                for (Instruction &I : BB)
                    if (auto *CB = dyn_cast<CallBase>(&I))
                        if (auto *Callee = dyn_cast<Function>(
                                CB->getCalledOperand()->stripPointerCasts()))
                            if (Callee->isDeclaration() && hostLikeDecl(Callee)) {
                                RuntimeFuncs.insert(F);
                                Changed = true;
                                goto NextF;
                            }
        NextF:;
        }
    }
}

static void reportAnalyzePhases(Module &M, const DenseSet<Function *> &Reach) {
    outs() << "analyze-phases (reachable from _eval):\n";
    const char *Subs[] = {"___ico_sequent", "___nba_comb", "___nba_sequent"};
    for (const char *Sub : Subs) {
        bool Any = false;
        for (Function &F : M) {
            if (F.isDeclaration())
                continue;
            if (!F.getName().contains(Sub))
                continue;
            Any = true;
            outs() << "  @" << F.getName() << "  reachable=" << Reach.count(&F) << "\n";
        }
        if (!Any)
            outs() << "  (" << Sub << " — no definition in module)\n";
    }
}

static void collectReachable(Function *Root, DenseSet<Function *> &Out) {
    SmallVector<Function *, 64> Stack;
    Stack.push_back(Root);
    while (!Stack.empty()) {
        auto *F = Stack.pop_back_val();
        if (!Out.insert(F).second) continue;
        for (auto &BB : *F)
            for (auto &I : BB)
                if (auto *CB = dyn_cast<CallBase>(&I))
                    if (auto *Callee = dyn_cast<Function>(
                            CB->getCalledOperand()->stripPointerCasts()))
                        if (!Callee->isDeclaration())
                            Stack.push_back(Callee);
    }
}

// ---------------------------------------------------------------------------
// Generation: stub creation
// ---------------------------------------------------------------------------

static void stubFunction(Function &F) {
    F.deleteBody();
    F.setPersonalityFn(nullptr);
    auto *BB = BasicBlock::Create(F.getContext(), "entry", &F);
    IRBuilder<> B(BB);
    Type *Ret = F.getReturnType();
    if (Ret->isVoidTy())               B.CreateRetVoid();
    else if (Ret->isIntegerTy(1))      B.CreateRet(ConstantInt::getFalse(F.getContext()));
    else if (Ret->isIntegerTy())       B.CreateRet(ConstantInt::get(Ret, 0));
    else if (Ret->isPointerTy())       B.CreateRet(ConstantPointerNull::get(cast<PointerType>(Ret)));
    else if (Ret->isFloatingPointTy()) B.CreateRet(ConstantFP::get(Ret, 0.0));
    else                               B.CreateRet(UndefValue::get(Ret));
}

// ---------------------------------------------------------------------------
// Generation: @fake_syms_buf + @vl_eval_batch_gpu kernel wrapper
// ---------------------------------------------------------------------------

static GlobalVariable *injectFakeSymsBuf(Module &M) {
    auto *ArrTy = ArrayType::get(Type::getInt8Ty(M.getContext()), 4096);
    auto *GV = new GlobalVariable(M, ArrTy, false,
                                   GlobalValue::InternalLinkage,
                                   ConstantAggregateZero::get(ArrTy), "fake_syms_buf");
    GV->setAlignment(Align(64));
    return GV;
}

static void injectKernelWrapper(Module &M, Function *EvalFn, uint64_t Storage,
                                 std::optional<int64_t> VlSymsOff, GlobalVariable *FakeSymsBuf) {
    LLVMContext &Ctx = M.getContext();
    Type *I8Ty  = Type::getInt8Ty(Ctx);
    Type *I32Ty = Type::getInt32Ty(Ctx);
    Type *I64Ty = Type::getInt64Ty(Ctx);
    auto *PtrTy = PointerType::get(Ctx, 0);
    auto *IntrTy = FunctionType::get(I32Ty, {}, false);

    auto *TidX   = cast<Function>(M.getOrInsertFunction("llvm.nvvm.read.ptx.sreg.tid.x",   IntrTy).getCallee());
    auto *CtaidX = cast<Function>(M.getOrInsertFunction("llvm.nvvm.read.ptx.sreg.ctaid.x", IntrTy).getCallee());
    auto *NtidX  = cast<Function>(M.getOrInsertFunction("llvm.nvvm.read.ptx.sreg.ntid.x",  IntrTy).getCallee());

    auto *Kernel = Function::Create(
        FunctionType::get(Type::getVoidTy(Ctx), {PtrTy, I32Ty}, false),
        GlobalValue::ExternalLinkage, "vl_eval_batch_gpu", &M);
    Kernel->getArg(0)->setName("storage_base");
    Kernel->getArg(1)->setName("nstates");

    auto *EntryBB = BasicBlock::Create(Ctx, "entry", Kernel);
    auto *BodyBB  = BasicBlock::Create(Ctx, "body",  Kernel);
    auto *ExitBB  = BasicBlock::Create(Ctx, "exit",  Kernel);

    IRBuilder<> B(EntryBB);
    auto *Gid32 = B.CreateAdd(
        B.CreateMul(B.CreateCall(CtaidX, {}, "bid"),
                    B.CreateCall(NtidX,  {}, "bdim"), "gid_mul"),
        B.CreateCall(TidX, {}, "tid"), "gid32");
    B.CreateCondBr(B.CreateICmpULT(Gid32, Kernel->getArg(1), "in_range"), BodyBB, ExitBB);

    B.SetInsertPoint(BodyBB);
    auto *StatePtr = B.CreateGEP(I8Ty, Kernel->getArg(0),
        {B.CreateMul(B.CreateZExt(Gid32, I64Ty, "gid"),
                     ConstantInt::get(I64Ty, Storage), "offset")},
        "state_ptr", true);
    if (VlSymsOff && FakeSymsBuf)
        B.CreateAlignedStore(FakeSymsBuf,
            B.CreateGEP(I8Ty, StatePtr, {ConstantInt::get(I64Ty, *VlSymsOff)},
                        "vlsyms_gep", true),
            Align(8));
    B.CreateCall(EvalFn, {StatePtr});
    B.CreateBr(ExitBB);

    B.SetInsertPoint(ExitBB);
    B.CreateRetVoid();

    M.getOrInsertNamedMetadata("nvvm.annotations")->addOperand(
        MDNode::get(Ctx, {ValueAsMetadata::get(Kernel),
                          MDString::get(Ctx, "kernel"),
                          ConstantAsMetadata::get(ConstantInt::get(I32Ty, 1))}));
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main(int argc, char **argv) {
    InitLLVM X(argc, argv);
    cl::ParseCommandLineOptions(argc, argv,
        "vlgpugen — Verilator merged.ll → NVPTX GPU kernel generator\n");

    if (InputFilename.empty()) { errs() << "error: no input .ll file\n"; return 1; }

    auto BufOr = MemoryBuffer::getFile(InputFilename);
    if (!BufOr) { errs() << "error: " << BufOr.getError().message() << "\n"; return 1; }

    LLVMContext Ctx;
    SMDiagnostic Err;
    auto M = parseIRFile(InputFilename, Err, Ctx);
    if (!M) { Err.print(argv[0], errs()); return 1; }

    auto VlOff   = detectVlSymsOffset(BufOr.get()->getBuffer());
    auto *EvalFn = findEvalFunction(*M);
    if (!EvalFn) { errs() << "error: eval function not found\n"; return 1; }

    DenseSet<Function *> Reach;
    collectReachable(EvalFn, Reach);

    DenseSet<Function *> RuntimeFuncs;
    for (auto *F : Reach) {
        std::string Body;
        functionToString(*F, Body);
        if (isRuntimeFunction(*F, Body))
            RuntimeFuncs.insert(F);
    }
    if (!NoDeclRuntimeMerge)
        mergeRuntimeViaDeclCalls(Reach, RuntimeFuncs);

    if (AnalyzePhases) {
        reportAnalyzePhases(*M, Reach);
        return 0;
    }

    DenseSet<Function *> GPUFuncs;
    for (auto *F : Reach) {
        if (!RuntimeFuncs.count(F))
            GPUFuncs.insert(F);
    }

    if (!Quiet) {
        outs() << "eval:            @" << EvalFn->getName() << "\n";
        outs() << "reachable (raw): " << Reach.size() << "\n";
        outs() << "GPU functions:   " << GPUFuncs.size() << "\n";
        outs() << "runtime (stub):  " << RuntimeFuncs.size() << "\n";
        if (VlOff) outs() << "vlSymsp offset:  " << *VlOff << " bytes\n";
        else       outs() << "vlSymsp offset:  (not detected)\n";
    }

    if (OutFile.empty()) return 0;  // analysis-only mode

    // ── generation mode ───────────────────────────────────────────────────
    if (StorageSize == 0) { errs() << "error: --storage-size required with --out\n"; return 1; }

    // Remove GlobalAliases (ctor/dtor aliases become invalid after deleteBody)
    SmallVector<GlobalAlias *, 16> Aliases;
    for (auto &GA : M->aliases()) Aliases.push_back(&GA);
    for (auto *GA : Aliases) { GA->replaceAllUsesWith(GA->getAliasee()); GA->eraseFromParent(); }

    for (auto *F : RuntimeFuncs) stubFunction(*F);

    for (auto &F : *M)
        if (!F.isDeclaration() && !Reach.count(&F))
            F.deleteBody();

    // NVPTX rejects comdat on declarations
    for (auto &F  : *M)          if (F.isDeclaration())  F.setComdat(nullptr);
    for (auto &GV : M->globals()) if (GV.isDeclaration()) GV.setComdat(nullptr);

    // Stub extern non-llvm calls from GPU functions
    DenseSet<Function *> ExternCalls;
    for (auto *F : GPUFuncs)
        for (auto &BB : *F)
            for (auto &I : BB)
                if (auto *CB = dyn_cast<CallBase>(&I))
                    if (auto *Callee = CB->getCalledFunction())
                        if (Callee->isDeclaration() &&
                            !Callee->getName().starts_with("llvm.") &&
                            !RuntimeFuncs.count(Callee))
                            ExternCalls.insert(Callee);
    for (auto *F : ExternCalls) stubFunction(*F);
    if (!ExternCalls.empty() && !Quiet)
        outs() << "stubbed extern calls: " << ExternCalls.size() << "\n";

    // Remove host-only globals (@llvm.global.annotations keeps .24-suffix decls alive)
    SmallVector<GlobalVariable *, 32> HostGVs;
    for (auto &GV : M->globals()) {
        StringRef N = GV.getName();
        if (N == "llvm.global.annotations" ||
            N.starts_with("_ZTV") || N.starts_with("_ZTI") || N.starts_with("_ZTS"))
            HostGVs.push_back(&GV);
    }
    for (auto *GV : HostGVs) { GV->replaceAllUsesWith(PoisonValue::get(GV->getType())); GV->eraseFromParent(); }
    if (!HostGVs.empty() && !Quiet)
        outs() << "removed host globals: " << HostGVs.size() << "\n";

    auto *FakeSymsBuf = VlOff ? injectFakeSymsBuf(*M) : nullptr;

    M->setTargetTriple(NVPTX_TRIPLE);
    M->setDataLayout(NVPTX_DATALAYOUT);

    injectKernelWrapper(*M, EvalFn, StorageSize, VlOff, FakeSymsBuf);

    std::error_code EC;
    raw_fd_ostream OS(OutFile, EC);
    if (EC) { errs() << "error: " << EC.message() << "\n"; return 1; }
    M->print(OS, nullptr);
    outs() << "written: " << OutFile << "\n";
    return 0;
}
