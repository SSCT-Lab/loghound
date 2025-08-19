import json
import re
import os
import generate_call_graph
# 在文件开头添加networkx导入
import networkx as nx
import evaluation


def process_method_name(method):
    method.replaceAll("$", ".")
    return method


def process_vsm_scores(vsm_result):
    vsm_process_result = {}
    for line in vsm_result:
        if line != "":
            temp = line.split(": ")
            # vsm_class_name = re.sub("\.java", "", temp[0].split("/")[-1])
            vsm_class_name = temp[0]
            vsm_score = float(temp[1])
            vsm_process_result[vsm_class_name] = vsm_score
    return vsm_process_result


# 加载调用图
def load_call_graph(callgraph_json):
    call_graph = {}

    # 遍历 JSON 中的键值对
    for method, called_methods in callgraph_json.items():
        call_graph[method] = called_methods

    return call_graph


# 重构执行路径
def reconstruct_execution_paths(log_methods, call_graph):
    def dfs(method, call_graph, visited):
        """
        深度优先搜索，递归构建执行路径。
        Args:
            method (str): 当前方法。
            call_graph (dict): 调用图。
            visited (set): 已访问方法集合，防止循环。
        Returns:
            dict: 以当前方法为根的执行路径。
        """
        method = re.sub(r"\(.*?\)", "", method)
        if method in visited:  # 防止循环调用
            return None
        visited.add(method)

        path = {method: []}  # 当前方法为根节点
        if method in call_graph:  # 如果该方法存在于调用图中
            for next_method in call_graph[method]:
                sub_path = dfs(next_method, call_graph, visited)  # 递归构建子路径
                if sub_path:
                    path[method].append(sub_path)  # 添加子路径
        return path

    execution_paths = {}
    visited = set()
    for method in log_methods:
        if method not in visited:
            path = dfs(method, call_graph, visited)
            if path:
                execution_paths.update(path)
    return execution_paths


# 去除重复路径
def remove_duplicate_paths(execution_paths):
    unique_paths = []
    seen_paths = set()
    for path in execution_paths:
        path_tuple = tuple(path)
        if path_tuple not in seen_paths:
            unique_paths.append(path)
            seen_paths.add(path_tuple)
    return unique_paths


def find_class_in_execution_paths(execution_paths, target_class):
    """
    在 execution_paths 中查找某个类是否出现过。

    Args:
        execution_paths (dict): 执行路径的树状结构。
        target_class (str): 需要查找的类名。

    Returns:
        bool: 如果找到目标类，返回 True；否则返回 False。
    """
    for method, sub_paths in execution_paths.items():
        # 检查当前方法是否包含目标类名
        if target_class in method:
            return True
        # 递归检查子路径
        for sub_path in sub_paths:
            if find_class_in_execution_paths(sub_path, target_class):
                return True
    return False


# 计算路径分数（path_score）
def calculate_path_score(execution_paths, vsm_result_key, vsm_result_value, beta=0.2):
    # vsm_class_name = re.sub("\.java", "", vsm_result_key.split("/")[-1])
    # vsm_score = float(vsm_result_value)
    # # print(vsm_class_name)
    #
    # if find_class_in_execution_paths(execution_paths, vsm_class_name):
    #     path_score = beta * vsm_score
    #     return vsm_result_key + ": " + str(path_score)
    vsm_method_name = vsm_result_key.split("\\")[-1].replace(".java", "")
    vsm_score = float(vsm_result_value)
    print("vsm score:", vsm_score)

    # 构建图结构
    G = build_graph_from_execution_paths(execution_paths)

    # 计算PageRank分数
    pagerank_scores = nx.pagerank(G, alpha=0.85)

    # 查找目标类或方法是否在执行路径中
    target_found = False
    target_nodes = []

    for node in G.nodes():
        clz_name = node.split("#")[0].split(".")[-1] if "#" in node else node.split(".")[-1]
        if vsm_method_name == clz_name:
            target_found = True
            target_nodes.append(node)

    if target_found:
        # 计算目标节点的PageRank分数总和
        target_pagerank_score = sum(pagerank_scores.get(node, 0) for node in target_nodes)

        # 结合VSM分数和PageRank分数计算最终分数
        # 可以调整alpha值来控制VSM和PageRank的权重
        final_score = beta * vsm_score + (1 - beta) * target_pagerank_score
        return vsm_result_key + ": " + str(final_score)

    return None

    # 用于识别类
    # for execution_path in execution_paths:
    #     if find_clz_in_execution_paths(execution_path, vsm_method_name):
    #         path_score = beta * vsm_score
    #         return vsm_result_key + ": " + str(path_score)

    # if find_method_in_execution_paths(execution_paths, vsm_method_name):
    #     path_score = beta * vsm_score
    #     return vsm_result_key + ": " + str(path_score)
    # return None


