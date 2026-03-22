#pragma once

#include "HYBRID_DEBUG_MAILBOX_ABI.h"

#include <stddef.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

static inline uint64_t hybrid_debug_mailbox_u64_from_words(uint32_t lo, uint32_t hi) {
    return (((uint64_t)hi) << 32) | (uint64_t)lo;
}

static inline void hybrid_debug_mailbox_u64_to_words(uint64_t value, uint32_t* lo,
                                                     uint32_t* hi) {
    if (lo) *lo = (uint32_t)(value & 0xffffffffu);
    if (hi) *hi = (uint32_t)(value >> 32);
}

static inline void hybrid_debug_mailbox_ring_init(hybrid_debug_mailbox_ring_t* ring,
                                                  uint32_t entry_words,
                                                  uint32_t capacity_entries) {
    if (!ring) return;
    ring->abi_version = HYBRID_DEBUG_MAILBOX_ABI_VERSION;
    ring->entry_words = entry_words;
    ring->capacity_entries = capacity_entries;
    ring->producer_index = 0;
    ring->consumer_index = 0;
    ring->overflow_count = 0;
    ring->reserved0 = 0;
    ring->reserved1 = 0;
}

static inline void hybrid_debug_mailbox_layout_init(hybrid_debug_mailbox_layout_t* layout,
                                                    uint32_t command_capacity,
                                                    uint32_t response_capacity,
                                                    uint32_t event_capacity) {
    if (!layout) return;
    hybrid_debug_mailbox_ring_init(&layout->command_ring, HYBRID_DEBUG_MAILBOX_COMMAND_WORDS,
                                   command_capacity);
    hybrid_debug_mailbox_ring_init(&layout->response_ring, HYBRID_DEBUG_MAILBOX_RESPONSE_WORDS,
                                   response_capacity);
    hybrid_debug_mailbox_ring_init(&layout->event_ring, HYBRID_DEBUG_MAILBOX_EVENT_WORDS,
                                   event_capacity);
}

static inline uint32_t hybrid_debug_mailbox_ring_count(const hybrid_debug_mailbox_ring_t* ring) {
    if (!ring || !ring->capacity_entries) return 0;
    return (ring->producer_index + ring->capacity_entries - ring->consumer_index)
           % ring->capacity_entries;
}

static inline uint32_t hybrid_debug_mailbox_ring_space(const hybrid_debug_mailbox_ring_t* ring) {
    if (!ring || ring->capacity_entries <= 1) return 0;
    return (ring->capacity_entries - 1) - hybrid_debug_mailbox_ring_count(ring);
}

static inline int hybrid_debug_mailbox_ring_empty(const hybrid_debug_mailbox_ring_t* ring) {
    return hybrid_debug_mailbox_ring_count(ring) == 0;
}

static inline int hybrid_debug_mailbox_ring_full(const hybrid_debug_mailbox_ring_t* ring) {
    return hybrid_debug_mailbox_ring_space(ring) == 0;
}

static inline int hybrid_debug_mailbox_ring_validate(const hybrid_debug_mailbox_ring_t* ring,
                                                     uint32_t expected_entry_words) {
    if (!ring) return 0;
    if (ring->abi_version != HYBRID_DEBUG_MAILBOX_ABI_VERSION) return 0;
    if (ring->entry_words != expected_entry_words) return 0;
    if (ring->capacity_entries <= 1) return 0;
    if (ring->producer_index >= ring->capacity_entries) return 0;
    if (ring->consumer_index >= ring->capacity_entries) return 0;
    return 1;
}

