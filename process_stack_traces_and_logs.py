import json
import logging
import re
import os
from collections import defaultdict
import generate_call_graph
import process_path

'''
    Calculate the log and stack trace scores
'''


def extract_methods(execution_path, methods=None):
    """
    提取所有方法名

    Args:
        execution_paths: 执行路径数据结构
        methods: 用于存储方法名的集合

    Returns:
        list: 所有方法名列表
    """
    if methods is None:
        methods = set()

    if isinstance(execution_path, list):
        for item in execution_path:
            extract_methods(item, methods)
    elif isinstance(execution_path, dict):
        for method, sub_paths in execution_path.items():
            methods.add(method)
            extract_methods(sub_paths, methods)

    return list(methods)


def calculate_stack_trace_score(datas):
    # 为堆栈跟踪中的文件分配递减分数
    scores = defaultdict(float)
    rank_score_map = [1.0, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.12, 0.11, 0.1]  # 前10名的分数
    for current_rank, trace in enumerate(datas):
        # print(current_rank)
        # print("==============================================")
        # print(trace)
        # 根据rank_score_map为前10个文件分配分数，超过10的文件分数为0.1
        score = rank_score_map[current_rank] if current_rank < len(rank_score_map) else 0.1
        # scores[trace] = 0.1
        # 如果文件已存在，仅保留最大分数
        scores[trace] = max(scores[trace], score)
    return scores


def calculate_log_score(execution_paths):
    if not execution_paths:
        return {}
    scores = defaultdict(float)
    for execution_path in execution_paths:
        methods = extract_methods(execution_path)
        # rank_score_map = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.12, 0.11, 0.1]
        # rank_score_map = [0.1]
        for current_rank, log in enumerate(methods):
            # score = rank_score_map[current_rank] if current_rank < len(rank_score_map) else 0.1
            scores[log] = 0.1
    return scores


def combine_scores(log_score, stack_trace_score, system):
    # 合并日志片段和堆栈跟踪分数
    combined_score = defaultdict(float)
    for method_name, score in log_score.items():
        if system not in method_name:
            continue
        combined_score[method_name] += score
    for method_name, score in stack_trace_score.items():
        if system not in method_name:
            continue
        combined_score[method_name] += score
    return combined_score


def extract_log_snippets(bug_report, api_key):
    title = bug_report['title']
    logs = bug_report['logs']
    if not logs:
        return []
    version = bug_report['version'].replace("HDFS", "hadoop").replace("MAPREDUCE", "hadoop")
    system = version.split("-")[0]

    if os.path.exists(f"classes/{title}-classes.json"):
        classes = json.load(open(f"classes/{title}-classes.json", "r", encoding="utf-8"))
    else:
        classes = generate_call_graph.extract_classes_and_content_from_log(logs, system)
        if not classes:
            print(f"{title}没有提取到类名和日志信息，使用GPT来提取日志信息和类名")
            classes = generate_call_graph.extract_classes_and_content_from_log_with_gpt(logs,
                                                                                        api_key=api_key)
        with open(f"classes/{title}-classes.json", "w", encoding="utf-8") as f:
            json.dump(classes, f, ensure_ascii=False, indent=4)

    with open(f'E:/Code/ASTgenerate/tree/{version}.json', 'r', encoding='utf-8') as file:
        call_graph = json.load(file)

    methods = []
    for clazz in classes:
        method_log = generate_call_graph.parse_log_methods(clazz, call_graph)
        methods.append(method_log)
    log_snippets = []
    for data in reversed(methods):
        log_snippets.append(data['method'].replace("()", ""))
    return log_snippets


def extract_stack_traces(stack_traces):
    pattern = re.compile(
        r'at\s+'  # 匹配"at "前缀
        r'(?P<class>[\w.$]+)\.'  # 匹配类名（包含包名和内部类）
        r'(?P<method>[\w]+)'  # 匹配方法名
        r'\s*\(.*?\)'  # 匹配括号及其中的内容（文件名和行号）
    )

    methods = []
    for stack_trace in stack_traces:
        st_list = [line.strip() for line in stack_trace.split("\n")]
        for line in st_list:
            method_match = pattern.search(line)
            if method_match:
                class_name = method_match.group('class')
                method_name = method_match.group('method')
                methods.append(f"{class_name}#{method_name}")
    return methods


def analyze_bug_report_method(bug_report_text, execution_path):
    """
    Analyze the class-level score of the bug report
    :param bug_report_text:
    :return:
    """
    # Extract stack trace information
    stack_traces = extract_stack_traces(bug_report_text['stack_traces'])
    # Calculate the scores of log fragments and stack traces
    log_score = calculate_log_score(execution_path)
    stack_trace_score = calculate_stack_trace_score(stack_traces)
    # Merge and output the scores
    combined_score = combine_scores(log_score, stack_trace_score, bug_report_text['version'].split("-")[0])
    return combined_score


def process_stack_traces_and_logs(structuration_info):
    """
        Process bug_report and obtain the log and stack trace information of this report
    """
    with open(structuration_info, "r", encoding='utf-8') as f:
        data = json.load(f)

    scores = []
    for item in data:
        execution_path = process_path.get_execution_paths(item)
        score = analyze_bug_report_method(item, execution_path)
        temp_score = []
        for file, score in score.items():
            logging.info(f"{file}: {score:.2f}")
            temp_score.append([file.replace(".", "\\"), score])
        # Sort by score from high to low
        sorted_temp_score = sorted(temp_score, key=lambda x: x[1], reverse=True)
        scores.append([item["title"], sorted_temp_score])

    # Create the log_result directory (if it doesn't exist)
    output_dir = 'ProcessData\\st_methods_result'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for item in scores:
        name, temp_score = item
        # Write to st_methods_result/{name}_st.txt
        output_file = os.path.join(output_dir, f"{name}_st.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_name, score in temp_score:
                f.write(f"{file_name}: {score:.2f}\n")
        logging.info(f"已将结果写入文件：{output_file}")
    return output_dir


if __name__ == '__main__':
    process_stack_traces_and_logs("parsed_enhanced_logs.json")
