#pragma once

#include "HYBRID_DEBUG_MAILBOX_MOCK.h"
#include "HYBRID_DEBUG_MAILBOX_FAULT_RUNTIME.h"

#include <stdint.h>

struct HybridDebugMailboxRuntimeRegBinding {
    uint32_t addr_space = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
    uint32_t reserved0 = 0;
    uint64_t reg_index = 0;
    void* target_opaquep = nullptr;
    uint32_t width_bits = 0;
    uint32_t reserved1 = 0;
};

struct HybridDebugMailboxRuntimeSession;
typedef int (*HybridDebugMailboxRuntimeRegDispatchHook)(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp);
struct HybridDebugMailboxRuntimeMemBinding {
    uint32_t addr_space = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
    uint32_t reserved0 = 0;
    uint64_t word_index = 0;
    void* target_opaquep = nullptr;
    uint32_t width_bits = 0;
    uint32_t reserved1 = 0;
};
typedef int (*HybridDebugMailboxRuntimeMemDispatchHook)(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp);

struct HybridDebugMailboxRuntimeSession {
    hybrid_debug_mailbox_mock_state_t state{};
    HybridDebugMailboxFaultDetail last_fault{};
    uint64_t total_epochs = 0;
    uint32_t csr_profile = HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0;
    hybrid_debug_mailbox_layout_t layout{};
    hybrid_debug_mailbox_command_t command_entries[32]{};
    hybrid_debug_mailbox_response_t response_entries[32]{};
    hybrid_debug_mailbox_event_t event_entries[32]{};
    HybridDebugMailboxRuntimeRegBinding reg_bindings[64]{};
    HybridDebugMailboxRuntimeMemBinding mem_bindings[128]{};
    uint32_t reg_binding_count = 0;
    uint32_t mem_binding_count = 0;
    uint32_t dispatch_busy = 0;
    HybridDebugMailboxRuntimeRegDispatchHook reg_dispatch_hookp = nullptr;
    HybridDebugMailboxRuntimeMemDispatchHook mem_dispatch_hookp = nullptr;
    void* reg_dispatch_contextp = nullptr;
    void* mem_dispatch_contextp = nullptr;
};

struct HybridDebugMailboxRunUntilEventArgs {
    uint64_t epoch_limit = 0;
    uint64_t external_stop_at = UINT64_MAX;
    uint64_t timeout_at = UINT64_MAX;
    uint64_t cycle_delta_per_epoch = 1;
    uint64_t pc_delta_per_epoch = 4;
};

struct HybridDebugMailboxEpochStepResult {
    uint64_t cycle_delta = 0;
    uint64_t pc_delta = 0;
    uint32_t stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
};

#include "HYBRID_DEBUG_MAILBOX_CSR_RUNTIME.h"

static inline void hybridDebugMailboxRuntimeSessionInit(HybridDebugMailboxRuntimeSession* sessionp,
                                                        uint64_t initialPc) {
    if (!sessionp) return;
    memset(sessionp, 0, sizeof(*sessionp));
    hybrid_debug_mailbox_mock_state_init(&sessionp->state, initialPc);
    hybridDebugMailboxFaultDetailClear(&sessionp->last_fault);
    sessionp->total_epochs = 0;
    hybrid_debug_mailbox_layout_init(&sessionp->layout, 32, 32, 32);
    sessionp->dispatch_busy = 0;
}

static inline void hybridDebugMailboxRuntimeSessionSeed(
    HybridDebugMailboxRuntimeSession* sessionp, uint64_t cycleCount, uint64_t pc,
    uint32_t stopReason, const hybrid_debug_mailbox_mock_state_t* seedStatep) {
    if (!sessionp) return;
    if (seedStatep) {
        sessionp->state = *seedStatep;
        sessionp->state.cycle_count = cycleCount;
        sessionp->state.pc = pc;
        sessionp->state.total_epochs = sessionp->total_epochs;
        sessionp->state.last_stop_reason = stopReason;
        hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);
    } else {
        hybrid_debug_mailbox_mock_state_seed(&sessionp->state, cycleCount, pc, stopReason);
        sessionp->state.total_epochs = sessionp->total_epochs;
        hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);
    }
    hybridDebugMailboxFaultDetailClear(&sessionp->last_fault);
}

