import argparse
import logging
import os
from process import preprocess_bug_report, process_stack_traces_and_logs, process_path, cal_final_score, process_source_code, vsm_construction, parse_report, evaluation
import nltk

# Download necessary NLTK data files
nltk.download('stopwords')
nltk.download('punkt')

logging.basicConfig(
    filename='loghound.log',
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)


def main():
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='accept')

    # 添加具体参数选项
    parser.add_argument('-bp', '--bug-reports',
                        required=True,
                        type=str,
                        help='The folder for storing bug reports')

    parser.add_argument('-t', '--report-type',
                        required=True,
                        type=str,
                        help='The file types of the bug report (json, doc, docx, txt)')

    parser.add_argument('-si', '--structuration-info',
                        required=True,
                        type=str,
                        help='Structured JSON file of bug_reports, such as [{file: xx, title: xx, version: xx, description: xx, logs: [], stack_traces: []}]')

    parser.add_argument('-sc', '--source-code',
                        required=True,
                        type=str,
                        help='The source code location where the parsing target is stored')

    parser.add_argument('-l', '--language',
                        required=True,
                        type=str,
                        help='The programming language for parsing source code')

    parser.add_argument('-v', '--version',
                        action='store_true',
                        help='Display version information')

    args = parser.parse_args()

    if "-v" in args or "--version" in args:
        print("version: 1.0.0")
        return

    bug_reports = args.bug_reports
    bug_reports_type = args.report_type
    source_code = args.source_code
    language = args.language
    structuration_info = args.structuration_info

    # # 1. Structure all the reports in the "bug_reports" section.
    if structuration_info is None:
        structuration_info = parse_report.parse(bug_reports)

    # 2. Preprocess bug_reports
    bug_reports_token = preprocess_bug_report.process_bug_report(bug_reports, language, bug_reports_type)

    # 3. Process source code
    for project_name in os.listdir(source_code):
        project_path = os.path.join(source_code, project_name)
        process_source_code.analyze_project_source_code_methods(project_path, language)

    # 4. Process VSM Information
    vsm_result_dir = vsm_construction.process_vsm_result(bug_reports_token, structuration_info)

    # 5. Process Path Information
    path_score_dir, coverage_dir = process_path.process_path_score(structuration_info)

    # 6. Process Stack Trace and Logs Information
    st_log_score_dir = process_stack_traces_and_logs.process_stack_traces_and_logs(structuration_info)

    # 7. Calculate Final Score
    output_path = os.path.join("ProcessData", "methods_total_scores")
    total_result = cal_final_score.add_scores(vsm_result_dir, st_log_score_dir, path_score_dir, output_path)
    print(total_result)


if __name__ == '__main__':
    main()