def build_graph_from_execution_paths(execution_paths):
    """
    从执行路径构建有向图

    Args:
        execution_paths (dict): 执行路径的树状结构

    Returns:
        nx.DiGraph: 构建的有向图
    """
    G = nx.DiGraph()

    def add_edges_from_path(path_dict):
        for method, sub_paths in path_dict.items():
            # 添加节点
            G.add_node(method)

            # 添加边和递归处理子路径
            for sub_path in sub_paths:
                # print(sub_path)
                if isinstance(sub_path, dict):
                    for called_method in sub_path.keys():
                        # print(called_method)
                        G.add_edge(method, called_method)
                        add_edges_from_path(sub_path)

    for execution_path in execution_paths:
        add_edges_from_path(execution_path)
    return G


def calculate_pagerank_path_score(execution_paths, vsm_result, beta=0.2):
    """
    使用PageRank算法为所有路径计算分数

    Args:
        execution_paths (dict): 执行路径
        vsm_result (dict): VSM结果
        beta (float): VSM权重

    Returns:
        dict: 每个节点的综合评分
    """
    # 构建图结构
    G = build_graph_from_execution_paths(execution_paths)
    # 计算PageRank分数
    pagerank_scores = nx.pagerank(G, alpha=0.85)

    # 获取所有类名映射
    class_pagerank_map = {}
    for node in G.nodes():
        clz_name = node.split("#")[0].split(".")[-1] if "#" in node else node.split(".")[-1]
        if clz_name not in class_pagerank_map:
            class_pagerank_map[clz_name] = 0
        class_pagerank_map[clz_name] += pagerank_scores[node]

    # 结合VSM分数计算最终分数
    final_scores = {}
    for vsm_key, vsm_value in vsm_result.items():
        vsm_method_name = vsm_key.split("\\")[-1].replace(".java", "")
        vsm_score = float(vsm_value)
        if class_pagerank_map.get(vsm_method_name, 0) == 0:
            continue
        pagerank_score = class_pagerank_map.get(vsm_method_name, 0)
        final_score = beta * vsm_score + (1 - beta) * pagerank_score
        final_scores[vsm_key] = final_score

    return final_scores


def calculate_pagerank_path_methods_score(execution_paths, vsm_result, beta=0.2):
    """
    使用PageRank算法为所有路径计算分数

    Args:
        execution_paths (dict): 执行路径
        vsm_result (dict): VSM结果
        beta (float): VSM权重

    Returns:
        dict: 每个节点的综合评分
    """
    # 构建图结构
    G = build_graph_from_execution_paths(execution_paths)
    # 计算PageRank分数
    pagerank_scores = nx.pagerank(G, alpha=0.85)

    # 获取所有方法名映射
    method_pagerank_map = {}
    for node in G.nodes():
        # full_name = node.split(".")[-1].replace("()", "")
        # print(full_name)
        if node not in method_pagerank_map:
            method_pagerank_map[node] = 0
        method_pagerank_map[node] += pagerank_scores[node]

    # 结合VSM分数计算最终分数
    final_scores = {}
    for method_name, pagerank_score in method_pagerank_map.items():
        # 查找对应的VSM分数，不存在则为0
        vsm_score = 0.0
        # 在vsm_result中查找匹配的方法
        for vsm_key, vsm_value in vsm_result.items():
            vsm_method_name = vsm_key.split("$")[-1] if "$" in vsm_key else vsm_key.split("\\")[-1]
            if vsm_method_name == method_name.split(".")[-1].replace("()", ""):
                vsm_score = float(vsm_value)
                break

        # 计算最终分数
        final_score = beta * vsm_score + (1 - beta) * pagerank_score
        final_scores[method_name] = final_score
    # for vsm_key, vsm_value in vsm_result.items():
    #     vsm_method_name = vsm_key.split("$")[-1] if "$" in vsm_key else vsm_key.split("\\")[-1]
    #     print("vsm_method_name：" + vsm_method_name)
    #     vsm_score = float(vsm_value)
    #     if method_pagerank_map.get(vsm_method_name, 0) == 0:
    #         continue
    #     pagerank_score = method_pagerank_map.get(vsm_method_name, 0)
    #     final_score = beta * vsm_score + (1 - beta) * pagerank_score
    #     final_scores[vsm_key] = final_score

    return final_scores