static inline void hybridDebugMailboxRuntimeSessionRecordFault(
    HybridDebugMailboxRuntimeSession* sessionp, const HybridDebugMailboxFaultDetail& detail) {
    if (!sessionp) return;
    sessionp->last_fault = detail;
    sessionp->state.last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
    hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);
}

static inline void hybridDebugMailboxRuntimeSessionClearFault(
    HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return;
    hybridDebugMailboxFaultDetailClear(&sessionp->last_fault);
}

static inline void hybridDebugMailboxRuntimeSessionSetFault(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t kind, uint32_t stage, uint32_t code,
    uint32_t aux0, uint64_t value0, uint64_t value1) {
    if (!sessionp) return;
    const HybridDebugMailboxFaultDetail detail
        = hybridDebugMailboxFaultDetailMake(kind, stage, code, aux0, value0, value1);
    hybridDebugMailboxRuntimeSessionRecordFault(sessionp, detail);
}

static inline void hybridDebugMailboxRuntimeSessionSetFaultDetail(
    HybridDebugMailboxRuntimeSession* sessionp, const HybridDebugMailboxFaultDetail& detail) {
    if (!sessionp) return;
    hybridDebugMailboxRuntimeSessionRecordFault(sessionp, detail);
}

static inline void hybridDebugMailboxRuntimeSessionClearRegBindings(
    HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return;
    memset(sessionp->reg_bindings, 0, sizeof(sessionp->reg_bindings));
    sessionp->reg_binding_count = 0;
}

static inline void hybridDebugMailboxRuntimeSessionSetRegDispatchHook(
    HybridDebugMailboxRuntimeSession* sessionp, HybridDebugMailboxRuntimeRegDispatchHook hookp) {
    if (!sessionp) return;
    sessionp->reg_dispatch_hookp = hookp;
}

static inline void hybridDebugMailboxRuntimeSessionSetRegDispatchContext(
    HybridDebugMailboxRuntimeSession* sessionp, void* contextp) {
    if (!sessionp) return;
    sessionp->reg_dispatch_contextp = contextp;
}

static inline void hybridDebugMailboxRuntimeSessionClearMemBindings(
    HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return;
    memset(sessionp->mem_bindings, 0, sizeof(sessionp->mem_bindings));
    sessionp->mem_binding_count = 0;
}

static inline void hybridDebugMailboxRuntimeSessionSetMemDispatchHook(
    HybridDebugMailboxRuntimeSession* sessionp, HybridDebugMailboxRuntimeMemDispatchHook hookp) {
    if (!sessionp) return;
    sessionp->mem_dispatch_hookp = hookp;
}

static inline void hybridDebugMailboxRuntimeSessionSetMemDispatchContext(
    HybridDebugMailboxRuntimeSession* sessionp, void* contextp) {
    if (!sessionp) return;
    sessionp->mem_dispatch_contextp = contextp;
}

static inline HybridDebugMailboxRuntimeRegBinding* hybridDebugMailboxRuntimeSessionFindRegBinding(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t reg_index) {
    if (!sessionp) return nullptr;
    for (uint32_t i = 0; i < sessionp->reg_binding_count; ++i) {
        HybridDebugMailboxRuntimeRegBinding& binding = sessionp->reg_bindings[i];
        if (binding.addr_space == addr_space && binding.reg_index == reg_index) return &binding;
    }
    return nullptr;
}

static inline const HybridDebugMailboxRuntimeRegBinding*
hybridDebugMailboxRuntimeSessionFindRegBindingConst(
    const HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t reg_index) {
    return hybridDebugMailboxRuntimeSessionFindRegBinding(
        const_cast<HybridDebugMailboxRuntimeSession*>(sessionp), addr_space, reg_index);
}

