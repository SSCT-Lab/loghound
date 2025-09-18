import json
import os.path
import re
import sys
from typing import List, Dict
import logging
from process import process_tools

logger = logging.getLogger(__name__)


def parse_log_methods(content, call_graph):
    """
    Parse the calling methods in the log file through classes.
    Args:
        content: The classes involved in the log.
        call_graph:
    Returns:
        list: Call the list of methods.
    """
    methods_log = {
        'method': "",
        'callee': []
    }
    clazz_name = content['class'].replace("$", ".").split(".")[-1]

    for clz, call_graph_data in call_graph.items():
        clz = clz.replace("$", ".")
        if clazz_name == clz.split('.')[-1]:
            clz_methods = call_graph_data['methods']
            # Traverse all the methods of the classes involving logs to find the corresponding methods for the
            # matching logs
            for method in clz_methods:
                for method_name, method_data in method.items():
                    logs = method_data['logs']
                    if len(logs) != 0:
                        matched = match_log_event(content['type'], content['content'].strip(), logs, True)
                        # If the target log is matched, the method and the involved calling method will be stored in
                        # methods_log
                        if matched:
                            methods_log['method'] = method_name
                            for call in method_data['calls']:
                                methods_log['callee'].append(call['callee'])

    if methods_log['method'] == "":
        for clz, call_graph_data in call_graph.items():
            normalized_clz = clz.replace("$", ".")
            normalized_clz_short = normalized_clz.split('.')[-1]

            if normalized_clz_short == clazz_name:
                continue

            for method in call_graph_data['methods']:
                for method_name, method_data in method.items():
                    logs = method_data['logs']
                    if len(logs) > 0 and match_log_event(content['type'], content['content'].strip(), logs, False):
                        methods_log['method'] = method_name
                        for call in method_data['calls']:
                            methods_log['callee'].append(call['callee'])

    return methods_log


def match_log_event(level, log, log_events, is_class=True):
    """
    Match the corresponding log content through the log event template
    :param level: loglevel
    :param log: log info
    :param log_events: log template
    :return: Whether the match is successful or not
    """
    try:
        for event in log_events:
            if len(event['template']) == 0 or (not is_class and len(event['template'].replace("{}", "").strip()) < 2):
                continue

            event_level = event['level']
            if level != "UNKNOWN" and level.lower() != event_level.lower():
                continue

            temp_placeholder = "__LOG_PLACEHOLDER__"
            escaped_template = event['template'].replace("{}", temp_placeholder).strip()
            escaped_template = re.escape(escaped_template)
            log_event = escaped_template.replace(temp_placeholder, "(.*)")
            # log_event = event['template'].replace('{}', '(.*)')
            match = re.match(log_event, log)
            if match:
                return True
    except Exception as e:
        logger.error(f"Match the corresponding log content through the log event template error: {e}")
        return False

    return False


def build_caller_map(call_graph: Dict, version) -> Dict[str, List[str]]:
    """
    Build the caller mapping table: The key is the full name of the method, and the value is a list of all the full names of the methods that call this method
    """
    caller_map_file = os.path.join('ProcessData', "caller_map", f'{version}_caller_map.json')
    if os.path.exists(caller_map_file):
        caller_map = process_tools.read_json(caller_map_file)
        return caller_map
    caller_map = {}
    for class_name, call_graph_data in call_graph.items():
        for method_entry in call_graph_data.get('methods', []):
            for caller_full_name, method_data in method_entry.items():
                # Traverse all the sub-methods of the current method call (callee)
                for callee in method_data.get('calls', []):
                    callee_name = callee['callee']
                    # Add the current method to the list of callers of the child methods
                    if callee_name not in caller_map:
                        caller_map[callee_name] = []
                    if caller_full_name not in caller_map[callee_name]:
                        caller_map[callee_name].append(caller_full_name)
    os.makedirs(os.path.join("ProcessData", "caller_map"), exist_ok=True)
    process_tools.save_to_json(caller_map, caller_map_file)
    return caller_map


