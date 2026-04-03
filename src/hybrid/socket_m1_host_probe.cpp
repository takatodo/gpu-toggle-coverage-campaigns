/**
 * socket_m1_host_probe.cpp — minimal Phase C host-side constructor/reset probe.
 *
 * This binary links against stock Verilator --cc output for tlul_socket_m1 and proves:
 *   - host-side construction works without sim-accel glue
 *   - root-layout offsets in host_abi.h still match the generated root type
 *   - rst_ni / clk_i can be driven from the host across a few cycles
 *
 * Expected usage is via src/tools/run_socket_m1_host_probe.py, which builds the generated
 * Verilator archive closure first and then links this file against it.
 */

#include <cstddef>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "Vtlul_socket_m1_gpu_cov_tb.h"
#include "Vtlul_socket_m1_gpu_cov_tb___024root.h"
#include "host_abi.h"

namespace {

using Model = Vtlul_socket_m1_gpu_cov_tb;
using Root = Vtlul_socket_m1_gpu_cov_tb___024root;

constexpr int kMaxEventDrains = 100000;

struct ProbeConfig {
  uint32_t reset_cycles = 4;
  uint32_t post_reset_cycles = 2;
  uint32_t batch_length = 1;
  uint32_t seed = 1;
  bool cfg_valid = true;
  std::string state_out;
};

struct OffsetCheck {
  const char* name;
  std::ptrdiff_t actual;
  std::ptrdiff_t expected;
};

struct ProbeSummary {
  bool constructor_ok = false;
  bool abi_ok = false;
  bool vl_symsp_bound = false;
  uint32_t reset_cycles = 0;
  uint32_t post_reset_cycles = 0;
  uint32_t batch_length = 0;
  uint32_t seed = 0;
  uint64_t sim_time = 0;
  int drained_events = 0;
  uint32_t cfg_signature_o = 0;
  uint32_t debug_reset_cycles_remaining_o = 0;
  uint32_t progress_cycle_count_o = 0;
  uint32_t debug_phase_o = 0;
  uint32_t toggle_bitmap_word0_o = 0;
  uint32_t toggle_bitmap_word1_o = 0;
  uint32_t toggle_bitmap_word2_o = 0;
  uint32_t done_o = 0;
  uint32_t final_clk_i = 0;
  uint32_t final_rst_ni = 0;
  uint32_t root_size = 0;
  std::vector<OffsetCheck> offsets;
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

ProbeConfig parse_args(int argc, char** argv) {
  ProbeConfig cfg;
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    if (arg == "--reset-cycles") {
      cfg.reset_cycles = parse_u32("--reset-cycles", (i + 1) < argc ? argv[++i] : nullptr);
      continue;
    }
    if (arg == "--post-reset-cycles") {
      cfg.post_reset_cycles =
          parse_u32("--post-reset-cycles", (i + 1) < argc ? argv[++i] : nullptr);
      continue;
    }
    if (arg == "--batch-length") {
      cfg.batch_length = parse_u32("--batch-length", (i + 1) < argc ? argv[++i] : nullptr);
      continue;
    }
    if (arg == "--seed") {
      cfg.seed = parse_u32("--seed", (i + 1) < argc ? argv[++i] : nullptr);
      continue;
    }
    if (arg == "--cfg-valid") {
      const uint32_t parsed = parse_u32("--cfg-valid", (i + 1) < argc ? argv[++i] : nullptr);
      if (parsed > 1U) fail("--cfg-valid expects 0 or 1");
      cfg.cfg_valid = parsed != 0U;
      continue;
    }
    if (arg == "--state-out") {
      cfg.state_out = (i + 1) < argc ? argv[++i] : "";
      if (cfg.state_out.empty()) fail("missing value for --state-out");
      continue;
    }
    if (arg == "--help" || arg == "-h") {
      std::cout
          << "Usage: socket_m1_host_probe [--reset-cycles N] [--post-reset-cycles N]\n"
          << "                           [--batch-length N] [--seed N] [--cfg-valid 0|1]\n"
          << "                           [--state-out path]\n";
      std::exit(0);
    }
    fail(std::string("unknown argument: ") + arg);
  }
  return cfg;
}

template <typename T>
std::ptrdiff_t byte_offset(const Root* root, const T* field) {
  const auto* base = reinterpret_cast<const uint8_t*>(root);
  const auto* ptr = reinterpret_cast<const uint8_t*>(field);
  return ptr - base;
}

std::vector<OffsetCheck> collect_offset_checks(const Root* root) {
  return {
      {"cfg_valid_i", byte_offset(root, &root->cfg_valid_i), VL_SOCKET_M1_OFF_CFG_VALID_I},
      {"done_o", byte_offset(root, &root->done_o), VL_SOCKET_M1_OFF_DONE_O},
      {"clk_i",
       byte_offset(root, &root->tlul_socket_m1_gpu_cov_tb__DOT__clk_i),
       VL_SOCKET_M1_OFF_CLK_I},
      {"rst_ni",
       byte_offset(root, &root->tlul_socket_m1_gpu_cov_tb__DOT__rst_ni),
       VL_SOCKET_M1_OFF_RST_NI},
      {"cfg_reset_cycles_i",
       byte_offset(root, &root->cfg_reset_cycles_i),
       VL_SOCKET_M1_OFF_CFG_RESET_CYCLES_I},
      {"cfg_signature_o",
       byte_offset(root, &root->cfg_signature_o),
       VL_SOCKET_M1_OFF_CFG_SIGNATURE_O},
      {"toggle_bitmap_word0_o",
       byte_offset(root, &root->toggle_bitmap_word0_o),
       VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD0_O},
      {"toggle_bitmap_word1_o",
       byte_offset(root, &root->toggle_bitmap_word1_o),
       VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD1_O},
      {"toggle_bitmap_word2_o",
       byte_offset(root, &root->toggle_bitmap_word2_o),
       VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD2_O},
      {"vlSymsp", byte_offset(root, &root->vlSymsp), VL_SOCKET_M1_OFF_VLSYMS},
  };
}

void configure_model(Model& model, const ProbeConfig& cfg) {
  model.cfg_valid_i = cfg.cfg_valid ? 1U : 0U;
  model.cfg_batch_length_i = cfg.batch_length;
  model.cfg_req_valid_pct_i = 0U;
  model.cfg_rsp_valid_pct_i = 0U;
  model.cfg_host_d_ready_pct_i = 0U;
  model.cfg_device_a_ready_pct_i = 0U;
  model.cfg_put_full_pct_i = 0U;
  model.cfg_put_partial_pct_i = 0U;
  model.cfg_req_fill_target_i = 0U;
  model.cfg_req_burst_len_max_i = 1U;
  model.cfg_req_family_i = 0U;
  model.cfg_req_address_mode_i = 0U;
  model.cfg_req_data_mode_i = 0U;
  model.cfg_req_data_hi_xor_i = 0U;
  model.cfg_access_ack_data_pct_i = 0U;
  model.cfg_rsp_error_pct_i = 0U;
  model.cfg_rsp_fill_target_i = 0U;
  model.cfg_rsp_delay_max_i = 0U;
  model.cfg_rsp_family_i = 0U;
  model.cfg_rsp_delay_mode_i = 0U;
  model.cfg_rsp_data_mode_i = 0U;
  model.cfg_rsp_data_hi_xor_i = 0U;
  model.cfg_reset_cycles_i = cfg.reset_cycles;
  model.cfg_drain_cycles_i = 0U;
  model.cfg_seed_i = cfg.seed;
  model.cfg_address_base_i = 0U;
  model.cfg_address_mask_i = 0xffffffffU;
  model.cfg_source_mask_i = 0xfU;
}

int run_scheduled_events(Model& model, VerilatedContext& context, int event_count) {
  int ran = 0;
  while (ran < event_count) {
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

void emit_summary(const ProbeSummary& summary) {
  std::cout << "{\n";
  std::cout << "  \"constructor_ok\": " << (summary.constructor_ok ? "true" : "false") << ",\n";
  std::cout << "  \"abi_ok\": " << (summary.abi_ok ? "true" : "false") << ",\n";
  std::cout << "  \"vl_symsp_bound\": " << (summary.vl_symsp_bound ? "true" : "false") << ",\n";
  std::cout << "  \"reset_cycles\": " << summary.reset_cycles << ",\n";
  std::cout << "  \"post_reset_cycles\": " << summary.post_reset_cycles << ",\n";
  std::cout << "  \"batch_length\": " << summary.batch_length << ",\n";
  std::cout << "  \"seed\": " << summary.seed << ",\n";
  std::cout << "  \"sim_time\": " << summary.sim_time << ",\n";
  std::cout << "  \"drained_events\": " << summary.drained_events << ",\n";
  std::cout << "  \"cfg_signature_o\": " << summary.cfg_signature_o << ",\n";
  std::cout << "  \"debug_reset_cycles_remaining_o\": "
            << summary.debug_reset_cycles_remaining_o << ",\n";
  std::cout << "  \"progress_cycle_count_o\": " << summary.progress_cycle_count_o << ",\n";
  std::cout << "  \"debug_phase_o\": " << summary.debug_phase_o << ",\n";
  std::cout << "  \"toggle_bitmap_word0_o\": " << summary.toggle_bitmap_word0_o << ",\n";
  std::cout << "  \"toggle_bitmap_word1_o\": " << summary.toggle_bitmap_word1_o << ",\n";
  std::cout << "  \"toggle_bitmap_word2_o\": " << summary.toggle_bitmap_word2_o << ",\n";
  std::cout << "  \"done_o\": " << summary.done_o << ",\n";
  std::cout << "  \"final_clk_i\": " << summary.final_clk_i << ",\n";
  std::cout << "  \"final_rst_ni\": " << summary.final_rst_ni << ",\n";
  std::cout << "  \"root_size\": " << summary.root_size << ",\n";
  std::cout << "  \"offset_checks\": [\n";
  for (size_t i = 0; i < summary.offsets.size(); ++i) {
    const auto& check = summary.offsets[i];
    std::cout << "    {\"field\": \"" << check.name << "\", \"actual\": " << check.actual
              << ", \"expected\": " << check.expected << ", \"match\": "
              << ((check.actual == check.expected) ? "true" : "false") << "}";
    if (i + 1 != summary.offsets.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  ]\n";
  std::cout << "}\n";
}

void write_state_file(const std::string& path, const Root* root) {
  std::ofstream out(path, std::ios::binary);
  if (!out) fail("failed to open --state-out for writing");
  out.write(reinterpret_cast<const char*>(root), VL_SOCKET_M1_STORAGE_SIZE);
  if (!out) fail("failed to write --state-out");
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const ProbeConfig cfg = parse_args(argc, argv);

    VerilatedContext context;
    context.randReset(0);
    context.quiet(true);
    context.time(0);

    Model model(&context, "socket_m1_host_probe");
    Root* const root = model.rootp;

    ProbeSummary summary;
    summary.constructor_ok = true;
    summary.vl_symsp_bound = (root->vlSymsp != nullptr);
    summary.reset_cycles = cfg.reset_cycles;
    summary.post_reset_cycles = cfg.post_reset_cycles;
    summary.batch_length = cfg.batch_length;
    summary.seed = cfg.seed;
    summary.root_size = static_cast<uint32_t>(sizeof(Root));
    summary.offsets = collect_offset_checks(root);
    summary.abi_ok = true;
    if (sizeof(Root) != VL_SOCKET_M1_STORAGE_SIZE) {
      summary.abi_ok = false;
    }
    for (const auto& check : summary.offsets) {
      if (check.actual != check.expected) {
        summary.abi_ok = false;
      }
    }
    if (!summary.abi_ok) {
      emit_summary(summary);
      return 2;
    }

    configure_model(model, cfg);
    root->tlul_socket_m1_gpu_cov_tb__DOT__rst_ni = 0U;
    root->tlul_socket_m1_gpu_cov_tb__DOT__clk_i = 0U;
    model.eval_step();
    summary.drained_events += run_scheduled_events(
        model,
        context,
        static_cast<int>(cfg.reset_cycles * 2U));

    root->tlul_socket_m1_gpu_cov_tb__DOT__rst_ni = 1U;
    model.eval_step();
    summary.drained_events += run_scheduled_events(
        model,
        context,
        static_cast<int>(cfg.post_reset_cycles * 2U));

    summary.sim_time = context.time();
    summary.cfg_signature_o = model.cfg_signature_o;
    summary.debug_reset_cycles_remaining_o = model.debug_reset_cycles_remaining_o;
    summary.progress_cycle_count_o = model.progress_cycle_count_o;
    summary.debug_phase_o = model.debug_phase_o;
    summary.toggle_bitmap_word0_o = model.toggle_bitmap_word0_o;
    summary.toggle_bitmap_word1_o = model.toggle_bitmap_word1_o;
    summary.toggle_bitmap_word2_o = model.toggle_bitmap_word2_o;
    summary.done_o = model.done_o;
    summary.final_clk_i = root->tlul_socket_m1_gpu_cov_tb__DOT__clk_i;
    summary.final_rst_ni = root->tlul_socket_m1_gpu_cov_tb__DOT__rst_ni;
    if (!cfg.state_out.empty()) {
      write_state_file(cfg.state_out, root);
    }

    model.final();
    emit_summary(summary);
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
}
