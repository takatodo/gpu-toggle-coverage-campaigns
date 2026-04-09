/**
 * tlul_fifo_sync_cpu_replay_host_probe.cpp — host probe for the no-port
 * tlul_fifo_sync replay wrapper.
 *
 * This is intentionally narrower than tlul_slice_host_probe.cpp:
 *   - the wrapper owns clk/reset through its timed coroutine
 *   - the host can only seed wrapper-local config fields and drain scheduled events
 *
 * The probe proves that the replay wrapper can be constructed, configured after
 * initial blocks, and dumped as a raw root image without sim-accel glue.
 */

#include <cstddef>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "Vtlul_fifo_sync_gpu_cov_cpu_replay_tb.h"
#include "Vtlul_fifo_sync_gpu_cov_cpu_replay_tb___024root.h"
#include "verilated.h"

namespace {

using Model = Vtlul_fifo_sync_gpu_cov_cpu_replay_tb;
using Root = Vtlul_fifo_sync_gpu_cov_cpu_replay_tb___024root;

constexpr int kMaxEventDrains = 100000;
constexpr const char* kTargetName = "tlul_fifo_sync_cpu_replay";

struct ProbeConfig {
  uint32_t clock_cycles = 6;
  std::string state_out;
  std::vector<std::pair<std::string, uint32_t>> sets;
};

struct ProbeSummary {
  bool constructor_ok = false;
  bool events_pending_after_init = false;
  uint32_t clock_cycles = 0;
  uint32_t event_drains = 0;
  uint64_t sim_time = 0;
  uint32_t root_size = 0;
  uint32_t cfg_valid = 0;
  uint32_t cfg_batch_length = 0;
  uint32_t cfg_signature_o = 0;
  uint32_t done_o = 0;
  uint32_t host_req_accepted_o = 0;
  uint32_t device_req_accepted_o = 0;
  uint32_t device_rsp_accepted_o = 0;
  uint32_t host_rsp_accepted_o = 0;
  uint32_t rsp_queue_overflow_o = 0;
  uint32_t progress_cycle_count_o = 0;
  uint32_t progress_signature_o = 0;
  uint32_t trace_metric_trace_step_o = 0;
  uint32_t trace_metric_trace_step_count_o = 0;
  uint32_t direct_req_done_q = 0;
  uint32_t direct_rsp_done_q = 0;
  uint32_t direct_trace_done_w = 0;
  uint32_t final_clk_i = 0;
  uint32_t final_reset_like_w = 0;
};

struct FieldDescriptor {
  const char* json_name = nullptr;
  std::ptrdiff_t offset = 0;
  size_t size = 0;
};

[[noreturn]] void fail(const std::string& message) {
  throw std::runtime_error(message);
}

uint32_t parse_u32(const char* flag, const char* value) {
  if (value == nullptr) fail(std::string("missing value for ") + flag);
  try {
    size_t consumed = 0;
    const std::string text(value);
    const unsigned long parsed = std::stoul(text, &consumed, 0);
    if (consumed != text.size()) fail(std::string("invalid integer for ") + flag + ": " + text);
    return static_cast<uint32_t>(parsed);
  } catch (const std::exception&) {
    fail(std::string("invalid integer for ") + flag + ": " + value);
  }
}

std::pair<std::string, uint32_t> parse_setting(const std::string& raw) {
  const size_t pos = raw.find('=');
  if (pos == std::string::npos || pos == 0U || pos + 1U >= raw.size()) {
    fail(std::string("bad --set argument: ") + raw + " (want field=value)");
  }
  return {raw.substr(0, pos), parse_u32("--set", raw.c_str() + pos + 1U)};
}

ProbeConfig parse_args(int argc, char** argv) {
  ProbeConfig cfg;
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    if (arg == "--clock-cycles") {
      cfg.clock_cycles = parse_u32("--clock-cycles", (i + 1) < argc ? argv[++i] : nullptr);
      continue;
    }
    if (arg == "--state-out") {
      cfg.state_out = (i + 1) < argc ? argv[++i] : "";
      if (cfg.state_out.empty()) fail("missing value for --state-out");
      continue;
    }
    if (arg == "--set") {
      if ((i + 1) >= argc) fail("missing value for --set");
      cfg.sets.push_back(parse_setting(argv[++i]));
      continue;
    }
    if (arg == "--help" || arg == "-h") {
      std::cout
          << "Usage: tlul_fifo_sync_cpu_replay_host_probe [--clock-cycles N]\n"
          << "                                            [--set field=value ...]\n"
          << "                                            [--state-out path]\n";
      std::exit(0);
    }
    fail(std::string("unknown argument: ") + arg);
  }
  return cfg;
}

