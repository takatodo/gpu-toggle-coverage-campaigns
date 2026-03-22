#pragma once

#include "HYBRID_DEBUG_MAILBOX_RUNTIME.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hybrid_debug_mailbox_mock_state_s {
    uint64_t cycle_count;
    uint64_t pc;
    uint64_t total_epochs;
    uint32_t last_stop_reason;
    uint32_t breakpoint_enabled;
    uint64_t breakpoint_pc;
    uint32_t watchpoint_enabled;
    uint32_t watchpoint_addr_space;
    uint64_t watchpoint_word_index;
    uint32_t reserved0;
    uint64_t gpr[32];
    uint64_t csr[32];
    uint64_t debug_regs[32];
    uint64_t mem_phys[64];
    uint64_t mem_dccm[64];
    uint64_t mem_iccm[64];
    uint64_t mem_mmio[64];
} hybrid_debug_mailbox_mock_state_t;

typedef enum hybrid_debug_mailbox_mock_debug_reg_e {
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_PC = HYBRID_DEBUG_MAILBOX_DEBUG_REG_PC,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_STOP_REASON
        = HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_STOP_REASON,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_TOTAL_EPOCHS = HYBRID_DEBUG_MAILBOX_DEBUG_REG_TOTAL_EPOCHS,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_CYCLE_COUNT = HYBRID_DEBUG_MAILBOX_DEBUG_REG_CYCLE_COUNT,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_KIND
        = HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_KIND,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_STAGE
        = HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_STAGE,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_CODE
        = HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_CODE,
    HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_AUX0
        = HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_AUX0
} hybrid_debug_mailbox_mock_debug_reg_t;

typedef enum hybrid_debug_mailbox_mock_csr_reg_e {
    HYBRID_DEBUG_MAILBOX_REG_CSR_MSTATUS = 0x300,
    HYBRID_DEBUG_MAILBOX_REG_CSR_MTVEC = 0x305,
    HYBRID_DEBUG_MAILBOX_REG_CSR_MSCRATCH = 0x340,
    HYBRID_DEBUG_MAILBOX_REG_CSR_MEPC = 0x341,
    HYBRID_DEBUG_MAILBOX_REG_CSR_MCAUSE = 0x342,
    HYBRID_DEBUG_MAILBOX_REG_CSR_DCSR = 0x7b0,
    HYBRID_DEBUG_MAILBOX_REG_CSR_DPC = 0x7b1
} hybrid_debug_mailbox_mock_csr_reg_t;

typedef enum hybrid_debug_mailbox_mock_csr_slot_e {
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MSTATUS = 0,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MTVEC = 1,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MSCRATCH = 2,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MEPC = 3,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MCAUSE = 4,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_DCSR = 5,
    HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_DPC = 6
} hybrid_debug_mailbox_mock_csr_slot_t;

static inline void hybrid_debug_mailbox_mock_refresh_arch_state(
    hybrid_debug_mailbox_mock_state_t* state) {
    if (!state) return;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_PC] = state->pc;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_STOP_REASON]
        = state->last_stop_reason;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_TOTAL_EPOCHS] = state->total_epochs;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_CYCLE_COUNT] = state->cycle_count;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_KIND] = 0;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_STAGE] = 0;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_CODE] = 0;
    state->debug_regs[HYBRID_DEBUG_MAILBOX_REG_DEBUG_LAST_FAULT_AUX0] = 0;
}

static inline void hybrid_debug_mailbox_mock_set_reg_selector(
    hybrid_debug_mailbox_command_t* cmd, uint32_t addr_space, uint64_t reg_index) {
    if (!cmd) return;
    cmd->addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(reg_index, &cmd->addr_lo, &cmd->addr_hi);
}

static inline void hybrid_debug_mailbox_mock_select_debug_reg(
    hybrid_debug_mailbox_command_t* cmd, uint32_t debug_reg) {
    hybrid_debug_mailbox_mock_set_reg_selector(cmd, HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG,
                                               (uint64_t)debug_reg);
}