static inline int hybrid_debug_mailbox_ring_push_bytes(hybrid_debug_mailbox_ring_t* ring,
                                                       void* entries, const void* value,
                                                       size_t entry_size_bytes) {
    uint8_t* const base = (uint8_t*)entries;
    if (!ring || !base || !value) return 0;
    if (!hybrid_debug_mailbox_ring_validate(
            ring, (uint32_t)((entry_size_bytes + sizeof(uint32_t) - 1)
                             / sizeof(uint32_t)))) {
        return 0;
    }
    if (hybrid_debug_mailbox_ring_full(ring)) {
        ring->overflow_count += 1;
        return 0;
    }
    memcpy(base + (((size_t)ring->producer_index) * entry_size_bytes), value, entry_size_bytes);
    ring->producer_index = (ring->producer_index + 1) % ring->capacity_entries;
    return 1;
}

static inline int hybrid_debug_mailbox_ring_pop_bytes(hybrid_debug_mailbox_ring_t* ring,
                                                      const void* entries, void* value,
                                                      size_t entry_size_bytes) {
    const uint8_t* const base = (const uint8_t*)entries;
    if (!ring || !base || !value) return 0;
    if (!hybrid_debug_mailbox_ring_validate(
            ring, (uint32_t)((entry_size_bytes + sizeof(uint32_t) - 1)
                             / sizeof(uint32_t)))) {
        return 0;
    }
    if (hybrid_debug_mailbox_ring_empty(ring)) return 0;
    memcpy(value, base + (((size_t)ring->consumer_index) * entry_size_bytes),
           entry_size_bytes);
    ring->consumer_index = (ring->consumer_index + 1) % ring->capacity_entries;
    return 1;
}

static inline int hybrid_debug_mailbox_push_command(hybrid_debug_mailbox_ring_t* ring,
                                                    hybrid_debug_mailbox_command_t* entries,
                                                    const hybrid_debug_mailbox_command_t* value) {
    return hybrid_debug_mailbox_ring_push_bytes(ring, entries, value, sizeof(*value));
}

static inline int hybrid_debug_mailbox_pop_command(hybrid_debug_mailbox_ring_t* ring,
                                                   const hybrid_debug_mailbox_command_t* entries,
                                                   hybrid_debug_mailbox_command_t* value) {
    return hybrid_debug_mailbox_ring_pop_bytes(ring, entries, value, sizeof(*value));
}

static inline int hybrid_debug_mailbox_push_response(hybrid_debug_mailbox_ring_t* ring,
                                                     hybrid_debug_mailbox_response_t* entries,
                                                     const hybrid_debug_mailbox_response_t* value) {
    return hybrid_debug_mailbox_ring_push_bytes(ring, entries, value, sizeof(*value));
}

static inline int hybrid_debug_mailbox_pop_response(hybrid_debug_mailbox_ring_t* ring,
                                                    const hybrid_debug_mailbox_response_t* entries,
                                                    hybrid_debug_mailbox_response_t* value) {
    return hybrid_debug_mailbox_ring_pop_bytes(ring, entries, value, sizeof(*value));
}

static inline int hybrid_debug_mailbox_push_event(hybrid_debug_mailbox_ring_t* ring,
                                                  hybrid_debug_mailbox_event_t* entries,
                                                  const hybrid_debug_mailbox_event_t* value) {
    return hybrid_debug_mailbox_ring_push_bytes(ring, entries, value, sizeof(*value));
}

static inline int hybrid_debug_mailbox_pop_event(hybrid_debug_mailbox_ring_t* ring,
                                                 const hybrid_debug_mailbox_event_t* entries,
                                                 hybrid_debug_mailbox_event_t* value) {
    return hybrid_debug_mailbox_ring_pop_bytes(ring, entries, value, sizeof(*value));
}

