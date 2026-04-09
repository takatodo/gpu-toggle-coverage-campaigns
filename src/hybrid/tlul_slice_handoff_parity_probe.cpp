/**
 * tlul_slice_handoff_parity_probe.cpp — compare host eval_step() against raw root___eval().
 *
 * This is a focused diagnostic for thin-top handoff work. It drives the same host-owned
 * clock sequence into two identical models:
 *   1. normal host eval_step()
 *   2. direct ROOT_EVAL_FN(root)
 *
 * The probe writes per-edge state dumps for both paths so the Python wrapper can annotate
 * raw state deltas back to named fields.
 */

#include <cstddef>
#include <cstdint>
#include <algorithm>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "verilated.h"

#ifndef MODEL_HEADER
#error "MODEL_HEADER must be defined"
#endif
#ifndef ROOT_HEADER
#error "ROOT_HEADER must be defined"
#endif
#ifndef MODEL_CLASS
#error "MODEL_CLASS must be defined"
#endif
#ifndef ROOT_CLASS
#error "ROOT_CLASS must be defined"
#endif
#ifndef ROOT_CLK_FIELD
#error "ROOT_CLK_FIELD must be defined"
#endif
#ifndef ROOT_CLK_REPORT_NAME
#define ROOT_CLK_REPORT_NAME "clk_i"
#endif
#ifndef ROOT_RST_FIELD
#error "ROOT_RST_FIELD must be defined"
#endif
#ifndef ROOT_RST_REPORT_NAME
#define ROOT_RST_REPORT_NAME "rst_ni"
#endif
#ifndef ROOT_RST_ASSERTED_VALUE
#define ROOT_RST_ASSERTED_VALUE 0U
#endif
#ifndef ROOT_RST_DEASSERTED_VALUE
#define ROOT_RST_DEASSERTED_VALUE 1U
#endif
#ifndef TARGET_NAME
#define TARGET_NAME "unknown_tlul_slice"
#endif
#ifndef HOST_CLOCK_CONTROL
#define HOST_CLOCK_CONTROL 0
#endif
#ifndef HOST_RESET_CONTROL
#define HOST_RESET_CONTROL 0
#endif
#ifndef ROOT_EVAL_FN
#error "ROOT_EVAL_FN must be defined"
#endif

#ifdef EXTRA_WATCH_FIELDS_HEADER
#include EXTRA_WATCH_FIELDS_HEADER
#endif
#ifndef EXTRA_WATCH_FIELDS
#define EXTRA_WATCH_FIELDS(X)
#endif

#include MODEL_HEADER
#include ROOT_HEADER

using RootEvalProbeRoot = ROOT_CLASS;
extern void ROOT_EVAL_FN(RootEvalProbeRoot* vlSelf);

