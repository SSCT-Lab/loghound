import json
import os.path
import re
import sys
from openai import OpenAI
from typing import List, Dict
import logging

import method_parser

logging.basicConfig(
    filename='extract_logs.log',
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)


def extract_classes_and_content_from_log(logs, system):
    """
    By parsing the corresponding dataset, obtain the class names related to the log
    :param log_text: log info
    :return: relevant class
    """
    pattern_hadoop = r'(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+\s+)?(WARN|INFO|DEBUG|ERROR)\s+([a-zA-Z0-9_.$]+):\s*(.*)'
    pattern_hbase = r'(TRACE|INFO|DEBUG|WARN|ERROR)\s+(?:\[.*?\]\s+)?([^\s:]+):\s*(.*)'
    pattern_cassandra = r'(INFO|DEBUG|WARN|ERROR)\s+\[.*?\]\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+([A-Z][A-Za-z0-9_]*)\.java\s+\(line\s+\d+\)\s+(.*)'
    general_pattern = re.compile(
        r'(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+\s+)?(?:INFO|DEBUG|WARN|ERROR)\s+([a-zA-Z0-9_.$]+):\s*(.*)'
    )
    classes_content = []
    if system == 'hbase':
        pattern = pattern_hbase
    elif system == 'hadoop':
        pattern = pattern_hadoop
    elif system == 'cassandra':
        pattern = pattern_cassandra
    elif system == 'zookeeper':
        return extract_zookeeper_log(logs)
    else:
        pattern = general_pattern

    for line in logs:
        match = re.search(pattern, line)
        if match:
            level = match.group(1)
            full_class_name = match.group(2).split("(")[0]
            content = match.group(3).strip()
            classes_content.append({
                'class': full_class_name,
                'type': level,
                'content': content
            })
    return classes_content


def extract_classes_and_content_from_stack_traces(stack_traces, system):
    pattern = re.compile(
        r'at\s+'
        r'(?P<class>[\w.$]+)\.'
        r'(?P<method>[\w]+)'
        r'\s*\(.*?\)'
    )

    methods_chain = []
    methods = []
    for stack_trace in stack_traces:
        st = []
        st_list = [line.strip() for line in stack_trace.split("\n")]
        for line in st_list:
            method_match = pattern.search(line)
            if method_match:
                class_name = method_match.group('class')
                method_name = method_match.group('method')
                if system not in class_name:
                    continue
                st.append(f"{class_name}#{method_name}")
                methods.append(f"{class_name}#{method_name}")
        methods_chain.append(build_nested_chain(st))
    return methods_chain, methods


def build_nested_chain(method_calls):
    """Convert the method list to the nested call chain format"""
    if not method_calls:
        return []

    # If there are subsequent methods, recursively build the call chain
    current = None
    # Reverse order the method call chain, building from the innermost method to the outside
    for method in reversed(method_calls):
        if current is None:
            # The innermost method has an empty list of values
            current = {method: []}
        else:
            # The outer method, whose value is a list containing the call chain of the next layer
            current = {method: [current]}

    return current