static inline void hybrid_debug_mailbox_mock_select_gpr(
    hybrid_debug_mailbox_command_t* cmd, uint32_t gpr_index) {
    hybrid_debug_mailbox_mock_set_reg_selector(cmd, HYBRID_DEBUG_MAILBOX_ADDR_REG_GPR,
                                               (uint64_t)gpr_index);
}

static inline void hybrid_debug_mailbox_mock_select_csr(
    hybrid_debug_mailbox_command_t* cmd, uint32_t csr_index) {
    hybrid_debug_mailbox_mock_set_reg_selector(cmd, HYBRID_DEBUG_MAILBOX_ADDR_REG_CSR,
                                               (uint64_t)csr_index);
}

static inline void hybrid_debug_mailbox_mock_select_mem_word(
    hybrid_debug_mailbox_command_t* cmd, uint32_t addr_space, uint64_t word_index) {
    hybrid_debug_mailbox_mock_set_reg_selector(cmd, addr_space, word_index);
}

static inline uint64_t* hybrid_debug_mailbox_mock_select_csr_storage(
    hybrid_debug_mailbox_mock_state_t* state, uint64_t csr_index) {
    if (!state || (csr_index >> 12) != 0) return NULL;
    switch ((uint32_t)csr_index) {
    case HYBRID_DEBUG_MAILBOX_REG_CSR_MSTATUS:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MSTATUS];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_MTVEC:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MTVEC];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_MSCRATCH:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MSCRATCH];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_MEPC:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MEPC];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_MCAUSE:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_MCAUSE];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_DCSR:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_DCSR];
    case HYBRID_DEBUG_MAILBOX_REG_CSR_DPC:
        return &state->csr[HYBRID_DEBUG_MAILBOX_MOCK_CSR_SLOT_DPC];
    default: return NULL;
    }
}

static inline void hybrid_debug_mailbox_mock_state_init(
    hybrid_debug_mailbox_mock_state_t* state, uint64_t initial_pc) {
    if (!state) return;
    state->cycle_count = 0;
    state->pc = initial_pc;
    state->total_epochs = 0;
    state->last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    state->breakpoint_enabled = 0;
    state->breakpoint_pc = 0;
    state->watchpoint_enabled = 0;
    state->watchpoint_addr_space = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
    state->watchpoint_word_index = 0;
    state->reserved0 = 0;
    memset(state->gpr, 0, sizeof(state->gpr));
    memset(state->csr, 0, sizeof(state->csr));
    memset(state->debug_regs, 0, sizeof(state->debug_regs));
    memset(state->mem_phys, 0, sizeof(state->mem_phys));
    memset(state->mem_dccm, 0, sizeof(state->mem_dccm));
    memset(state->mem_iccm, 0, sizeof(state->mem_iccm));
    memset(state->mem_mmio, 0, sizeof(state->mem_mmio));
    hybrid_debug_mailbox_mock_refresh_arch_state(state);
}

static inline void hybrid_debug_mailbox_mock_state_seed(
    hybrid_debug_mailbox_mock_state_t* state, uint64_t cycle_count, uint64_t pc,
    uint32_t stop_reason) {
    if (!state) return;
    state->cycle_count = cycle_count;
    state->pc = pc;
    state->total_epochs = 0;
    state->last_stop_reason = stop_reason;
    state->watchpoint_enabled = 0;
    state->watchpoint_addr_space = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
    state->watchpoint_word_index = 0;
    state->reserved0 = 0;
    hybrid_debug_mailbox_mock_refresh_arch_state(state);
}

static inline void hybrid_debug_mailbox_mock_set_breakpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint64_t breakpoint_pc) {
    if (!state) return;
    state->breakpoint_enabled = 1;
    state->breakpoint_pc = breakpoint_pc;
}

static inline void hybrid_debug_mailbox_mock_clear_breakpoint(
    hybrid_debug_mailbox_mock_state_t* state) {
    if (!state) return;
    state->breakpoint_enabled = 0;
    state->breakpoint_pc = 0;
}

