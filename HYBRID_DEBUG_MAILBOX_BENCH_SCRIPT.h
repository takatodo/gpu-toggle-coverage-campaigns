#pragma once

#include <fstream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

// This helper is intentionally included late from the generated bench TU, after the
// bench-local types and array preload helpers are available.

struct HybridDebugMailboxBenchScriptConfig {
    std::string mailbox_script;
    uint32_t nvars = 0;
    uint32_t nstates = 0;
    const std::vector<std::string>* direct_preload_filesp = nullptr;
    const DirectPreloadStats* direct_preload_statsp = nullptr;
    const std::vector<std::string>* array_preload_payload_filesp = nullptr;
    const ArrayPreloadPayloadStats* array_preload_statsp = nullptr;
    bool wrote_array_preload_target_summary = false;
    std::string array_preload_target_summary_path;
    bool wrote_array_preload_hidden_storage = false;
    std::string array_preload_hidden_storage_path;
};

struct HybridDebugMailboxBenchRegDispatchContext {
    std::vector<SimAccelValue>* current_statep = nullptr;
    uint32_t nstates = 0;
    const std::map<MailboxCanonicalRegKey, MailboxCanonicalRegBinding>* reg_bindingsp = nullptr;
};

struct HybridDebugMailboxBenchMemDispatchContext {
    std::vector<SimAccelValue>* current_statep = nullptr;
    uint32_t nstates = 0;
    std::unordered_map<std::string, ArrayPreloadTargetData>* array_preload_targetsp = nullptr;
    const std::map<uint32_t, MailboxCanonicalMemBinding>* mem_bindingsp = nullptr;
};

static inline bool hybridDebugMailboxBenchNoopStep(HybridDebugMailboxEpochStepResult* stepResultp,
                                                   HybridDebugMailboxFaultDetail* faultDetailp) {
    if (stepResultp) memset(stepResultp, 0, sizeof(*stepResultp));
    if (faultDetailp) hybridDebugMailboxFaultDetailClear(faultDetailp);
    return true;
}

static inline bool hybridDebugMailboxBenchExecuteQueuedCommand(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t& cmd,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp) {
    if (!sessionp || !rspp || !eventp) return false;
    memset(rspp, 0, sizeof(*rspp));
    memset(eventp, 0, sizeof(*eventp));
    if (!hybridDebugMailboxRuntimeSessionPushCommand(sessionp, &cmd)) {
        hybridDebugMailboxRuntimeSessionSetFaultDetail(
            sessionp, hybridDebugMailboxCommunicationFaultDetail(
                          HYBRID_DEBUG_MAILBOX_FAULT_STAGE_H2D, 100U, cmd.opcode, cmd.request_id,
                          hybrid_debug_mailbox_ring_count(&sessionp->layout.command_ring)));
        hybridDebugMailboxRuntimeBuildSessionFaultReply(sessionp, &cmd, rspp, eventp);
        return true;
    }
    hybridDebugMailboxRuntimeServe(sessionp, 1, false, hybridDebugMailboxBenchNoopStep);
    if (!hybridDebugMailboxRuntimeSessionPopResponse(sessionp, rspp)) {
        if (sessionp->last_fault.kind != HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
            hybridDebugMailboxRuntimeBuildSessionFaultReply(sessionp, &cmd, rspp, eventp);
            return true;
        }
        return false;
    }
    if (!hybridDebugMailboxRuntimeSessionPopEvent(sessionp, eventp)) {
        memset(eventp, 0, sizeof(*eventp));
        eventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
        eventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    }
    return true;
}

