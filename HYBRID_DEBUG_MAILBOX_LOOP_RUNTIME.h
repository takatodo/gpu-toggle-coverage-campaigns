#pragma once

// This header expects HybridDebugMailboxRuntimeSession and fault/session helpers
// to be fully defined by the includer.

static inline void hybridDebugMailboxFaultDetailPackEvent(
    const HybridDebugMailboxFaultDetail& detail, hybrid_debug_mailbox_event_t* eventp) {
    if (!eventp) return;
    eventp->arg0 = detail.kind;
    eventp->arg1 = detail.stage;
    eventp->reserved0 = detail.code;
    eventp->reserved1 = detail.aux0;
    hybrid_debug_mailbox_u64_to_words(detail.value0, &eventp->reserved2, &eventp->reserved3);
}

static inline hybrid_debug_mailbox_event_t hybridDebugMailboxRuntimeMakeFaultEvent(
    const HybridDebugMailboxRuntimeSession* sessionp) {
    hybrid_debug_mailbox_event_t event{};
    event.event_type = HYBRID_DEBUG_MAILBOX_EVENT_FAULT;
    event.stop_reason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
    if (sessionp) {
        event.arg0 = sessionp->last_fault.kind;
        event.arg1 = sessionp->last_fault.stage;
        event.reserved0 = sessionp->last_fault.code;
        event.reserved1 = sessionp->last_fault.aux0;
        hybrid_debug_mailbox_u64_to_words(sessionp->last_fault.value0, &event.reserved2,
                                          &event.reserved3);
    }
    return event;
}

static inline void hybridDebugMailboxRuntimeBuildFaultReply(
    const hybrid_debug_mailbox_command_t* cmdp, const HybridDebugMailboxFaultDetail& detail,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp) {
    if (rspp) {
        *rspp = hybrid_debug_mailbox_mock_make_response(cmdp, HYBRID_DEBUG_MAILBOX_STATUS_FAULT);
    }
    if (eventp) {
        memset(eventp, 0, sizeof(*eventp));
        eventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_FAULT;
        eventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
        hybridDebugMailboxFaultDetailPackEvent(detail, eventp);
    }
}

static inline void hybridDebugMailboxRuntimeBuildSessionFaultReply(
    const HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t* cmdp,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp) {
    HybridDebugMailboxFaultDetail detail{};
    if (sessionp) {
        detail = sessionp->last_fault;
    } else {
        hybridDebugMailboxFaultDetailClear(&detail);
    }
    hybridDebugMailboxRuntimeBuildFaultReply(cmdp, detail, rspp, eventp);
}

static inline uint64_t hybridDebugMailboxDecodeOptionalLimit(uint32_t lo, uint32_t hi) {
    const uint64_t value = hybrid_debug_mailbox_u64_from_words(lo, hi);
    return value == UINT64_MAX ? UINT64_MAX : value;
}

static inline uint32_t hybridDebugMailboxClassifyStopEventType(uint32_t stopReason) {
    switch (stopReason) {
    case HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT:
        return HYBRID_DEBUG_MAILBOX_EVENT_BREAKPOINT;
    case HYBRID_DEBUG_MAILBOX_STOP_WATCHPOINT_HIT:
        return HYBRID_DEBUG_MAILBOX_EVENT_WATCHPOINT;
    case HYBRID_DEBUG_MAILBOX_STOP_FAULT:
        return HYBRID_DEBUG_MAILBOX_EVENT_FAULT;
    case HYBRID_DEBUG_MAILBOX_STOP_NONE:
        return HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    default:
        return HYBRID_DEBUG_MAILBOX_EVENT_STOP;
    }
}