def extract_classes_and_content_from_log_with_gpt(logs, api_key, model="qwen-turbo"):
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    prompt = f"""
    Logs: {logs}
    Based on all the log information provided to you, you need to extract their class names and log contents, and the output format is:
    [{{
        "class": full_class_name1,
        "type": level1,
        "content": content1
    }},
    {{
        "class": full_class_name2,
        "type": level2,
        "content": content2 
    }}]
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        extra_body={"enable_thinking": False},
    )
    results = response.choices[0].message.content
    logging.info("GPT Results: " + results)
    extract_results = json.loads(results)
    print(extract_results)
    logging.info("Extract Results: " + str(extract_results))
    return extract_results


def extract_zookeeper_log(logs):
    parsed_logs = []

    main_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})'  # 时间戳
        r'(?:\s+\[myid:\d+\])?\s*-\s*'  # 可选的[myid:n]和分隔符
        r'(?P<level>[A-Z]+)\s+'  # 日志级别
        r'\[(?:[^]]*:)?(?P<class>[A-Za-z0-9]+)@(?P<line>\d+)\]\s*'  # 类名@行号部分
        r'-\s*(?P<content>.*)$'  # 日志内容
    )

    package_class_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+'  # 时间戳
        r'(?P<level>[A-Z]+)\s+'  # 日志级别
        r'(?:\w+\.)+(?P<class>[A-Z][a-zA-Z0-9]+):\s*'  # 包名.类名: 格式
        r'(?P<content>.*)$'  # 日志内容
    )

    for log in logs:
        log = log.strip()
        if not log:
            continue

        class_name = "UNKNOWN"
        line_number = None
        level = "UNKNOWN"
        content = ""

        # Try to match the main pattern (including the format of the @ line number)
        match = main_pattern.match(log)
        if match:
            level = match.group('level')
            class_name = match.group('class') or "UNKNOWN"
            line_number = match.group('line')
            content = match.group('content').strip()
        else:
            # Try to match the package name and class name format
            pkg_match = package_class_pattern.match(log)
            if pkg_match:
                level = pkg_match.group('level')
                class_name = pkg_match.group('class')
                content = pkg_match.group('content').strip()
            else:
                # Handle other possible formats, extract levels and content
                # Extract log level
                level_match = re.search(r'\s([A-Z]+)\s+', log)
                if level_match:
                    level = level_match.group(1)

                # Extract the class name (handle the format like FastLeaderElection@618)
                class_line_match = re.search(r'([A-Za-z0-9]+)@(\d+)\]', log)
                if class_line_match:
                    class_name = class_line_match.group(1)
                    line_number = class_line_match.group(2)

                # Extract the content (- the part after)
                content_match = re.search(r'-\s*(.*)$', log)
                if content_match:
                    content = content_match.group(1).strip()
                else:
                    content = log

        parsed_logs.append({
            'class': class_name,
            'type': level,
            'line': line_number,
            'content': content
        })

    return parsed_logs


def parse_log_methods(content, call_graph, system):
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
    for call_graph_data in call_graph:
        clz = call_graph_data["class_name"].replace("$", ".")
        if clazz_name == clz.split('.')[-1]:
            clz_methods = call_graph_data['methods']
            # Traverse all the methods of the classes involving logs to find the corresponding methods for the
            # matching logs
            for method in clz_methods:
                for method_name, method_data in method.items():
                    logs = method_data['logs']
                    if len(logs) != 0:
                        matched = match_log_event(content['type'], content['content'].strip(), logs)
                        # If the target log is matched, the method and the involved calling method will be stored in
                        # methods_log
                        if matched:
                            methods_log['method'] = method_name
                            for call in method_data['calls']:
                                if system not in call['callee']:
                                    continue
                                methods_log['callee'].append(call['callee'])
    return methods_log


def match_log_event(level, log, log_events):
    """
    Match the corresponding log content through the log event template
    :param level: loglevel
    :param log: log info
    :param log_events: log template
    :return: Whether the match is successful or not
    """
    try:
        for event in log_events:
            if len(event['template']) == 0 or event['template'] == "{}":
                continue

            event_level = event['level']
            if level.lower() != event_level.lower():
                continue
            log_event = event['template'].replace('{}', '(.*)')
            match = re.match(log_event, log)
            if match:
                return True
    except Exception as e:
        logging.info(f"Match the corresponding log content through the log event template error: {e}")
        return False

    return False


def build_caller_map(call_graph: Dict, version) -> Dict[str, List[str]]:
    """
    Build the caller mapping table: The key is the full name of the method, and the value is a list of all the full names of the methods that call this method
    """
    caller_map_file = os.path.join('tree', f'{version}_caller_map.json')
    if os.path.exists(caller_map_file):
        with open(caller_map_file, 'r', encoding="utf-8") as f:
            caller_map = json.load(f)
        return caller_map
    caller_map = {}
    for call_graph_data in call_graph:
        class_name = call_graph_data["class_name"]
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
    if not os.path.exists("tree"):
        os.mkdir("tree")
    with open(caller_map_file, "w", encoding="utf-8") as f:
        json.dump(caller_map, f, ensure_ascii=False, indent=4)
    return caller_map


def get_upstream_callers(
        target_method: str,
        caller_map: Dict[str, List[str]],
        depth: int,
        max_depth: int = 100
) -> List[List[str]]:
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
    # if depth < 0 or depth > max_depth:
    #     return []
    #
    # # Initial call chain: Directly includes the target method itself (depth 0)
    # call_chains = [[target_method]]
    # current_depth = 0
    #
    # while current_depth < depth:
    #     new_chains = []
    #     for chain in call_chains:
    #         # Take the starting point of the current chain (the top-level caller)
    #         current_head = chain[0]
    #         # Find all methods that call the current starting point
    #         for caller in caller_map.get(current_head, []):
    #             # Avoid circular calls (such as A->B->A)
    #             if caller not in chain:
    #                 new_chain = [caller] + chain
    #                 new_chains.append(new_chain)
    #     # If there is no new call chain, terminate prematurely (to avoid invalid loops)
    #     if not new_chains:
    #         break
    #     call_chains = new_chains
    #     current_depth += 1
    #
    #     if current_depth > max_depth:
    #         call_chains = []
    #         break
    #
    # # Filter out the call chains that just reach the target depth (remove shorter chains)
    # return call_chains


def serialize_chain(chain: Dict) -> str:
    """The serialized call chain is used for deduplication"""
    return json.dumps(chain, sort_keys=True, ensure_ascii=False)


def reconstruct_execution_paths(log_methods, version, call_graph, end_methods, depth: int = 0, max_depth: int = 100):
    """
    Reconstruct the execution path of the log based on the methods involved in the log
    :param end_method: End dfs methods
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

    # Unify the end_methods format (remove possible parentheses to match the method name)
    end_methods_normalized = {m.replace("()", "") for m in end_methods}
    processed_log_methods = set()  # The method for tracking processed logs
    seen_chains = set()

    # Build a caller mapping table (reverse lookup of call relationships)
    caller_map = build_caller_map(call_graph, version)

    # Depth-first search function
    def dfs(method_full_name, visited):
        # Termination occurs when the maximum depth downstream is exceeded
        normalized_method = method_full_name.replace("()", "")
        if normalized_method in end_methods_normalized:
            return {method_full_name: []}

        if method_full_name in visited:
            return None

        if version.split("-")[0] not in method_full_name:
            return None

        visited = visited.union({method_full_name})

        if '#' not in method_full_name:
            return {method_full_name: []}  # 处理没有类名的方法

        class_name, method_simple_name = method_full_name.split('#', 1)

        path = {method_full_name: []}

        # Look for classes and methods in the call diagram
        if class_name in call_graph:
            class_info = call_graph[class_name]
            for method_entry in class_info.get('methods', []):
                for method_entry_name, method_data in method_entry.items():
                    if method_entry_name == method_full_name:
                        callees = method_data['calls']
                        for callee in callees:
                            callee_full_name = callee['callee']
                            sub_path = dfs(callee_full_name, visited)
                            if sub_path:
                                path[method_full_name].append(sub_path)
                        break
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
        for chain in upstream_chains:
            if len(chain) == 1:
                # Depth 0: Directly use the downstream path
                current_chain = downstream_path
            else:
                # Build a nested structure of the upstream chain (such as M3 -> M2 -> M1)
                current_node = downstream_path
                for caller in reversed(chain[:-1]):  # Exclude the last element (target method)
                    current_node = {caller: [current_node]}
                current_chain = current_node

            # Serialization deduplication
            chain_str = serialize_chain(current_chain)
            if chain_str not in seen_chains:
                seen_chains.add(chain_str)
                execution_paths.append(current_chain)
        if len(processed_log_methods) == len(valid_methods):
            break

    return execution_paths


