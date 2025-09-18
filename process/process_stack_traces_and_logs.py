import logging
import os
from collections import defaultdict
from process import process_tools, process_path, evaluation

'''
    Calculate the log and stack trace scores
'''

logger = logging.getLogger(__name__)


def calculate_stack_trace_score(datas):
    # Assign a decrement score to the files in the stack trace
    scores = defaultdict(float)
    rank_score_map = [1.0, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.12, 0.11, 0.1]
    for data in datas:
        for current_rank, trace in enumerate(data):
            # Assign scores to the top 10 files based on the rank_score_map, and the score for files exceeding 10 is 0.1
            score = rank_score_map[current_rank] if current_rank < len(rank_score_map) else 0.1
            scores[trace] = max(scores[trace], score)
    return scores


def calculate_log_score(execution_paths):
    if not execution_paths:
        return {}
    scores = defaultdict(float)
    methods = process_tools.extract_methods(execution_paths)
    for current_rank, log in enumerate(methods):
        scores[log] = 0.1
    return scores


def combine_scores(log_score, stack_trace_score):
    # Merge log fragments and stack trace scores
    combined_score = defaultdict(float)
    for method_name, score in stack_trace_score.items():
        combined_score[method_name] += score
    for method_name, score in log_score.items():
        combined_score[method_name] += score
    return combined_score


def analyze_bug_report_method(bug_report_text, execution_path):
    """
    Analyze the class-level score of the bug report
    :param bug_report_text:
    :return:
    """
    # Extract stack trace information
    _, stack_traces = process_tools.extract_rank_from_stack_traces(bug_report_text['stack_traces'], bug_report_text['version'].split("-")[0])
    # Calculate the scores of log fragments and stack traces
    log_score = calculate_log_score(execution_path)
    stack_trace_score = calculate_stack_trace_score(stack_traces)
    # Merge and output the scores
    combined_score = combine_scores(log_score, stack_trace_score)
    return combined_score


def process_stack_traces_and_logs(structuration_info):
    """
        Process bug_report and obtain the log and stack trace information of this report
    """
    data = process_tools.read_json(structuration_info)
    scores = []
    for item in data:
        execution_path = process_tools.read_json(os.path.join("ProcessData", "log_methods", f"{item['title']}-log_methods.json"))
        score = analyze_bug_report_method(item, execution_path)
        temp_score = []
        for file, score in score.items():
            logger.info(f"{file}: {score:.2f}")
            temp_score.append([file, score])
        # Sort by score from high to low
        sorted_temp_score = sorted(temp_score, key=lambda x: x[1], reverse=True)
        scores.append([item["title"], sorted_temp_score])

    # Create the log_result directory (if it doesn't exist)
    output_dir = os.path.join('ProcessData', 'st_log_methods_result')
    os.makedirs(output_dir, exist_ok=True)

    for item in scores:
        name, temp_score = item
        # Write to st_methods_result/{name}_st.txt
        output_file = os.path.join(output_dir, f"{name}_st_log_score.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_name, score in temp_score:
                f.write(f"{file_name}: {score:.2f}\n")
        logger.info(f"The result has been written to the file: {output_file}")
    return output_dir
