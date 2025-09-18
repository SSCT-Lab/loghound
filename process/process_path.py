import logging
import re
import os
import networkx as nx
from process import process_tools, generate_call_graph, evaluation

logger = logging.getLogger(__name__)


def process_vsm_scores(vsm_result):
    vsm_process_result = {}
    for line in vsm_result:
        if line != "":
            temp = line.split(": ")
            vsm_class_name = temp[0]
            vsm_score = float(temp[1])
            vsm_process_result[vsm_class_name] = vsm_score
    return vsm_process_result


def build_graph_from_execution_paths(execution_paths):
    """
    Build a directed graph from the execution path


    Args:
        execution_paths (dict): The tree-like structure of the execution path

    Returns:
        nx.DiGraph: The constructed directed graph
    """
    G = nx.DiGraph()

    def add_edges_from_path(path_dict):
        for method, sub_paths in path_dict.items():
            G.add_node(method)

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


def calculate_pagerank_path_methods_score(execution_paths, vsm_result, coverage_file, beta=0.2):
    """
    Use the PageRank algorithm to calculate scores for all paths

    Args:
        execution_paths (dict)
        vsm_result (dict)
        beta (float)

    Returns:
        dict: The comprehensive score of each node
    """
    G = build_graph_from_execution_paths(execution_paths)
    pagerank_scores = nx.pagerank(G, alpha=0.85)
    coverage_scores = {}
    with open(coverage_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 分割方法名和分数
            method, score = line.split(': ')
            coverage_scores[method] = float(score)

    method_pagerank_map = {}
    for node in G.nodes():
        if node not in method_pagerank_map:
            method_pagerank_map[node] = 0
        method_pagerank_map[node] += pagerank_scores[node]

    final_scores = {}
    for method_name, pagerank_score in method_pagerank_map.items():
        method_name = method_name.replace("$", ".")
        vsm_score = 0.0
        for vsm_key, vsm_value in vsm_result.items():
            vsm_method_name = vsm_key.replace("$", ".").split(".")[-1]
            if vsm_method_name == method_name.split(".")[-1]:
                vsm_score = float(vsm_value)
                break

        coverage_score = 0.0
        for cov_method, score in coverage_scores.items():
            cov_method_name = cov_method.replace("$", ".").split(".")[-1]
            if cov_method_name == method_name.split(".")[-1]:
                coverage_score = float(score)
                break

        final_score = beta * vsm_score + (1 - beta) * pagerank_score * coverage_score
        final_scores[method_name] = final_score

    return final_scores


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

        os.makedirs(output_directory, exist_ok=True)
        output_file_path = os.path.join(f"{output_directory}", f"{title}_paths_score.txt")
        # Calculate the path score using PageRank
        final_scores = calculate_pagerank_path_methods_score(execution_paths, vsm_result, os.path.join("ProcessData", "code_coverage", f"{title}_coverage.txt"), beta=0.2)
        final_scores = {k: score for k, score in final_scores.items() if score > 0}
        final_scores = evaluation.normalize_scores(final_scores)
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            for k, v in sorted(final_scores.items(), key=lambda item: item[1], reverse=True):
                if v > 0:  # 只写入非零分数
                    output_file.write(f"{k}: {v}\n")
        logger.info(f"Processed and saved: {output_file_path}")
        print(f"Processed and saved: {output_file_path}")

    except Exception as e:
        logger.error(f"Error processing bug report {issue_report['title']}: {e}")
        print(f"Error processing bug report {issue_report['title']}: {e}")


def get_execution_paths(issue_report):
    title = issue_report["title"]
    call_graph_file = os.path.join("ProcessData", "call_graph", f"{title}-path.json")
    if os.path.exists(call_graph_file):
        execution_paths = process_tools.read_json(call_graph_file)
    else:
        execution_paths = generate_call_graph.generation(issue_report, os.path.join("ProcessData", "tree",
                                                                                    f"{issue_report['version']}.json"))
    return execution_paths


def process_method(method_sig):
    without_generics = re.sub(r'<.*>', '', method_sig)
    without_params = re.sub(r'\(.*\)', '', without_generics)
    method_sig = "#".join(without_params.rsplit(".", 1))
    return method_sig


def process_code_coverage(issue, methods, alpha=1):
    version = issue["version"]
    coverage_dir = os.path.join("coverage")
    coverage_data = process_tools.read_json(os.path.join(coverage_dir, f"{version}_coverage_method_coverage.json"))

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
    output_dir = os.path.join("ProcessData", "code_coverage")
    os.makedirs(output_dir, exist_ok=True)
    output = os.path.join(output_dir, issue['title'] + "_coverage.txt")
    with open(output, "w", encoding="utf-8") as f:
        for k, v in methods_scores.items():
            if v > 0:
                f.write(f"{k}: {v}\n")


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
    data = process_tools.read_json(structuration_info)
    output_directory = os.path.join("ProcessData", "path_methods_results")
    coverage_output_dir = os.path.join("ProcessData", "code_coverage")
    for item in data:
        title = item["title"]
        try:
            vsm_directory = os.path.join('ProcessData', 'vsm_result')
            # Obtain the VSM score.
            vsm_name = title + "_vsm.txt"
            with open(os.path.join(vsm_directory, vsm_name), "r") as f:
                vsm_result = f.read().split("\n")
            process_vsm_score = evaluation.normalize_scores(process_vsm_scores(vsm_result))
            execution_paths = get_execution_paths(item)
            methods = get_methods(execution_paths)
            process_code_coverage(item, methods)
            analyze_methods_paths(item, process_vsm_score, output_directory)
            logger.info(f"Processed and saved: {output_directory}")
            print(f"Success processing file {title}")
        except Exception as e:
            logger.error(f"Error processing bug report {title}: {e}")
            print(f"Error processing file {title}: {e}")
    return output_directory, coverage_output_dir


if __name__ == '__main__':
    process_path_score(os.path.join("..", "ProcessData", "parsed_enhanced_logs.json"))