import json
import re
import os
from collections import defaultdict

'''
    计算日志分数
'''


def extract_log_snippets(log_text):
    # 使用正则表达式提取日志片段
    log_snippet_pattern = r'(.*) (.*\.java) (.*)'
    classes = []
    for log in log_text:
        log_snippets = re.findall(log_snippet_pattern, log)
        for snippet in log_snippets:
            classes.append(snippet[1])
    return classes


def extract_stack_traces(stack_traces_text):
    # 使用正则表达式提取堆栈跟踪信息
    methods = []
    for stack_trace_text in stack_traces_text:
        stack_trace_pattern = r'at ([\w\.]+)\.([\w]+)\(([\w]+\.java):\d+\)'
        stack_traces = re.findall(stack_trace_pattern, stack_trace_text)
        for stack_trace in stack_traces:
            methods.append(stack_trace[0] + "#" + stack_trace[1])
            # methods.append(stack_trace[0])
    return methods


def calculate_log_snippet_score(log_snippets, alpha=0.1):
    # 为日志片段中的每个文件分配固定分数0.1，只计算一次
    log_score = defaultdict(float)
    print(log_score)
    for snippet in log_snippets:
        class_name = snippet[2]  # Fully qualified class name
        method_name = snippet[3]
        # print(class_name, method_name)
        full_method_name = f"{class_name}#{method_name}"
        # print(full_method_name)
        log_score[full_method_name] = alpha
    return log_score


def calculate_stack_trace_score(stack_traces):
    # 为堆栈跟踪中的文件分配递减分数
    stack_trace_score = defaultdict(float)
    rank_score_map = [1.0, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.12, 0.11, 0.1]  # 前10名的分数
    for current_rank, trace in enumerate(stack_traces):
        # print(current_rank)
        # print("==============================================")
        # print(trace)
        # 根据rank_score_map为前10个文件分配分数，超过10的文件分数为0.1
        score = rank_score_map[current_rank] if current_rank < len(rank_score_map) else 0.1
        # 如果文件已存在，仅保留最大分数
        stack_trace_score[trace] = max(stack_trace_score[trace], score)
    return stack_trace_score


def combine_scores(log_score, stack_trace_score):
    # 合并日志片段和堆栈跟踪分数
    combined_score = defaultdict(float)
    for method_name, score in log_score.items():
        combined_score[method_name] += score
    for method_name, score in stack_trace_score.items():
        combined_score[method_name] += score
    return combined_score


def analyze_bug_report(bug_report_text):
    # 提取日志片段和堆栈跟踪信息
    log_snippets = extract_log_snippets(bug_report_text["logs"])
    stack_traces = extract_stack_traces(bug_report_text["stack_traces"])
    # print(stack_traces)
    # 计算日志片段和堆栈跟踪的分数
    log_score = calculate_log_snippet_score(log_snippets)
    stack_trace_score = calculate_stack_trace_score(stack_traces)
    # print(stack_trace_score)
    # 合并并输出分数
    combined_score = combine_scores(log_score, stack_trace_score)
    return combined_score


def analyze_bug_report_method(bug_report_text):
    """
    由于bug report中只有stack trace存在方法，因此只计算stack trace即可
    :param bug_report_text:
    :return:
    """
    stack_traces = extract_stack_traces(bug_report_text["stack_traces"])
    stack_trace_score = calculate_stack_trace_score(stack_traces)
    return stack_trace_score


def get_log_text(bug_report):
    fields = bug_report.get('fields', {})
    summary = fields.get('summary', '')
    description = fields.get('description', '')

    # 确保 summary 和 description 为字符串
    summary = summary if isinstance(summary, str) else ''
    description = description if isinstance(description, str) else ''

    log_text = summary + ' ' + description
    # print(log_text)
    # 检查 description 是否包含日志或堆栈跟踪的格式
    log_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+) (.+): (.+)'
    stack_trace_pattern = r'at ([\w\.]+)\(([\w]+\.java):\d+\)'

    if re.search(log_pattern, description) or re.search(stack_trace_pattern, description, re.MULTILINE):
        return log_text