def find_method_in_execution_paths(execution_paths, target_method):
    for method, sub_paths in execution_paths.items():
        clz_method = method.split("#")
        clz = clz_method[0]
        method = clz_method[1]
        method = clz.split(".")[-1] + "#" + method
        if target_method == method:
            return True
        for sub_path in sub_paths:
            if find_method_in_execution_paths(sub_path, target_method):
                return True
    # return False


def find_clz_in_execution_paths(execution_paths, target_clz):
    for clz, sub_paths in execution_paths.items():
        clz = clz.split("#")[0].split(".")[-1]
        # print(clz)
        # print(sub_paths)
        if target_clz == clz:
            return True
        for sub_path in sub_paths:
            if find_clz_in_execution_paths(sub_path, target_clz):
                return True
    return False


# 分析路径（包括获取执行路径和计算分数）
def analyze_paths(issue_report, vsm_result):
    try:
        title = issue_report["title"]
        if os.path.exists(f"call_graph\\{title}-path.json"):
            execution_paths = json.load(open(f"call_graph\\{title}-path.json", 'r', encoding='utf-8'))
        else:
            # execution_paths = generate_call_graph(issue_report)
            return None
        # 保存路径和得分到单独的文件
        output_directory = f"ProcessData/path_results"
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        output_file_path = f"{output_directory}/{title}_paths_score.txt"
        # 使用PageRank计算路径得分
        final_scores = calculate_pagerank_path_score(execution_paths, vsm_result, beta=0.2)
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            for k, v in final_scores.items():
                if v > 0:  # 只写入非零分数
                    output_file.write(f"{k}: {v}\n")
        print(f"Processed and saved: {output_file_path}")
        # 计算路径得分
        # with open(output_file_path, "w", encoding="utf-8") as output_file:
        #     for k, v in vsm_result.items():
        #         print(k, v)
        #         score = calculate_path_score(execution_paths, k, v, beta=0.2)
        #         if score:
        #             output_file.write(f"{score}\n")

    except Exception as e:
        print(f"Error processing bug report {title}: {e}")


def analyze_methods_paths(issue_report, vsm_result, output_directory):
    """
    Used to calculate the path score at the method level
    :param issue_report:
    :param vsm_result:
    :return:
    """
    try:
        title = issue_report['title']
        execution_paths = get_execution_paths(issue_report)
        if not execution_paths:
            return None

        # 保存路径和得分到单独的文件
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        output_file_path = f"{output_directory}/{title}_paths_score.txt"
        # 使用PageRank计算路径得分
        final_scores = calculate_pagerank_path_methods_score(execution_paths, vsm_result, beta=0.2)
        final_scores = {k: score for k, score in final_scores.items() if score > 0}
        final_scores = evaluation.normalize_vsm_scores(final_scores)
        print(final_scores)
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            for k, v in final_scores.items():
                if v > 0:  # 只写入非零分数
                    output_file.write(f"{k}: {v}\n")
        print(f"Processed and saved: {output_file_path}")
        # 计算路径得分
        # with open(output_file_path, "w", encoding="utf-8") as output_file:
        #     for k, v in vsm_result.items():
        #         print(k, v)
        #         score = calculate_path_score(execution_paths, k, v, beta=0.2)
        #         if score:
        #             output_file.write(f"{score}\n")

    except Exception as e:
        print(f"Error processing bug report {title}: {e}")


def get_execution_paths(issue_report):
    title = issue_report["title"]
    call_graph_file = os.path.join("ProcessData", "call_graph", f"{title}-path.json")
    if os.path.exists(call_graph_file):
        execution_paths = json.load(open(call_graph_file, 'r', encoding='utf-8'))
    else:
        execution_paths = generate_call_graph.generation(issue_report, os.path.join("ProcessData", "tree",
                                                                                    issue_report['version'] + ".json"))
    return execution_paths