static inline void hybrid_debug_mailbox_mock_set_watchpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t addr_space, uint64_t word_index) {
    if (!state) return;
    state->watchpoint_enabled = 1;
    state->watchpoint_addr_space = addr_space;
    state->watchpoint_word_index = word_index;
}

static inline void hybrid_debug_mailbox_mock_clear_watchpoint(
    hybrid_debug_mailbox_mock_state_t* state) {
    if (!state) return;
    state->watchpoint_enabled = 0;
    state->watchpoint_addr_space = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
    state->watchpoint_word_index = 0;
}

static inline int hybrid_debug_mailbox_mock_is_watchpoint_hit(
    const hybrid_debug_mailbox_mock_state_t* state, uint32_t addr_space, uint64_t word_index) {
    return state && state->watchpoint_enabled && state->watchpoint_addr_space == addr_space
           && state->watchpoint_word_index == word_index;
}

static inline uint64_t* hybrid_debug_mailbox_mock_select_mem(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t addr_space, uint64_t index) {
    if (!state || index >= 64) return NULL;
    switch (addr_space) {
    case HYBRID_DEBUG_MAILBOX_ADDR_MEM_PHYS: return &state->mem_phys[index];
    case HYBRID_DEBUG_MAILBOX_ADDR_MEM_DCCM: return &state->mem_dccm[index];
    case HYBRID_DEBUG_MAILBOX_ADDR_MEM_ICCM: return &state->mem_iccm[index];
    case HYBRID_DEBUG_MAILBOX_ADDR_MEM_MMIO: return &state->mem_mmio[index];
    default: return NULL;
    }
}

static inline uint64_t* hybrid_debug_mailbox_mock_select_reg(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t addr_space, uint64_t index) {
    if (!state) return NULL;
    switch (addr_space) {
    case HYBRID_DEBUG_MAILBOX_ADDR_REG_GPR:
        return index < 32 ? &state->gpr[index] : NULL;
    case HYBRID_DEBUG_MAILBOX_ADDR_REG_CSR:
        return hybrid_debug_mailbox_mock_select_csr_storage(state, index);
    case HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG:
        if (index == HYBRID_DEBUG_MAILBOX_REG_DEBUG_PC) return &state->pc;
        return index < 32 ? &state->debug_regs[index] : NULL;
    default: return NULL;
    }
}