template <typename StepFn>
static inline bool hybridDebugMailboxRunUntilEvent(HybridDebugMailboxRuntimeSession* sessionp,
                                                   const HybridDebugMailboxRunUntilEventArgs& args,
                                                   StepFn&& stepFn,
                                                   uint64_t* epochsExecutedOut) {
    if (!sessionp) return false;
    hybridDebugMailboxRuntimeSessionClearFault(sessionp);
    uint64_t epochsExecuted = 0;
    const uint64_t startCycleCount = sessionp->state.cycle_count;
    uint32_t stopReason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    for (uint64_t epoch = 0; epoch < args.epoch_limit; ++epoch) {
        const uint64_t elapsedCycles = sessionp->state.cycle_count - startCycleCount;
        if (args.timeout_at != UINT64_MAX && elapsedCycles >= args.timeout_at) {
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_TIMEOUT;
            break;
        }
        if (args.external_stop_at != UINT64_MAX && epochsExecuted >= args.external_stop_at) {
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_EXTERNAL_STOP;
            break;
        }
        HybridDebugMailboxEpochStepResult step{};
        HybridDebugMailboxFaultDetail fault{};
        hybridDebugMailboxFaultDetailClear(&fault);
        if (!stepFn(&step, &fault)) {
            if (fault.kind == HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
                fault = hybridDebugMailboxCommunicationFaultDetail(
                    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME, 0U, 0U,
                    sessionp->state.cycle_count, sessionp->state.pc);
            }
            hybridDebugMailboxRuntimeSessionSetFaultDetail(sessionp, fault);
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
            break;
        }
        const uint64_t cycleDelta
            = step.cycle_delta != 0 ? step.cycle_delta : args.cycle_delta_per_epoch;
        const uint64_t pcDelta = step.pc_delta != 0 ? step.pc_delta : args.pc_delta_per_epoch;
        sessionp->state.cycle_count += cycleDelta;
        sessionp->state.pc += pcDelta;
        epochsExecuted += 1;
        sessionp->total_epochs += 1;
        sessionp->state.total_epochs = sessionp->total_epochs;
        hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);
        if (step.stop_reason != HYBRID_DEBUG_MAILBOX_STOP_NONE) {
            stopReason = step.stop_reason;
            break;
        }
        if (sessionp->state.breakpoint_enabled
            && sessionp->state.pc == sessionp->state.breakpoint_pc) {
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_BREAKPOINT_HIT;
            break;
        }
        if (args.timeout_at != UINT64_MAX
            && (sessionp->state.cycle_count - startCycleCount) >= args.timeout_at) {
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_TIMEOUT;
            break;
        }
    }
    if (stopReason == HYBRID_DEBUG_MAILBOX_STOP_NONE) {
        stopReason = HYBRID_DEBUG_MAILBOX_STOP_EPOCH_LIMIT;
    }
    sessionp->state.last_stop_reason = stopReason;
    sessionp->state.total_epochs = sessionp->total_epochs;
    hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);
    if (epochsExecutedOut) *epochsExecutedOut = epochsExecuted;
    return true;
}

