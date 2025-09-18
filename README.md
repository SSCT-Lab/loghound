# loghound

`loghound` is a method-level fault localization approach that identifies fault locations at the method level through comprehensive analysis of VSM (Vector Space Model) calculations, path construction, test coverage, and stack trace information.

This method enables static code analysis without the need for dynamic execution or source code compilation to build call graphs. It incorporates various parameters and weights, achieving excellent fault localization performance.

## Prerequisites

- Python 3.x
- Required packages: Install using

```bash
pip install -r requirements.txt
```

## Project Structure

```plaintext
project_root/
├── analyzer/
│   ├── analyzer.py
│   ├── extract_bug_reports.py
│   ├── tonic.py
│   ├── type_resolver.py
│   └── preprocess_bug_report.py
├── bug_reports/
├── classes/
├── conf/
│   └── conf.yml
├── dataset/
│   └── docs_output_file/
|   └── dbugset_crawl.py
|   └── get-target-system.sh
├── logRestore/
│   ├── src/
│   │   └── main/
│   │       └── java/
│   │           └── org/
│   │               └── example/
│   │                   ├── LogRestore.java
│   │                   └── Main.java
├── process/
│   ├── cal_final_score.py
│   ├── evaluation.py
│   ├── generate_call_graph.py
│   ├── log_extract.py
│   ├── param_lib.py
│   ├── parse_report.py
│   ├── preprocess_bug_report.py
│   ├── process_path.py
│   ├── process_source_code.py
│   ├── process_stack_traces_and_logs.py
│   ├── process_tock.py
│   └── vsm_construction.py
├── ql/
│   ├── sanity/
│   │   └── sanity-pack/
│   └── sanity-coverage/
│       ├── static_coverage_summary_cak.ql
│       ├── static_coverage_summary_hao21.ql
│       ├── static_coverage_summary_hao23.ql
│       ├── static_coverage_summary_h360.ql
│       ├── static_coverage_summary_hb50.ql
│       ├── static_coverage_summary_zks.ql
│       ├── codenji-pack.lock.yml
│       └── qlpack.yml
├── tgt_sys/
│   ├── build_dy.sh
│   ├── get_target_system.sh
│   ├── run_coverage.sh
├── dbugset_resolve.xlsx
├── structuration_info.json
├── app.py
├── cover_cal.py
├── eval.py
├── read_version_json.py
├── requirements.txt
├── smp.py
└── README.md
```

## How to Run

### 1. Configuration Setup

First, modify the LLM API settings in the configuration file:

- Navigate to `conf/conf.yaml`
- Update the LLM `api`, `model`, and `base_url` parameters

### 2. Static Code Analysis

Run the following command to perform static analysis of the distributed system source code and build the call graph:

```bash
python smp.py -sc source_code_list  # Replace with actual source code path
```

### 3. Execute Full LogHound Workflow

Run the complete fault localization process with:

```bash
python app.py -bp bug_reports -t docx -si structuration-info.json -sc source_code_list -l java
```

**source_code_list need to replace with actual source code path**

## View Evaluation Results

To check the evaluation results, use:

```bash
python eval.py -a dbugset_resolve.xlsx -n 5  # -n specifies the top N results to view
```



## Parameter Description

| Short | Long                   | Required | Type   | Description                                                  |
| ----- | ---------------------- | -------- | ------ | ------------------------------------------------------------ |
| `-a`  | `--answer`             | ✅        | `str`  | Path to the ground truth file (evaluation reference)         |
| `-n`  |                        | ❌        | `int`  | Number of top results to evaluate (default: not limited)     |
| `-bp` | `--bug-reports`        | ✅        | `str`  | Folder containing bug reports                                |
| `-t`  | `--report-type`        | ✅        | `str`  | Bug report file type (`json`, `doc`, `docx`, `txt`)          |
| `-si` | `--structuration-info` | ✅        | `str`  | JSON file with structured bug report info in format: `[{file: xx, title: xx, version: xx, description: xx, logs: [], stack_traces: []}]` |
| `-sc` | `--source-code`        | ✅        | `str`  | Path to source code for parsing                              |
| `-l`  | `--language`           | ✅        | `str`  | Programming language of the source code                      |
| `-v`  | `--version`            | ❌        | `flag` | Show version information                                     |
