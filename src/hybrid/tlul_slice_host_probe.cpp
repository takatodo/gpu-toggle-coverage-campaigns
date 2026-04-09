/**
 * tlul_slice_host_probe.cpp — generic OpenTitan TL-UL slice host probe.
 *
 * This binary is compiled with model-specific macros from
 * src/tools/run_tlul_slice_host_probe.py and proves that a stock-Verilator
 * TL-UL coverage TB can:
 *   - construct on the host without sim-accel glue
 *   - accept host-side config input initialization
 *   - advance its timed clock/reset coroutine far enough to dump a reusable root image
 *
 * Unlike socket_m1_host_probe.cpp, this probe does not claim a stable ABI.
 * It is intended as a reusable initialization shim for reference-design flows.
 */

#include <cstddef>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
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

#ifdef EXTRA_WATCH_FIELDS_HEADER
#include EXTRA_WATCH_FIELDS_HEADER
#endif
#ifndef EXTRA_WATCH_FIELDS
#define EXTRA_WATCH_FIELDS(X)
#endif

#include MODEL_HEADER
#include ROOT_HEADER

namespace {

using Model = MODEL_CLASS;
using Root = ROOT_CLASS;

constexpr int kMaxEventDrains = 100000;

struct ProbeConfig {
  uint32_t reset_cycles = 4;
  uint32_t post_reset_cycles = 2;
  std::string state_out;
  std::string program_entries_bin;
  std::string memory_image;
  std::vector<uint32_t> clock_sequence;
  std::string edge_state_dir;
  std::vector<std::pair<std::string, uint32_t>> sets;
};

struct EdgeSummary {
  uint32_t index = 0;
  uint32_t clock_level = 0;
  uint64_t sim_time = 0;
  std::string dump_state;
  uint32_t done_o = 0;
  uint32_t progress_cycle_count_o = 0;
  uint32_t progress_signature_o = 0;
  uint32_t toggle_bitmap_word0_o = 0;
  uint32_t toggle_bitmap_word1_o = 0;
  uint32_t toggle_bitmap_word2_o = 0;
};

struct ProbeSummary {
  bool constructor_ok = false;
  uint32_t reset_cycles = 0;
  uint32_t post_reset_cycles = 0;
  uint64_t sim_time = 0;
  int drained_events = 0;
  uint32_t root_size = 0;
  uint32_t cfg_signature_o = 0;
  uint32_t host_req_accepted_o = 0;
  uint32_t device_req_accepted_o = 0;
  uint32_t device_rsp_accepted_o = 0;
  uint32_t host_rsp_accepted_o = 0;
  uint32_t rsp_queue_overflow_o = 0;
  uint32_t progress_cycle_count_o = 0;
  uint32_t progress_signature_o = 0;
  uint32_t toggle_bitmap_word0_o = 0;
  uint32_t toggle_bitmap_word1_o = 0;
  uint32_t toggle_bitmap_word2_o = 0;
  uint32_t done_o = 0;
  uint32_t final_clk_i = 0;
  uint32_t final_reset_field_value = 0;
  uint32_t final_rst_ni = 0;
  std::vector<EdgeSummary> edge_runs;
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
    if (arg == "--state-out") {
      cfg.state_out = (i + 1) < argc ? argv[++i] : "";
      if (cfg.state_out.empty()) fail("missing value for --state-out");
      continue;
    }
    if (arg == "--program-entries-bin") {
      cfg.program_entries_bin = (i + 1) < argc ? argv[++i] : "";
      if (cfg.program_entries_bin.empty()) fail("missing value for --program-entries-bin");
      continue;
    }
    if (arg == "--memory-image") {
      cfg.memory_image = (i + 1) < argc ? argv[++i] : "";
      if (cfg.memory_image.empty()) fail("missing value for --memory-image");
      continue;
    }
    if (arg == "--clock-sequence") {
      const char* raw = (i + 1) < argc ? argv[++i] : nullptr;
      if (raw == nullptr) fail("missing value for --clock-sequence");
      cfg.clock_sequence = parse_clock_sequence(raw);
      continue;
    }
    if (arg == "--edge-state-dir") {
      cfg.edge_state_dir = (i + 1) < argc ? argv[++i] : "";
      if (cfg.edge_state_dir.empty()) fail("missing value for --edge-state-dir");
      continue;
    }
    if (arg == "--set") {
      if ((i + 1) >= argc) fail("missing value for --set");
      cfg.sets.push_back(parse_setting(argv[++i]));
      continue;
    }
    if (arg == "--help" || arg == "-h") {
      std::cout
          << "Usage: tlul_slice_host_probe [--reset-cycles N] [--post-reset-cycles N]\n"
          << "                             [--set field=value ...] [--state-out path]\n"
          << "                             [--program-entries-bin path]\n"
          << "                             [--memory-image path]\n"
          << "                             [--clock-sequence 1,0,...] [--edge-state-dir path]\n";
      std::exit(0);
    }
    fail(std::string("unknown argument: ") + arg);
  }
  if (cfg.clock_sequence.empty() && !cfg.edge_state_dir.empty()) {
    fail("--edge-state-dir requires --clock-sequence");
  }
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

void write_state_file(const std::string& path, const Root* root);

void preload_program_entries(Root* root, const std::string& path) {
#ifdef PROGRAM_ENTRIES_ARRAY
  std::ifstream in(path, std::ios::binary);
  if (!in) fail("failed to open --program-entries-bin for reading");
  const std::vector<uint8_t> bytes(
      (std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  if (bytes.empty()) fail("--program-entries-bin is empty");
  if ((bytes.size() % sizeof(uint64_t)) != 0U) {
    fail("--program-entries-bin size must be a multiple of 8 bytes");
  }
  const size_t depth =
      sizeof(root->PROGRAM_ENTRIES_ARRAY) / sizeof(root->PROGRAM_ENTRIES_ARRAY[0]);
  const size_t word_count = bytes.size() / sizeof(uint64_t);
  if (word_count > depth) {
    fail("--program-entries-bin exceeds PROGRAM_ENTRIES_ARRAY depth");
  }
  for (size_t index = 0; index < depth; ++index) {
    root->PROGRAM_ENTRIES_ARRAY[index] = 0ULL;
  }
  for (size_t index = 0; index < word_count; ++index) {
    uint64_t word = 0;
    for (size_t byte_index = 0; byte_index < sizeof(uint64_t); ++byte_index) {
      word |= (static_cast<uint64_t>(bytes[index * sizeof(uint64_t) + byte_index]) << (byte_index * 8U));
    }
    root->PROGRAM_ENTRIES_ARRAY[index] = word;
  }
#else
  (void)root;
  (void)path;
  fail("--program-entries-bin requires PROGRAM_ENTRIES_ARRAY support in the compiled probe");
#endif
}

void preload_memory_image(Root* root, const std::string& path) {
#if defined(MEMORY_IMAGE_ARRAY) && defined(MEMORY_IMAGE_WORD_BITS) && defined(MEMORY_IMAGE_EXPECTED_DEPTH)
  std::ifstream in(path, std::ios::binary);
  if (!in) fail("failed to open --memory-image for reading");
  const std::vector<uint8_t> bytes(
      (std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  if (bytes.empty()) fail("--memory-image is empty");
  const size_t depth = sizeof(root->MEMORY_IMAGE_ARRAY) / sizeof(root->MEMORY_IMAGE_ARRAY[0]);
  if (depth != static_cast<size_t>(MEMORY_IMAGE_EXPECTED_DEPTH)) {
    fail("--memory-image target depth does not match the compiled probe");
  }
#if MEMORY_IMAGE_WORD_BITS == 64
  constexpr size_t kWordBytes = sizeof(uint64_t);
  const size_t word_count = (bytes.size() + kWordBytes - 1U) / kWordBytes;
  if (word_count > depth) fail("--memory-image exceeds MEMORY_IMAGE_ARRAY depth");
  for (size_t index = 0; index < depth; ++index) {
    root->MEMORY_IMAGE_ARRAY[index] = 0ULL;
  }
  for (size_t index = 0; index < word_count; ++index) {
    uint64_t word = 0ULL;
    for (size_t byte_index = 0; byte_index < kWordBytes; ++byte_index) {
      const size_t global_index = index * kWordBytes + byte_index;
      if (global_index >= bytes.size()) break;
      word |= (static_cast<uint64_t>(bytes[global_index]) << (byte_index * 8U));
    }
    root->MEMORY_IMAGE_ARRAY[index] = word;
  }
#elif MEMORY_IMAGE_WORD_BITS == 32
  constexpr size_t kWordBytes = sizeof(uint32_t);
  const size_t word_count = (bytes.size() + kWordBytes - 1U) / kWordBytes;
  if (word_count > depth) fail("--memory-image exceeds MEMORY_IMAGE_ARRAY depth");
  for (size_t index = 0; index < depth; ++index) {
    root->MEMORY_IMAGE_ARRAY[index] = 0U;
  }
  for (size_t index = 0; index < word_count; ++index) {
    uint32_t word = 0U;
    for (size_t byte_index = 0; byte_index < kWordBytes; ++byte_index) {
      const size_t global_index = index * kWordBytes + byte_index;
      if (global_index >= bytes.size()) break;
      word |= (static_cast<uint32_t>(bytes[global_index]) << (byte_index * 8U));
    }
    root->MEMORY_IMAGE_ARRAY[index] = word;
  }
#else
  fail("--memory-image requires MEMORY_IMAGE_WORD_BITS 32 or 64");
#endif
#else
  (void)root;
  (void)path;
  fail("--memory-image requires MEMORY_IMAGE_ARRAY support in the compiled probe");
#endif
}

std::vector<EdgeSummary> run_host_clock_sequence(
    Model& model,
    VerilatedContext& context,
    Root* root,
    const std::vector<uint32_t>& clock_sequence,
    const std::string& edge_state_dir) {
  std::vector<EdgeSummary> runs;
  if (!edge_state_dir.empty()) {
    std::filesystem::create_directories(edge_state_dir);
  }
  runs.reserve(clock_sequence.size());
  for (size_t index = 0; index < clock_sequence.size(); ++index) {
    const uint32_t level = clock_sequence[index];
    context.time(context.time() + 1U);
    root->ROOT_CLK_FIELD = level;
    model.eval_step();

    EdgeSummary summary;
    summary.index = static_cast<uint32_t>(index + 1U);
    summary.clock_level = level;
    summary.sim_time = context.time();
    summary.done_o = model.done_o;
    summary.progress_cycle_count_o = model.progress_cycle_count_o;
    summary.progress_signature_o = model.progress_signature_o;
    summary.toggle_bitmap_word0_o = model.toggle_bitmap_word0_o;
    summary.toggle_bitmap_word1_o = model.toggle_bitmap_word1_o;
    summary.toggle_bitmap_word2_o = model.toggle_bitmap_word2_o;
    if (!edge_state_dir.empty()) {
      const std::filesystem::path dump =
          std::filesystem::path(edge_state_dir) / ("edge_" + std::to_string(index + 1U) + ".bin");
      write_state_file(dump.string(), root);
      summary.dump_state = dump.string();
    }
    runs.push_back(summary);
  }
  return runs;
}

template <typename T>
std::ptrdiff_t byte_offset(const Root* root, const T* field) {
  const auto* base = reinterpret_cast<const uint8_t*>(root);
  const auto* ptr = reinterpret_cast<const uint8_t*>(field);
  return ptr - base;
}

void write_state_file(const std::string& path, const Root* root) {
  std::ofstream out(path, std::ios::binary);
  if (!out) fail("failed to open --state-out for writing");
  out.write(reinterpret_cast<const char*>(root), sizeof(Root));
  if (!out) fail("failed to write --state-out");
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

void emit_edge_runs(const std::vector<EdgeSummary>& runs) {
  std::cout << "  \"edge_runs\": [";
  if (!runs.empty()) std::cout << "\n";
  for (size_t i = 0; i < runs.size(); ++i) {
    const auto& run = runs[i];
    std::cout << "    {\n";
    std::cout << "      \"index\": " << run.index << ",\n";
    std::cout << "      \"clock_level\": " << run.clock_level << ",\n";
    std::cout << "      \"sim_time\": " << run.sim_time << ",\n";
    std::cout << "      \"dump_state\": ";
    if (run.dump_state.empty()) {
      std::cout << "null,\n";
    } else {
      std::cout << "\"" << run.dump_state << "\",\n";
    }
    std::cout << "      \"done_o\": " << run.done_o << ",\n";
    std::cout << "      \"progress_cycle_count_o\": " << run.progress_cycle_count_o << ",\n";
    std::cout << "      \"progress_signature_o\": " << run.progress_signature_o << ",\n";
    std::cout << "      \"toggle_bitmap_word0_o\": " << run.toggle_bitmap_word0_o << ",\n";
    std::cout << "      \"toggle_bitmap_word1_o\": " << run.toggle_bitmap_word1_o << ",\n";
    std::cout << "      \"toggle_bitmap_word2_o\": " << run.toggle_bitmap_word2_o << "\n";
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
  std::cout << "  \"sim_time\": " << summary.sim_time << ",\n";
  std::cout << "  \"drained_events\": " << summary.drained_events << ",\n";
  std::cout << "  \"root_size\": " << summary.root_size << ",\n";
  emit_field_offsets(fields);
  emit_field_sizes(fields);
  emit_watch_field_names(watch_fields);
  emit_edge_runs(summary.edge_runs);
  std::cout << "  \"reset_field_name\": \"" << ROOT_RST_REPORT_NAME << "\",\n";
  std::cout << "  \"reset_asserted_value\": " << ROOT_RST_ASSERTED_VALUE << ",\n";
  std::cout << "  \"reset_deasserted_value\": " << ROOT_RST_DEASSERTED_VALUE << ",\n";
  std::cout << "  \"cfg_signature_o\": " << summary.cfg_signature_o << ",\n";
  std::cout << "  \"host_req_accepted_o\": " << summary.host_req_accepted_o << ",\n";
  std::cout << "  \"device_req_accepted_o\": " << summary.device_req_accepted_o << ",\n";
  std::cout << "  \"device_rsp_accepted_o\": " << summary.device_rsp_accepted_o << ",\n";
  std::cout << "  \"host_rsp_accepted_o\": " << summary.host_rsp_accepted_o << ",\n";
  std::cout << "  \"rsp_queue_overflow_o\": " << summary.rsp_queue_overflow_o << ",\n";
  std::cout << "  \"progress_cycle_count_o\": " << summary.progress_cycle_count_o << ",\n";
  std::cout << "  \"progress_signature_o\": " << summary.progress_signature_o << ",\n";
  std::cout << "  \"toggle_bitmap_word0_o\": " << summary.toggle_bitmap_word0_o << ",\n";
  std::cout << "  \"toggle_bitmap_word1_o\": " << summary.toggle_bitmap_word1_o << ",\n";
  std::cout << "  \"toggle_bitmap_word2_o\": " << summary.toggle_bitmap_word2_o << ",\n";
  std::cout << "  \"done_o\": " << summary.done_o << ",\n";
  std::cout << "  \"final_clk_i\": " << summary.final_clk_i << ",\n";
  std::cout << "  \"final_reset_field_value\": " << summary.final_reset_field_value << ",\n";
  std::cout << "  \"final_rst_ni\": " << summary.final_rst_ni << "\n";
  std::cout << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const ProbeConfig cfg = parse_args(argc, argv);

    VerilatedContext context;
    context.commandArgs(argc, argv);
    context.randReset(0);
    context.quiet(true);
    context.time(0);

    Model model(&context, TARGET_NAME);
    Root* const root = model.rootp;

    ProbeSummary summary;
    summary.constructor_ok = true;
    summary.reset_cycles = cfg.reset_cycles;
    summary.post_reset_cycles = cfg.post_reset_cycles;
    summary.root_size = static_cast<uint32_t>(sizeof(Root));

    configure_defaults(model);
    for (const auto& entry : cfg.sets) {
      apply_setting(model, entry.first, entry.second);
    }
    if (!cfg.program_entries_bin.empty()) {
      preload_program_entries(root, cfg.program_entries_bin);
    }
    if (!cfg.memory_image.empty()) {
      preload_memory_image(root, cfg.memory_image);
    }

    root->ROOT_CLK_FIELD = 0U;
    root->ROOT_RST_FIELD = HOST_RESET_CONTROL ? ROOT_RST_ASSERTED_VALUE : ROOT_RST_DEASSERTED_VALUE;
    model.eval_step();
    if (HOST_CLOCK_CONTROL) {
      summary.drained_events += run_host_cycles(model, context, root, cfg.reset_cycles);
      if (HOST_RESET_CONTROL) {
        root->ROOT_RST_FIELD = ROOT_RST_DEASSERTED_VALUE;
        model.eval_step();
      }
      summary.drained_events += run_host_cycles(model, context, root, cfg.post_reset_cycles);
    } else {
      summary.drained_events += run_scheduled_events(
          model,
          context,
          static_cast<int>(cfg.reset_cycles * 2U));

      root->ROOT_RST_FIELD = ROOT_RST_DEASSERTED_VALUE;
      model.eval_step();
      summary.drained_events += run_scheduled_events(
          model,
          context,
          static_cast<int>(cfg.post_reset_cycles * 2U));
    }

    if (!cfg.clock_sequence.empty()) {
      if (!HOST_CLOCK_CONTROL) {
        fail("--clock-sequence requires host-owned clock control");
      }
      summary.edge_runs =
          run_host_clock_sequence(model, context, root, cfg.clock_sequence, cfg.edge_state_dir);
    }

    summary.sim_time = context.time();
    summary.cfg_signature_o = model.cfg_signature_o;
    summary.host_req_accepted_o = model.host_req_accepted_o;
    summary.device_req_accepted_o = model.device_req_accepted_o;
    summary.device_rsp_accepted_o = model.device_rsp_accepted_o;
    summary.host_rsp_accepted_o = model.host_rsp_accepted_o;
    summary.rsp_queue_overflow_o = model.rsp_queue_overflow_o;
    summary.progress_cycle_count_o = model.progress_cycle_count_o;
    summary.progress_signature_o = model.progress_signature_o;
    summary.toggle_bitmap_word0_o = model.toggle_bitmap_word0_o;
    summary.toggle_bitmap_word1_o = model.toggle_bitmap_word1_o;
    summary.toggle_bitmap_word2_o = model.toggle_bitmap_word2_o;
    summary.done_o = model.done_o;
    summary.final_clk_i = root->ROOT_CLK_FIELD;
    summary.final_reset_field_value = root->ROOT_RST_FIELD;
    summary.final_rst_ni =
        (summary.final_reset_field_value == ROOT_RST_DEASSERTED_VALUE) ? 1U : 0U;
    if (!cfg.state_out.empty()) {
      write_state_file(cfg.state_out, root);
    }

    model.final();
    emit_summary(summary, root);
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
}
