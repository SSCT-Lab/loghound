import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from multiprocessing import Pool


def get_bug_tokens(base_path):
    # 存储每个错误报告的 tokens 列表
    bug_reports_tokens = []
    bug_report_names = []

    # 获取bug_reports文件夹下的所有文件，排除隐藏文件
    files = [f for f in os.listdir(base_path) if not f.startswith('.')]

    # 过滤出 .txt 文件（每个txt文件对应一个错误报告）
    tokens_files = [f for f in files if f.endswith('.txt')]

    # 按照文件名排序，确保顺序一致
    tokens_files.sort()

    for tokens_file in tokens_files:
        tokens_file_path = os.path.join(base_path, tokens_file)
        # print(tokens_file)
        # 打开并读取 tokens 文件
        with open(tokens_file_path, 'r', encoding='utf-8') as f:
            tokens = [line.strip() for line in f if line.strip()]
            if tokens:
                bug_reports_tokens.append(tokens)
                bug_report_names.append(tokens_file.replace('_tokens.txt', ''))

    return bug_reports_tokens, bug_report_names


def get_source_files(base_path, project_name):
    # 获取项目下所有的tokens文件
    project_dir = os.path.join(base_path, project_name)
    source_files = [f for f in os.listdir(project_dir) if f.endswith('_tokens.txt') and not f.startswith('.')]
    source_files.sort()
    return source_files


def get_source_tokens(file_path):
    # 读取源代码文件的tokens，并返回其相对路径和tokens
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        relative_path = lines[0].strip()  # 第一行是Java文件的相对路径
        tokens = [line.strip() for line in lines[1:] if line.strip()]  # 剩余行是tokens
    return relative_path, tokens


def save_vsm_result(bug_report_name, vsm_results):
    # 创建vsm_result文件夹（如果不存在）
    output_dir = 'ProcessData/vsm_result'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 定义输出文件路径
    output_file = os.path.join(output_dir, f"{bug_report_name}_vsm.txt")

    # 将VSM结果写入txt文件，并按相似度排序
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in vsm_results:
            f.write(f"{result[0]}: {result[1]:.4f}\n")


def process_source_file(args):
    bug_report_text, source_file_path, stop_words = args
    relative_path, source_tokens = get_source_tokens(source_file_path)

    # 将源代码的 tokens 转换为字符串
    source_code_text = ' '.join(source_tokens)

    # 构建文档集合：一个错误报告 + 一个源代码段
    documents = [bug_report_text, source_code_text]

    # 创建 TfidfVectorizer 实例
    vectorizer = TfidfVectorizer(stop_words=stop_words)

    # 计算 TF-IDF 矩阵
    tfidf_matrix = vectorizer.fit_transform(documents)

    # 分割错误报告和源代码段的向量
    bug_report_vector = tfidf_matrix[0]
    source_code_vector = tfidf_matrix[1]

    # 计算相似度
    similarity = cosine_similarity(bug_report_vector, source_code_vector.reshape(1, -1)).flatten()[0]

    return (relative_path, similarity)


def aggregate_vsm_results(vsm_results):
    # 定义一个字典，用于聚合同一类的多个tokens文件
    aggregated_results = {}

    for relative_path, similarity in vsm_results:
        # 提取类名（假设类名是文件名的第一部分）
        class_name = relative_path.split('_')[0]

        # 如果字典中没有该类名，直接添加
        if class_name not in aggregated_results:
            aggregated_results[class_name] = (relative_path, similarity)
        else:
            # 更新为相似度更高的文件
            if similarity > aggregated_results[class_name][1]:
                aggregated_results[class_name] = (relative_path, similarity)

    # 返回聚合后的结果
    return list(aggregated_results.values())


def aggregate_vsm_results_methods(vsm_results):
    """
    按照方法命来进行聚合
    :param vsm_results:
    :return:
    """
    # 定义一个字典，用于聚合同一类的多个tokens文件
    aggregated_results = {}

    for relative_path, similarity in vsm_results:
        # 提取类名#方法名
        # print(relative_path)
        full_name = relative_path

        # 如果字典中没有该类名，直接添加
        if full_name not in aggregated_results:
            aggregated_results[full_name] = (relative_path, similarity)
        else:
            # 更新为相似度更高的文件
            if similarity > aggregated_results[full_name][1]:
                aggregated_results[full_name] = (relative_path, similarity)

    # 返回聚合后的结果
    return list(aggregated_results.values())


if __name__ == '__main__':

    # 获取错误报告的 tokens 及对应项目名称和错误报告名称
    bug_reports_tokens, bug_report_names = get_bug_tokens("ProcessData\\bug_reports_tokens")

    # print(bug_report_names)
    # print(bug_reports_tokens)
    with open("parsed_enhanced_logs.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    projects = {item['title']: item['version'] for item in data}

    # 定义停用词列表
    stop_words = ['public', 'class', 'void', 'new', 'if', 'else', 'for', 'while', 'return',
                  '{', '}', '(', ')', ';', '...']

    for i, (bug_tokens, bug_report_name) in enumerate(zip(bug_reports_tokens, bug_report_names)):
        # 将错误报告的 tokens 转换为字符串
        bug_report_text = ' '.join(bug_tokens)

        project_name = projects.get(bug_report_name.replace("_token.txt", ""))
        if project_name.startswith("MAPREDUCE") or project_name.startswith("HDFS"):
            project_name = project_name.replace("MAPREDUCE", "hadoop")
            project_name = project_name.replace("HDFS", "hadoop")

        # print(project_name)

        # 获取对应项目下的所有源代码tokens文件
        source_files = get_source_files("ProcessData\\source_code_methods_tokens", project_name)

        if not source_files:
            print(f"未找到项目 {project_name} 的源代码tokens文件")
            continue

        # 准备传递给子进程的参数列表
        args_list = [
            (bug_report_text, os.path.join("ProcessData\\source_code_methods_tokens", project_name, source_file), stop_words)
            for source_file in source_files
        ]

        # 使用多进程池并行处理源代码文件
        with Pool(processes=4) as pool:  # 根据您的CPU核心数调整进程数量
            vsm_results = pool.map(process_source_file, args_list)

        # 按类名聚合结果，仅保留相似度最高的文件
        # aggregated_results = aggregate_vsm_results(vsm_results)

        # 按类名#方法名聚合结果，仅保留相似度最高的文件
        aggregated_results = aggregate_vsm_results_methods(vsm_results)

        # 按相似度从高到低排序
        aggregated_results.sort(key=lambda x: x[1], reverse=True)

        # 保存结果到vsm_result文件夹中的对应错误报告txt文件
        save_vsm_result(bug_report_name.replace("_token.txt", ""), aggregated_results)

        # # 输出结果
        print(f"错误报告 {i} ({bug_report_name}) 的相似度分析已完成，并保存到 ProcessData\\vsm_result\\{bug_report_name.replace('_token.txt', '')}_vsm.txt")