static inline const char* hybrid_debug_mailbox_opcode_name(uint32_t opcode) {
    switch (opcode) {
    case HYBRID_DEBUG_MAILBOX_OP_NOP: return "NOP";
    case HYBRID_DEBUG_MAILBOX_OP_READ_REG: return "READ_REG";
    case HYBRID_DEBUG_MAILBOX_OP_WRITE_REG: return "WRITE_REG";
    case HYBRID_DEBUG_MAILBOX_OP_READ_MEM: return "READ_MEM";
    case HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM: return "WRITE_MEM";
    case HYBRID_DEBUG_MAILBOX_OP_RUN_CYCLES: return "RUN_CYCLES";
    case HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT: return "RUN_UNTIL_EVENT";
    case HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON: return "GET_STOP_REASON";
    case HYBRID_DEBUG_MAILBOX_OP_SET_BREAKPOINT: return "SET_BREAKPOINT";
    case HYBRID_DEBUG_MAILBOX_OP_CLEAR_BREAKPOINT: return "CLEAR_BREAKPOINT";
    case HYBRID_DEBUG_MAILBOX_OP_SET_WATCHPOINT: return "SET_WATCHPOINT";
    case HYBRID_DEBUG_MAILBOX_OP_CLEAR_WATCHPOINT: return "CLEAR_WATCHPOINT";
    case HYBRID_DEBUG_MAILBOX_OP_SNAPSHOT_SAVE: return "SNAPSHOT_SAVE";
    case HYBRID_DEBUG_MAILBOX_OP_SNAPSHOT_RESTORE: return "SNAPSHOT_RESTORE";
    default: return "UNKNOWN";
    }
}

static inline const char* hybrid_debug_mailbox_status_name(uint32_t status) {
    switch (status) {
    case HYBRID_DEBUG_MAILBOX_STATUS_OK: return "OK";
    case HYBRID_DEBUG_MAILBOX_STATUS_BAD_OPCODE: return "BAD_OPCODE";
    case HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR: return "BAD_ADDR";
    case HYBRID_DEBUG_MAILBOX_STATUS_DENIED: return "DENIED";
    case HYBRID_DEBUG_MAILBOX_STATUS_FAULT: return "FAULT";
    case HYBRID_DEBUG_MAILBOX_STATUS_TIMEOUT: return "TIMEOUT";
    case HYBRID_DEBUG_MAILBOX_STATUS_BUSY: return "BUSY";
    case HYBRID_DEBUG_MAILBOX_STATUS_UNSUPPORTED: return "UNSUPPORTED";
    default: return "UNKNOWN";
    }
}

static inline const char* hybrid_debug_mailbox_event_type_name(uint32_t event_type) {
    switch (event_type) {
    case HYBRID_DEBUG_MAILBOX_EVENT_NONE: return "NONE";
    case HYBRID_DEBUG_MAILBOX_EVENT_STOP: return "STOP";
    case HYBRID_DEBUG_MAILBOX_EVENT_BREAKPOINT: return "BREAKPOINT";
    case HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT: return "WATCHPOINT";
    case HYBRID_DEBUG_MAILBOX_EVENT_FAULT: return "FAULT";
    case HYBRID_DEBUG_MAILBOX_EVENT_EPOCH_DONE: return "EPOCH_DONE";
    default: return "UNKNOWN";
    }
}

static inline const char* hybrid_debug_mailbox_stop_reason_name(uint32_t stop_reason) {
    switch (stop_reason) {
    case HYBRID_DEBUG_MAILBOX_STOP_NONE: return "NONE";
    case HYBRID_DEBUG_MAILBOX_STOP_RUN_CYCLES_DONE: return "RUN_CYCLES_DONE";
    case HYBRID_DEBUG_MAILBOX_STOP_EPOCH_LIMIT: return "EPOCH_LIMIT";
    case HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT: return "BREAKPOINT_HIT";
    case HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT: return "WATCHPOINT_HIT";
    case HYBRID_DEBUG_MAILBOX_STOP_EXTERNAL_STOP: return "EXTERNAL_STOP";
    case HYBRID_DEBUG_MAILBOX_STOP_FAULT: return "FAULT";
    case HYBRID_DEBUG_MAILBOX_STOP_TIMEOUT: return "TIMEOUT";
    default: return "UNKNOWN";
    }
}

#ifdef __cplusplus
}
#endif