static inline HybridDebugMailboxRuntimeMemBinding* hybridDebugMailboxRuntimeSessionFindMemBinding(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t word_index) {
    if (!sessionp) return nullptr;
    for (uint32_t i = 0; i < sessionp->mem_binding_count; ++i) {
        HybridDebugMailboxRuntimeMemBinding& binding = sessionp->mem_bindings[i];
        if (binding.addr_space == addr_space && binding.word_index == word_index) return &binding;
    }
    return nullptr;
}

static inline const HybridDebugMailboxRuntimeMemBinding*
hybridDebugMailboxRuntimeSessionFindMemBindingConst(
    const HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t word_index) {
    return hybridDebugMailboxRuntimeSessionFindMemBinding(
        const_cast<HybridDebugMailboxRuntimeSession*>(sessionp), addr_space, word_index);
}

static inline bool hybridDebugMailboxRuntimeSessionBindRegOpaque(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t reg_index,
    void* targetOpaquep, uint32_t width_bits) {
    if (!sessionp || !targetOpaquep || width_bits == 0 || width_bits > 64) return false;
    if (addr_space == HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG
        && reg_index != HYBRID_DEBUG_MAILBOX_DEBUG_REG_PC) {
        return false;
    }
    HybridDebugMailboxRuntimeRegBinding* bindingp
        = hybridDebugMailboxRuntimeSessionFindRegBinding(sessionp, addr_space, reg_index);
    if (!bindingp) {
        if (sessionp->reg_binding_count
            >= static_cast<uint32_t>(sizeof(sessionp->reg_bindings)
                                     / sizeof(sessionp->reg_bindings[0]))) {
            return false;
        }
        bindingp = &sessionp->reg_bindings[sessionp->reg_binding_count++];
    }
    bindingp->addr_space = addr_space;
    bindingp->reg_index = reg_index;
    bindingp->target_opaquep = targetOpaquep;
    bindingp->width_bits = width_bits;
    bindingp->reserved0 = 0;
    bindingp->reserved1 = 0;
    return true;
}

static inline bool hybridDebugMailboxRuntimeSessionReadBuiltinDebugReg(
    const HybridDebugMailboxRuntimeSession* sessionp, uint64_t reg_index, uint64_t* valuep) {
    if (!sessionp || !valuep) return false;
    switch (reg_index) {
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_PC:
        *valuep = sessionp->state.pc;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_STOP_REASON:
        *valuep = sessionp->state.last_stop_reason;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_TOTAL_EPOCHS:
        *valuep = sessionp->total_epochs;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_CYCLE_COUNT:
        *valuep = sessionp->state.cycle_count;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_KIND:
        *valuep = sessionp->last_fault.kind;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_STAGE:
        *valuep = sessionp->last_fault.stage;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_CODE:
        *valuep = sessionp->last_fault.code;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_AUX0:
        *valuep = sessionp->last_fault.aux0;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_VALUE0:
        *valuep = sessionp->last_fault.value0;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_VALUE1:
        *valuep = sessionp->last_fault.value1;
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_COMMANDS:
        *valuep = hybrid_debug_mailbox_ring_count(&sessionp->layout.command_ring);
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_RESPONSES:
        *valuep = hybrid_debug_mailbox_ring_count(&sessionp->layout.response_ring);
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_EVENTS:
        *valuep = hybrid_debug_mailbox_ring_count(&sessionp->layout.event_ring);
        return true;
    default:
        break;
    }
    return hybridDebugMailboxRuntimeSessionReadDiscoveryDebugReg(sessionp, reg_index, valuep);
}