static inline int hybridDebugMailboxBenchRegDispatchHook(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp) {
    if (!sessionp || !cmdp || !rspp || !eventp || !haveEventp) return -1;
    const auto* contextp = static_cast<const HybridDebugMailboxBenchRegDispatchContext*>(
        sessionp->reg_dispatch_contextp);
    if (!contextp || !contextp->current_statep || !contextp->reg_bindingsp) return 0;
    const uint64_t regIndex = hybrid_debug_mailbox_u64_from_words(cmdp->addr_lo, cmdp->addr_hi);
    const MailboxCanonicalRegKey regKey{cmdp->addr_space, regIndex};
    const auto bindingIt = contextp->reg_bindingsp->find(regKey);
    if (bindingIt == contextp->reg_bindingsp->end()) return 0;

    const MailboxCanonicalRegBinding& binding = bindingIt->second;
    hybrid_debug_mailbox_response_t rsp
        = hybrid_debug_mailbox_mock_make_response(cmdp, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    hybrid_debug_mailbox_event_t ev{};
    int haveEvent = 0;
    if (cmdp->opcode == HYBRID_DEBUG_MAILBOX_OP_READ_REG) {
        const SimAccelValue value = maskToWidth(
            readVarValueAtState(*contextp->current_statep, binding.visible.var_idx, 0,
                                contextp->nstates),
            binding.visible.width);
        hybrid_debug_mailbox_u64_to_words(value, &rsp.arg0, &rsp.arg1);
        rsp.size_bytes = 8;
    } else if (cmdp->opcode == HYBRID_DEBUG_MAILBOX_OP_WRITE_REG) {
        const uint64_t valueRaw = hybrid_debug_mailbox_u64_from_words(cmdp->arg0, cmdp->arg1);
        const SimAccelValue value = maskToWidth(valueRaw, binding.visible.width);
        writeVarValueRange(contextp->current_statep, binding.visible.var_idx, 0, contextp->nstates,
                           contextp->nstates, value);
    } else {
        return 0;
    }
    *rspp = rsp;
    *eventp = ev;
    *haveEventp = haveEvent;
    return 1;
}

static inline int hybridDebugMailboxBenchMemDispatchHook(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    int* haveEventp) {
    if (!sessionp || !cmdp || !rspp || !eventp || !haveEventp) return -1;
    const auto* contextp = static_cast<const HybridDebugMailboxBenchMemDispatchContext*>(
        sessionp->mem_dispatch_contextp);
    if (!contextp || !contextp->current_statep || !contextp->array_preload_targetsp
        || !contextp->mem_bindingsp) {
        return 0;
    }
    const auto memBindingIt = contextp->mem_bindingsp->find(cmdp->addr_space);
    if (memBindingIt == contextp->mem_bindingsp->end()) return 0;
    auto targetIt = contextp->array_preload_targetsp->find(memBindingIt->second.target_path);
    if (targetIt == contextp->array_preload_targetsp->end()) {
        *rspp = hybrid_debug_mailbox_mock_make_response(cmdp, HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR);
        memset(eventp, 0, sizeof(*eventp));
        *haveEventp = 0;
        return 1;
    }

    const uint64_t wordIndex = hybrid_debug_mailbox_u64_from_words(cmdp->addr_lo, cmdp->addr_hi);
    hybrid_debug_mailbox_response_t rsp
        = hybrid_debug_mailbox_mock_make_response(cmdp, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    hybrid_debug_mailbox_event_t ev{};
    int haveEvent = 0;

    if (cmdp->opcode == HYBRID_DEBUG_MAILBOX_OP_READ_MEM) {
        uint64_t value = 0;
        if (!readArrayPreloadWordState0(targetIt->second, *contextp->current_statep,
                                        contextp->nstates, wordIndex, &value, nullptr)) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
        } else {
            hybrid_debug_mailbox_u64_to_words(value, &rsp.arg0, &rsp.arg1);
            rsp.size_bytes = 8;
            if (hybrid_debug_mailbox_mock_is_watchpoint_hit(&sessionp->state, cmdp->addr_space,
                                                            wordIndex)) {
                sessionp->state.last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT;
                ev = hybrid_debug_mailbox_mock_make_stop_event(
                    &sessionp->state, HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT,
                    sessionp->state.last_stop_reason);
                haveEvent = 1;
            }
        }
    } else if (cmdp->opcode == HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM) {
        const uint64_t valueRaw = hybrid_debug_mailbox_u64_from_words(cmdp->arg0, cmdp->arg1);
        const uint64_t value = maskToWordBits(valueRaw, targetIt->second.word_bits);
        std::string detail;
        if (!writeArrayPreloadWord(&targetIt->second, contextp->current_statep, contextp->nstates,
                                   wordIndex, value, &detail)) {
            rsp.status = HYBRID_DEBUG_MAILBOX_STATUS_BAD_ADDR;
        } else {
            if (detail.find("hidden") != std::string::npos) {
                applyArrayPreloadHiddenRuntimeStorage(contextp->nstates,
                                                      *contextp->array_preload_targetsp, nullptr);
            }
            if (hybrid_debug_mailbox_mock_is_watchpoint_hit(&sessionp->state, cmdp->addr_space,
                                                            wordIndex)) {
                sessionp->state.last_stop_reason = HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT;
                ev = hybrid_debug_mailbox_mock_make_stop_event(
                    &sessionp->state, HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT,
                    sessionp->state.last_stop_reason);
                haveEvent = 1;
            }
        }
    } else {
        return 0;
    }

    *rspp = rsp;
    *eventp = ev;
    *haveEventp = haveEvent;
    return 1;
}

template <typename RunMailboxHybridPassFn>
static inline int hybridDebugMailboxRunBenchScript(
    const HybridDebugMailboxBenchScriptConfig& cfg,
    std::unordered_map<std::string, ArrayPreloadTargetData>* arrayPreloadTargetsp,
    const std::vector<SimAccelValue>& initialStateVarMajor, RunMailboxHybridPassFn&& runMailboxHybridPass) {
    if (!arrayPreloadTargetsp) {
        std::cerr << "Internal error: mailbox bench script requires array preload targets\n";
        return 2;
    }

    std::ifstream mailboxIn(cfg.mailbox_script);
    if (!mailboxIn) {
        std::cerr << "Could not open mailbox script: " << cfg.mailbox_script << "\n";
        return 2;
    }
    std::ofstream mailboxTrace("mailbox_trace.tsv");
    if (!mailboxTrace) {
        std::cerr << "Could not create mailbox trace: mailbox_trace.tsv\n";
        return 2;
    }

    const auto debugVisibleVars = loadDebugVisibleVars("kernel_generated.vars.tsv", cfg.nvars);
    constexpr const char* kCanonicalRegNamespace = "canonical-v1";
    constexpr const char* kLegacyRegNamespace = "debug-visible";
    mailboxTrace
        << "seq\tverb\tstatus\tnamespace\tkey\tvalue_hex\tstop_reason\tepochs_executed\tdetail\n";

    auto emitMailboxTrace = [&](size_t seq, const std::string& verb, const std::string& status,
                                const std::string& nameSpace, const std::string& key,
                                const std::string& valueHex, const std::string& stopReason,
                                uint64_t epochsExecuted, const std::string& detail) {
        mailboxTrace << seq << '\t' << verb << '\t' << status << '\t' << nameSpace << '\t' << key
                     << '\t' << valueHex << '\t' << stopReason << '\t' << epochsExecuted << '\t'
                     << detail << '\n';
    };
    auto mailboxError = [&](size_t lineNo, const std::string& msg) -> int {
        std::cerr << "Mailbox script error at line " << lineNo << ": " << msg << "\n";
        return 2;
    };

    std::vector<SimAccelValue> currentState = initialStateVarMajor;
    std::map<MailboxCanonicalRegKey, MailboxCanonicalRegBinding> mailboxRegBindings;
    std::map<uint32_t, MailboxCanonicalMemBinding> mailboxMemBindings;
    auto& arrayPreloadTargets = *arrayPreloadTargetsp;
    HybridDebugMailboxRuntimeSession mailboxSession{};
    hybridDebugMailboxRuntimeSessionInit(&mailboxSession, 0);
    HybridDebugMailboxBenchRegDispatchContext mailboxRegDispatchCtx{};
    mailboxRegDispatchCtx.current_statep = &currentState;
    mailboxRegDispatchCtx.nstates = cfg.nstates;
    mailboxRegDispatchCtx.reg_bindingsp = &mailboxRegBindings;
    hybridDebugMailboxRuntimeSessionSetRegDispatchContext(&mailboxSession, &mailboxRegDispatchCtx);
    hybridDebugMailboxRuntimeSessionSetRegDispatchHook(&mailboxSession,
                                                       hybridDebugMailboxBenchRegDispatchHook);
    HybridDebugMailboxBenchMemDispatchContext mailboxMemDispatchCtx{};
    mailboxMemDispatchCtx.current_statep = &currentState;
    mailboxMemDispatchCtx.nstates = cfg.nstates;
    mailboxMemDispatchCtx.array_preload_targetsp = &arrayPreloadTargets;
    mailboxMemDispatchCtx.mem_bindingsp = &mailboxMemBindings;
    hybridDebugMailboxRuntimeSessionSetMemDispatchContext(&mailboxSession, &mailboxMemDispatchCtx);
    hybridDebugMailboxRuntimeSessionSetMemDispatchHook(&mailboxSession,
                                                       hybridDebugMailboxBenchMemDispatchHook);
    size_t mailboxCommandCount = 0;
    auto mailboxLastStopReason = [&]() {
        return std::string(
            hybrid_debug_mailbox_stop_reason_name(mailboxSession.state.last_stop_reason));
    };

    const std::vector<std::string>& directPreloadFiles
        = cfg.direct_preload_filesp ? *cfg.direct_preload_filesp : std::vector<std::string>{};
    const std::vector<std::string>& arrayPreloadPayloadFiles
        = cfg.array_preload_payload_filesp ? *cfg.array_preload_payload_filesp
                                           : std::vector<std::string>{};
    const DirectPreloadStats emptyDirectPreloadStats{};
    const ArrayPreloadPayloadStats emptyArrayPreloadStats{};
    const DirectPreloadStats& directPreloadStats
        = cfg.direct_preload_statsp ? *cfg.direct_preload_statsp : emptyDirectPreloadStats;
    const ArrayPreloadPayloadStats& arrayPreloadStats
        = cfg.array_preload_statsp ? *cfg.array_preload_statsp : emptyArrayPreloadStats;

    std::cout << "mailbox_mode=1\n";
    std::cout << "mailbox_script=" << cfg.mailbox_script << "\n";
    std::cout << "mailbox_reg_namespace=" << kCanonicalRegNamespace << "\n";
    std::cout << "mailbox_reg_namespace_contract=addr_space+addr_lo\n";
    std::cout << "mailbox_reg_legacy_namespace=" << kLegacyRegNamespace << "\n";
    std::cout << "mailbox_reg_reserved_debug0=pc\n";
    std::cout << "mailbox_mem_namespace=" << kCanonicalRegNamespace << "\n";
    std::cout << "mailbox_mem_namespace_contract=addr_space+word_index\n";
    std::cout << "mailbox_memory_namespace_count=" << arrayPreloadTargets.size() << "\n";
    std::cout << "direct_preload_file_count=" << directPreloadFiles.size() << "\n";
    if (!directPreloadFiles.empty()) {
        std::cout << "direct_preload_rules_applied=" << directPreloadStats.rules_applied << "\n";
        std::cout << "direct_preload_values_applied=" << directPreloadStats.values_applied << "\n";
        std::cout << "direct_preload_lines_ignored=" << directPreloadStats.lines_ignored << "\n";
    }
    std::cout << "array_preload_payload_file_count=" << arrayPreloadPayloadFiles.size() << "\n";
    if (!arrayPreloadPayloadFiles.empty()) {
        std::cout << "array_preload_payload_files_loaded=" << arrayPreloadStats.files_loaded << "\n";
        std::cout << "array_preload_targets_loaded=" << arrayPreloadStats.targets_loaded << "\n";
        std::cout << "array_preload_words_loaded=" << arrayPreloadStats.words_loaded << "\n";
        std::cout << "array_preload_mapped_rows_loaded=" << arrayPreloadStats.mapped_rows_loaded
                  << "\n";
        std::cout << "array_preload_hidden_rows_loaded=" << arrayPreloadStats.hidden_rows_loaded
                  << "\n";
        std::cout << "array_preload_hidden_only_targets=" << arrayPreloadStats.hidden_only_targets
                  << "\n";
        std::cout << "array_preload_hidden_storage_targets="
                  << arrayPreloadStats.hidden_storage_targets << "\n";
        std::cout << "array_preload_hidden_storage_words="
                  << arrayPreloadStats.hidden_storage_words << "\n";
        std::cout << "array_preload_hidden_runtime_state_count="
                  << sim_accel_eval_preload_runtime_state_count() << "\n";
        std::cout << "array_preload_hidden_runtime_targets_applied="
                  << arrayPreloadStats.hidden_runtime_targets_applied << "\n";
        std::cout << "array_preload_hidden_runtime_rules_applied="
                  << arrayPreloadStats.hidden_runtime_rules_applied << "\n";
        std::cout << "array_preload_hidden_runtime_values_applied="
                  << arrayPreloadStats.hidden_runtime_values_applied << "\n";
        std::cout << "array_preload_hidden_runtime_lines_ignored="
                  << arrayPreloadStats.hidden_runtime_lines_ignored << "\n";
        if (cfg.wrote_array_preload_target_summary) {
            std::cout << "array_preload_target_summary_tsv="
                      << cfg.array_preload_target_summary_path << "\n";
        }
        if (cfg.wrote_array_preload_hidden_storage) {
            std::cout << "array_preload_hidden_storage_tsv="
                      << cfg.array_preload_hidden_storage_path << "\n";
        }
        std::cout << "array_preload_mapped_rules_applied="
                  << arrayPreloadStats.mapped_rules_applied << "\n";
        std::cout << "array_preload_mapped_values_applied="
                  << arrayPreloadStats.mapped_values_applied << "\n";
        std::cout << "array_preload_lines_ignored=" << arrayPreloadStats.lines_ignored << "\n";
    }

    std::string line;
    for (size_t lineNo = 1; std::getline(mailboxIn, line); ++lineNo) {
        const auto hashPos = line.find('#');
        if (hashPos != std::string::npos) line.resize(hashPos);
        const std::vector<std::string> toks = splitWhitespace(line);
        if (toks.empty()) continue;

        const std::string& verb = toks[0];
        if (verb == "MAP_REG") {
            if (toks.size() != 4) return mailboxError(lineNo, "MAP_REG requires: addr_space addr_lo name");
            MailboxCanonicalRegKey regKey;
            std::string regParseError;
            if (!parseMailboxCanonicalRegKey(toks[1], toks[2], &regKey, &regParseError)) {
                return mailboxError(lineNo, regParseError);
            }
            if (regKey.first == HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG && regKey.second == 0) {
                return mailboxError(lineNo, "MAP_REG cannot bind DEBUG[0]; it is reserved for pc");
            }
            const auto regIt = debugVisibleVars.find(toks[3]);
            if (regIt == debugVisibleVars.end()) {
                return mailboxError(lineNo, "unknown debug-visible register: " + toks[3]);
            }
            MailboxCanonicalRegBinding binding;
            binding.debug_visible_name = toks[3];
            binding.visible = regIt->second;
            const auto inserted = mailboxRegBindings.emplace(regKey, binding);
            if (!inserted.second) {
                return mailboxError(lineNo, "duplicate MAP_REG binding for "
                                                + formatMailboxCanonicalRegKey(regKey));
            }
            continue;
        } else if (verb == "MAP_MEM") {
            if (toks.size() != 3) return mailboxError(lineNo, "MAP_MEM requires: addr_space target_path");
            uint32_t addrSpace = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
            if (!parseMailboxMemAddrSpaceToken(toks[1], &addrSpace)) {
                return mailboxError(lineNo, "unknown memory addr_space: " + toks[1]);
            }
            if (!mailboxMemAddrSpaceSupportsCanonicalBinding(addrSpace)) {
                return mailboxError(lineNo, "unsupported memory addr_space: " + toks[1]);
            }
            if (arrayPreloadTargets.find(toks[2]) == arrayPreloadTargets.end()) {
                return mailboxError(lineNo, "unknown memory namespace: " + toks[2]);
            }
            const auto inserted
                = mailboxMemBindings.emplace(addrSpace, MailboxCanonicalMemBinding{toks[2]});
            if (!inserted.second) {
                return mailboxError(lineNo, "duplicate MAP_MEM binding for "
                                                + std::string(mailboxMemAddrSpaceName(addrSpace)));
            }
            continue;
        }

        const size_t seq = mailboxCommandCount++;
        if (verb == "WRITE_REG") {
            if (toks.size() != 4) return mailboxError(lineNo, "WRITE_REG requires: addr_space addr_lo value");
            uint64_t valueRaw = 0;
            if (!parseU64(toks[3], &valueRaw)) {
                return mailboxError(lineNo, "invalid WRITE_REG value: " + toks[3]);
            }
            if (toks[1] == kLegacyRegNamespace) {
                const auto regIt = debugVisibleVars.find(toks[2]);
                if (regIt == debugVisibleVars.end()) {
                    return mailboxError(lineNo, "unknown debug-visible register: " + toks[2]);
                }
                const SimAccelValue value = maskToWidth(valueRaw, regIt->second.width);
                writeVarValueRange(&currentState, regIt->second.var_idx, 0, cfg.nstates, cfg.nstates,
                                   value);
                emitMailboxTrace(seq, verb, "ok", toks[1], toks[2],
                                 formatArrayPreloadHex(value, regIt->second.width),
                                 mailboxLastStopReason(), 0, "");
            } else {
                MailboxCanonicalRegKey regKey;
                std::string regParseError;
                if (!parseMailboxCanonicalRegKey(toks[1], toks[2], &regKey, &regParseError)) {
                    return mailboxError(lineNo, regParseError);
                }
                hybrid_debug_mailbox_command_t cmd{};
                cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_WRITE_REG;
                cmd.request_id = static_cast<uint32_t>(seq + 1);
                cmd.addr_space = regKey.first;
                hybrid_debug_mailbox_u64_to_words(regKey.second, &cmd.addr_lo, &cmd.addr_hi);
                hybrid_debug_mailbox_u64_to_words(valueRaw, &cmd.arg0, &cmd.arg1);
                hybrid_debug_mailbox_response_t rsp{};
                hybrid_debug_mailbox_event_t ev{};
                if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                    return mailboxError(lineNo, "WRITE_REG queue execution failed");
                }
                if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                    return mailboxError(lineNo, std::string("WRITE_REG failed: ")
                                                    + hybrid_debug_mailbox_status_name(rsp.status));
                }
                const auto bindingIt = mailboxRegBindings.find(regKey);
                const uint32_t width = bindingIt != mailboxRegBindings.end()
                                           ? bindingIt->second.visible.width
                                           : 64u;
                const uint64_t committedValue = hybrid_debug_mailbox_u64_from_words(rsp.arg0, rsp.arg1);
                emitMailboxTrace(seq, verb, "ok", mailboxRegAddrSpaceName(regKey.first),
                                 formatMailboxCanonicalRegKey(regKey),
                                 formatArrayPreloadHex(committedValue, width),
                                 mailboxLastStopReason(), 0, "");
            }
        } else if (verb == "READ_REG") {
            if (toks.size() != 3) return mailboxError(lineNo, "READ_REG requires: addr_space addr_lo");
            if (toks[1] == kLegacyRegNamespace) {
                const auto regIt = debugVisibleVars.find(toks[2]);
                if (regIt == debugVisibleVars.end()) {
                    return mailboxError(lineNo, "unknown debug-visible register: " + toks[2]);
                }
                const SimAccelValue value = maskToWidth(
                    readVarValueAtState(currentState, regIt->second.var_idx, 0, cfg.nstates),
                    regIt->second.width);
                emitMailboxTrace(seq, verb, "ok", toks[1], toks[2],
                                 formatArrayPreloadHex(value, regIt->second.width),
                                 mailboxLastStopReason(), 0, "");
            } else {
                MailboxCanonicalRegKey regKey;
                std::string regParseError;
                if (!parseMailboxCanonicalRegKey(toks[1], toks[2], &regKey, &regParseError)) {
                    return mailboxError(lineNo, regParseError);
                }
                hybrid_debug_mailbox_command_t cmd{};
                cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_READ_REG;
                cmd.request_id = static_cast<uint32_t>(seq + 1);
                cmd.addr_space = regKey.first;
                hybrid_debug_mailbox_u64_to_words(regKey.second, &cmd.addr_lo, &cmd.addr_hi);
                hybrid_debug_mailbox_response_t rsp{};
                hybrid_debug_mailbox_event_t ev{};
                if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                    return mailboxError(lineNo, "READ_REG queue execution failed");
                }
                if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                    return mailboxError(lineNo, std::string("READ_REG failed: ")
                                                    + hybrid_debug_mailbox_status_name(rsp.status));
                }
                const auto bindingIt = mailboxRegBindings.find(regKey);
                const uint32_t width = bindingIt != mailboxRegBindings.end()
                                           ? bindingIt->second.visible.width
                                           : 64u;
                const uint64_t readback = hybrid_debug_mailbox_u64_from_words(rsp.arg0, rsp.arg1);
                emitMailboxTrace(seq, verb, "ok", mailboxRegAddrSpaceName(regKey.first),
                                 formatMailboxCanonicalRegKey(regKey),
                                 formatArrayPreloadHex(readback, width),
                                 mailboxLastStopReason(), 0, "");
            }
        } else if (verb == "READ_MEM") {
            if (toks.size() != 3) return mailboxError(lineNo, "READ_MEM requires: namespace word_index");
            uint64_t wordIndex = 0;
            if (!parseU64(toks[2], &wordIndex)) {
                return mailboxError(lineNo, "invalid memory word index: " + toks[2]);
            }
            auto targetIt = arrayPreloadTargets.end();
            uint32_t memAddrSpace = HYBRID_DEBUG_MAILBOX_ADDR_MEM_PHYS;
            std::string memNamespace = toks[1];
            std::string memKey = toks[1] + "[" + toks[2] + "]";
            uint32_t parsedAddrSpace = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
            if (parseMailboxMemAddrSpaceToken(toks[1], &parsedAddrSpace)
                && mailboxMemAddrSpaceSupportsCanonicalBinding(parsedAddrSpace)) {
                const auto bindingIt = mailboxMemBindings.find(parsedAddrSpace);
                if (bindingIt == mailboxMemBindings.end()) {
                    return mailboxError(lineNo,
                                        "unmapped canonical memory addr_space: " + toks[1]);
                }
                targetIt = arrayPreloadTargets.find(bindingIt->second.target_path);
                if (targetIt == arrayPreloadTargets.end()) {
                    return mailboxError(lineNo, "unknown mapped canonical memory target: "
                                                    + bindingIt->second.target_path);
                }
                memAddrSpace = parsedAddrSpace;
                memNamespace = mailboxMemAddrSpaceName(parsedAddrSpace);
                memKey = memNamespace + "[" + toks[2] + "]";
            } else {
                targetIt = arrayPreloadTargets.find(toks[1]);
                if (targetIt == arrayPreloadTargets.end()) {
                    return mailboxError(lineNo, "unknown memory namespace: " + toks[1]);
                }
            }
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_READ_MEM;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            cmd.addr_space = memAddrSpace;
            hybrid_debug_mailbox_u64_to_words(wordIndex, &cmd.addr_lo, &cmd.addr_hi);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "READ_MEM queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("READ_MEM failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            const uint64_t value = hybrid_debug_mailbox_u64_from_words(rsp.arg0, rsp.arg1);
            std::string detail;
            emitMailboxTrace(seq, verb, "ok", memNamespace, memKey,
                             formatArrayPreloadHex(value, targetIt->second.word_bits),
                             mailboxLastStopReason(), 0, detail);
        } else if (verb == "WRITE_MEM") {
            if (toks.size() != 4) {
                return mailboxError(lineNo, "WRITE_MEM requires: namespace word_index value");
            }
            uint64_t wordIndex = 0;
            uint64_t valueRaw = 0;
            if (!parseU64(toks[2], &wordIndex)) {
                return mailboxError(lineNo, "invalid memory word index: " + toks[2]);
            }
            if (!parseU64(toks[3], &valueRaw)) {
                return mailboxError(lineNo, "invalid WRITE_MEM value: " + toks[3]);
            }
            auto targetIt = arrayPreloadTargets.end();
            uint32_t memAddrSpace = HYBRID_DEBUG_MAILBOX_ADDR_MEM_PHYS;
            std::string memNamespace = toks[1];
            std::string memKey = toks[1] + "[" + toks[2] + "]";
            uint32_t parsedAddrSpace = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
            if (parseMailboxMemAddrSpaceToken(toks[1], &parsedAddrSpace)
                && mailboxMemAddrSpaceSupportsCanonicalBinding(parsedAddrSpace)) {
                const auto bindingIt = mailboxMemBindings.find(parsedAddrSpace);
                if (bindingIt == mailboxMemBindings.end()) {
                    return mailboxError(lineNo,
                                        "unmapped canonical memory addr_space: " + toks[1]);
                }
                targetIt = arrayPreloadTargets.find(bindingIt->second.target_path);
                if (targetIt == arrayPreloadTargets.end()) {
                    return mailboxError(lineNo, "unknown mapped canonical memory target: "
                                                    + bindingIt->second.target_path);
                }
                memAddrSpace = parsedAddrSpace;
                memNamespace = mailboxMemAddrSpaceName(parsedAddrSpace);
                memKey = memNamespace + "[" + toks[2] + "]";
            } else {
                targetIt = arrayPreloadTargets.find(toks[1]);
                if (targetIt == arrayPreloadTargets.end()) {
                    return mailboxError(lineNo, "unknown memory namespace: " + toks[1]);
                }
            }
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            cmd.addr_space = memAddrSpace;
            hybrid_debug_mailbox_u64_to_words(wordIndex, &cmd.addr_lo, &cmd.addr_hi);
            hybrid_debug_mailbox_u64_to_words(valueRaw, &cmd.arg0, &cmd.arg1);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "WRITE_MEM queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("WRITE_MEM failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            const uint64_t committedValue = maskToWordBits(
                hybrid_debug_mailbox_u64_from_words(cmd.arg0, cmd.arg1), targetIt->second.word_bits);
            std::string detail;
            emitMailboxTrace(seq, verb, "ok", memNamespace, memKey,
                             formatArrayPreloadHex(committedValue, targetIt->second.word_bits),
                             mailboxLastStopReason(), 0, detail);
        } else if (verb == "SET_WATCHPOINT") {
            if (toks.size() != 3) return mailboxError(lineNo, "SET_WATCHPOINT requires: addr_space word_index");
            uint32_t memAddrSpace = HYBRID_DEBUG_MAILBOX_ADDR_NONE;
            if (!parseMailboxMemAddrSpaceToken(toks[1], &memAddrSpace)
                || !mailboxMemAddrSpaceSupportsCanonicalBinding(memAddrSpace)) {
                return mailboxError(lineNo, "unsupported watchpoint addr_space: " + toks[1]);
            }
            uint64_t wordIndex = 0;
            if (!parseU64(toks[2], &wordIndex)) {
                return mailboxError(lineNo, "invalid watchpoint word index: " + toks[2]);
            }
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_SET_WATCHPOINT;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            cmd.addr_space = memAddrSpace;
            hybrid_debug_mailbox_u64_to_words(wordIndex, &cmd.addr_lo, &cmd.addr_hi);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "SET_WATCHPOINT queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("SET_WATCHPOINT failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            emitMailboxTrace(seq, verb, "ok", mailboxMemAddrSpaceName(memAddrSpace),
                             std::string(mailboxMemAddrSpaceName(memAddrSpace)) + "[" + toks[2]
                                 + "]",
                             "-", mailboxLastStopReason(), 0, "");
        } else if (verb == "CLEAR_WATCHPOINT") {
            if (toks.size() != 1) return mailboxError(lineNo, "CLEAR_WATCHPOINT takes no arguments");
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_CLEAR_WATCHPOINT;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "CLEAR_WATCHPOINT queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("CLEAR_WATCHPOINT failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            emitMailboxTrace(seq, verb, "ok", "WATCHPOINT", "WATCHPOINT[0]", "-",
                             mailboxLastStopReason(), 0, "");
        } else if (verb == "SET_BREAKPOINT") {
            if (toks.size() != 2) return mailboxError(lineNo, "SET_BREAKPOINT requires: pc");
            uint64_t breakpointPc = 0;
            if (!parseU64(toks[1], &breakpointPc)) {
                return mailboxError(lineNo, "invalid breakpoint pc: " + toks[1]);
            }
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_SET_BREAKPOINT;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            hybrid_debug_mailbox_u64_to_words(breakpointPc, &cmd.addr_lo, &cmd.addr_hi);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "SET_BREAKPOINT queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("SET_BREAKPOINT failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            emitMailboxTrace(seq, verb, "ok", "DEBUG", "BREAKPOINT[0]",
                             formatArrayPreloadHex(breakpointPc, 64), mailboxLastStopReason(), 0,
                             "");
        } else if (verb == "CLEAR_BREAKPOINT") {
            if (toks.size() != 1) return mailboxError(lineNo, "CLEAR_BREAKPOINT takes no arguments");
            hybrid_debug_mailbox_command_t cmd{};
            cmd.opcode = HYBRID_DEBUG_MAILBOX_OP_CLEAR_BREAKPOINT;
            cmd.request_id = static_cast<uint32_t>(seq + 1);
            hybrid_debug_mailbox_response_t rsp{};
            hybrid_debug_mailbox_event_t ev{};
            if (!hybridDebugMailboxBenchExecuteQueuedCommand(&mailboxSession, cmd, &rsp, &ev)) {
                return mailboxError(lineNo, "CLEAR_BREAKPOINT queue execution failed");
            }
            if (rsp.status != HYBRID_DEBUG_MAILBOX_STATUS_OK) {
                return mailboxError(lineNo, std::string("CLEAR_BREAKPOINT failed: ")
                                                + hybrid_debug_mailbox_status_name(rsp.status));
            }
            emitMailboxTrace(seq, verb, "ok", "DEBUG", "BREAKPOINT[0]", "-",
                             mailboxLastStopReason(), 0, "");
        } else if (verb == "RUN_UNTIL_EVENT") {
            if (toks.size() < 3 || ((toks.size() - 1) % 2) != 0) {
                return mailboxError(lineNo, "RUN_UNTIL_EVENT requires key/value pairs");
            }
            uint64_t epochLimit = 0;
            uint64_t externalStopAt = 0;
            uint64_t timeoutAt = 0;
            bool haveEpochLimit = false;
            bool haveExternalStopAt = false;
            bool haveTimeoutAt = false;
            for (size_t idx = 1; idx + 1 < toks.size(); idx += 2) {
                if (toks[idx] == "EPOCH_LIMIT") {
                    if (!parseU64(toks[idx + 1], &epochLimit)) {
                        return mailboxError(lineNo, "invalid EPOCH_LIMIT: " + toks[idx + 1]);
                    }
                    haveEpochLimit = true;
                } else if (toks[idx] == "EXTERNAL_STOP_AT") {
                    if (!parseU64(toks[idx + 1], &externalStopAt)) {
                        return mailboxError(lineNo, "invalid EXTERNAL_STOP_AT: " + toks[idx + 1]);
                    }
                    haveExternalStopAt = true;
                } else if (toks[idx] == "TIMEOUT_AT") {
                    if (!parseU64(toks[idx + 1], &timeoutAt)) {
                        return mailboxError(lineNo, "invalid TIMEOUT_AT: " + toks[idx + 1]);
                    }
                    haveTimeoutAt = true;
                } else {
                    return mailboxError(lineNo, "unknown RUN_UNTIL_EVENT key: " + toks[idx]);
                }
            }
            if (!haveEpochLimit) return mailboxError(lineNo, "RUN_UNTIL_EVENT missing EPOCH_LIMIT");
            HybridDebugMailboxRunUntilEventArgs runArgs;
            runArgs.epoch_limit = epochLimit;
            runArgs.external_stop_at = haveExternalStopAt ? externalStopAt : UINT64_MAX;
            runArgs.timeout_at = haveTimeoutAt ? timeoutAt : UINT64_MAX;
            runArgs.cycle_delta_per_epoch = 1;
            runArgs.pc_delta_per_epoch = 4;
            uint64_t epochsExecuted = 0;
            const bool runOk = hybridDebugMailboxRunUntilEvent(
                &mailboxSession, runArgs,
                [&](HybridDebugMailboxEpochStepResult* stepResult,
                    HybridDebugMailboxFaultDetail* faultDetailp) -> bool {
                    std::vector<SimAccelValue> nextState;
                    if (!runMailboxHybridPass(currentState, &nextState, faultDetailp)) return false;
                    currentState.swap(nextState);
                    if (stepResult) {
                        stepResult->cycle_delta = 1;
                        stepResult->pc_delta = 4;
                        stepResult->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
                    }
                    return true;
                },
                &epochsExecuted);
            if (!runOk) return mailboxError(lineNo, "RUN_UNTIL_EVENT helper failed");
            std::string detail = "epoch_limit=" + std::to_string(epochLimit);
            if (haveExternalStopAt) detail += ",external_stop_at=" + std::to_string(externalStopAt);
            if (haveTimeoutAt) detail += ",timeout_at=" + std::to_string(timeoutAt);
            if (mailboxSession.state.last_stop_reason == HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT) {
                detail += ",breakpoint_pc=" + formatArrayPreloadHex(mailboxSession.state.pc, 64);
            } else if (mailboxSession.state.last_stop_reason == HYBRID_DEBUG_MAILBOX_STOP_FAULT) {
                detail += "," + formatHybridDebugMailboxFaultDetail(mailboxSession.last_fault);
            }
            emitMailboxTrace(seq, verb, "ok", "-", "-", "-", mailboxLastStopReason(),
                             epochsExecuted, detail);
        } else if (verb == "GET_STOP_REASON") {
            if (toks.size() != 1) return mailboxError(lineNo, "GET_STOP_REASON takes no arguments");
            const std::string detail
                = mailboxSession.state.last_stop_reason == HYBRID_DEBUG_MAILBOX_STOP_FAULT
                      ? formatHybridDebugMailboxFaultDetail(mailboxSession.last_fault)
                      : "";
            emitMailboxTrace(seq, verb, "ok", "-", "-", "-", mailboxLastStopReason(), 0, detail);
        } else {
            return mailboxError(lineNo, "unknown mailbox verb: " + verb);
        }
    }

    std::cout << "mailbox_trace_tsv=mailbox_trace.tsv\n";
    std::cout << "mailbox_command_count=" << mailboxCommandCount << "\n";
    std::cout << "mailbox_last_stop_reason=" << mailboxLastStopReason() << "\n";
    std::cout << "mailbox_total_epochs=" << mailboxSession.total_epochs << "\n";
    std::cout << "mailbox_last_fault_kind="
              << hybridDebugMailboxFaultKindName(mailboxSession.last_fault.kind) << "\n";
    std::cout << "mailbox_last_fault_stage="
              << hybridDebugMailboxFaultStageName(mailboxSession.last_fault.stage) << "\n";
    std::cout << "mailbox_last_fault_code=" << mailboxSession.last_fault.code << "\n";
    std::cout << "mailbox_last_fault_aux0=" << mailboxSession.last_fault.aux0 << "\n";
    std::cout << "mailbox_last_fault_value0="
              << formatArrayPreloadHex(mailboxSession.last_fault.value0, 64) << "\n";
    std::cout << "mailbox_last_fault_value1="
              << formatArrayPreloadHex(mailboxSession.last_fault.value1, 64) << "\n";
    std::cout << "mailbox_reg_binding_count=" << mailboxRegBindings.size() << "\n";
    std::cout << "mailbox_mem_binding_count=" << mailboxMemBindings.size() << "\n";
    return 0;
}