static inline int hybrid_debug_mailbox_mock_read_reg(hybrid_debug_mailbox_mock_state_t* state,
                                                     uint32_t addr_space, uint64_t index,
                                                     uint64_t* valuep) {
    uint64_t* regp = hybrid_debug_mailbox_mock_select_reg(state, addr_space, index);
    if (!regp || !valuep) return 0;
    *valuep = *regp;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_write_reg(hybrid_debug_mailbox_mock_state_t* state,
                                                      uint32_t addr_space, uint64_t index,
                                                      uint64_t value) {
    uint64_t* regp = hybrid_debug_mailbox_mock_select_reg(state, addr_space, index);
    if (!regp) return 0;
    *regp = value;
    hybrid_debug_mailbox_mock_refresh_arch_state(state);
    return 1;
}

static inline int hybrid_debug_mailbox_mock_read_mem(hybrid_debug_mailbox_mock_state_t* state,
                                                     uint32_t addr_space, uint64_t index,
                                                     uint64_t* valuep) {
    uint64_t* wordp = hybrid_debug_mailbox_mock_select_mem(state, addr_space, index);
    if (!wordp || !valuep) return 0;
    *valuep = *wordp;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_write_mem(hybrid_debug_mailbox_mock_state_t* state,
                                                      uint32_t addr_space, uint64_t index,
                                                      uint64_t value) {
    uint64_t* wordp = hybrid_debug_mailbox_mock_select_mem(state, addr_space, index);
    if (!wordp) return 0;
    *wordp = value;
    return 1;
}

static inline hybrid_debug_mailbox_response_t hybrid_debug_mailbox_mock_make_response(
    const hybrid_debug_mailbox_command_t* cmd, uint32_t status) {
    hybrid_debug_mailbox_response_t rsp;
    memset(&rsp, 0, sizeof(rsp));
    if (cmd) rsp.request_id = cmd->request_id;
    rsp.status = status;
    return rsp;
}

static inline hybrid_debug_mailbox_event_t hybrid_debug_mailbox_mock_make_stop_event(
    const hybrid_debug_mailbox_mock_state_t* state, uint32_t event_type, uint32_t stop_reason) {
    hybrid_debug_mailbox_event_t ev;
    memset(&ev, 0, sizeof(ev));
    ev.event_type = event_type;
    ev.stop_reason = stop_reason;
    if (state) {
        hybrid_debug_mailbox_u64_to_words(state->cycle_count, &ev.cycle_count_lo,
                                          &ev.cycle_count_hi);
        hybrid_debug_mailbox_u64_to_words(state->pc, &ev.pc_lo, &ev.pc_hi);
    }
    return ev;
}

static inline int hybrid_debug_mailbox_mock_execute_immediate(
    const hybrid_debug_mailbox_command_t* cmd, hybrid_debug_mailbox_mock_state_t* state,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp) {
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;

    if (!cmd || !state || !rspp || !eventp || !haveEventp) return -1;
    rsp = hybrid_debug_mailbox_mock_make_response(cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    memset(&ev, 0, sizeof(ev));
    *haveEventp = 0;
    hybrid_debug_mailbox_mock_refresh_arch_state(state);

    switch (cmd->opcode) {
    case HYBRID_DEBUG_MAILBOX_OP_READ_REG: {
        const uint64_t regIndex = hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi);
        uint64_t value = 0;
        if (!hybrid_debug_mailbox_mock_read_reg(state, cmd->addr_space, regIndex, &value)) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
            break;
        }
        hybrid_debug_mailbox_u64_to_words(value, &rsp.arg0, &rsp.arg1);
        rsp.size_bytes = 8;
        break;
    }
    case HYBRID_DEBUG_MAILBOX_OP_WRITE_REG: {
        const uint64_t regIndex = hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi);
        if (!hybrid_debug_mailbox_mock_write_reg(
                state, cmd->addr_space, regIndex,
                hybrid_debug_mailbox_u64_from_words(cmd->arg0, cmd->arg1))) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
            break;
        }
        break;
    }
    case HYBRID_DEBUG_MAILBOX_OP_READ_MEM: {
        const uint64_t wordIndex = hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi);
        uint64_t value = 0;
        if (!hybrid_debug_mailbox_mock_read_mem(state, cmd->addr_space, wordIndex, &value)) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
            break;
        }
        hybrid_debug_mailbox_u64_to_words(value, &rsp.arg0, &rsp.arg1);
        rsp.size_bytes = 8;
        if (hybrid_debug_mailbox_mock_is_watchpoint_hit(state, cmd->addr_space, wordIndex)) {
            state->last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT;
            ev = hybrid_debug_mailbox_mock_make_stop_event(
                state, HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT, state->last_stop_reason);
            *haveEventp = 1;
        }
        break;
    }
    case HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM: {
        const uint64_t wordIndex = hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi);
        if (!hybrid_debug_mailbox_mock_write_mem(
                state, cmd->addr_space, wordIndex,
                hybrid_debug_mailbox_u64_from_words(cmd->arg0, cmd->arg1))) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
            break;
        }
        if (hybrid_debug_mailbox_mock_is_watchpoint_hit(state, cmd->addr_space, wordIndex)) {
            state->last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT;
            ev = hybrid_debug_mailbox_mock_make_stop_event(
                state, HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT, state->last_stop_reason);
            *haveEventp = 1;
        }
        break;
    }
    case HYBRID_DEBUG_MAILBOX_OP_SET_BREAKPOINT:
        hybrid_debug_mailbox_mock_set_breakpoint(
            state, hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi));
        break;
    case HYBRID_DEBUG_MAILBOX_OP_CLEAR_BREAKPOINT:
        hybrid_debug_mailbox_mock_clear_breakpoint(state);
        break;
    case HYBRID_DEBUG_MAILBOX_OP_SET_WATCHPOINT:
        hybrid_debug_mailbox_mock_set_watchpoint(
            state, cmd->addr_space, hybrid_debug_mailbox_u64_from_words(cmd->addr_lo, cmd->addr_hi));
        break;
    case HYBRID_DEBUG_MAILBOX_OP_CLEAR_WATCHPOINT:
        hybrid_debug_mailbox_mock_clear_watchpoint(state);
        break;
    case HYBRID_DEBUG_MAILBOX_OP_RUN_CYCLES:
        state->cycle_count += (uint64_t)cmd->arg0;
        state->pc += 4ull * (uint64_t)cmd->arg0;
        state->total_epochs += (uint64_t)cmd->arg0;
        hybrid_debug_mailbox_mock_refresh_arch_state(state);
        state->last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_RUN_CYCLES_DONE;
        ev = hybrid_debug_mailbox_mock_make_stop_event(
            state, HYBRID_DEBUG_MAILBOX_EVENT_STOP,
            HYBRID_DEBUG_MAILBOX_STOP_RUN_CYCLES_DONE);
        *haveEventp = 1;
        break;
    case HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT: {
        uint64_t runCycles = (uint64_t)cmd->arg0;
        uint64_t stopCycles = runCycles;
        uint32_t eventType = HYBRID_DEBUG_MAILBOX_EVENT_STOP;
        uint32_t stopReason = cmd->arg1 ? cmd->arg1
                                        : (uint32_t)HYBRID_DEBUG_MAILBOX_STOP_EPOCH_LIMIT;
        const uint64_t startPc = state->pc;
        if (state->breakpoint_enabled) {
            const uint64_t breakpointPc = state->breakpoint_pc;
            if (breakpointPc >= startPc) {
                const uint64_t deltaBytes = breakpointPc - startPc;
                if ((deltaBytes % 4ull) == 0ull) {
                    const uint64_t deltaCycles = deltaBytes / 4ull;
                    if (deltaCycles <= runCycles) {
                        stopCycles = deltaCycles;
                        stopReason = HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT;
                        eventType = HYBRID_DEBUG_MAILBOX_EVENT_BREAKPOINT;
                    }
                }
            }
        }
        state->cycle_count += stopCycles;
        state->total_epochs += stopCycles;
        state->pc = startPc + (4ull * stopCycles);
        hybrid_debug_mailbox_mock_refresh_arch_state(state);
        state->last_stop_reason = stopReason;
        ev = hybrid_debug_mailbox_mock_make_stop_event(
            state, eventType, state->last_stop_reason);
        *haveEventp = 1;
        break;
    }
    case HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON:
        rsp.arg0 = state->last_stop_reason;
        hybrid_debug_mailbox_u64_to_words(state->cycle_count, &rsp.arg1, &rsp.size_bytes);
        break;
    default: rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_UNSUPPORTED; break;
    }

    *rspp = rsp;
    *eventp = ev;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_read_reg(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t reg_index, uint64_t* valuep, uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state || !valuep) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_READ_REG;
    cmd.addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(reg_index, &cmd.addr_lo, &cmd.addr_hi);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    *valuep = hybrid_debug_mailbox_u64_from_words(rsp.arg0, rsp.arg1);
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_write_reg(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t reg_index, uint64_t value, uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_WRITE_REG;
    cmd.addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(reg_index, &cmd.addr_lo, &cmd.addr_hi);
    hybrid_debug_mailbox_u64_to_words(value, &cmd.arg0, &cmd.arg1);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_read_mem_ex(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t word_index, uint64_t* valuep, uint32_t* statusp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state || !valuep) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_READ_MEM;
    cmd.addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(word_index, &cmd.addr_lo, &cmd.addr_hi);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (eventp) *eventp = ev;
    if (haveEventp) *haveEventp = haveEvent;
    if (statusp) *statusp = rsp.status;
    if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    *valuep = hybrid_debug_mailbox_u64_from_words(rsp.arg0, rsp.arg1);
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_read_mem(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t word_index, uint64_t* valuep, uint32_t* statusp) {
    return hybrid_debug_mailbox_mock_execute_read_mem_ex(state, request_id, addr_space, word_index,
                                                         valuep, statusp, NULL, NULL);
}

static inline int hybrid_debug_mailbox_mock_execute_set_breakpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint64_t breakpoint_pc,
    uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_SET_BREAKPOINT;
    cmd.addr_space = HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG;
    hybrid_debug_mailbox_u64_to_words(breakpoint_pc, &cmd.addr_lo, &cmd.addr_hi);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_clear_breakpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_CLEAR_BREAKPOINT;
    cmd.addr_space = HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG;
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_write_mem_ex(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t word_index, uint64_t value, uint32_t* statusp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM;
    cmd.addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(word_index, &cmd.addr_lo, &cmd.addr_hi);
    hybrid_debug_mailbox_u64_to_words(value, &cmd.arg0, &cmd.arg1);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (eventp) *eventp = ev;
    if (haveEventp) *haveEventp = haveEvent;
    if (statusp) *statusp = rsp.status;
    if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_write_mem(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t word_index, uint64_t value, uint32_t* statusp) {
    return hybrid_debug_mailbox_mock_execute_write_mem_ex(state, request_id, addr_space, word_index,
                                                          value, statusp, NULL, NULL);
}

static inline int hybrid_debug_mailbox_mock_execute_set_watchpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t addr_space,
    uint64_t word_index, uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_SET_WATCHPOINT;
    cmd.addr_space = addr_space;
    hybrid_debug_mailbox_u64_to_words(word_index, &cmd.addr_lo, &cmd.addr_hi);
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_execute_clear_watchpoint(
    hybrid_debug_mailbox_mock_state_t* state, uint32_t request_id, uint32_t* statusp) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    memset(&rsp, 0, sizeof(rsp));
    memset(&ev, 0, sizeof(ev));
    cmd.request_id = request_id;
    cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_CLEAR_WATCHPOINT;
    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (statusp) *statusp = rsp.status;
    if (haveEvent || rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_mock_process_one(
    hybrid_debug_mailbox_layout_t* layout, hybrid_debug_mailbox_command_t* command_entries,
    hybrid_debug_mailbox_response_t* response_entries, hybrid_debug_mailbox_event_t* event_entries,
    hybrid_debug_mailbox_mock_state_t* state) {
    hybrid_debug_mailbox_command_t cmd;
    hybrid_debug_mailbox_response_t rsp;
    hybrid_debug_mailbox_event_t ev;
    int haveEvent = 0;

    if (!layout || !command_entries || !response_entries || !event_entries || !state) return -1;
    memset(&cmd, 0, sizeof(cmd));
    if (!hybrid_debug_mailbox_pop_command(&layout->command_ring, command_entries, &cmd)) return 0;

    if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, state, &rsp, &ev, &haveEvent) < 0) {
        return -1;
    }
    if (haveEvent && !hybrid_debug_mailbox_push_event(&layout->event_ring, event_entries, &ev)) {
        rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BUSY;
    }
    if (!hybrid_debug_mailbox_push_response(&layout->response_ring, response_entries, &rsp)) {
        return -1;
    }
    return 1;
}

static inline uint32_t hybrid_debug_mailbox_mock_process_all(
    hybrid_debug_mailbox_layout_t* layout, hybrid_debug_mailbox_command_t* command_entries,
    hybrid_debug_mailbox_response_t* response_entries, hybrid_debug_mailbox_event_t* event_entries,
    hybrid_debug_mailbox_mock_state_t* state, uint32_t max_commands) {
    uint32_t processed = 0;
    while (processed < max_commands) {
        const int rc = hybrid_debug_mailbox_mock_process_one(
            layout, command_entries, response_entries, event_entries, state);
        if (rc <= 0) break;
        processed += 1;
    }
    return processed;
}

#ifdef __cplusplus
}
#endif