def get_upstream_callers(
        target_method,
        caller_map,
        depth,
        max_depth=100
):
    """
    Obtain the upstream call chain of the specified depth of the target method (the path from the caller to the target method)
    for example：depth=1 -> [M2, M1]，depth=2 -> [M3, M2, M1]
    """
    if depth < 0 or depth > max_depth:
        return []

    # Initial call chain: Directly includes the target method itself (depth 0)
    call_chains = [[target_method]]
    current_depth = 0

    while current_depth < depth:
        new_chains = []
        for chain in call_chains:
            # Take the starting point of the current chain (the top-level caller)
            current_head = chain[0]
            # Find all methods that call the current starting point
            for caller in caller_map.get(current_head, []):
                # Avoid circular calls (such as A->B->A)
                if caller not in chain:
                    new_chain = [caller] + chain
                    new_chains.append(new_chain)
        # If there is no new call chain, terminate prematurely (to avoid invalid loops)
        if not new_chains:
            break
        call_chains.extend(new_chains)
        current_depth += 1

        if current_depth > max_depth:
            call_chains = []
            break

    # Retain all chains with extension depth <= max_expand_depth (i.e., length <= 1 + max_expand_depth)
    return [chain for chain in call_chains if len(chain) <= 1 + depth]


def serialize_chain(chain):
    """The serialized call chain is used for deduplication"""
    return json.dumps(chain, sort_keys=True, ensure_ascii=False)


def truncate_to_last_log_method(path, log_methods):
    """
    截断路径，只保留到最后一个日志方法的部分
    :param path: 嵌套字典结构的路径
    :param log_methods: 所有日志方法的集合
    :return: 截断后的路径，若没有日志方法则返回None
    """
    if not isinstance(path, dict) or len(path) != 1:
        return None

    current_method = next(iter(path.keys()))
    children = path[current_method]

    # 先处理子路径，获取截断后的子路径
    truncated_children = []
    has_log_in_children = False
    for child in children:
        truncated_child = truncate_to_last_log_method(child, log_methods)
        if truncated_child is not None:
            truncated_children.append(truncated_child)
            has_log_in_children = True

    # 子路径中存在日志方法，保留当前节点和截断后的子路径
    if has_log_in_children:
        return {current_method: truncated_children}
    # 子路径中没有日志方法，但当前节点是日志方法，保留当前节点
    elif current_method in log_methods:
        return {current_method: []}
    # 既不是日志方法，子路径也没有日志方法，返回None
    else:
        return None


def reconstruct_execution_paths(log_methods, version, call_graph, depth=1):
    """
    Reconstruct the execution path of the log based on the methods involved in the log
    :param version: system version
    :param log_methods: The methods involved in printing out the log
    :param call_graph: The complete call diagram
    :param depth: The depth of upward expansion (1,2,3)
    :return: Multiple execution paths
    """
    # Filter out empty methods
    valid_methods = [m for m in log_methods if m['method']]
    if not valid_methods:
        return []

    log_method_names = {m['method'] for m in valid_methods}

    # Unify the end_methods format (remove possible parentheses to match the method name)
    processed_log_methods = set()  # The method for tracking processed logs
    seen_methods = set()

    # Build a caller mapping table (reverse lookup of call relationships)
    caller_map = build_caller_map(call_graph, version)

    # Depth-first search function
    def dfs(method_full_name, visited):
        # Termination occurs when the maximum depth downstream is exceeded
        simple_method_name = method_full_name.replace("$", ".").split('.')[-1]

        if simple_method_name in visited:
            return None

        if version.split("-")[0] not in method_full_name:
            return None

        visited = visited.union({simple_method_name})

        if '#' not in method_full_name:
            return {method_full_name: []}

        simple_class_name, method_simple_name = simple_method_name.split('#')

        path = {method_full_name: []}

        # Look for classes and methods in the call diagram
        for class_name, class_info in call_graph.items():
            if simple_class_name not in class_name:
                continue
            for method_entry in class_info.get('methods', []):
                for method_entry_name, method_data in method_entry.items():
                    if method_entry_name.replace("$", ".").split(".")[-1] == simple_method_name:
                        callees = method_data['calls']
                        for callee in callees:
                            callee_full_name = callee['callee']
                            sub_path = dfs(callee_full_name, visited)
                            if sub_path:
                                if method_full_name in valid_methods:
                                    processed_log_methods.add(method_full_name)
                                path[method_full_name].append(sub_path)
                        return path
        return path

    # Build an execution path for each valid method
    execution_paths = []
    for method in valid_methods:
        method_name = method['method']
        if not method_name:
            continue

        if method_name in processed_log_methods:
            continue
        processed_log_methods.add(method_name)

        # 1. Build the downward call path of the current method (M1 -> MM1 ->...
        downstream_path = dfs(method_name, set())
        if not downstream_path:
            continue

        # 2. Obtain the upstream call chain of the specified depth (such as depth=1: [M2, M1], depth=2: [M3, M2, M1])
        upstream_chains = get_upstream_callers(method_name, caller_map, depth)
        # If there is no upstream call chain, use itself as the starting point
        if not upstream_chains:
            upstream_chains = [[method_name]]

        # 3. Combine the upstream call chain and the downstream path to construct a complete execution path
        for chain in reversed(upstream_chains):
            if len(chain) == 1:
                # Depth 0: Directly use the downstream path
                current_chain = downstream_path
            else:
                # Build a nested structure of the upstream chain (such as M3 -> M2 -> M1)
                current_node = downstream_path
                for caller in reversed(chain[:-1]):  # Exclude the last element (target method)
                    current_node = {caller: [current_node]}
                current_chain = current_node

            truncated_chain = truncate_to_last_log_method(current_chain, log_method_names)
            # truncated_chain = current_chain
            if truncated_chain is None:
                continue

            # Serialization deduplication
            first_method = next(iter(truncated_chain))
            if first_method not in seen_methods:
                execution_paths.append(truncated_chain)
                methods = process_tools.extract_methods(truncated_chain)
                for m in methods:
                    seen_methods.add(m)
        if len(processed_log_methods) == len(valid_methods):
            break

    return execution_paths


