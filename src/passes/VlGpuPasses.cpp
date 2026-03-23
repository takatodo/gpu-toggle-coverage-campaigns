/**
 * VlGpuPasses.cpp
 *
 * LLVM opt pass plugin for Verilator → NVPTX GPU kernel generation.
 *
 * Passes:
 *   vl-strip-x86-attrs   FunctionPass  x86 固有属性 / comdat / personality を除去
 *   vl-patch-convergence FunctionPass  収束ループの無限ハング回避 CFG パッチ
 *
 * Usage:
 *   opt-18 --load-pass-plugin=VlGpuPasses.so \
 *          -passes="lowerinvoke,vl-strip-x86-attrs,vl-patch-convergence,default<O3>" \
 *          -S vl_batch_gpu.ll -o vl_batch_gpu_opt.ll
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
// clang++ -emit-llvm が付加する x86 固有の要素を NVPTX 向けに除去する。
//
//   - 関数属性 (#N)         → setAttributes(empty)
//   - comdat 参照           → setComdat(nullptr)
//   - personality 関数      → clearPersonalityFn()
//   - linkonce_odr リンケージ → internal に降格
//     (NVPTX では linkonce_odr がリンカ警告を出すため)

struct VlStripX86AttrsPass : public PassInfoMixin<VlStripX86AttrsPass> {
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
        F.setAttributes(AttributeList());
        F.setComdat(nullptr);
        if (F.hasPersonalityFn())
            F.setPersonalityFn(nullptr);
        if (F.getLinkage() == GlobalValue::LinkOnceODRLinkage)
            F.setLinkage(GlobalValue::InternalLinkage);
        return PreservedAnalyses::all();  // CFG/値を変更しないので解析保存
    }
};

// ─── VlPatchConvergencePass ───────────────────────────────────────────────────
//
// Verilator が --no-timing でコンパイルした際に生成される収束ループを
// GPU 上で無限ハングしないようにパッチする。
//
// Verilator の eval 関数は以下の構造を持つ:
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
//     call void @VL_FATAL_MT(...)   ; GPU 上では no-op stub
//     br label %body                 ; ← ここが問題: stub 後に body に戻り無限ループ
//
//   exit:
//     ret void
//
// パッチ内容:
//   1. fatal ブロックの br %body → br %exit  (loop abort)
//   2. icmp のしきい値 100 → 0               (1 回目で即 fatal → 2 iterations で脱出)

static BasicBlock *findLoopExit(BasicBlock *HeaderBB) {
    // HeaderBB に戻る条件分岐を探し、もう一方のターゲットを exit とみなす
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
        // icmp ugt i32 %N, 100 を収集
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
            // icmp を使う条件分岐を探す (br i1 %ovf, %fatal, %body)
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

            // fatal ブロックの無条件分岐を body → exit にリダイレクト
            auto *FatalTerm = FatalBB->getTerminator();
            if (auto *FatalBr = dyn_cast<BranchInst>(FatalTerm)) {
                if (!FatalBr->isConditional()) {
                    FatalBr->setSuccessor(0, ExitBB);
                    errs() << "[vl-patch-convergence] " << F.getName()
                           << ": fatal→exit redirected\n";
                    Changed = true;
                }
            }

            // しきい値 100 → 0 (1 回目の ico/act/nba 実行直後に脱出)
            Cmp->setOperand(1, ConstantInt::get(Cmp->getOperand(1)->getType(), 0));
            errs() << "[vl-patch-convergence] " << F.getName()
                   << ": threshold 100→0\n";
            Changed = true;
        }

        return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
    }
};

// ─── Plugin 登録 ─────────────────────────────────────────────────────────────

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