def process_method(method_sig):
    without_generics = re.sub(r'<.*>', '', method_sig)
    without_params = re.sub(r'\(.*\)', '', without_generics)
    method_sig = "#".join(without_params.rsplit(".", 1))
    return method_sig


def process_code_coverage(issue, methods, alpha=1):
    version = issue["version"]
    coverage_dir = "coverage"
    with open(os.path.join(coverage_dir, f"{version}_coverage.json")) as f:
        coverage_data = json.load(f)

    cov_methods = dict()
    total = 1
    for method in methods:
        method = method.replace("()", "")
        value = cov_methods.get(method, set())
        for cov_data in coverage_data:
            method_sig = cov_data["method_sig"]
            covering_tests = cov_data["covering_tests"]
            method_sig = process_method(method_sig)
            if method_sig.split(".")[-1] == method.split(".")[-1]:
                old = len(value)
                for test in covering_tests:
                    value.add(test)
                new = len(value)
                total += new - old
        cov_methods[method] = value
    methods_scores = dict()
    n = len(cov_methods)
    for method, tests in cov_methods.items():
        methods_scores[method] = (len(tests) + alpha) / (total + alpha * n)
        methods_scores[method] = 1 - methods_scores[method]

    methods_scores = dict(sorted(
        methods_scores.items(),
        key=lambda item: item[1],  # Sort by the second item (value)
        reverse=True  # Setting it to True indicates descending sorting, while False indicates ascending sorting
    ))
    if not os.path.exists(os.path.join("ProcessData", "code_coverage")):
        os.makedirs(os.path.join("ProcessData", "code_coverage"))
    output = os.path.join("ProcessData", "code_coverage", issue['title'] + "_coverage.txt")
    with open(output, "w", encoding="utf-8") as f:
        for k, v in methods_scores.items():
            if v > 0:
                f.write(f"{k}: {v}\n")
    return methods_scores


def get_methods(execution_paths, methods=None):
    """
        Recursively extract all methods from the nested structure

        parameter:
            data: Nested data structures containing methods
            methods: A collection used for storing the extraction results

        return:
            A list of all extracted methods (de-duplicated)
        """
    if methods is None:
        methods = set()

    # If it is a list, each element is processed recursively
    if isinstance(execution_paths, list):
        for item in execution_paths:
            get_methods(item, methods)

    # If it is a dictionary, handle keys and values
    elif isinstance(execution_paths, dict):
        for key, value in execution_paths.items():
            methods.add(key)
            get_methods(value, methods)

    return list(methods)


def process_path_score(structuration_info):
    with open(structuration_info, "r", encoding="utf-8") as f:
        data = json.load(f)
    output_directory = f"ProcessData/path_methods_results"
    for item in data:
        title = item["title"]
        try:
            vsm_directory = os.path.join('ProcessData', 'vsm_result')
            # Obtain the VSM score.
            vsm_name = title + "_vsm.txt"
            with open(os.path.join(vsm_directory, vsm_name), "r") as f:
                vsm_result = f.read().split("\n")
            process_vsm_score = evaluation.normalize_vsm_scores(process_vsm_scores(vsm_result))
            analyze_methods_paths(item, process_vsm_score, output_directory)
            execution_paths = get_execution_paths(item)
            methods = get_methods(execution_paths)
            process_code_coverage(item, methods)
            print(f"Success processing file {title}")
        except Exception as e:
            print(f"Error processing file {title}: {e}")
    return output_directory


if __name__ == '__main__':
    # with open("parsed_enhanced_logs.json", "r", encoding="utf-8") as f:
    #     data = json.load(f)
    #
    # for item in data:
    #     title = item["title"]
    #     call_graph_file = os.path.join("call_graph", f"{title}-path.json")
    #     if not os.path.exists(call_graph_file):
    #         continue
    #     execution_paths = json.load(open(call_graph_file, 'r', encoding='utf-8'))
    #     methods = get_methods(execution_paths)
    #     methods_scores = process_code_coverage(item, methods)
    process_path_score("parsed_enhanced_logs.json")