static inline bool hybridDebugMailboxRuntimeSessionBindMemOpaque(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t addr_space, uint64_t word_index,
    void* targetOpaquep, uint32_t width_bits, uint32_t vltype, bool writable) {
    if (!sessionp || !targetOpaquep || width_bits == 0 || width_bits > 64) return false;
    HybridDebugMailboxRuntimeMemBinding* bindingp
        = hybridDebugMailboxRuntimeSessionFindMemBinding(sessionp, addr_space, word_index);
    if (!bindingp) {
        if (sessionp->mem_binding_count
            >= static_cast<uint32_t>(sizeof(sessionp->mem_bindings)
                                     / sizeof(sessionp->mem_bindings[0]))) {
            return false;
        }
        bindingp = &sessionp->mem_bindings[sessionp->mem_binding_count++];
    }
    bindingp->addr_space = addr_space;
    bindingp->word_index = word_index;
    bindingp->target_opaquep = targetOpaquep;
    bindingp->width_bits = width_bits;
    bindingp->reserved0 = vltype;
    bindingp->reserved1 = writable ? 1U : 0U;
    return true;
}

static inline void hybridDebugMailboxRuntimeSessionResetQueues(
    HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return;
    memset(sessionp->command_entries, 0, sizeof(sessionp->command_entries));
    memset(sessionp->response_entries, 0, sizeof(sessionp->response_entries));
    memset(sessionp->event_entries, 0, sizeof(sessionp->event_entries));
    hybrid_debug_mailbox_layout_init(&sessionp->layout, 32, 32, 32);
}

static inline bool hybridDebugMailboxRuntimeSessionPushCommand(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp) {
    if (!sessionp || !cmdp) return false;
    if (sessionp->dispatch_busy) return false;
    return hybrid_debug_mailbox_push_command(&sessionp->layout.command_ring,
                                             sessionp->command_entries, cmdp);
}

static inline bool hybridDebugMailboxRuntimeSessionPopResponse(
    HybridDebugMailboxRuntimeSession* sessionp, hybrid_debug_mailbox_response_t* rspp) {
    if (!sessionp || !rspp) return false;
    return hybrid_debug_mailbox_pop_response(&sessionp->layout.response_ring,
                                             sessionp->response_entries, rspp);
}

static inline bool hybridDebugMailboxRuntimeSessionPopEvent(
    HybridDebugMailboxRuntimeSession* sessionp, hybrid_debug_mailbox_event_t* eventp) {
    if (!sessionp || !eventp) return false;
    return hybrid_debug_mailbox_pop_event(&sessionp->layout.event_ring, sessionp->event_entries,
                                          eventp);
}

static inline uint32_t hybridDebugMailboxRuntimeSessionPendingCommands(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return 0;
    return hybrid_debug_mailbox_ring_count(&sessionp->layout.command_ring);
}

static inline uint32_t hybridDebugMailboxRuntimeSessionPendingResponses(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return 0;
    return hybrid_debug_mailbox_ring_count(&sessionp->layout.response_ring);
}

static inline uint32_t hybridDebugMailboxRuntimeSessionPendingEvents(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return 0;
    return hybrid_debug_mailbox_ring_count(&sessionp->layout.event_ring);
}

#include "HYBRID_DEBUG_MAILBOX_LOOP_RUNTIME.h"

struct HybridDebugMailboxMockStats {
    uint32_t enabled = 0;
    uint32_t bound_to_hybrid = 0;
    uint32_t commands_processed = 0;
    uint32_t response_count = 0;
    uint32_t event_count = 0;
    uint32_t epoch_done_event_count = 0;
    uint32_t stop_event_count = 0;
    uint32_t breakpoint_event_count = 0;
    uint32_t watchpoint_event_count = 0;
    uint32_t fault_event_count = 0;
    uint32_t last_status = HYBRID_DEBUG_MAILBOX_STATUS_OK;
    uint32_t last_event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    uint32_t last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    uint64_t last_cycle_count = 0;
    uint64_t last_pc = 0;
    uint32_t last_fault_kind = HYBRID_DEBUG_MAILBOX_FAULT_NONE;
    uint32_t last_fault_stage = HYBRID_DEBUG_MAILBOX_FAULT_STAGE_NONE;
    uint32_t last_fault_code = 0;
    uint32_t last_fault_aux0 = 0;
    uint64_t last_fault_value0 = 0;
    uint64_t last_fault_value1 = 0;
    uint64_t epoch_reps = 0;
    uint64_t effective_cycle_budget = 0;
};