template <typename T>
void assign_u32(T& field, uint32_t value) {
  field = static_cast<T>(value);
}

template <typename T>
std::ptrdiff_t byte_offset(const Root* root, const T* field) {
  const auto* base = reinterpret_cast<const uint8_t*>(root);
  const auto* ptr = reinterpret_cast<const uint8_t*>(field);
  return ptr - base;
}

auto& cfg_valid(Root* root) { return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_valid; }
auto& cfg_batch_length(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_batch_length;
}
auto& cfg_req_valid_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_valid_pct;
}
auto& cfg_rsp_valid_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_valid_pct;
}
auto& cfg_host_d_ready_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_host_d_ready_pct;
}
auto& cfg_device_a_ready_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_device_a_ready_pct;
}
auto& cfg_put_full_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_put_full_pct;
}
auto& cfg_put_partial_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_put_partial_pct;
}
auto& cfg_req_fill_target(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_fill_target;
}
auto& cfg_req_burst_len_max(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_burst_len_max;
}
auto& cfg_req_family(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_family;
}
auto& cfg_req_address_mode(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_address_mode;
}
auto& cfg_req_data_mode(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_data_mode;
}
auto& cfg_req_data_hi_xor(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_req_data_hi_xor;
}
auto& cfg_access_ack_data_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_access_ack_data_pct;
}
auto& cfg_rsp_error_pct(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_error_pct;
}
auto& cfg_rsp_fill_target(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_fill_target;
}
auto& cfg_rsp_delay_max(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_delay_max;
}
auto& cfg_rsp_family(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_family;
}
auto& cfg_rsp_delay_mode(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_delay_mode;
}
auto& cfg_rsp_data_mode(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_data_mode;
}
auto& cfg_rsp_data_hi_xor(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_rsp_data_hi_xor;
}
auto& cfg_reset_cycles(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_reset_cycles;
}
auto& cfg_drain_cycles(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_drain_cycles;
}
auto& cfg_seed(Root* root) { return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_seed; }
auto& cfg_address_base(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_address_base;
}
auto& cfg_address_mask(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_address_mask;
}
auto& cfg_source_mask(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_source_mask;
}

auto& done(Root* root) { return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__done; }
auto& cfg_signature(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_signature;
}
auto& trace_metric_trace_step(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__trace_metric_trace_step;
}
auto& cycle_count_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__cycle_count_q;
}
auto& trace_step_count_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__trace_step_count_q;
}
auto& progress_signature_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__progress_signature_q;
}
auto& host_req_accepted_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_req_accepted_q;
}
auto& device_req_accepted_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_req_accepted_q;
}
auto& device_rsp_accepted_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_rsp_accepted_q;
}
auto& host_rsp_accepted_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_rsp_accepted_q;
}
auto& rsp_queue_overflow_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__rsp_queue_overflow_q;
}
auto& direct_req_done_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_req_done_q;
}
auto& direct_rsp_done_q(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_rsp_done_q;
}
auto& direct_trace_done_w(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_trace_done_w;
}
auto& clk_i(Root* root) { return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__clk_i; }
auto& reset_like_w(Root* root) {
  return root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__reset_like_w;
}

