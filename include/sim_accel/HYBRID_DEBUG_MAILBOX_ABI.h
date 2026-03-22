#pragma once

#include <string.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HYBRID_DEBUG_MAILBOX_ABI_VERSION 1u
#define HYBRID_DEBUG_MAILBOX_COMMAND_WORDS 16u
#define HYBRID_DEBUG_MAILBOX_RESPONSE_WORDS 12u
#define HYBRID_DEBUG_MAILBOX_EVENT_WORDS 12u

typedef enum hybrid_debug_mailbox_opcode_e {
    HYBRID_DEBUG_MAILBOX_OP_NOP = 0,
    HYBRID_DEBUG_MAILBOX_OP_READ_REG = 1,
    HYBRID_DEBUG_MAILBOX_OP_WRITE_REG = 2,
    HYBRID_DEBUG_MAILBOX_OP_READ_MEM = 3,
    HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM = 4,
    HYBRID_DEBUG_MAILBOX_OP_RUN_CYCLES = 5,
    HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT = 6,
    HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON = 7,
    HYBRID_DEBUG_MAILBOX_OP_SET_BREAKPOINT = 8,
    HYBRID_DEBUG_MAILBOX_OP_CLEAR_BREAKPOINT = 9,
    HYBRID_DEBUG_MAILBOX_OP_SET_WATCHPOINT = 10,
    HYBRID_DEBUG_MAILBOX_OP_CLEAR_WATCHPOINT = 11,
    HYBRID_DEBUG_MAILBOX_OP_SNAPSHOT_SAVE = 12,
    HYBRID_DEBUG_MAILBOX_OP_SNAPSHOT_RESTORE = 13
} hybrid_debug_mailbox_opcode_t;

typedef enum hybrid_debug_mailbox_status_e {
    HYBRID_DEBUG_MAILBOX_STATUS_OK = 0,
    HYBRID_DEBUG_MAILBOX_STATUS_BAD_OPCODE = 1,
    HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR = 2,
    HYBRID_DEBUG_MAILBOX_STATUS_DENIED = 3,
    HYBRID_DEBUG_MAILBOX_STATUS_FAULT = 4,
    HYBRID_DEBUG_MAILBOX_STATUS_TIMEOUT = 5,
    HYBRID_DEBUG_MAILBOX_STATUS_BUSY = 6,
    HYBRID_DEBUG_MAILBOX_STATUS_UNSUPPORTED = 7
} hybrid_debug_mailbox_status_t;

typedef enum hybrid_debug_mailbox_event_type_e {
    HYBRID_DEBUG_MAILBOX_EVENT_NONE = 0,
    HYBRID_DEBUG_MAILBOX_EVENT_STOP = 1,
    HYBRID_DEBUG_MAILBOX_EVENT_BREAKPOINT = 2,
    HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT = 3,
    HYBRID_DEBUG_MAILBOX_EVENT_FAULT = 4,
    HYBRID_DEBUG_MAILBOX_EVENT_EPOCH_DONE = 5
} hybrid_debug_mailbox_event_type_t;

typedef enum hybrid_debug_mailbox_stop_reason_e {
    HYBRID_DEBUG_MAILBOX_STOP_NONE = 0,
    HYBRID_DEBUG_MAILBOX_STOP_RUN_CYCLES_DONE = 1,
    HYBRID_DEBUG_MAILBOX_STOP_EPOCH_LIMIT = 2,
    HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT = 3,
    HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT = 4,
    HYBRID_DEBUG_MAILBOX_STOP_EXTERNAL_STOP = 5,
    HYBRID_DEBUG_MAILBOX_STOP_FAULT = 6,
    HYBRID_DEBUG_MAILBOX_STOP_TIMEOUT = 7
} hybrid_debug_mailbox_stop_reason_t;