def generation(issue_report, source_code_tree, depth: int = 0, api_key: str = ''):
    try:
        if not os.path.exists("classes"):
            os.mkdir("classes")

        title = issue_report['title']
        logging.info(f"process file {title}......")
        logs = issue_report['logs']

        version = issue_report['version']
        system = version.split("-")[0]

        st_methods, end_methods = extract_classes_and_content_from_stack_traces(issue_report['stack_traces'], system)
        execution_paths = []
        if len(logs) != 0:
            logging.info("Parsing the log file...")
            # Extract the class name
            classes_file = os.path.join("classes", f"{title}-classes.json")
            if os.path.exists(classes_file):
                classes = json.load(open(classes_file, "r", encoding="utf-8"))
            else:
                classes = extract_classes_and_content_from_log(logs, system)
                if not classes:
                    logging.info(
                        f"{title} failed to extract the class name and log information. Use GPT to extract the log information and class name")
                    classes = extract_classes_and_content_from_log_with_gpt(logs, api_key=api_key)

                logging.info(f"Extract {len(classes)} class names from the issue '{title}'")
                logging.info(f"classes info: {classes}")

                with open(classes_file, "w", encoding="utf-8") as f:
                    json.dump(classes, f, ensure_ascii=False, indent=4)

            logging.info("Parsing the call tree...")

            with open(source_code_tree, 'r', encoding='utf-8') as file:
                call_graph = json.load(file)

            methods = []
            for clazz in classes:
                method_log = parse_log_methods(clazz, call_graph, system)
                methods.append(method_log)
            logging.info("The execution path is being constructed...")
            execution_paths = reconstruct_execution_paths(methods, version, call_graph, end_methods, depth=depth)

        if st_methods:
            for st_method in st_methods:
                execution_paths.append(st_method)

        logging.info(f"The {len(execution_paths)} execution paths were constructed")
        print(f"The {len(execution_paths)} execution paths were constructed")

        output_call_graph = os.path.join("ProcessData", 'call_graph', f'{title}-path.json')
        if not os.path.exists(os.path.join("ProcessData", "call_graph")):
            os.makedirs(os.path.join("ProcessData", "call_graph"))
        with open(output_call_graph, 'w', encoding='utf-8') as f:
            json.dump(execution_paths, f, indent=2, ensure_ascii=False)

    except FileNotFoundError:
        print(f"Error: '{issue_report['title']}' not found or {source_code_tree} not found")
        sys.exit(1)

    except Exception as e:
        print(f"An unknown error occurred: {e}")
        sys.exit(1)