static inline void hybridDebugMailboxMockStatsRecordFault(
    HybridDebugMailboxMockStats* statsp, const HybridDebugMailboxFaultDetail& detail,
    bool replaceStopEvent = true) {
    if (!statsp) return;
    statsp->last_status = HYBRID_DEBUG_MAILBOX_STATUS_FAULT;
    statsp->last_event_type = HYBRID_DEBUG_MAILBOX_EVENT_FAULT;
    statsp->last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
    statsp->last_fault_kind = detail.kind;
    statsp->last_fault_stage = detail.stage;
    statsp->last_fault_code = detail.code;
    statsp->last_fault_aux0 = detail.aux0;
    statsp->last_fault_value0 = detail.value0;
    statsp->last_fault_value1 = detail.value1;
    if (replaceStopEvent && statsp->stop_event_count > 0) {
        statsp->stop_event_count -= 1;
    }
    statsp->fault_event_count += 1;
}

struct HybridDebugMailboxEpochContext {
    hybrid_debug_mailbox_layout_t layout{};
    hybrid_debug_mailbox_command_t commands[8]{};
    hybrid_debug_mailbox_response_t responses[8]{};
    hybrid_debug_mailbox_event_t events[8]{};
    hybrid_debug_mailbox_mock_state_t state{};
    hybrid_debug_mailbox_command_t run_cmd{};
    hybrid_debug_mailbox_command_t get_stop_cmd{};
};

static inline bool beginHybridDebugMailboxEpoch(uint32_t runCycles, uint64_t seedCycleCount,
                                                uint64_t seedPc, uint32_t seedStopReason,
                                                const hybrid_debug_mailbox_mock_state_t* seedStatep,
                                                HybridDebugMailboxEpochContext* ctxp) {
    if (!ctxp) return false;
    HybridDebugMailboxEpochContext& ctx = *ctxp;
    memset(&ctx, 0, sizeof(ctx));
    hybrid_debug_mailbox_layout_init(&ctx.layout, 8, 8, 8);
    if (seedStatep) {
        ctx.state = *seedStatep;
        ctx.state.cycle_count = seedCycleCount;
        ctx.state.pc = seedPc;
        ctx.state.last_stop_reason = seedStopReason;
        hybrid_debug_mailbox_mock_refresh_arch_state(&ctx.state);
    } else {
        hybrid_debug_mailbox_mock_state_seed(&ctx.state, seedCycleCount, seedPc, seedStopReason);
    }

    ctx.run_cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT;
    ctx.run_cmd.flags = HYBRID_DEBUG_MAILBOX_FLAG_BLOCKING;
    ctx.run_cmd.request_id = 1;
    ctx.run_cmd.arg0 = runCycles;
    ctx.run_cmd.arg1 = seedStopReason;
    if (!hybrid_debug_mailbox_push_command(&ctx.layout.command_ring, ctx.commands, &ctx.run_cmd)) {
        return false;
    }

    ctx.get_stop_cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON;
    ctx.get_stop_cmd.request_id = 2;
    if (!hybrid_debug_mailbox_push_command(&ctx.layout.command_ring, ctx.commands,
                                           &ctx.get_stop_cmd)) {
        return false;
    }

    hybrid_debug_mailbox_command_t dispatchCmd{};
    if (!hybrid_debug_mailbox_pop_command(&ctx.layout.command_ring, ctx.commands, &dispatchCmd)) {
        return false;
    }
    if (dispatchCmd.opcode != HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT) return false;
    ctx.run_cmd = dispatchCmd;
    return true;
}