typedef enum hybrid_debug_mailbox_addr_space_e {
    HYBRID_DEBUG_MAILBOX_ADDR_NONE = 0,
    HYBRID_DEBUG_MAILBOX_ADDR_REG_GPR = 1,
    HYBRID_DEBUG_MAILBOX_ADDR_REG_CSR = 2,
    HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG = 3,
    HYBRID_DEBUG_MAILBOX_ADDR_MEM_PHYS = 16,
    HYBRID_DEBUG_MAILBOX_ADDR_MEM_DCCM = 17,
    HYBRID_DEBUG_MAILBOX_ADDR_MEM_ICCM = 18,
    HYBRID_DEBUG_MAILBOX_ADDR_MEM_MMIO = 19
} hybrid_debug_mailbox_addr_space_t;

typedef enum hybrid_debug_mailbox_debug_reg_e {
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_PC = 0,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_STOP_REASON = 1,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_TOTAL_EPOCHS = 2,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_CYCLE_COUNT = 3,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_KIND = 4,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_STAGE = 5,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_CODE = 6,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_AUX0 = 7,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_VALUE0 = 8,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_LAST_FAULT_VALUE1 = 9,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_COMMANDS = 10,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_RESPONSES = 11,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_PENDING_EVENTS = 12,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_KNOWN_CSR_COUNT = 13,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_BOUND_CSR_COUNT = 14,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_CSR_PROFILE = 15,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_KNOWN_CSR_INDEX_BASE = 32,
    HYBRID_DEBUG_MAILBOX_DEBUG_REG_BOUND_CSR_INDEX_BASE = 64
} hybrid_debug_mailbox_debug_reg_t;

typedef enum hybrid_debug_mailbox_flag_e {
    HYBRID_DEBUG_MAILBOX_FLAG_NONE = 0,
    HYBRID_DEBUG_MAILBOX_FLAG_BATCH_CONT = 1u << 0,
    HYBRID_DEBUG_MAILBOX_FLAG_BLOCKING = 1u << 1,
    HYBRID_DEBUG_MAILBOX_FLAG_PRIVILEGED = 1u << 2,
    HYBRID_DEBUG_MAILBOX_FLAG_SLOW_PATH = 1u << 3
} hybrid_debug_mailbox_flag_t;

typedef struct hybrid_debug_mailbox_command_s {
    uint32_t opcode;
    uint32_t flags;
    uint32_t request_id;
    uint32_t addr_space;
    uint32_t addr_lo;
    uint32_t addr_hi;
    uint32_t size_bytes;
    uint32_t arg0;
    uint32_t arg1;
    uint32_t payload_offset_bytes;
    uint32_t payload_size_bytes;
    uint32_t reserved0;
    uint32_t reserved1;
    uint32_t reserved2;
    uint32_t reserved3;
    uint32_t reserved4;
} hybrid_debug_mailbox_command_t;

typedef struct hybrid_debug_mailbox_response_s {
    uint32_t request_id;
    uint32_t status;
    uint32_t size_bytes;
    uint32_t arg0;
    uint32_t arg1;
    uint32_t payload_offset_bytes;
    uint32_t payload_size_bytes;
    uint32_t reserved0;
    uint32_t reserved1;
    uint32_t reserved2;
    uint32_t reserved3;
    uint32_t reserved4;
} hybrid_debug_mailbox_response_t;

typedef struct hybrid_debug_mailbox_event_s {
    uint32_t event_type;
    uint32_t stop_reason;
    uint32_t cycle_count_lo;
    uint32_t cycle_count_hi;
    uint32_t pc_lo;
    uint32_t pc_hi;
    uint32_t arg0;
    uint32_t arg1;
    uint32_t reserved0;
    uint32_t reserved1;
    uint32_t reserved2;
    uint32_t reserved3;
} hybrid_debug_mailbox_event_t;

typedef struct hybrid_debug_mailbox_ring_s {
    uint32_t abi_version;
    uint32_t entry_words;
    uint32_t capacity_entries;
    uint32_t producer_index;
    uint32_t consumer_index;
    uint32_t overflow_count;
    uint32_t reserved0;
    uint32_t reserved1;
} hybrid_debug_mailbox_ring_t;

