#ifndef HYBRID_DEBUG_MAILBOX_PRELOAD_SHARED_H_
#define HYBRID_DEBUG_MAILBOX_PRELOAD_SHARED_H_

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

struct HybridDebugMailboxInitFileStats {
    size_t rules_applied = 0;
    size_t values_applied = 0;
    size_t lines_ignored = 0;
};

struct HybridDebugMailboxDirectPreloadStats {
    size_t rules_applied = 0;
    size_t values_applied = 0;
    size_t lines_ignored = 0;
};

struct HybridDebugMailboxArrayPreloadCoreRow {
    std::string target_path;
    uint64_t word_index = 0ULL;
    uint64_t value = 0ULL;
    uint64_t word_bits = 0ULL;
    uint64_t base_addr = 0ULL;
    uint64_t address_unit_bytes = 0ULL;
    std::string endianness;
    std::string state_selector;
    bool has_state_selector = false;
};

struct HybridDebugMailboxDirectPreloadRow {
    uint64_t var_idx = 0ULL;
    uint64_t value = 0ULL;
    std::string var_name;
    uint64_t width_bits = 0ULL;
    uint64_t address = 0ULL;
    uint64_t byte_count = 0ULL;
    std::string state_selector;
    bool has_state_selector = false;
};

enum HybridDebugMailboxPreloadVisitStatus {
    HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_APPLIED = 0,
    HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_IGNORED = 1,
    HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_ERROR = 2,
};

struct HybridDebugMailboxDirectPreloadVisitResult {
    HybridDebugMailboxPreloadVisitStatus status
        = HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_APPLIED;
    uint64_t values_applied = 0ULL;
};

static inline std::vector<std::string> hybridDebugMailboxPreloadSplitTabs(const std::string& s) {
    std::vector<std::string> out;
    std::string token;
    std::stringstream ss(s);
    while (std::getline(ss, token, '\t')) out.push_back(token);
    return out;
}

static inline bool hybridDebugMailboxPreloadParseU64(const std::string& s, uint64_t* outp) {
    if (!outp || s.empty()) return false;
    errno = 0;
    char* endp = nullptr;
    const unsigned long long raw = std::strtoull(s.c_str(), &endp, 0);
    if (errno != 0 || endp == s.c_str() || *endp != '\0') return false;
    *outp = static_cast<uint64_t>(raw);
    return true;
}

static inline uint64_t hybridDebugMailboxPreloadMaskToWidth(uint64_t value, uint32_t width_bits) {
    if (width_bits == 0U) return 0ULL;
    if (width_bits >= 64U) return value;
    return value & ((uint64_t{1} << width_bits) - 1ULL);
}

static inline bool hybridDebugMailboxPreloadParseStateSelector(const std::string& s,
                                                               uint32_t nstates,
                                                               uint32_t* beginp,
                                                               uint32_t* countp) {
    if (!beginp || !countp || s.empty()) return false;
    const size_t plus_pos = s.find('+');
    if (plus_pos != std::string::npos) {
        uint64_t begin_raw = 0ULL;
        uint64_t count_raw = 0ULL;
        if (!hybridDebugMailboxPreloadParseU64(s.substr(0, plus_pos), &begin_raw)
            || !hybridDebugMailboxPreloadParseU64(s.substr(plus_pos + 1), &count_raw)
            || count_raw == 0ULL || begin_raw >= nstates || count_raw > nstates
            || begin_raw + count_raw > nstates) {
            return false;
        }
        *beginp = static_cast<uint32_t>(begin_raw);
        *countp = static_cast<uint32_t>(count_raw);
        return true;
    }

    const size_t colon_pos = s.find(':');
    if (colon_pos != std::string::npos) {
        uint64_t begin_raw = 0ULL;
        uint64_t end_raw = 0ULL;
        if (!hybridDebugMailboxPreloadParseU64(s.substr(0, colon_pos), &begin_raw)
            || !hybridDebugMailboxPreloadParseU64(s.substr(colon_pos + 1), &end_raw)
            || begin_raw >= nstates || end_raw > nstates || end_raw <= begin_raw) {
            return false;
        }
        *beginp = static_cast<uint32_t>(begin_raw);
        *countp = static_cast<uint32_t>(end_raw - begin_raw);
        return true;
    }

    uint64_t single_raw = 0ULL;
    if (!hybridDebugMailboxPreloadParseU64(s, &single_raw) || single_raw >= nstates) return false;
    *beginp = static_cast<uint32_t>(single_raw);
    *countp = 1U;
    return true;
}