void configure_defaults(Root* root) {
  assign_u32(cfg_valid(root), 1U);
  assign_u32(cfg_batch_length(root), 256U);
  assign_u32(cfg_req_valid_pct(root), 65U);
  assign_u32(cfg_rsp_valid_pct(root), 70U);
  assign_u32(cfg_host_d_ready_pct(root), 75U);
  assign_u32(cfg_device_a_ready_pct(root), 80U);
  assign_u32(cfg_put_full_pct(root), 34U);
  assign_u32(cfg_put_partial_pct(root), 33U);
  assign_u32(cfg_req_fill_target(root), 2U);
  assign_u32(cfg_req_burst_len_max(root), 0U);
  assign_u32(cfg_req_family(root), 0U);
  assign_u32(cfg_req_address_mode(root), 0U);
  assign_u32(cfg_req_data_mode(root), 0U);
  assign_u32(cfg_req_data_hi_xor(root), 0U);
  assign_u32(cfg_access_ack_data_pct(root), 50U);
  assign_u32(cfg_rsp_error_pct(root), 10U);
  assign_u32(cfg_rsp_fill_target(root), 2U);
  assign_u32(cfg_rsp_delay_max(root), 4U);
  assign_u32(cfg_rsp_family(root), 0U);
  assign_u32(cfg_rsp_delay_mode(root), 0U);
  assign_u32(cfg_rsp_data_mode(root), 0U);
  assign_u32(cfg_rsp_data_hi_xor(root), 0U);
  assign_u32(cfg_reset_cycles(root), 4U);
  assign_u32(cfg_drain_cycles(root), 16U);
  assign_u32(cfg_seed(root), 1U);
  assign_u32(cfg_address_base(root), 0U);
  assign_u32(cfg_address_mask(root), 0x00000ffcU);
  assign_u32(cfg_source_mask(root), 0x000000ffU);
}

void apply_setting(Root* root, const std::string& name, uint32_t value) {
  if (name == "cfg_valid") assign_u32(cfg_valid(root), value);
  else if (name == "cfg_batch_length") assign_u32(cfg_batch_length(root), value);
  else if (name == "cfg_req_valid_pct") assign_u32(cfg_req_valid_pct(root), value);
  else if (name == "cfg_rsp_valid_pct") assign_u32(cfg_rsp_valid_pct(root), value);
  else if (name == "cfg_host_d_ready_pct") assign_u32(cfg_host_d_ready_pct(root), value);
  else if (name == "cfg_device_a_ready_pct") assign_u32(cfg_device_a_ready_pct(root), value);
  else if (name == "cfg_put_full_pct") assign_u32(cfg_put_full_pct(root), value);
  else if (name == "cfg_put_partial_pct") assign_u32(cfg_put_partial_pct(root), value);
  else if (name == "cfg_req_fill_target") assign_u32(cfg_req_fill_target(root), value);
  else if (name == "cfg_req_burst_len_max") assign_u32(cfg_req_burst_len_max(root), value);
  else if (name == "cfg_req_family") assign_u32(cfg_req_family(root), value);
  else if (name == "cfg_req_address_mode") assign_u32(cfg_req_address_mode(root), value);
  else if (name == "cfg_req_data_mode") assign_u32(cfg_req_data_mode(root), value);
  else if (name == "cfg_req_data_hi_xor") assign_u32(cfg_req_data_hi_xor(root), value);
  else if (name == "cfg_access_ack_data_pct") assign_u32(cfg_access_ack_data_pct(root), value);
  else if (name == "cfg_rsp_error_pct") assign_u32(cfg_rsp_error_pct(root), value);
  else if (name == "cfg_rsp_fill_target") assign_u32(cfg_rsp_fill_target(root), value);
  else if (name == "cfg_rsp_delay_max") assign_u32(cfg_rsp_delay_max(root), value);
  else if (name == "cfg_rsp_family") assign_u32(cfg_rsp_family(root), value);
  else if (name == "cfg_rsp_delay_mode") assign_u32(cfg_rsp_delay_mode(root), value);
  else if (name == "cfg_rsp_data_mode") assign_u32(cfg_rsp_data_mode(root), value);
  else if (name == "cfg_rsp_data_hi_xor") assign_u32(cfg_rsp_data_hi_xor(root), value);
  else if (name == "cfg_reset_cycles") assign_u32(cfg_reset_cycles(root), value);
  else if (name == "cfg_drain_cycles") assign_u32(cfg_drain_cycles(root), value);
  else if (name == "cfg_seed") assign_u32(cfg_seed(root), value);
  else if (name == "cfg_address_base") assign_u32(cfg_address_base(root), value);
  else if (name == "cfg_address_mask") assign_u32(cfg_address_mask(root), value);
  else if (name == "cfg_source_mask") assign_u32(cfg_source_mask(root), value);
  else fail(std::string("unsupported --set field: ") + name);
}

int run_scheduled_events(Model& model, VerilatedContext& context, uint32_t event_count) {
  int ran = 0;
  while (static_cast<uint32_t>(ran) < event_count) {
    if (!model.eventsPending()) fail("scheduler exhausted before requested event count");
    if (ran >= kMaxEventDrains) fail("scheduled event limit exceeded");
    const uint64_t next = model.nextTimeSlot();
    if (next < context.time()) fail("nextTimeSlot moved backwards");
    context.time(next);
    model.eval_step();
    ++ran;
  }
  return ran;
}