typedef struct hybrid_debug_mailbox_layout_s {
    hybrid_debug_mailbox_ring_t command_ring;
    hybrid_debug_mailbox_ring_t response_ring;
    hybrid_debug_mailbox_ring_t event_ring;
} hybrid_debug_mailbox_layout_t;

enum {
    HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0 = 0,
    HYBRID_DEBUG_MAILBOX_CSR_PROFILE_VEER_EL2_V0 = 1,
};

static inline const char* hybrid_debug_mailbox_csr_name(uint32_t csr_index) {
    switch (csr_index) {
    case 0x300u: return "mstatus";
    case 0x301u: return "misa";
    case 0x304u: return "mie";
    case 0x305u: return "mtvec";
    case 0x340u: return "mscratch";
    case 0x341u: return "mepc";
    case 0x342u: return "mcause";
    case 0x343u: return "mtval";
    case 0x344u: return "mip";
    case 0x7B0u: return "dcsr";
    case 0x7B1u: return "dpc";
    case 0x7B2u: return "dscratch0";
    case 0x7B3u: return "dscratch1";
    default: return "";
    }
}

static inline uint32_t hybrid_debug_mailbox_known_csr_count(void) { return 13u; }

static inline uint32_t hybrid_debug_mailbox_known_csr_index_at(uint32_t ordinal) {
    switch (ordinal) {
    case 0u: return 0x300u;
    case 1u: return 0x301u;
    case 2u: return 0x304u;
    case 3u: return 0x305u;
    case 4u: return 0x340u;
    case 5u: return 0x341u;
    case 6u: return 0x342u;
    case 7u: return 0x343u;
    case 8u: return 0x344u;
    case 9u: return 0x7B0u;
    case 10u: return 0x7B1u;
    case 11u: return 0x7B2u;
    case 12u: return 0x7B3u;
    default: return 0u;
    }
}

static inline int hybrid_debug_mailbox_csr_index_from_name(const char* name,
                                                           uint32_t* csr_indexp) {
    if (!name || !csr_indexp) return 0;
    struct HybridDebugMailboxKnownCsr {
        const char* name;
        uint32_t index;
    };
    static const HybridDebugMailboxKnownCsr kKnownCsrs[] = {
        {"mstatus", 0x300u},   {"misa", 0x301u},      {"mie", 0x304u},
        {"mtvec", 0x305u},     {"mscratch", 0x340u},  {"mepc", 0x341u},
        {"mcause", 0x342u},    {"mtval", 0x343u},     {"mip", 0x344u},
        {"dcsr", 0x7B0u},      {"dpc", 0x7B1u},       {"dscratch0", 0x7B2u},
        {"dscratch1", 0x7B3u},
    };
    for (uint32_t i = 0; i < sizeof(kKnownCsrs) / sizeof(kKnownCsrs[0]); ++i) {
        if (strcmp(name, kKnownCsrs[i].name) == 0) {
            *csr_indexp = kKnownCsrs[i].index;
            return 1;
        }
    }
    return 0;
}

static inline const char* hybrid_debug_mailbox_csr_profile_name(uint32_t profile) {
    switch (profile) {
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0: return "base_v0";
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_VEER_EL2_V0: return "veer_el2_v0";
    default: return "";
    }
}

static inline int hybrid_debug_mailbox_csr_profile_valid(uint32_t profile) {
    switch (profile) {
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0:
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_VEER_EL2_V0: return 1;
    default: return 0;
    }
}

static inline uint32_t hybrid_debug_mailbox_csr_profile_count(uint32_t profile) {
    switch (profile) {
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0:
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_VEER_EL2_V0:
        return hybrid_debug_mailbox_known_csr_count();
    default: return 0u;
    }
}

static inline uint32_t hybrid_debug_mailbox_csr_profile_index_at(uint32_t profile,
                                                                 uint32_t ordinal) {
    switch (profile) {
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0:
    case HYBRID_DEBUG_MAILBOX_CSR_PROFILE_VEER_EL2_V0:
        return hybrid_debug_mailbox_known_csr_index_at(ordinal);
    default:
        return 0u;
    }
}

#ifdef __cplusplus
}
#endif