if __name__ == '__main__':
    '''
        处理bug_report并获取该报告的日志和堆栈跟踪信息
    '''
    with open("parsed_enhanced_logs.json", "r", encoding='utf-8') as f:
        data = json.load(f)

    st_scores = []
    for item in data:
        st_score = analyze_bug_report_method(item)
        temp_score = []
        for file, score in st_score.items():
            print(f"{file}: {score:.2f}")
            temp_score.append([file.replace(".", "\\"), score])
            # 按照得分从大到小排序
            sorted_temp_score = sorted(temp_score, key=lambda x: x[1], reverse=True)
        st_scores.append([item["title"], sorted_temp_score])

    # 创建log_result目录（如果不存在）
    output_dir = 'ProcessData\\st_methods_result'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for item in st_scores:
        name, temp_score = item
        # 写入到log_result/{name}_st.txt
        output_file = os.path.join(output_dir, f"{name}_st.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_name, score in temp_score:
                f.write(f"{file_name}: {score:.2f}\n")
        print(f"已将结果写入文件：{output_file}")

    # for project_name in project_names:
    #     directory = 'bug_reports/'+ project_name +'/details'
    # directory = 'bug_reports/'
    # items = os.listdir(directory)
    #
    # # 仅获取文件，忽略文件夹
    # files = [item.replace('.json', '') for item in items if os.path.isfile(os.path.join(directory, item))]
    # print(files)
    #
    # log_scores = []
    # for name in files:
    #     # with open('bug_reports/' + project_name + '/' + name + '.json', 'r') as f:
    #     with open('bug_reports/' + name + '.json', 'r', encoding='utf-8') as f:
    #         data = json.load(f)
    #
    #     # 判断是否含有log或堆栈跟踪信息
    #     log_text = get_log_text(data)
    #     if log_text is not None:
    #         # 导出日志
    #         # if not os.path.exists('log_texts/' + project_name):
    #             # os.mkdir('log_texts/' + project_name)
    #         if not os.path.exists('log_texts/'):
    #             os.mkdir('log_texts/')
    #         # with open('log_texts/' + project_name + '/' + name + '_logtext.txt', 'w') as f:
    #         with open('log_texts/' + name + '_logtext.txt', 'w', encoding="utf-8") as f:
    #             f.write(log_text)
    #
    #         # 分析日志并输出结果
    #         result = analyze_bug_report(log_text)
    #         # print(result + "\n")
    #         # print('bug_reports/Zookeeper/' + name + '.json'+"文件可疑性分数:")
    #         temp_score = []
    #         for file, score in result.items():
    #             # print(f"{file}: {score:.2f}")
    #             temp_score.append([file, score])
    #             # 按照得分从大到小排序
    #             sorted_temp_score = sorted(temp_score, key=lambda x: x[1], reverse=True)
    #         log_scores.append([name, sorted_temp_score])
    #
    # # sorted_log_scores = sorted(log_scores, key=lambda x: x[0], reverse=True)
    # print(f"共处理了 {len(log_scores)} 个错误报告。")

    # 创建log_result目录（如果不存在）
    # output_dir = 'log_result'
    # if not os.path.exists(output_dir):
    #     os.makedirs(output_dir)
    #
    # for item in log_scores:
    #     name, temp_score = item
    #     # 写入到log_result/{name}_log.txt
    #     output_file = os.path.join(output_dir, f"{name}_log.txt")
    #     with open(output_file, 'w', encoding='utf-8') as f:
    #         for file_name, score in temp_score:
    #             f.write(f"{file_name}: {score:.2f}\n")
    #     print(f"已将结果写入文件：{output_file}")
    # str = """
    #     at org.apache.zookeeper.server.quorum.QuorumCnxManagerSendWorker.send(QuorumCnxManager.java:512)
    #     at org.apache.zookeeper.server.quorum.QuorumCnxManagerSendWorker.run(QuorumCnxManager.java:548)
    # """
    # log_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+) ([\w\.]+): (.+)'
    # stack_trace_pattern = r'at ([\w\.]+)\(([\w]+\.java):\d+\)'
    # print(re.search(log_pattern, str))
    # print(re.search(stack_trace_pattern, str))
