#pragma once

#include <stdint.h>
#include <string.h>

enum HybridDebugMailboxFaultKind : uint32_t {
    HYBRID_DEBUG_MAILBOX_FAULT_NONE = 0,
    HYBRID_DEBUG_MAILBOX_FAULT_KERNEL_LAUNCH_FAILURE = 1,
    HYBRID_DEBUG_MAILBOX_FAULT_COMMUNICATION_FAILURE = 2,
    HYBRID_DEBUG_MAILBOX_FAULT_CPU_GPU_MISMATCH = 3,
};

enum HybridDebugMailboxFaultStage : uint32_t {
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_NONE = 0,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_H2D = 1,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_LAUNCH = 2,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_SYNC = 3,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H = 4,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_COMPARE = 5,
    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME = 6,
};

struct HybridDebugMailboxFaultDetail {
    uint32_t kind = HYBRID_DEBUG_MAILBOX_FAULT_NONE;
    uint32_t stage = HYBRID_DEBUG_MAILBOX_FAULT_STAGE_NONE;
    uint32_t code = 0;
    uint32_t aux0 = 0;
    uint64_t value0 = 0;
    uint64_t value1 = 0;
};

static inline const char* hybridDebugMailboxFaultKindName(uint32_t kind) {
    switch (kind) {
    case HYBRID_DEBUG_MAILBOX_FAULT_NONE: return "NONE";
    case HYBRID_DEBUG_MAILBOX_FAULT_KERNEL_LAUNCH_FAILURE: return "KERNEL_LAUNCH_FAILURE";
    case HYBRID_DEBUG_MAILBOX_FAULT_COMMUNICATION_FAILURE: return "COMMUNICATION_FAILURE";
    case HYBRID_DEBUG_MAILBOX_FAULT_CPU_GPU_MISMATCH: return "CPU_GPU_MISMATCH";
    default: return "UNKNOWN";
    }
}

static inline const char* hybridDebugMailboxFaultStageName(uint32_t stage) {
    switch (stage) {
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_NONE: return "NONE";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_H2D: return "H2D";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_LAUNCH: return "LAUNCH";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_SYNC: return "SYNC";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H: return "D2H";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_COMPARE: return "COMPARE";
    case HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME: return "RUNTIME";
    default: return "UNKNOWN";
    }
}

static inline void hybridDebugMailboxFaultDetailClear(HybridDebugMailboxFaultDetail* detailp) {
    if (!detailp) return;
    memset(detailp, 0, sizeof(*detailp));
    detailp->kind = HYBRID_DEBUG_MAILBOX_FAULT_NONE;
    detailp->stage = HYBRID_DEBUG_MAILBOX_FAULT_STAGE_NONE;
}

static inline HybridDebugMailboxFaultDetail hybridDebugMailboxFaultDetailMake(
    uint32_t kind, uint32_t stage, uint32_t code, uint32_t aux0, uint64_t value0,
    uint64_t value1) {
    HybridDebugMailboxFaultDetail detail{};
    detail.kind = kind;
    detail.stage = stage;
    detail.code = code;
    detail.aux0 = aux0;
    detail.value0 = value0;
    detail.value1 = value1;
    return detail;
}

static inline HybridDebugMailboxFaultDetail hybridDebugMailboxCommunicationFaultDetail(
    uint32_t stage, uint32_t code, uint32_t aux0, uint64_t value0, uint64_t value1) {
    return hybridDebugMailboxFaultDetailMake(HYBRID_DEBUG_MAILBOX_FAULT_COMMUNICATION_FAILURE,
                                             stage, code, aux0, value0, value1);
}

static inline HybridDebugMailboxFaultDetail hybridDebugMailboxCpuGpuMismatchFaultDetail(
    uint32_t code, uint32_t aux0, uint64_t value0, uint64_t value1) {
    return hybridDebugMailboxFaultDetailMake(HYBRID_DEBUG_MAILBOX_FAULT_CPU_GPU_MISMATCH,
                                             HYBRID_DEBUG_MAILBOX_FAULT_STAGE_COMPARE, code,
                                             aux0, value0, value1);
}

static inline HybridDebugMailboxFaultDetail hybridDebugMailboxKernelLaunchFaultDetail(
    uint32_t code, uint32_t aux0, uint64_t value0, uint64_t value1) {
    return hybridDebugMailboxFaultDetailMake(HYBRID_DEBUG_MAILBOX_FAULT_KERNEL_LAUNCH_FAILURE,
                                             HYBRID_DEBUG_MAILBOX_FAULT_STAGE_LAUNCH, code, aux0,
                                             value0, value1);
}

static inline HybridDebugMailboxFaultDetail hybridDebugMailboxFaultDetailFromStageLabel(
    const char* stageLabel, uint32_t code, uint32_t aux0, uint64_t value0, uint64_t value1) {
    if (stageLabel && strstr(stageLabel, "launch") != nullptr) {
        return hybridDebugMailboxKernelLaunchFaultDetail(code, aux0, value0, value1);
    }
    if (stageLabel && strstr(stageLabel, "D2H") != nullptr) {
        return hybridDebugMailboxCommunicationFaultDetail(HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H,
                                                          code, aux0, value0, value1);
    }
    if (stageLabel && strstr(stageLabel, "H2D") != nullptr) {
        return hybridDebugMailboxCommunicationFaultDetail(HYBRID_DEBUG_MAILBOX_FAULT_STAGE_H2D,
                                                          code, aux0, value0, value1);
    }
    if (stageLabel && (strstr(stageLabel, "sync") != nullptr
                       || strstr(stageLabel, "elapsed") != nullptr)) {
        return hybridDebugMailboxCommunicationFaultDetail(HYBRID_DEBUG_MAILBOX_FAULT_STAGE_SYNC,
                                                          code, aux0, value0, value1);
    }
    return hybridDebugMailboxCommunicationFaultDetail(HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME,
                                                      code, aux0, value0, value1);
}