def generation(issue_report, source_code_tree, depth: int = 1):
    try:
        os.makedirs(os.path.join("classes"), exist_ok=True)
        title = issue_report['title']
        logger.info(f"process file {title}......")
        logs = issue_report['logs']

        version = issue_report['version']
        system = version.split("-")[0]

        st_methods, _ = process_tools.extract_content_from_stack_traces(issue_report['stack_traces'], system)
        execution_paths = []
        if len(logs) != 0:
            logger.info("Parsing the log file...")
            # Extract the class name
            classes_file = os.path.join("classes", f"{title}-classes.json")
            if os.path.exists(classes_file):
                classes = process_tools.read_json(classes_file)
            else:
                classes = process_tools.extract_classes_and_content_from_log(logs, system)
                if len(classes) != len(logs):
                    logger.info(
                        f"{title} failed to extract the class name and log information. Use GPT to extract the log information and class name")
                    classes = process_tools.extract_classes_and_content_from_log_with_gpt(logs)

                logger.info(f"Extract {len(classes)} class names from the issue '{title}'")
                logger.info(f"classes info: {classes}")

                process_tools.save_to_json(classes, classes_file)

            logger.info("Parsing the call tree...")

            tree_graph = process_tools.read_json(source_code_tree)

            methods = []
            for clazz in classes:
                method_log = parse_log_methods(clazz, tree_graph)
                methods.append(method_log)
            logger.info("The execution path is being constructed...")
            execution_paths = reconstruct_execution_paths(methods, version, tree_graph, depth=depth)

        output_log_methods = os.path.join("ProcessData", 'log_methods', f'{title}-log_methods.json')
        os.makedirs(os.path.join("ProcessData", "log_methods"), exist_ok=True)
        process_tools.save_to_json(execution_paths, output_log_methods)

        if st_methods:
            for st_method in st_methods:
                if st_method:
                    execution_paths.append(st_method)

        logger.info(f"The {len(execution_paths)} execution paths were constructed")
        print(f"The {len(execution_paths)} execution paths were constructed")

        output_call_graph = os.path.join("ProcessData", 'call_graph', f'{title}-path.json')
        os.makedirs(os.path.join("ProcessData", "call_graph"), exist_ok=True)
        process_tools.save_to_json(execution_paths, output_call_graph)
        return execution_paths
    except FileNotFoundError as e:
        logger.error(f"Error: '{issue_report['title']}' not found or {source_code_tree} not found. Error Message: {e}")
        print(f"Error: '{issue_report['title']}' not found or {source_code_tree} not found")
        sys.exit(1)

    except Exception as e:
        logger.error(f"An unknown error occurred: {e}")
        print(f"An unknown error occurred: {e}")
        sys.exit(1)