template <typename StepFn>
static inline bool hybridDebugMailboxRuntimeExecuteRunCycles(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t& cmd,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    StepFn&& stepFn) {
    if (!sessionp || !rspp || !eventp) return false;
    *rspp = hybrid_debug_mailbox_mock_make_response(&cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    memset(eventp, 0, sizeof(*eventp));
    eventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    eventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;

    hybridDebugMailboxRuntimeSessionClearFault(sessionp);
    const uint64_t targetCycles = hybrid_debug_mailbox_u64_from_words(cmd.arg0, cmd.arg1);
    const uint64_t startCycleCount = sessionp->state.cycle_count;
    uint32_t stopReason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    uint64_t epochsExecuted = 0;

    while ((sessionp->state.cycle_count - startCycleCount) < targetCycles) {
        HybridDebugMailboxEpochStepResult step{};
        HybridDebugMailboxFaultDetail fault{};
        hybridDebugMailboxFaultDetailClear(&fault);
        if (!stepFn(&step, &fault)) {
            if (fault.kind == HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
                fault = hybridDebugMailboxCommunicationFaultDetail(
                    HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME, 0U, 0U,
                    sessionp->state.cycle_count, sessionp->state.pc);
            }
            hybridDebugMailboxRuntimeSessionSetFaultDetail(sessionp, fault);
            stopReason = HYBRID_DEBUG_MAILBOX_STOP_FAULT;
            break;
        }

        const uint64_t cycleDelta = step.cycle_delta != 0 ? step.cycle_delta : 1ULL;
        const uint64_t pcDelta = step.pc_delta;
        sessionp->state.cycle_count += cycleDelta;
        sessionp->state.pc += pcDelta;
        epochsExecuted += 1;
        sessionp->total_epochs += 1;
        sessionp->state.total_epochs = sessionp->total_epochs;
        hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);

        if (step.stop_reason != HYBRID_DEBUG_MAILBOX_STOP_NONE) {
            stopReason = step.stop_reason;
            break;
        }
    }

    if (stopReason == HYBRID_DEBUG_MAILBOX_STOP_NONE) {
        stopReason = HYBRID_DEBUG_MAILBOX_STOP_RUN_CYCLES_DONE;
    }
    sessionp->state.last_stop_reason = stopReason;
    sessionp->state.total_epochs = sessionp->total_epochs;
    hybrid_debug_mailbox_mock_refresh_arch_state(&sessionp->state);

    const uint64_t cyclesExecuted = sessionp->state.cycle_count - startCycleCount;
    hybrid_debug_mailbox_u64_to_words(cyclesExecuted, &rspp->arg0, &rspp->arg1);
    rspp->size_bytes = 8;
    if (stopReason == HYBRID_DEBUG_MAILBOX_STOP_FAULT) {
        hybridDebugMailboxRuntimeBuildSessionFaultReply(sessionp, &cmd, rspp, eventp);
        hybrid_debug_mailbox_u64_to_words(cyclesExecuted, &rspp->arg0, &rspp->arg1);
        rspp->size_bytes = 8;
        return true;
    }

    *eventp = hybrid_debug_mailbox_mock_make_stop_event(
        &sessionp->state, hybridDebugMailboxClassifyStopEventType(stopReason), stopReason);
    return true;
}