static inline bool finishHybridDebugMailboxEpoch(HybridDebugMailboxEpochContext* ctxp,
                                                 uint64_t actualCycleCount, uint64_t actualPc,
                                                 uint32_t eventType, uint32_t stopReason,
                                                 HybridDebugMailboxMockStats* statsp,
                                                 const HybridDebugMailboxFaultDetail* faultDetailp
                                                 = nullptr) {
    if (!ctxp || !statsp) return false;
    HybridDebugMailboxMockStats stats;
    stats.enabled = 1;
    stats.commands_processed = 1;
    HybridDebugMailboxEpochContext& ctx = *ctxp;
    ctx.state.cycle_count = actualCycleCount;
    ctx.state.pc = actualPc;
    ctx.state.last_stop_reason = stopReason;

    const hybrid_debug_mailbox_response_t runRsp
        = hybrid_debug_mailbox_mock_make_response(&ctx.run_cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    if (!hybrid_debug_mailbox_push_response(&ctx.layout.response_ring, ctx.responses, &runRsp)) {
        return false;
    }
    const hybrid_debug_mailbox_event_t stopEv = hybrid_debug_mailbox_mock_make_stop_event(
        &ctx.state, eventType, stopReason);
    hybrid_debug_mailbox_event_t eventWithDetail = stopEv;
    if (stopReason == HYBRID_DEBUG_MAILBOX_STOP_FAULT && faultDetailp) {
        hybridDebugMailboxFaultDetailPackEvent(*faultDetailp, &eventWithDetail);
    }
    if (!hybrid_debug_mailbox_push_event(&ctx.layout.event_ring, ctx.events, &eventWithDetail)) {
        return false;
    }

    hybrid_debug_mailbox_command_t getStopCmd{};
    if (!hybrid_debug_mailbox_pop_command(&ctx.layout.command_ring, ctx.commands, &getStopCmd)) {
        return false;
    }
    if (getStopCmd.opcode != HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON) return false;
    stats.commands_processed += 1;

    hybrid_debug_mailbox_response_t stopRsp
        = hybrid_debug_mailbox_mock_make_response(&getStopCmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    stopRsp.arg0 = stopReason;
    hybrid_debug_mailbox_u64_to_words(actualCycleCount, &stopRsp.arg1, &stopRsp.size_bytes);
    if (!hybrid_debug_mailbox_push_response(&ctx.layout.response_ring, ctx.responses, &stopRsp)) {
        return false;
    }

    hybrid_debug_mailbox_response_t rsp{};
    hybrid_debug_mailbox_response_t rsp2{};
    hybrid_debug_mailbox_event_t ev{};
    if (!hybrid_debug_mailbox_pop_response(&ctx.layout.response_ring, ctx.responses, &rsp)) {
        return false;
    }
    stats.response_count += 1;
    stats.last_status = rsp.status;
    if (!hybrid_debug_mailbox_pop_response(&ctx.layout.response_ring, ctx.responses, &rsp2)) {
        return false;
    }
    stats.response_count += 1;
    stats.last_status = rsp2.status;
    stats.last_stop_reason = rsp2.arg0;
    if (!hybrid_debug_mailbox_pop_event(&ctx.layout.event_ring, ctx.events, &ev)) return false;
    stats.event_count += 1;
    stats.last_event_type = ev.event_type;
    if (ev.event_type == HYBRID_DEBUG_MAILBOX_EVENT_EPOCH_DONE) {
        stats.epoch_done_event_count += 1;
    } else if (ev.event_type == HYBRID_DEBUG_MAILBOX_EVENT_BREAKPOINT) {
        stats.breakpoint_event_count += 1;
    } else if (ev.event_type == HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT) {
        stats.watchpoint_event_count += 1;
    } else if (ev.event_type == HYBRID_DEBUG_MAILBOX_EVENT_STOP) {
        stats.stop_event_count += 1;
    } else if (ev.event_type == HYBRID_DEBUG_MAILBOX_EVENT_FAULT) {
        stats.fault_event_count += 1;
    }
    stats.last_stop_reason = ev.stop_reason;
    stats.last_cycle_count
        = hybrid_debug_mailbox_u64_from_words(ev.cycle_count_lo, ev.cycle_count_hi);
    stats.last_pc = hybrid_debug_mailbox_u64_from_words(ev.pc_lo, ev.pc_hi);
    if (faultDetailp) {
        stats.last_fault_kind = faultDetailp->kind;
        stats.last_fault_stage = faultDetailp->stage;
        stats.last_fault_code = faultDetailp->code;
        stats.last_fault_aux0 = faultDetailp->aux0;
        stats.last_fault_value0 = faultDetailp->value0;
        stats.last_fault_value1 = faultDetailp->value1;
    }
    *statsp = stats;
    return true;
}

static inline bool runHybridDebugMailboxMock(uint32_t runCycles, uint64_t seedCycleCount,
                                             uint64_t seedPc, uint32_t seedStopReason,
                                             HybridDebugMailboxMockStats* statsp) {
    HybridDebugMailboxEpochContext ctx{};
    if (!beginHybridDebugMailboxEpoch(runCycles, seedCycleCount, seedPc, seedStopReason, nullptr,
                                      &ctx)) {
        return false;
    }
    return finishHybridDebugMailboxEpoch(
        &ctx, seedCycleCount + runCycles, seedPc + (4ull * static_cast<uint64_t>(runCycles)),
        HYBRID_DEBUG_MAILBOX_EVENT_STOP, seedStopReason, statsp);
}

static inline void bindHybridDebugMailboxMockStats(uint32_t runCycles, int reps,
                                                   HybridDebugMailboxMockStats* statsp) {
    if (!statsp) return;
    statsp->enabled = 1;
    statsp->bound_to_hybrid = 1;
    statsp->epoch_reps = reps > 0 ? static_cast<uint64_t>(reps) : 0;
    statsp->effective_cycle_budget = static_cast<uint64_t>(runCycles) * statsp->epoch_reps;
}

static inline void accumulateHybridDebugMailboxMockStats(
    HybridDebugMailboxMockStats* totalStatsp, const HybridDebugMailboxMockStats& epochStats) {
    if (!totalStatsp) return;
    totalStatsp->enabled = totalStatsp->enabled || epochStats.enabled;
    totalStatsp->bound_to_hybrid = totalStatsp->bound_to_hybrid || epochStats.bound_to_hybrid;
    totalStatsp->commands_processed += epochStats.commands_processed;
    totalStatsp->response_count += epochStats.response_count;
    totalStatsp->event_count += epochStats.event_count;
    totalStatsp->epoch_done_event_count += epochStats.epoch_done_event_count;
    totalStatsp->stop_event_count += epochStats.stop_event_count;
    totalStatsp->breakpoint_event_count += epochStats.breakpoint_event_count;
    totalStatsp->watchpoint_event_count += epochStats.watchpoint_event_count;
    totalStatsp->fault_event_count += epochStats.fault_event_count;
    totalStatsp->last_status = epochStats.last_status;
    totalStatsp->last_event_type = epochStats.last_event_type;
    totalStatsp->last_stop_reason = epochStats.last_stop_reason;
    totalStatsp->last_cycle_count = epochStats.last_cycle_count;
    totalStatsp->last_pc = epochStats.last_pc;
    totalStatsp->last_fault_kind = epochStats.last_fault_kind;
    totalStatsp->last_fault_stage = epochStats.last_fault_stage;
    totalStatsp->last_fault_code = epochStats.last_fault_code;
    totalStatsp->last_fault_aux0 = epochStats.last_fault_aux0;
    totalStatsp->last_fault_value0 = epochStats.last_fault_value0;
    totalStatsp->last_fault_value1 = epochStats.last_fault_value1;
}