namespace {

using Model = MODEL_CLASS;
using Root = ROOT_CLASS;

struct ProbeConfig {
  uint32_t reset_cycles = 4;
  uint32_t post_reset_cycles = 2;
  std::vector<uint32_t> clock_sequence;
  std::string host_edge_state_dir;
  std::string root_eval_edge_state_dir;
  std::vector<std::pair<std::string, uint32_t>> sets;
};

struct EdgeSample {
  uint64_t sim_time = 0;
  std::string dump_state;
  uint32_t done_o = 0;
  uint32_t progress_cycle_count_o = 0;
  uint32_t progress_signature_o = 0;
  uint32_t toggle_bitmap_word0_o = 0;
  uint32_t toggle_bitmap_word1_o = 0;
  uint32_t toggle_bitmap_word2_o = 0;
};

struct EdgeParityRun {
  uint32_t index = 0;
  uint32_t clock_level = 0;
  EdgeSample host_eval;
  EdgeSample root_eval;
  EdgeSample fake_syms_eval;
  EdgeSample raw_import_eval;
};

struct ProbeSummary {
  bool constructor_ok = false;
  uint32_t reset_cycles = 0;
  uint32_t post_reset_cycles = 0;
  uint32_t root_size = 0;
  std::vector<EdgeParityRun> edge_runs;
};

struct FieldDescriptor {
  std::string name;
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

std::vector<uint32_t> parse_clock_sequence(const std::string& raw) {
  std::vector<uint32_t> sequence;
  size_t start = 0;
  while (start < raw.size()) {
    const size_t end = raw.find(',', start);
    const std::string token =
        raw.substr(start, end == std::string::npos ? std::string::npos : end - start);
    if (token != "0" && token != "1") {
      fail(std::string("bad --clock-sequence token: ") + token + " (want 0 or 1)");
    }
    sequence.push_back(token == "1" ? 1U : 0U);
    if (end == std::string::npos) break;
    start = end + 1U;
    if (start >= raw.size()) fail("bad --clock-sequence: trailing comma");
  }
  if (sequence.empty()) fail("bad --clock-sequence: empty sequence");
  return sequence;
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
    if (arg == "--clock-sequence") {
      const char* raw = (i + 1) < argc ? argv[++i] : nullptr;
      if (raw == nullptr) fail("missing value for --clock-sequence");
      cfg.clock_sequence = parse_clock_sequence(raw);
      continue;
    }
    if (arg == "--host-edge-state-dir") {
      cfg.host_edge_state_dir = (i + 1) < argc ? argv[++i] : "";
      if (cfg.host_edge_state_dir.empty()) fail("missing value for --host-edge-state-dir");
      continue;
    }
    if (arg == "--root-eval-edge-state-dir") {
      cfg.root_eval_edge_state_dir = (i + 1) < argc ? argv[++i] : "";
      if (cfg.root_eval_edge_state_dir.empty()) fail("missing value for --root-eval-edge-state-dir");
      continue;
    }
    if (arg == "--set") {
      if ((i + 1) >= argc) fail("missing value for --set");
      cfg.sets.push_back(parse_setting(argv[++i]));
      continue;
    }
    if (arg == "--help" || arg == "-h") {
      std::cout
          << "Usage: tlul_slice_handoff_parity_probe [--reset-cycles N] [--post-reset-cycles N]\n"
          << "                                       [--set field=value ...]\n"
          << "                                       --clock-sequence 1,0,...\n"
          << "                                       [--host-edge-state-dir path]\n"
          << "                                       [--root-eval-edge-state-dir path]\n";
      std::exit(0);
    }
    fail(std::string("unknown argument: ") + arg);
  }
  if (cfg.clock_sequence.empty()) fail("--clock-sequence is required");
  return cfg;
}

template <typename T>
void assign_u32(T& field, uint32_t value) {
  field = static_cast<T>(value);
}

void configure_defaults(Model& model) {
  assign_u32(model.cfg_valid_i, 1U);
  assign_u32(model.cfg_batch_length_i, 256U);
  assign_u32(model.cfg_req_valid_pct_i, 65U);
  assign_u32(model.cfg_rsp_valid_pct_i, 70U);
  assign_u32(model.cfg_host_d_ready_pct_i, 75U);
  assign_u32(model.cfg_device_a_ready_pct_i, 80U);
  assign_u32(model.cfg_put_full_pct_i, 34U);
  assign_u32(model.cfg_put_partial_pct_i, 33U);
  assign_u32(model.cfg_req_fill_target_i, 2U);
  assign_u32(model.cfg_req_burst_len_max_i, 0U);
  assign_u32(model.cfg_req_family_i, 0U);
  assign_u32(model.cfg_req_address_mode_i, 0U);
  assign_u32(model.cfg_req_data_mode_i, 0U);
  assign_u32(model.cfg_req_data_hi_xor_i, 0U);
  assign_u32(model.cfg_access_ack_data_pct_i, 50U);
  assign_u32(model.cfg_rsp_error_pct_i, 10U);
  assign_u32(model.cfg_rsp_fill_target_i, 2U);
  assign_u32(model.cfg_rsp_delay_max_i, 4U);
  assign_u32(model.cfg_rsp_family_i, 0U);
  assign_u32(model.cfg_rsp_delay_mode_i, 0U);
  assign_u32(model.cfg_rsp_data_mode_i, 0U);
  assign_u32(model.cfg_rsp_data_hi_xor_i, 0U);
  assign_u32(model.cfg_reset_cycles_i, 4U);
  assign_u32(model.cfg_drain_cycles_i, 24U);
  assign_u32(model.cfg_seed_i, 1U);
  assign_u32(model.cfg_address_base_i, 0U);
  assign_u32(model.cfg_address_mask_i, 0x00000ffcU);
  assign_u32(model.cfg_source_mask_i, 0x000000ffU);
}

void apply_setting(Model& model, const std::string& name, uint32_t value) {
  if (name == "cfg_valid_i") assign_u32(model.cfg_valid_i, value);
  else if (name == "cfg_batch_length_i") assign_u32(model.cfg_batch_length_i, value);
  else if (name == "cfg_req_valid_pct_i") assign_u32(model.cfg_req_valid_pct_i, value);
  else if (name == "cfg_rsp_valid_pct_i") assign_u32(model.cfg_rsp_valid_pct_i, value);
  else if (name == "cfg_host_d_ready_pct_i") assign_u32(model.cfg_host_d_ready_pct_i, value);
  else if (name == "cfg_device_a_ready_pct_i") assign_u32(model.cfg_device_a_ready_pct_i, value);
  else if (name == "cfg_put_full_pct_i") assign_u32(model.cfg_put_full_pct_i, value);
  else if (name == "cfg_put_partial_pct_i") assign_u32(model.cfg_put_partial_pct_i, value);
  else if (name == "cfg_req_fill_target_i") assign_u32(model.cfg_req_fill_target_i, value);
  else if (name == "cfg_req_burst_len_max_i") assign_u32(model.cfg_req_burst_len_max_i, value);
  else if (name == "cfg_req_family_i") assign_u32(model.cfg_req_family_i, value);
  else if (name == "cfg_req_address_mode_i") assign_u32(model.cfg_req_address_mode_i, value);
  else if (name == "cfg_req_data_mode_i") assign_u32(model.cfg_req_data_mode_i, value);
  else if (name == "cfg_req_data_hi_xor_i") assign_u32(model.cfg_req_data_hi_xor_i, value);
  else if (name == "cfg_access_ack_data_pct_i") assign_u32(model.cfg_access_ack_data_pct_i, value);
  else if (name == "cfg_rsp_error_pct_i") assign_u32(model.cfg_rsp_error_pct_i, value);
  else if (name == "cfg_rsp_fill_target_i") assign_u32(model.cfg_rsp_fill_target_i, value);
  else if (name == "cfg_rsp_delay_max_i") assign_u32(model.cfg_rsp_delay_max_i, value);
  else if (name == "cfg_rsp_family_i") assign_u32(model.cfg_rsp_family_i, value);
  else if (name == "cfg_rsp_delay_mode_i") assign_u32(model.cfg_rsp_delay_mode_i, value);
  else if (name == "cfg_rsp_data_mode_i") assign_u32(model.cfg_rsp_data_mode_i, value);
  else if (name == "cfg_rsp_data_hi_xor_i") assign_u32(model.cfg_rsp_data_hi_xor_i, value);
  else if (name == "cfg_reset_cycles_i") assign_u32(model.cfg_reset_cycles_i, value);
  else if (name == "cfg_drain_cycles_i") assign_u32(model.cfg_drain_cycles_i, value);
  else if (name == "cfg_seed_i") assign_u32(model.cfg_seed_i, value);
  else if (name == "cfg_address_base_i") assign_u32(model.cfg_address_base_i, value);
  else if (name == "cfg_address_mask_i") assign_u32(model.cfg_address_mask_i, value);
  else if (name == "cfg_source_mask_i") assign_u32(model.cfg_source_mask_i, value);
  else fail(std::string("unsupported --set field: ") + name);
}

void write_state_file(const std::string& path, const Root* root) {
  std::ofstream out(path, std::ios::binary);
  if (!out) fail(std::string("failed to open state dump for writing: ") + path);
  out.write(reinterpret_cast<const char*>(root), sizeof(Root));
  if (!out) fail(std::string("failed to write state dump: ") + path);
}

int run_host_cycles(Model& model, VerilatedContext& context, Root* root, uint32_t cycle_count) {
  int evals = 0;
  for (uint32_t cycle = 0; cycle < cycle_count; ++cycle) {
    context.time(context.time() + 1U);
    root->ROOT_CLK_FIELD = 1U;
    model.eval_step();
    ++evals;
    context.time(context.time() + 1U);
    root->ROOT_CLK_FIELD = 0U;
    model.eval_step();
    ++evals;
  }
  return evals;
}

template <typename T>
std::ptrdiff_t byte_offset(const Root* root, const T* field) {
  const auto* base = reinterpret_cast<const uint8_t*>(root);
  const auto* ptr = reinterpret_cast<const uint8_t*>(field);
  return ptr - base;
}

std::vector<FieldDescriptor> collect_standard_field_descriptors(const Root* root) {
  return {
      {"done_o", byte_offset(root, &root->done_o), sizeof(root->done_o)},
      {"cfg_signature_o", byte_offset(root, &root->cfg_signature_o), sizeof(root->cfg_signature_o)},
      {"host_req_accepted_o",
       byte_offset(root, &root->host_req_accepted_o),
       sizeof(root->host_req_accepted_o)},
      {"device_req_accepted_o",
       byte_offset(root, &root->device_req_accepted_o),
       sizeof(root->device_req_accepted_o)},
      {"device_rsp_accepted_o",
       byte_offset(root, &root->device_rsp_accepted_o),
       sizeof(root->device_rsp_accepted_o)},
      {"host_rsp_accepted_o",
       byte_offset(root, &root->host_rsp_accepted_o),
       sizeof(root->host_rsp_accepted_o)},
      {"rsp_queue_overflow_o",
       byte_offset(root, &root->rsp_queue_overflow_o),
       sizeof(root->rsp_queue_overflow_o)},
      {"progress_cycle_count_o",
       byte_offset(root, &root->progress_cycle_count_o),
       sizeof(root->progress_cycle_count_o)},
      {"progress_signature_o",
       byte_offset(root, &root->progress_signature_o),
       sizeof(root->progress_signature_o)},
      {"toggle_bitmap_word0_o",
       byte_offset(root, &root->toggle_bitmap_word0_o),
       sizeof(root->toggle_bitmap_word0_o)},
      {"toggle_bitmap_word1_o",
       byte_offset(root, &root->toggle_bitmap_word1_o),
       sizeof(root->toggle_bitmap_word1_o)},
      {"toggle_bitmap_word2_o",
       byte_offset(root, &root->toggle_bitmap_word2_o),
       sizeof(root->toggle_bitmap_word2_o)},
      {"clk_i", byte_offset(root, &root->ROOT_CLK_FIELD), sizeof(root->ROOT_CLK_FIELD)},
      {ROOT_RST_REPORT_NAME, byte_offset(root, &root->ROOT_RST_FIELD), sizeof(root->ROOT_RST_FIELD)},
  };
}

std::vector<FieldDescriptor> collect_extra_watch_field_descriptors(const Root* root) {
  std::vector<FieldDescriptor> fields;
#define APPEND_EXTRA_WATCH_FIELD(json_name, member_name) \
  fields.push_back({json_name, byte_offset(root, &root->member_name), sizeof(root->member_name)});
  EXTRA_WATCH_FIELDS(APPEND_EXTRA_WATCH_FIELD)
#undef APPEND_EXTRA_WATCH_FIELD
  return fields;
}

void emit_field_offsets(const std::vector<FieldDescriptor>& fields) {
  std::cout << "  \"field_offsets\": {\n";
  for (size_t i = 0; i < fields.size(); ++i) {
    const auto& field = fields[i];
    std::cout << "    \"" << field.name << "\": " << field.offset;
    if (i + 1U < fields.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  },\n";
}

void emit_field_sizes(const std::vector<FieldDescriptor>& fields) {
  std::cout << "  \"field_sizes\": {\n";
  for (size_t i = 0; i < fields.size(); ++i) {
    const auto& field = fields[i];
    std::cout << "    \"" << field.name << "\": " << field.size;
    if (i + 1U < fields.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  },\n";
}

void emit_watch_field_names(const std::vector<FieldDescriptor>& fields) {
  std::cout << "  \"watch_field_names\": [";
  if (!fields.empty()) std::cout << "\n";
  for (size_t i = 0; i < fields.size(); ++i) {
    const auto& field = fields[i];
    std::cout << "    \"" << field.name << "\"";
    if (i + 1U < fields.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  ],\n";
}

void emit_edge_sample(const char* label, const EdgeSample& sample) {
  std::cout << "      \"" << label << "\": {\n";
  std::cout << "        \"sim_time\": " << sample.sim_time << ",\n";
  std::cout << "        \"dump_state\": ";
  if (sample.dump_state.empty()) {
    std::cout << "null,\n";
  } else {
    std::cout << "\"" << sample.dump_state << "\",\n";
  }
  std::cout << "        \"done_o\": " << sample.done_o << ",\n";
  std::cout << "        \"progress_cycle_count_o\": " << sample.progress_cycle_count_o << ",\n";
  std::cout << "        \"progress_signature_o\": " << sample.progress_signature_o << ",\n";
  std::cout << "        \"toggle_bitmap_word0_o\": " << sample.toggle_bitmap_word0_o << ",\n";
  std::cout << "        \"toggle_bitmap_word1_o\": " << sample.toggle_bitmap_word1_o << ",\n";
  std::cout << "        \"toggle_bitmap_word2_o\": " << sample.toggle_bitmap_word2_o << "\n";
  std::cout << "      }";
}

void emit_edge_runs(const std::vector<EdgeParityRun>& runs) {
  std::cout << "  \"edge_runs\": [";
  if (!runs.empty()) std::cout << "\n";
  for (size_t i = 0; i < runs.size(); ++i) {
    const auto& run = runs[i];
    std::cout << "    {\n";
    std::cout << "      \"index\": " << run.index << ",\n";
    std::cout << "      \"clock_level\": " << run.clock_level << ",\n";
    emit_edge_sample("host_eval", run.host_eval);
    std::cout << ",\n";
    emit_edge_sample("root_eval", run.root_eval);
    std::cout << ",\n";
    emit_edge_sample("fake_syms_eval", run.fake_syms_eval);
    std::cout << ",\n";
    emit_edge_sample("raw_import_eval", run.raw_import_eval);
    std::cout << "\n";
    std::cout << "    }";
    if (i + 1U < runs.size()) std::cout << ",";
    std::cout << "\n";
  }
  std::cout << "  ],\n";
}

void emit_summary(const ProbeSummary& summary, const Root* root) {
  auto fields = collect_standard_field_descriptors(root);
  const auto watch_fields = collect_extra_watch_field_descriptors(root);
  fields.insert(fields.end(), watch_fields.begin(), watch_fields.end());

  std::cout << "{\n";
  std::cout << "  \"target\": \"" << TARGET_NAME << "\",\n";
  std::cout << "  \"constructor_ok\": " << (summary.constructor_ok ? "true" : "false") << ",\n";
  std::cout << "  \"host_clock_control\": " << (HOST_CLOCK_CONTROL ? "true" : "false") << ",\n";
  std::cout << "  \"host_reset_control\": " << (HOST_RESET_CONTROL ? "true" : "false") << ",\n";
  std::cout << "  \"reset_cycles\": " << summary.reset_cycles << ",\n";
  std::cout << "  \"post_reset_cycles\": " << summary.post_reset_cycles << ",\n";
  std::cout << "  \"root_size\": " << summary.root_size << ",\n";
  emit_field_offsets(fields);
  emit_field_sizes(fields);
  emit_watch_field_names(watch_fields);
  emit_edge_runs(summary.edge_runs);
  std::cout << "  \"reset_field_name\": \"" << ROOT_RST_REPORT_NAME << "\",\n";
  std::cout << "  \"reset_asserted_value\": " << ROOT_RST_ASSERTED_VALUE << ",\n";
  std::cout << "  \"reset_deasserted_value\": " << ROOT_RST_DEASSERTED_VALUE << "\n";
  std::cout << "}\n";
}

void initialize_model(
    Model& model,
    VerilatedContext& context,
    Root* root,
    const ProbeConfig& cfg) {
  configure_defaults(model);
  for (const auto& entry : cfg.sets) {
    apply_setting(model, entry.first, entry.second);
  }
  root->ROOT_CLK_FIELD = 0U;
  root->ROOT_RST_FIELD = ROOT_RST_ASSERTED_VALUE;
  model.eval_step();
  run_host_cycles(model, context, root, cfg.reset_cycles);
  root->ROOT_RST_FIELD = ROOT_RST_DEASSERTED_VALUE;
  model.eval_step();
  run_host_cycles(model, context, root, cfg.post_reset_cycles);
}

EdgeSample capture_sample(
    const Model& model,
    const VerilatedContext& context,
    const Root* root,
    const std::string& dump_path) {
  EdgeSample sample;
  sample.sim_time = context.time();
  sample.done_o = model.done_o;
  sample.progress_cycle_count_o = model.progress_cycle_count_o;
  sample.progress_signature_o = model.progress_signature_o;
  sample.toggle_bitmap_word0_o = model.toggle_bitmap_word0_o;
  sample.toggle_bitmap_word1_o = model.toggle_bitmap_word1_o;
  sample.toggle_bitmap_word2_o = model.toggle_bitmap_word2_o;
  if (!dump_path.empty()) {
    write_state_file(dump_path, root);
    sample.dump_state = dump_path;
  }
  return sample;
}

std::vector<EdgeParityRun> run_edge_parity(
    Model& host_model,
    VerilatedContext& host_context,
    Root* host_root,
    Model& root_eval_model,
    VerilatedContext& root_eval_context,
    Root* root_eval_root,
    Model& fake_syms_model,
    VerilatedContext& fake_syms_context,
    Root* fake_syms_root,
    Model& raw_import_model,
    VerilatedContext& raw_import_context,
    Root* raw_import_root,
    const ProbeConfig& cfg) {
  alignas(VL_CACHE_LINE_BYTES) unsigned char fake_syms_buf[4096] = {};
  std::vector<uint8_t> raw_import_state(sizeof(Root));
  std::memcpy(raw_import_state.data(), host_root, sizeof(Root));
  const auto raw_import_saved_vlSymsp = raw_import_root->vlSymsp;
  const auto raw_import_saved_vlNamep = raw_import_root->vlNamep;
  if (!cfg.host_edge_state_dir.empty()) {
    std::filesystem::create_directories(cfg.host_edge_state_dir);
  }
  if (!cfg.root_eval_edge_state_dir.empty()) {
    std::filesystem::create_directories(cfg.root_eval_edge_state_dir);
  }
  const std::filesystem::path fake_syms_dir =
      std::filesystem::path(cfg.root_eval_edge_state_dir).parent_path() / "fake_syms_eval";
  std::filesystem::create_directories(fake_syms_dir);
  const std::filesystem::path raw_import_dir =
      std::filesystem::path(cfg.root_eval_edge_state_dir).parent_path() / "raw_import_eval";
  std::filesystem::create_directories(raw_import_dir);
  std::vector<EdgeParityRun> runs;
  runs.reserve(cfg.clock_sequence.size());
  for (size_t index = 0; index < cfg.clock_sequence.size(); ++index) {
    const uint32_t level = cfg.clock_sequence[index];

    host_context.time(host_context.time() + 1U);
    host_root->ROOT_CLK_FIELD = level;
    host_model.eval_step();

    root_eval_context.time(root_eval_context.time() + 1U);
    root_eval_root->ROOT_CLK_FIELD = level;
    ::ROOT_EVAL_FN(root_eval_root);

    fake_syms_context.time(fake_syms_context.time() + 1U);
    fake_syms_root->ROOT_CLK_FIELD = level;
    fake_syms_root->vlSymsp =
        reinterpret_cast<decltype(fake_syms_root->vlSymsp)>(fake_syms_buf);
    ::ROOT_EVAL_FN(fake_syms_root);

    raw_import_context.time(raw_import_context.time() + 1U);
    std::copy(raw_import_state.begin(),
              raw_import_state.end(),
              reinterpret_cast<uint8_t*>(raw_import_root));
    raw_import_root->vlSymsp = raw_import_saved_vlSymsp;
    raw_import_root->vlNamep = raw_import_saved_vlNamep;
    raw_import_root->ROOT_CLK_FIELD = level;
    raw_import_root->ROOT_RST_FIELD = ROOT_RST_DEASSERTED_VALUE;
    ::ROOT_EVAL_FN(raw_import_root);

    EdgeParityRun run;
    run.index = static_cast<uint32_t>(index + 1U);
    run.clock_level = level;
    const std::string host_dump =
        cfg.host_edge_state_dir.empty()
            ? std::string()
            : (std::filesystem::path(cfg.host_edge_state_dir) /
               ("edge_" + std::to_string(index + 1U) + ".bin"))
                  .string();
    const std::string root_eval_dump =
        cfg.root_eval_edge_state_dir.empty()
            ? std::string()
            : (std::filesystem::path(cfg.root_eval_edge_state_dir) /
               ("edge_" + std::to_string(index + 1U) + ".bin"))
                  .string();
    const std::string fake_syms_dump =
        (fake_syms_dir / ("edge_" + std::to_string(index + 1U) + ".bin")).string();
    const std::string raw_import_dump =
        (raw_import_dir / ("edge_" + std::to_string(index + 1U) + ".bin")).string();
    run.host_eval = capture_sample(host_model, host_context, host_root, host_dump);
    run.root_eval = capture_sample(root_eval_model, root_eval_context, root_eval_root, root_eval_dump);
    run.fake_syms_eval =
        capture_sample(fake_syms_model, fake_syms_context, fake_syms_root, fake_syms_dump);
    run.raw_import_eval =
        capture_sample(raw_import_model, raw_import_context, raw_import_root, raw_import_dump);
    std::memcpy(raw_import_state.data(), raw_import_root, sizeof(Root));
    std::memcpy(&raw_import_state[byte_offset(raw_import_root, &raw_import_root->vlSymsp)],
                &raw_import_saved_vlSymsp,
                sizeof(raw_import_saved_vlSymsp));
    std::memcpy(&raw_import_state[byte_offset(raw_import_root, &raw_import_root->vlNamep)],
                &raw_import_saved_vlNamep,
                sizeof(raw_import_saved_vlNamep));
    runs.push_back(run);
  }
  return runs;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (!(HOST_CLOCK_CONTROL && HOST_RESET_CONTROL)) {
      fail("handoff parity probe requires host-owned clock/reset control");
    }
    const ProbeConfig cfg = parse_args(argc, argv);

    VerilatedContext host_context;
    host_context.randReset(0);
    host_context.quiet(true);
    host_context.time(0);

    VerilatedContext root_eval_context;
    root_eval_context.randReset(0);
    root_eval_context.quiet(true);
    root_eval_context.time(0);

    VerilatedContext fake_syms_context;
    fake_syms_context.randReset(0);
    fake_syms_context.quiet(true);
    fake_syms_context.time(0);

    VerilatedContext raw_import_context;
    raw_import_context.randReset(0);
    raw_import_context.quiet(true);
    raw_import_context.time(0);

    Model host_model(&host_context, TARGET_NAME);
    Model root_eval_model(&root_eval_context, TARGET_NAME);
    Model fake_syms_model(&fake_syms_context, TARGET_NAME);
    Model raw_import_model(&raw_import_context, TARGET_NAME);
    Root* const host_root = host_model.rootp;
    Root* const root_eval_root = root_eval_model.rootp;
    Root* const fake_syms_root = fake_syms_model.rootp;
    Root* const raw_import_root = raw_import_model.rootp;

    initialize_model(host_model, host_context, host_root, cfg);
    initialize_model(root_eval_model, root_eval_context, root_eval_root, cfg);
    initialize_model(fake_syms_model, fake_syms_context, fake_syms_root, cfg);
    initialize_model(raw_import_model, raw_import_context, raw_import_root, cfg);

    ProbeSummary summary;
    summary.constructor_ok = true;
    summary.reset_cycles = cfg.reset_cycles;
    summary.post_reset_cycles = cfg.post_reset_cycles;
    summary.root_size = static_cast<uint32_t>(sizeof(Root));
    summary.edge_runs = run_edge_parity(
        host_model,
        host_context,
        host_root,
        root_eval_model,
        root_eval_context,
        root_eval_root,
        fake_syms_model,
        fake_syms_context,
        fake_syms_root,
        raw_import_model,
        raw_import_context,
        raw_import_root,
        cfg);

    emit_summary(summary, host_root);
    host_model.final();
    root_eval_model.final();
    fake_syms_model.final();
    raw_import_model.final();
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
}