template <typename StepFn>
static inline bool hybridDebugMailboxRuntimeExecuteRunUntilEvent(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t& cmd,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp,
    StepFn&& stepFn) {
    if (!sessionp || !rspp || !eventp) return false;
    *rspp = hybrid_debug_mailbox_mock_make_response(&cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    memset(eventp, 0, sizeof(*eventp));
    eventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    eventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;

    HybridDebugMailboxRunUntilEventArgs args{};
    args.epoch_limit = cmd.arg0;
    args.cycle_delta_per_epoch = cmd.arg1 != 0 ? cmd.arg1 : 1;
    args.external_stop_at = hybridDebugMailboxDecodeOptionalLimit(cmd.addr_lo, cmd.addr_hi);
    args.timeout_at = hybridDebugMailboxDecodeOptionalLimit(cmd.reserved0, cmd.reserved1);
    const uint64_t pcDelta
        = hybrid_debug_mailbox_u64_from_words(cmd.reserved2, cmd.reserved3);
    if (pcDelta != 0) {
        args.pc_delta_per_epoch = pcDelta;
    } else if (hybridDebugMailboxRuntimeSessionFindRegBindingConst(
                   sessionp, HYBRID_DEBUG_MAILBOX_ADDR_REG_DEBUG,
                   HYBRID_DEBUG_MAILBOX_DEBUG_REG_PC)) {
        args.pc_delta_per_epoch = 0;
    } else {
        args.pc_delta_per_epoch = 4;
    }

    uint64_t epochsExecuted = 0;
    const bool ok = hybridDebugMailboxRunUntilEvent(sessionp, args, stepFn, &epochsExecuted);
    hybrid_debug_mailbox_u64_to_words(epochsExecuted, &rspp->arg0, &rspp->arg1);
    rspp->size_bytes = 8;

    const uint32_t stopReason = sessionp->state.last_stop_reason;
    if (!ok || stopReason == HYBRID_DEBUG_MAILBOX_STOP_FAULT) {
        hybridDebugMailboxRuntimeBuildSessionFaultReply(sessionp, &cmd, rspp, eventp);
        hybrid_debug_mailbox_u64_to_words(epochsExecuted, &rspp->arg0, &rspp->arg1);
        rspp->size_bytes = 8;
        return true;
    } else if (stopReason == HYBRID_DEBUG_MAILBOX_STOP_TIMEOUT) {
        rspp->status = HYBRID_DEBUG_MAILBOX_STATUS_TIMEOUT;
    }

    *eventp = hybrid_debug_mailbox_mock_make_stop_event(
        &sessionp->state, hybridDebugMailboxClassifyStopEventType(stopReason), stopReason);
    return true;
}

template <typename StepFn>
static inline bool hybridDebugMailboxRuntimeExecuteCommand(
    HybridDebugMailboxRuntimeSession* sessionp, const hybrid_debug_mailbox_command_t& cmd,
    hybrid_debug_mailbox_response_t* rspp, hybrid_debug_mailbox_event_t* eventp, StepFn&& stepFn) {
    if (!sessionp || !rspp || !eventp) return false;
    hybrid_debug_mailbox_response_t rsp{};
    hybrid_debug_mailbox_event_t ev{};
    int haveEvent = 0;
    sessionp->dispatch_busy = 1;

    if (cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_NOP) {
        rsp = hybrid_debug_mailbox_mock_make_response(&cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
    } else if (cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_RUN_CYCLES) {
        if (!hybridDebugMailboxRuntimeExecuteRunCycles(sessionp, cmd, &rsp, &ev, stepFn)) {
            sessionp->dispatch_busy = 0;
            return -1;
        }
        haveEvent = ev.event_type != HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    } else if (cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_RUN_UNTIL_EVENT) {
        if (!hybridDebugMailboxRuntimeExecuteRunUntilEvent(sessionp, cmd, &rsp, &ev, stepFn)) {
            sessionp->dispatch_busy = 0;
            return -1;
        }
        haveEvent = ev.event_type != HYBRID_DEBUG_MAILBOX_EVENT_NONE;
    } else if (cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_GET_STOP_REASON) {
        rsp = hybrid_debug_mailbox_mock_make_response(&cmd, HYBRID_DEBUG_MAILBOX_STATUS_OK);
        rsp.arg0 = sessionp->state.last_stop_reason;
        hybrid_debug_mailbox_u64_to_words(sessionp->state.cycle_count, &rsp.arg1, &rsp.size_bytes);
    } else if ((cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_READ_REG
                || cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_WRITE_REG)
               && sessionp->reg_dispatch_hookp) {
        const int hookRc
            = sessionp->reg_dispatch_hookp(sessionp, &cmd, &rsp, &ev, &haveEvent);
        if (hookRc < 0) {
            sessionp->dispatch_busy = 0;
            return -1;
        }
        if (hookRc == 0) {
            if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, &sessionp->state, &rsp, &ev,
                                                            &haveEvent)
                < 0) {
                sessionp->dispatch_busy = 0;
                return false;
            }
        }
    } else if ((cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_READ_MEM
                || cmd.opcode == HYBRID_DEBUG_MAILBOX_OP_WRITE_MEM)
               && sessionp->mem_dispatch_hookp) {
        const int hookRc
            = sessionp->mem_dispatch_hookp(sessionp, &cmd, &rsp, &ev, &haveEvent);
        if (hookRc < 0) {
            sessionp->dispatch_busy = 0;
            return -1;
        }
        if (hookRc == 0) {
            if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, &sessionp->state, &rsp, &ev,
                                                            &haveEvent)
                < 0) {
                sessionp->dispatch_busy = 0;
                return false;
            }
        }
    } else {
        if (hybrid_debug_mailbox_mock_execute_immediate(&cmd, &sessionp->state, &rsp, &ev,
                                                        &haveEvent)
            < 0) {
            sessionp->dispatch_busy = 0;
            return false;
        }
    }

    sessionp->dispatch_busy = 0;
    *rspp = rsp;
    *eventp = haveEvent ? ev : hybrid_debug_mailbox_mock_make_stop_event(
                                       &sessionp->state, HYBRID_DEBUG_MAILBOX_EVENT_NONE,
                                       HYBRID_DEBUG_MAILBOX_STOP_NONE);
    if (!haveEvent) {
        eventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
        eventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    }
    return true;
}