def main(structuration_info, source_call_graph, depth: int = 0, api_key: str = ''):
    try:
        with open(structuration_info, 'r', encoding='utf-8') as file:
            datas = json.load(file)

        if not os.path.exists("classes"):
            os.mkdir("classes")

        for data in datas:
            title = data['title']
            # logging.info(f"process file {title}......")
            # logs = data['logs']
            # if len(logs) == 0:
            #     logging.info(f"{title} no log was found")
            #     continue
            # version = data['version']
            # if title.startswith("HDFS") or title.startswith("MapReduce"):
            #     version = version.replace("MAPREDUCE", "hadoop")
            #     version = version.replace("HDFS", "hadoop")
            # logging.info("Parsing the log file...")
            # # Extract the class name
            # system = version.split("-")[0]
            # classes_file = os.path.join("classes", f"{title}-classes.json")
            # if os.path.exists(classes_file):
            #     classes = json.load(open(classes_file, "r", encoding="utf-8"))
            # else:
            #     classes = extract_classes_and_content_from_log(logs, system)
            #     if not classes:
            #         logging.info(
            #             f"{title} failed to extract the class name and log information. Use GPT to extract the log information and class name")
            #         classes = extract_classes_and_content_from_log_with_gpt(logs, api_key=api_key)
            #
            #     logging.info(f"Extract {len(classes)} class names from the file '{structuration_info}'")
            #     logging.info(f"classes info: {classes}")
            #
            #     with open(classes_file, "w", encoding="utf-8") as f:
            #         json.dump(classes, f, ensure_ascii=False, indent=4)
            #
            # logging.info("Parsing the call tree...")
            #
            # with open(source_call_graph, 'r', encoding='utf-8') as file:
            #     call_graph = json.load(file)
            #
            # methods = []
            # for clazz in classes:
            #     method_log = parse_log_methods(clazz, call_graph)
            #     methods.append(method_log)
            #
            # logging.info("The execution path is being constructed...")

            st_methods, end_methods = extract_classes_and_content_from_stack_traces(data['stack_traces'])
            # execution_paths = reconstruct_execution_paths(methods, version, call_graph, end_methods, depth=depth)
            execution_paths = []
            if st_methods:
                for st_method in st_methods:
                    execution_paths.append(st_method)

            logging.info(f"The {len(execution_paths)} execution paths were constructed")
            print(f"The {len(execution_paths)} execution paths were constructed")

            output_call_graph = os.path.join('call_graph', f'{title}-path.json')
            with open(output_call_graph, 'w', encoding='utf-8') as f:
                json.dump(execution_paths, f, indent=2, ensure_ascii=False)

    except FileNotFoundError:
        print(f"Error: '{structuration_info}' not found ")
        sys.exit(1)
    except Exception as e:
        print(f"An unknown error occurred: {e}")
        sys.exit(1)


if __name__ == '__main__':
    with open ("parsed_enhanced_logs.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        # if item["title"] != "Cassandra-1432":
        #     continue
        generation(item, f"ProcessData/tree/{item['version']}.json")