static inline bool hybridDebugMailboxPreloadParseStateSelectorUnbounded(const std::string& s,
                                                                        uint64_t* beginp,
                                                                        uint64_t* countp) {
    if (!beginp || !countp || s.empty()) return false;
    const size_t plus_pos = s.find('+');
    if (plus_pos != std::string::npos) {
        uint64_t begin = 0ULL;
        uint64_t count = 0ULL;
        if (!hybridDebugMailboxPreloadParseU64(s.substr(0, plus_pos), &begin)
            || !hybridDebugMailboxPreloadParseU64(s.substr(plus_pos + 1), &count)
            || count == 0ULL) {
            return false;
        }
        *beginp = begin;
        *countp = count;
        return true;
    }

    const size_t colon_pos = s.find(':');
    if (colon_pos != std::string::npos) {
        uint64_t begin = 0ULL;
        uint64_t end = 0ULL;
        if (!hybridDebugMailboxPreloadParseU64(s.substr(0, colon_pos), &begin)
            || !hybridDebugMailboxPreloadParseU64(s.substr(colon_pos + 1), &end)
            || end <= begin) {
            return false;
        }
        *beginp = begin;
        *countp = end - begin;
        return true;
    }

    uint64_t single = 0ULL;
    if (!hybridDebugMailboxPreloadParseU64(s, &single)) return false;
    *beginp = single;
    *countp = 1ULL;
    return true;
}

static inline bool hybridDebugMailboxPreloadSelectorIncludesState0(const std::string& s,
                                                                   bool* appliesp) {
    if (!appliesp || s.empty()) return false;
    uint64_t begin = 0ULL;
    uint64_t count = 0ULL;
    if (!hybridDebugMailboxPreloadParseStateSelectorUnbounded(s, &begin, &count)) return false;
    *appliesp = begin == 0ULL && count != 0ULL;
    return true;
}

static inline std::string hybridDebugMailboxPreloadFormatStateSelector(uint32_t begin,
                                                                       uint32_t count) {
    if (count <= 1U) return std::to_string(begin);
    return std::to_string(begin) + "+" + std::to_string(count);
}

static inline void hybridDebugMailboxPreloadReplaceAll(std::string* textp, const char* from,
                                                       const char* to) {
    if (!textp || !from || !to || !from[0]) return;
    const std::string from_str{from};
    const std::string to_str{to};
    size_t pos = 0U;
    while ((pos = textp->find(from_str, pos)) != std::string::npos) {
        textp->replace(pos, from_str.size(), to_str);
        pos += to_str.size();
    }
}

static inline bool hybridDebugMailboxArrayPreloadHeaderHasStateSelector(
    const std::vector<std::string>& cols, bool* has_state_selectorp) {
    if (!has_state_selectorp || cols.empty() || cols[0] != "target_path") return false;
    *has_state_selectorp = !cols.empty()
                           && (cols.back() == "state_selector" || cols.back() == "state_index");
    return true;
}

static inline bool hybridDebugMailboxArrayPreloadParseCoreRow(
    const std::vector<std::string>& cols, bool has_state_selector,
    HybridDebugMailboxArrayPreloadCoreRow* rowp) {
    if (!rowp) return false;
    *rowp = HybridDebugMailboxArrayPreloadCoreRow{};
    const size_t min_cols = has_state_selector ? 8U : 7U;
    if (cols.size() < min_cols || cols[0].empty()) return false;
    uint64_t word_index = 0ULL;
    uint64_t value = 0ULL;
    uint64_t word_bits = 0ULL;
    uint64_t base_addr = 0ULL;
    uint64_t address_unit_bytes = 0ULL;
    if (!hybridDebugMailboxPreloadParseU64(cols[1], &word_index)
        || !hybridDebugMailboxPreloadParseU64(cols[2], &value)
        || !hybridDebugMailboxPreloadParseU64(cols[3], &word_bits)
        || !hybridDebugMailboxPreloadParseU64(cols[4], &base_addr)
        || !hybridDebugMailboxPreloadParseU64(cols[5], &address_unit_bytes)) {
        return false;
    }
    rowp->target_path = cols[0];
    rowp->word_index = word_index;
    rowp->value = value;
    rowp->word_bits = word_bits;
    rowp->base_addr = base_addr;
    rowp->address_unit_bytes = address_unit_bytes;
    rowp->endianness = cols[6];
    rowp->has_state_selector = has_state_selector;
    if (has_state_selector) rowp->state_selector = cols.back();
    return true;
}

static inline bool hybridDebugMailboxDirectPreloadHeaderHasStateSelector(
    const std::vector<std::string>& cols, bool* has_state_selectorp) {
    if (!has_state_selectorp || cols.empty() || cols[0] != "var_idx") return false;
    *has_state_selectorp = !cols.empty()
                           && (cols.back() == "state_selector" || cols.back() == "state_index");
    return true;
}