template <typename StepFn>
static inline uint32_t hybridDebugMailboxRuntimeMainLoop(HybridDebugMailboxRuntimeSession* sessionp,
                                                         uint32_t maxCommands,
                                                         bool stopOnEvent,
                                                         bool consumeStopEvent,
                                                         hybrid_debug_mailbox_event_t* stopEventp,
                                                         bool faultOnBackpressure,
                                                         bool faultOnExecuteFailure,
                                                         StepFn&& stepFn) {
    if (!sessionp) return 0;
    if (stopEventp) {
        memset(stopEventp, 0, sizeof(*stopEventp));
        stopEventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
        stopEventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    }
    const uint32_t limit = maxCommands == 0 ? UINT32_MAX : maxCommands;
    uint32_t processed = 0;
    while (processed < limit) {
        if (hybrid_debug_mailbox_ring_full(&sessionp->layout.response_ring)) {
            if (faultOnBackpressure) {
                hybridDebugMailboxRuntimeSessionSetFaultDetail(
                    sessionp, hybridDebugMailboxCommunicationFaultDetail(
                                  HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H, 1U,
                                  hybrid_debug_mailbox_ring_count(
                                      &sessionp->layout.response_ring),
                                  hybrid_debug_mailbox_ring_count(
                                      &sessionp->layout.command_ring),
                                  0ULL));
            }
            break;
        }
        if (hybrid_debug_mailbox_ring_full(&sessionp->layout.event_ring)) {
            if (faultOnBackpressure) {
                hybridDebugMailboxRuntimeSessionSetFaultDetail(
                    sessionp, hybridDebugMailboxCommunicationFaultDetail(
                                  HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H, 2U,
                                  hybrid_debug_mailbox_ring_count(&sessionp->layout.event_ring),
                                  hybrid_debug_mailbox_ring_count(
                                      &sessionp->layout.command_ring),
                                  0ULL));
            }
            break;
        }

        hybrid_debug_mailbox_command_t cmd{};
        if (!hybrid_debug_mailbox_pop_command(&sessionp->layout.command_ring,
                                              sessionp->command_entries, &cmd)) {
            break;
        }

        hybrid_debug_mailbox_response_t rsp{};
        hybrid_debug_mailbox_event_t ev{};
        if (!hybridDebugMailboxRuntimeExecuteCommand(sessionp, cmd, &rsp, &ev, stepFn)) {
            if (faultOnExecuteFailure
                && sessionp->last_fault.kind == HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
                hybridDebugMailboxRuntimeSessionSetFaultDetail(
                    sessionp, hybridDebugMailboxCommunicationFaultDetail(
                                  HYBRID_DEBUG_MAILBOX_FAULT_STAGE_RUNTIME, 3U, cmd.opcode,
                                  cmd.request_id, 0ULL));
            }
            break;
        }
        if (ev.event_type != HYBRID_DEBUG_MAILBOX_EVENT_NONE) {
            if (!hybrid_debug_mailbox_push_event(&sessionp->layout.event_ring,
                                                 sessionp->event_entries, &ev)) {
                if (faultOnBackpressure) {
                    hybridDebugMailboxRuntimeSessionSetFaultDetail(
                        sessionp, hybridDebugMailboxCommunicationFaultDetail(
                                      HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H, 4U,
                                      ev.event_type, cmd.request_id, ev.stop_reason));
                }
                break;
            }
        }
        if (!hybrid_debug_mailbox_push_response(&sessionp->layout.response_ring,
                                                sessionp->response_entries, &rsp)) {
            if (faultOnBackpressure) {
                hybridDebugMailboxRuntimeSessionSetFaultDetail(
                    sessionp, hybridDebugMailboxCommunicationFaultDetail(
                                  HYBRID_DEBUG_MAILBOX_FAULT_STAGE_D2H, 5U, rsp.status,
                                  cmd.request_id,
                                  hybrid_debug_mailbox_ring_count(
                                      &sessionp->layout.response_ring)));
            }
            break;
        }
        processed += 1;
        if (stopOnEvent && ev.event_type != HYBRID_DEBUG_MAILBOX_EVENT_NONE) {
            if (consumeStopEvent && stopEventp) {
                hybrid_debug_mailbox_pop_event(&sessionp->layout.event_ring,
                                               sessionp->event_entries, stopEventp);
            }
            break;
        }
    }
    if (sessionp->last_fault.kind != HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
        if (stopEventp && stopEventp->event_type == HYBRID_DEBUG_MAILBOX_EVENT_NONE) {
            *stopEventp = hybridDebugMailboxRuntimeMakeFaultEvent(sessionp);
        }
    }
    return processed;
}

