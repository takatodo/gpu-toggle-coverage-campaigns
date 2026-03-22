#pragma once

#include "HYBRID_DEBUG_MAILBOX_ABI.h"

#include <stdint.h>

struct HybridDebugMailboxRuntimeSession;

// This header expects HybridDebugMailboxRuntimeSession and related binding
// structs to be fully defined by the includer.

static inline uint32_t hybridDebugMailboxRuntimeSessionBoundCsrCount(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return 0U;
    uint32_t count = 0U;
    for (uint32_t i = 0; i < sessionp->reg_binding_count; ++i) {
        const HybridDebugMailboxRuntimeRegBinding& binding = sessionp->reg_bindings[i];
        if (binding.addr_space == HYBRID_DEBUG_MAILBOX_ADDR_REG_CSR) count += 1U;
    }
    return count;
}

static inline uint32_t hybridDebugMailboxRuntimeSessionKnownCsrProfile(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    if (!sessionp) return HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0;
    if (!hybrid_debug_mailbox_csr_profile_valid(sessionp->csr_profile)) {
        return HYBRID_DEBUG_MAILBOX_CSR_PROFILE_BASE_V0;
    }
    return sessionp->csr_profile;
}

static inline bool hybridDebugMailboxRuntimeSessionSetKnownCsrProfile(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t profile) {
    if (!sessionp) return false;
    if (!hybrid_debug_mailbox_csr_profile_valid(profile)) return false;
    sessionp->csr_profile = profile;
    return true;
}

static inline uint32_t hybridDebugMailboxRuntimeSessionKnownCsrCount(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    return hybrid_debug_mailbox_csr_profile_count(
        hybridDebugMailboxRuntimeSessionKnownCsrProfile(sessionp));
}

static inline bool hybridDebugMailboxRuntimeSessionKnownCsrIndexAt(
    const HybridDebugMailboxRuntimeSession* sessionp, uint32_t ordinal, uint32_t* csrIndexp) {
    if (!csrIndexp) return false;
    const uint32_t profile = hybridDebugMailboxRuntimeSessionKnownCsrProfile(sessionp);
    const uint32_t count = hybrid_debug_mailbox_csr_profile_count(profile);
    if (ordinal >= count) return false;
    *csrIndexp = hybrid_debug_mailbox_csr_profile_index_at(profile, ordinal);
    return true;
}

static inline bool hybridDebugMailboxRuntimeSessionBoundCsrIndexAt(
    const HybridDebugMailboxRuntimeSession* sessionp, uint32_t ordinal, uint32_t* csrIndexp) {
    if (!sessionp || !csrIndexp) return false;
    uint32_t seen = 0U;
    for (uint32_t i = 0; i < sessionp->reg_binding_count; ++i) {
        const HybridDebugMailboxRuntimeRegBinding& binding = sessionp->reg_bindings[i];
        if (binding.addr_space != HYBRID_DEBUG_MAILBOX_ADDR_REG_CSR) continue;
        if (seen == ordinal) {
            *csrIndexp = static_cast<uint32_t>(binding.reg_index);
            return true;
        }
        seen += 1U;
    }
    return false;
}

static inline const char* hybridDebugMailboxRuntimeSessionBoundCsrNameAt(
    const HybridDebugMailboxRuntimeSession* sessionp, uint32_t ordinal) {
    uint32_t csrIndex = 0U;
    if (!hybridDebugMailboxRuntimeSessionBoundCsrIndexAt(sessionp, ordinal, &csrIndex)) {
        return nullptr;
    }
    return hybrid_debug_mailbox_csr_name(csrIndex);
}

static inline bool hybridDebugMailboxRuntimeSessionReadDiscoveryDebugReg(
    const HybridDebugMailboxRuntimeSession* sessionp, uint64_t reg_index, uint64_t* valuep) {
    if (!sessionp || !valuep) return false;
    switch (reg_index) {
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_KNOWN_CSR_COUNT:
        *valuep = hybridDebugMailboxRuntimeSessionKnownCsrCount(sessionp);
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_BOUND_CSR_COUNT:
        *valuep = hybridDebugMailboxRuntimeSessionBoundCsrCount(sessionp);
        return true;
    case HYBRID_DEBUG_MAILBOX_DEBUG_REG_CSR_PROFILE:
        *valuep = hybridDebugMailboxRuntimeSessionKnownCsrProfile(sessionp);
        return true;
    default:
        break;
    }
    if (reg_index >= HYBRID_DEBUG_MAILBOX_DEBUG_REG_KNOWN_CSR_INDEX_BASE) {
        const uint64_t ordinal = reg_index - HYBRID_DEBUG_MAILBOX_DEBUG_REG_KNOWN_CSR_INDEX_BASE;
        uint32_t csrIndex = 0U;
        if (hybridDebugMailboxRuntimeSessionKnownCsrIndexAt(sessionp,
                                                            static_cast<uint32_t>(ordinal),
                                                            &csrIndex)) {
            *valuep = csrIndex;
            return true;
        }
    }
    if (reg_index >= HYBRID_DEBUG_MAILBOX_DEBUG_REG_BOUND_CSR_INDEX_BASE) {
        const uint64_t ordinal = reg_index - HYBRID_DEBUG_MAILBOX_DEBUG_REG_BOUND_CSR_INDEX_BASE;
        uint32_t csrIndex = 0U;
        if (hybridDebugMailboxRuntimeSessionBoundCsrIndexAt(sessionp, static_cast<uint32_t>(ordinal),
                                                            &csrIndex)) {
            *valuep = csrIndex;
            return true;
        }
    }
    return false;
}