void write_state_file(const std::string& path, const Root* root) {
  std::ofstream out(path, std::ios::binary);
  if (!out) fail("failed to open --state-out for writing");
  out.write(reinterpret_cast<const char*>(root), sizeof(Root));
  if (!out) fail("failed to write --state-out");
}

std::vector<FieldDescriptor> collect_field_descriptors(const Root* root) {
  return {
      {"cfg_valid", byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_valid),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_valid)},
      {"cfg_batch_length",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_batch_length),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_batch_length)},
      {"done_o", byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__done),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__done)},
      {"cfg_signature_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_signature),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__cfg_signature)},
      {"host_req_accepted_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_req_accepted_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_req_accepted_q)},
      {"device_req_accepted_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_req_accepted_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_req_accepted_q)},
      {"device_rsp_accepted_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_rsp_accepted_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__device_rsp_accepted_q)},
      {"host_rsp_accepted_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_rsp_accepted_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__host_rsp_accepted_q)},
      {"rsp_queue_overflow_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__rsp_queue_overflow_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__rsp_queue_overflow_q)},
      {"progress_cycle_count_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__cycle_count_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__cycle_count_q)},
      {"progress_signature_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__progress_signature_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__progress_signature_q)},
      {"trace_metric_trace_step_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__trace_metric_trace_step),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__trace_metric_trace_step)},
      {"trace_metric_trace_step_count_o",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__trace_step_count_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__trace_step_count_q)},
      {"direct_req_done_q",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_req_done_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_req_done_q)},
      {"direct_rsp_done_q",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_rsp_done_q),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_rsp_done_q)},
      {"direct_trace_done_w",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_trace_done_w),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__core__DOT__direct_trace_done_w)},
      {"clk_i",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__clk_i),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__clk_i)},
      {"reset_like_w",
       byte_offset(root, &root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__reset_like_w),
       sizeof(root->tlul_fifo_sync_gpu_cov_cpu_replay_tb__DOT__dut__DOT__reset_like_w)},
  };
}