static inline bool hybridDebugMailboxDirectPreloadParseRow(
    const std::vector<std::string>& cols, bool has_state_selector,
    HybridDebugMailboxDirectPreloadRow* rowp) {
    if (!rowp) return false;
    *rowp = HybridDebugMailboxDirectPreloadRow{};
    const size_t min_cols = has_state_selector ? 7U : 6U;
    if (cols.size() < min_cols) return false;
    uint64_t var_idx = 0ULL;
    uint64_t value = 0ULL;
    uint64_t width_bits = 0ULL;
    uint64_t address = 0ULL;
    uint64_t byte_count = 0ULL;
    if (!hybridDebugMailboxPreloadParseU64(cols[0], &var_idx)
        || !hybridDebugMailboxPreloadParseU64(cols[1], &value)
        || !hybridDebugMailboxPreloadParseU64(cols[3], &width_bits)
        || !hybridDebugMailboxPreloadParseU64(cols[4], &address)
        || !hybridDebugMailboxPreloadParseU64(cols[5], &byte_count)) {
        return false;
    }
    rowp->var_idx = var_idx;
    rowp->value = value;
    rowp->var_name = cols[2];
    rowp->width_bits = width_bits;
    rowp->address = address;
    rowp->byte_count = byte_count;
    rowp->has_state_selector = has_state_selector;
    if (has_state_selector) rowp->state_selector = cols.back();
    return true;
}

static inline bool hybridDebugMailboxDirectVarNameToTarget(const std::string& var_name,
                                                           std::string* target_pathp,
                                                           uint64_t* word_indexp,
                                                           bool* is_array_elementp) {
    if (!target_pathp || !word_indexp || !is_array_elementp || var_name.empty()) return false;
    const std::string ket_token{"__KET__"};
    const std::string bra_token{"__BRA__"};
    size_t bra_pos = std::string::npos;
    if (var_name.size() > ket_token.size()
        && var_name.compare(var_name.size() - ket_token.size(), ket_token.size(), ket_token)
               == 0) {
        bra_pos = var_name.rfind(bra_token);
    }
    if (bra_pos != std::string::npos) {
        uint64_t element_index = 0ULL;
        const size_t index_pos = bra_pos + bra_token.size();
        const size_t ket_pos = var_name.size() - ket_token.size();
        if (index_pos >= ket_pos
            || !hybridDebugMailboxPreloadParseU64(var_name.substr(index_pos, ket_pos - index_pos),
                                                  &element_index)) {
            return false;
        }
        *target_pathp = var_name.substr(0, bra_pos);
        if (target_pathp->empty()) return false;
        hybridDebugMailboxPreloadReplaceAll(target_pathp, "__DOT__", ".");
        *word_indexp = element_index;
        *is_array_elementp = true;
        return true;
    }

    *target_pathp = var_name;
    hybridDebugMailboxPreloadReplaceAll(target_pathp, "__DOT__", ".");
    if (target_pathp->empty()) return false;
    *word_indexp = 0ULL;
    *is_array_elementp = false;
    return true;
}

static inline HybridDebugMailboxDirectPreloadVisitResult hybridDebugMailboxDirectPreloadApplied(
    uint64_t values_applied) {
    HybridDebugMailboxDirectPreloadVisitResult result{};
    result.status = HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_APPLIED;
    result.values_applied = values_applied;
    return result;
}

static inline HybridDebugMailboxDirectPreloadVisitResult hybridDebugMailboxDirectPreloadIgnored() {
    HybridDebugMailboxDirectPreloadVisitResult result{};
    result.status = HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_IGNORED;
    return result;
}

static inline HybridDebugMailboxDirectPreloadVisitResult hybridDebugMailboxDirectPreloadError() {
    HybridDebugMailboxDirectPreloadVisitResult result{};
    result.status = HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_ERROR;
    return result;
}

template <typename RowFn>
static inline bool hybridDebugMailboxVisitDirectPreloadFile(
    const char* direct_path, HybridDebugMailboxDirectPreloadStats* statsp, RowFn&& row_fn) {
    if (statsp) *statsp = HybridDebugMailboxDirectPreloadStats{};
    if (!direct_path || !direct_path[0]) return false;

    std::ifstream inf(direct_path);
    if (!inf) return false;

    std::string line;
    bool has_state_selector = false;
    bool saw_data = false;
    bool success = true;
    while (std::getline(inf, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> cols = hybridDebugMailboxPreloadSplitTabs(line);
        if (cols.empty()) continue;
        if (hybridDebugMailboxDirectPreloadHeaderHasStateSelector(cols, &has_state_selector)) {
            continue;
        }
        HybridDebugMailboxDirectPreloadRow row{};
        if (!hybridDebugMailboxDirectPreloadParseRow(cols, has_state_selector, &row)) {
            if (statsp) ++statsp->lines_ignored;
            success = false;
            continue;
        }
        saw_data = true;
        const HybridDebugMailboxDirectPreloadVisitResult visit_result = row_fn(row);
        if (visit_result.status == HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_APPLIED) {
            if (statsp) {
                ++statsp->rules_applied;
                statsp->values_applied += visit_result.values_applied;
            }
            continue;
        }
        if (statsp) ++statsp->lines_ignored;
        if (visit_result.status == HYBRID_DEBUG_MAILBOX_PRELOAD_VISIT_ERROR) success = false;
    }
    return saw_data && success;
}

#endif