template <typename StepFn>
static inline uint32_t hybridDebugMailboxRuntimeDispatch(HybridDebugMailboxRuntimeSession* sessionp,
                                                         uint32_t maxCommands, StepFn&& stepFn) {
    return hybridDebugMailboxRuntimeMainLoop(sessionp, maxCommands, false, false, nullptr, true,
                                             true, stepFn);
}

template <typename StepFn>
static inline uint32_t hybridDebugMailboxRuntimeServe(HybridDebugMailboxRuntimeSession* sessionp,
                                                      uint32_t maxCommands,
                                                      bool stopOnEvent, StepFn&& stepFn) {
    return hybridDebugMailboxRuntimeMainLoop(sessionp, maxCommands, stopOnEvent, false, nullptr,
                                             true, true, stepFn);
}

template <typename StepFn>
static inline uint32_t hybridDebugMailboxRuntimeServeUntilEvent(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t maxCommands,
    hybrid_debug_mailbox_event_t* stopEventp, StepFn&& stepFn) {
    return hybridDebugMailboxRuntimeMainLoop(sessionp, maxCommands, true, true, stopEventp, true,
                                             true, stepFn);
}

template <typename StepFn>
static inline uint32_t hybridDebugMailboxRuntimeRunLoop(
    HybridDebugMailboxRuntimeSession* sessionp, uint32_t maxCommands,
    hybrid_debug_mailbox_event_t* stopEventp, StepFn&& stepFn) {
    if (!sessionp) return 0;
    if (stopEventp) {
        memset(stopEventp, 0, sizeof(*stopEventp));
        stopEventp->event_type = HYBRID_DEBUG_MAILBOX_EVENT_NONE;
        stopEventp->stop_reason = HYBRID_DEBUG_MAILBOX_STOP_NONE;
    }
    const uint32_t limit = maxCommands == 0 ? UINT32_MAX : maxCommands;
    uint32_t totalProcessed = 0;
    while (totalProcessed < limit) {
        const uint32_t remaining = limit - totalProcessed;
        hybrid_debug_mailbox_event_t loopEvent{};
        const uint32_t processed = hybridDebugMailboxRuntimeMainLoop(
            sessionp, remaining, true, true, &loopEvent, true, true, stepFn);
        totalProcessed += processed;
        if (loopEvent.event_type != HYBRID_DEBUG_MAILBOX_EVENT_NONE) {
            if (stopEventp) *stopEventp = loopEvent;
            break;
        }
        if (sessionp->last_fault.kind != HYBRID_DEBUG_MAILBOX_FAULT_NONE) {
            if (stopEventp) *stopEventp = hybridDebugMailboxRuntimeMakeFaultEvent(sessionp);
            break;
        }
        if (processed == 0U) break;
        if (hybridDebugMailboxRuntimeSessionPendingCommands(sessionp) == 0U) break;
    }
    return totalProcessed;
}