void emit_field_offsets(const std::vector<FieldDescriptor>& fields) {
  std::cout << "  \"field_offsets\": {\n";
  for (size_t i = 0; i < fields.size(); ++i) {
    const auto& field = fields[i];
    std::cout << "    \"" << field.json_name << "\": " << field.offset;
    if (i + 1U < fields.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  },\n";
}

void emit_field_sizes(const std::vector<FieldDescriptor>& fields) {
  std::cout << "  \"field_sizes\": {\n";
  for (size_t i = 0; i < fields.size(); ++i) {
    const auto& field = fields[i];
    std::cout << "    \"" << field.json_name << "\": " << field.size;
    if (i + 1U < fields.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  },\n";
}

void emit_watch_field_names() {
  std::cout << "  \"watch_field_names\": [\n"
            << "    \"trace_metric_trace_step_o\",\n"
            << "    \"trace_metric_trace_step_count_o\",\n"
            << "    \"direct_req_done_q\",\n"
            << "    \"direct_rsp_done_q\",\n"
            << "    \"direct_trace_done_w\"\n"
            << "  ],\n";
}

void emit_summary(const ProbeSummary& summary, const Root* root) {
  const auto fields = collect_field_descriptors(root);
  std::cout << "{\n";
  std::cout << "  \"target\": \"" << kTargetName << "\",\n";
  std::cout << "  \"wrapper_top\": \"tlul_fifo_sync_gpu_cov_cpu_replay_tb\",\n";
  std::cout << "  \"constructor_ok\": " << (summary.constructor_ok ? "true" : "false") << ",\n";
  std::cout << "  \"host_clock_control\": false,\n";
  std::cout << "  \"host_reset_control\": false,\n";
  std::cout << "  \"events_pending_after_init\": "
            << (summary.events_pending_after_init ? "true" : "false") << ",\n";
  std::cout << "  \"clock_cycles\": " << summary.clock_cycles << ",\n";
  std::cout << "  \"event_drains\": " << summary.event_drains << ",\n";
  std::cout << "  \"sim_time\": " << summary.sim_time << ",\n";
  std::cout << "  \"root_size\": " << summary.root_size << ",\n";
  emit_field_offsets(fields);
  emit_field_sizes(fields);
  emit_watch_field_names();
  std::cout << "  \"cfg_valid\": " << summary.cfg_valid << ",\n";
  std::cout << "  \"cfg_batch_length\": " << summary.cfg_batch_length << ",\n";
  std::cout << "  \"cfg_signature_o\": " << summary.cfg_signature_o << ",\n";
  std::cout << "  \"done_o\": " << summary.done_o << ",\n";
  std::cout << "  \"host_req_accepted_o\": " << summary.host_req_accepted_o << ",\n";
  std::cout << "  \"device_req_accepted_o\": " << summary.device_req_accepted_o << ",\n";
  std::cout << "  \"device_rsp_accepted_o\": " << summary.device_rsp_accepted_o << ",\n";
  std::cout << "  \"host_rsp_accepted_o\": " << summary.host_rsp_accepted_o << ",\n";
  std::cout << "  \"rsp_queue_overflow_o\": " << summary.rsp_queue_overflow_o << ",\n";
  std::cout << "  \"progress_cycle_count_o\": " << summary.progress_cycle_count_o << ",\n";
  std::cout << "  \"progress_signature_o\": " << summary.progress_signature_o << ",\n";
  std::cout << "  \"trace_metric_trace_step_o\": " << summary.trace_metric_trace_step_o << ",\n";
  std::cout << "  \"trace_metric_trace_step_count_o\": "
            << summary.trace_metric_trace_step_count_o << ",\n";
  std::cout << "  \"direct_req_done_q\": " << summary.direct_req_done_q << ",\n";
  std::cout << "  \"direct_rsp_done_q\": " << summary.direct_rsp_done_q << ",\n";
  std::cout << "  \"direct_trace_done_w\": " << summary.direct_trace_done_w << ",\n";
  std::cout << "  \"final_clk_i\": " << summary.final_clk_i << ",\n";
  std::cout << "  \"final_reset_like_w\": " << summary.final_reset_like_w << "\n";
  std::cout << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const ProbeConfig cfg = parse_args(argc, argv);

    VerilatedContext context;
    context.randReset(0);
    context.quiet(true);
    context.time(0);
    context.commandArgs(argc, argv);

    Model model(&context, "tlul_fifo_sync_gpu_cov_cpu_replay_tb");
    Root* const root = model.rootp;

    ProbeSummary summary;
    summary.constructor_ok = true;
    summary.clock_cycles = cfg.clock_cycles;
    summary.root_size = static_cast<uint32_t>(sizeof(Root));

    model.eval_step();
    summary.events_pending_after_init = model.eventsPending();
    if (!summary.events_pending_after_init) {
      fail("cpu replay wrapper did not schedule timed events after initial eval");
    }

    configure_defaults(root);
    for (const auto& entry : cfg.sets) {
      apply_setting(root, entry.first, entry.second);
    }
    model.eval_step();

    const uint32_t event_budget = cfg.clock_cycles * 2U;
    summary.event_drains = static_cast<uint32_t>(run_scheduled_events(model, context, event_budget));
    summary.sim_time = context.time();

    if (!cfg.state_out.empty()) {
      write_state_file(cfg.state_out, root);
    }

    summary.cfg_valid = cfg_valid(root);
    summary.cfg_batch_length = cfg_batch_length(root);
    summary.cfg_signature_o = cfg_signature(root);
    summary.done_o = done(root);
    summary.host_req_accepted_o = host_req_accepted_q(root);
    summary.device_req_accepted_o = device_req_accepted_q(root);
    summary.device_rsp_accepted_o = device_rsp_accepted_q(root);
    summary.host_rsp_accepted_o = host_rsp_accepted_q(root);
    summary.rsp_queue_overflow_o = rsp_queue_overflow_q(root);
    summary.progress_cycle_count_o = cycle_count_q(root);
    summary.progress_signature_o = progress_signature_q(root);
    summary.trace_metric_trace_step_o = trace_metric_trace_step(root);
    summary.trace_metric_trace_step_count_o = trace_step_count_q(root);
    summary.direct_req_done_q = direct_req_done_q(root);
    summary.direct_rsp_done_q = direct_rsp_done_q(root);
    summary.direct_trace_done_w = direct_trace_done_w(root);
    summary.final_clk_i = clk_i(root);
    summary.final_reset_like_w = reset_like_w(root);

    emit_summary(summary, root);
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
}
