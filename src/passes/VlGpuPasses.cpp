/**
 * VlGpuPasses.cpp
 *
 * LLVM NewPM pass plugin for the stock-Verilator → NVPTX path (see README “Pipeline layout”).
 *
 * Passes (registered names for -passes=...):
 *   vl-strip-x86-attrs    FunctionPass  strip x86-only attrs, comdat, personality; demote linkonce_odr
 *   vl-patch-convergence  FunctionPass  break infinite convergence loops after VL_FATAL_MT stubs
 *
 * EH lowering is **not** implemented here: use LLVM’s built-in `lowerinvoke` before these passes
 * (see build_vl_gpu.py: lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence).
 *
 * Upstream IR: **vlgpugen** (`--out`) emits `vl_batch_gpu.ll` (Phase 3). This plugin then lowers EH,
 * strips x86-only metadata, and patches convergence loops before `opt -O3` / `llc` / `ptxas`.
 * Legacy Python `gen_vl_gpu_kernel.py` remains for parity checks — see README.
 *
 * Usage:
 *   opt-18 --load-pass-plugin=./VlGpuPasses.so \
 *          -passes="lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence" \
 *          -S vl_batch_gpu.ll -o vl_batch_gpu_patched.ll
 *
 * Build:
 *   make -C src/passes
 */

#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

// ─── VlStripX86AttrsPass ──────────────────────────────────────────────────────
//
// Remove x86-oriented metadata from clang++ -emit-llvm output before NVPTX.
//
//   - function attributes (#N)     → setAttributes(empty)
//   - comdat                     → setComdat(nullptr)
//   - personality                → clearPersonalityFn()
//   - linkonce_odr linkage       → internal (NVPTX linkers warn on linkonce_odr)

struct VlStripX86AttrsPass : public PassInfoMixin<VlStripX86AttrsPass> {
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
        F.setAttributes(AttributeList());
        F.setComdat(nullptr);
        if (F.hasPersonalityFn())
            F.setPersonalityFn(nullptr);
        if (F.getLinkage() == GlobalValue::LinkOnceODRLinkage)
            F.setLinkage(GlobalValue::InternalLinkage);
        return PreservedAnalyses::all();  // no CFG/value change
    }
};

// ─── VlPatchConvergencePass ───────────────────────────────────────────────────
//
// Patch Verilator’s convergence loop (seen with --no-timing TB) so it cannot spin forever
// on GPU after VL_FATAL_MT becomes a no-op stub.
//
// Typical eval shape:
//
//   header:
//     %iter1 = add i32 %iter, 1
//     %ovf   = icmp ugt i32 %iter1, 100
//     br i1 %ovf, label %fatal, label %body
//
//   body:
//     %again = call i1 @eval_phase__ico(...)
//     br i1 %again, label %header, label %exit
//
//   fatal:
//     call void @VL_FATAL_MT(...)   ; stubbed to empty body on GPU
//     br label %body                 ; problem: loops forever after stub
//
//   exit:
//     ret void
//
// Patches:
//   1. fatal block: unconditional br to %body → br to %exit
//   2. icmp threshold 100 → 0 (fatal after first body iteration; ≤2 iterations to exit)

static BasicBlock *findLoopExit(BasicBlock *HeaderBB) {
    // Find a conditional branch that targets HeaderBB; the other successor is treated as exit.
    Function *F = HeaderBB->getParent();
    for (auto &BB : *F) {
        auto *Br = dyn_cast<BranchInst>(BB.getTerminator());
        if (!Br || !Br->isConditional())
            continue;
        if (Br->getSuccessor(0) == HeaderBB)
            return Br->getSuccessor(1);
        if (Br->getSuccessor(1) == HeaderBB)
            return Br->getSuccessor(0);
    }
    return nullptr;
}

struct VlPatchConvergencePass : public PassInfoMixin<VlPatchConvergencePass> {
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
        // Collect icmp ugt i32 %N, 100
        SmallVector<ICmpInst *, 4> Candidates;
        for (auto &BB : F)
            for (auto &I : BB)
                if (auto *Cmp = dyn_cast<ICmpInst>(&I))
                    if (Cmp->getPredicate() == ICmpInst::ICMP_UGT)
                        if (Cmp->getOperand(0)->getType()->isIntegerTy(32))
                            if (auto *C = dyn_cast<ConstantInt>(Cmp->getOperand(1)))
                                if (C->getZExtValue() == 100)
                                    Candidates.push_back(Cmp);

        if (Candidates.empty())
            return PreservedAnalyses::all();

        bool Changed = false;
        for (auto *Cmp : Candidates) {
            // Find the conditional br driven by this icmp (br i1 %ovf, %fatal, %body)
            BranchInst *GuardBr = nullptr;
            for (auto *U : Cmp->users())
                if (auto *Br = dyn_cast<BranchInst>(U))
                    if (Br->isConditional()) { GuardBr = Br; break; }
            if (!GuardBr)
                continue;

            BasicBlock *HeaderBB = Cmp->getParent();
            BasicBlock *FatalBB  = GuardBr->getSuccessor(0);  // true  → fatal
            BasicBlock *BodyBB   = GuardBr->getSuccessor(1);  // false → body
            (void)BodyBB;

            BasicBlock *ExitBB = findLoopExit(HeaderBB);
            if (!ExitBB) {
                errs() << "[vl-patch-convergence] SKIP: exit not found in "
                       << F.getName() << "\n";
                continue;
            }

            // Redirect fatal block’s unconditional branch from %body to %exit
            auto *FatalTerm = FatalBB->getTerminator();
            if (auto *FatalBr = dyn_cast<BranchInst>(FatalTerm)) {
                if (!FatalBr->isConditional()) {
                    FatalBr->setSuccessor(0, ExitBB);
                    errs() << "[vl-patch-convergence] " << F.getName()
                           << ": fatal→exit redirected\n";
                    Changed = true;
                }
            }

            // Threshold 100 → 0 (exit soon after first ico/act/nba pass)
            Cmp->setOperand(1, ConstantInt::get(Cmp->getOperand(1)->getType(), 0));
            errs() << "[vl-patch-convergence] " << F.getName()
                   << ": threshold 100→0\n";
            Changed = true;
        }

        return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
    }
};

// ─── Plugin registration ────────────────────────────────────────────────────

static PassPluginLibraryInfo getVlGpuPassesPluginInfo() {
    return {LLVM_PLUGIN_API_VERSION, "VlGpuPasses", LLVM_VERSION_STRING,
        [](PassBuilder &PB) {
            PB.registerPipelineParsingCallback(
                [](StringRef Name, FunctionPassManager &FPM,
                   ArrayRef<PassBuilder::PipelineElement>) -> bool {
                    if (Name == "vl-strip-x86-attrs") {
                        FPM.addPass(VlStripX86AttrsPass());
                        return true;
                    }
                    if (Name == "vl-patch-convergence") {
                        FPM.addPass(VlPatchConvergencePass());
                        return true;
                    }
                    return false;
                });
        }};
}

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo llvmGetPassPluginInfo() {
    return getVlGpuPassesPluginInfo();
}
