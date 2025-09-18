import json
import os
import re
from openai import OpenAI
from process import param_lib
import logging
import nltk
import yaml
from nltk.corpus import stopwords


logger = logging.getLogger(__name__)


def preprocess_code(code_str, language, segment_size=800, remove_duplicates=True):
    """
    Preprocess the source code, including tokenization, removal of specific language keywords, splitting and
    concatenating words and removal of stop words.

    参数:
    code_str (str): Source code string or error report string.
    language (str): Programming languages (such as 'java', 'go', 'js').

    return:
    list: The processed list of tokens.
    """
    logger.info(f"Preprocessing code, code language={language}")

    logger.info("Tokenizing code...")
    # Step 1: Tokenize the code into a sequence of lexical tokens
    tokens = re.findall(r'\b\w+\b', code_str)

    # Step 2: Remove programming language-specific keywords
    logging.info("Removing programming language-specific keywords...")
    if language == 'java':
        programming_java_keywords = param_lib.java_keywords
        tokens = [token for token in tokens if token.lower() not in programming_java_keywords]
    elif language == "go":
        go_keywords = param_lib.go_keywords
        tokens = [token for token in tokens if token.lower() not in go_keywords]
    elif language == 'js':
        javascript_keywords = param_lib.javascript_keywords
        tokens = [token for token in tokens if token.lower() not in javascript_keywords]

    # Step 3: Split concatenated words based on camelCase and underscores
    logging.info("Splitting concatenated words...")
    split_tokens = []
    for token in tokens:
        # Split by underscores (snake_case)
        sub_tokens = re.split(r'_', token)
        for sub_token in sub_tokens:
            # Split camelCase words
            camel_case_tokens = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', sub_token)
            split_tokens.extend(camel_case_tokens)

    # Convert all tokens to lowercase
    split_tokens = [token.lower() for token in split_tokens]

    # Step 4: Remove stop words using NLTK's stop words list
    logging.info("Removing stop words...")
    stop_words = set(stopwords.words('english'))
    tokens_no_stopwords = [token for token in split_tokens if token not in stop_words]

    stemmed_tokens = tokens_no_stopwords

    if remove_duplicates:
        # A deduplication method that retains the original order
        unique_tokens = []
        for token in stemmed_tokens:
            if token not in unique_tokens:
                unique_tokens.append(token)
        stemmed_tokens = unique_tokens

    # Split the stemmed_tokens into segments
    segmented_tokens = [stemmed_tokens[i:i + segment_size] for i in range(0, len(stemmed_tokens), segment_size)]

    return segmented_tokens


def remove_comments(code_str):
    """
    Remove comments from Java code
    """
    code_str = re.sub(r'//.*', '', code_str)
    code_str = re.sub(r'/\*.*?\*/', '', code_str, flags=re.DOTALL)
    return code_str


def save_to_json(results, output_path):
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"The result has been saved to {output_path}")
        logger.info(f"The result has been saved to {output_path}")
    except Exception as e:
        print(f"Error saving JSON file: {e}")
        logger.error(f"Error reading JSON file: {e}")


def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Reading JSON file: {file_path}")
        print(f"Reading JSON file: {file_path}")
        return data
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        logger.error(f"Error reading JSON file: {e}")


def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = f.read()
        logger.info(f"Reading TXT file: {file_path}")
        print(f"Reading TXT file: {file_path}")
        return data
    except Exception as e:
        print(f"Error reading TXT file: {e}")
        logger.error(f"Error reading TXT file: {e}")


def extract_classes_and_content_from_log(logs, system):
    """
    By parsing the corresponding dataset, obtain the class names related to the log
    Args:
    logs: log info
    system: target system
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


def extract_zookeeper_log(logs):
    parsed_logs = []

    main_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})' 
        r'(?:\s+\[myid:\d+\])?\s*-\s*'
        r'(?P<level>[A-Z]+)\s+'
        r'\[(?:[^]]*:)?(?P<class>[A-Za-z0-9]+)@(?P<line>\d+)\]\s*' 
        r'-\s*(?P<content>.*)$'
    )

    package_class_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+' 
        r'(?P<level>[A-Z]+)\s+' 
        r'(?:\w+\.)+(?P<class>[A-Z][a-zA-Z0-9]+):\s*'
        r'(?P<content>.*)$'
    )

    for log in logs:
        log = log.strip()
        if not log:
            continue

        class_name = "UNKNOWN"
        line_number = None
        level = "UNKNOWN"

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


def extract_classes_and_content_from_log_with_gpt(logs):
    data = read_yaml_config(os.path.join("conf", "conf.yml"))
    client = OpenAI(
        api_key=data["api_key"],
        base_url=data["base_url"],
    )
    prompt = f"""
    Logs: {logs}
    Based on all the log information provided to you, you need to extract their class names and log contents, such as:
    [
        04-10 05:19:52,789 DEBUG [main-SendThread(localhost:2181)] org.apache.zookeeper.ClientCnxnSocketNIO.cleanup (ClientCnxnSocketNIO.java:200) - Ignoring exception during shutdown output,
        INFO [main] 2010-08-25 19:29:50,813 SystemTable.java (line 240) Saved Token found: 85070591730234615865843651857942052864,
        2011-03-22 13:22:46,600 INFO org.apache.hadoop.ipc.Client: Retrying connect to server: C4C1/157.5.100.1:9000. Already tried 1 time(s).
        2012-05-12 23:57:33,815 INFO datanode.DataNode (DataNode.java:run(1406)) - DataTransfer: Transmitted BP-1770179175-192.168.44.128-1336847247907:blk_3471690017167574595_1003 (numBytes=100) to /127.0.0.1:54041,
        2012-01-11 13:50:21,432 INFO org.apache.hadoop.yarn.server.nodemanager.containermanager.container.Container: Processing container_1326289061888_0002_01_000001 of type UPDATE_DIAGNOSTICS_MSG,
        2012-01-27 09:52:38,190 - INFO [NIOServerCxn.Factory:0.0.0.0/0.0.0.0:12913:NIOServerCnxn@770] - Client attempting to renew session 0x134485fd7bcb26f at /172.17.136.82:49367,
        zookeeper.log.2012-01-27-leader-225.gz:2012-01-27 09:52:34,010 - INFO [SessionTracker:ZooKeeperServer@314] - Expiring session 0x134485fd7bcb26f, timeout of 6000ms exceeded,
        INFO  - [QuorumPeer:/0:0:0:0:0:0:0:0:10218:FileSnap@82] - Reading snapshot /XXXXXXX/zookeeper/version-2/snapshot.1000469b4
    ]
    output: [{{
        "class": ClientCnxnSocketNIO,
        "type": DEBUG,
        "content": Ignoring exception during shutdown output
    }},
    {{
        "class": SystemTable,
        "type": INFO,
        "content": Saved Token found: 85070591730234615865843651857942052864
    }},
    {{
        "class": Client,
        "type": INFO,
        "content": Retrying connect to server: C4C1/157.5.100.1:9000. Already tried 1 time(s)
    }},
    {{
        "class": DataNode,
        "type": INFO,
        "content": DataTransfer: Transmitted BP-1770179175-192.168.44.128-1336847247907:blk_3471690017167574595_1003 (numBytes=100) to /127.0.0.1:54041
    }},
    {{
        "class": Container,
        "type": INFO,
        "content": Processing container_1326289061888_0002_01_000001 of type UPDATE_DIAGNOSTICS_MSG
    }},
    {{
        "class": NIOServerCnxn,
        "type": INFO,
        "content": Client attempting to renew session 0x134485fd7bcb26f at /172.17.136.82:49367
    }},
    {{
        "class": ZooKeeperServer,
        "type": INFO,
        "content": Expiring session 0x134485fd7bcb26f, timeout of 6000ms exceeded
    }},
    {{
        "class": FileSnap,
        "type": INFO,
        "content": Reading snapshot /XXXXXXX/zookeeper/version-2/snapshot.1000469b4
    }}]
    The output format is:
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
        model=data["model"],
        messages=messages,
        temperature=0,
        extra_body={"enable_thinking": False},
    )
    results = response.choices[0].message.content
    logger.info("GPT Results: " + results)
    extract_results = json.loads(results)
    print(extract_results)
    logger.info("Extract Results: " + str(extract_results))
    return extract_results


def extract_rank_from_stack_traces(stack_traces, system):
    new_stack_traces = []
    for stack_trace in stack_traces:
        if "Caused by" in stack_trace:
            new_st = ""
            sts = re.findall(r'Caused by:.*?(?=Caused by:|$)', stack_trace, re.DOTALL)
            first_caused_index = stack_trace.find('Caused by:')
            if first_caused_index != -1:
                pre_caused = stack_trace[:first_caused_index].strip()
            else:
                pre_caused = stack_trace.strip()
            for st in sts:
                new_st += st + "\n"
            new_stack_traces.append(new_st + pre_caused)
        else:
            new_stack_traces.append(stack_trace)

    return extract_content_from_stack_traces(new_stack_traces, system)


def extract_content_from_stack_traces(stack_traces, system):
    pattern = re.compile(
        r'at\s+'
        r'(?P<class>[\w.$]+)\.'
        r'(?P<method>[\w<>]+)'
        r'(?P<file>\s*\(.*?\))'
    )

    methods_chain = []
    methods = []
    for stack_trace in stack_traces:
        st = []
        st_list = [line.strip() for line in stack_trace.split("\n")]
        for line in st_list:
            method_match = pattern.search(line)
            if method_match:
                file = method_match.group('file')
                class_name = method_match.group('class')
                if re.search("\$[0-9]+", class_name) or ".java" not in file or (system not in class_name or "apache" not in class_name) and "thrift" not in class_name:
                    continue
                method_name = method_match.group('method')
                st.append(f"{class_name}#{method_name}")
        methods.append(st)
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


def read_yaml_config(file_path):
    """
    Read the contents of the YAML configuration file.

    Args:
        file_path (str): The path of the YAML configuration file

    Returns:
        dict: The parsed YAML data (usually in dictionary form).
              If the read or parse fails, return None.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
            logger.info(f"The configuration file was successfully read: {file_path}")
            return config_data
    except FileNotFoundError:
        logger.error(f"Error: The configuration file was not found - {file_path}")
    except yaml.YAMLError as e:
        logger.error(f"Error: Failed to parse the YAML file - {file_path}. error message: {e}")
    except Exception as e:
        logger.error(f"An unknown error occurred when reading the configuration file: {file_path}. error message: {e}")

    return None


def extract_methods(call_graph, methods=None):
    """
    Extract all method names

    Args:
        call_graph: Execute the path data structure
        methods: A collection for storing method names

    Returns:
        list: List all the methods
    """
    if methods is None:
        methods = set()

    if isinstance(call_graph, list):
        for item in call_graph:
            extract_methods(item, methods)
    elif isinstance(call_graph, dict):
        for method, sub_paths in call_graph.items():
            methods.add(method)
            extract_methods(sub_paths, methods)

    return list(methods)


def extract_name(file_name):
    return file_name.split("_")[0]


def read_file_lines(file_path):
    result = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for line in lines:
                l = line.strip('\n')
                l = l.split(":")
                l[1] = float(l[1])
                result.append(l)
        return result
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        print(f"Error reading file {file_path}: {e}")
        return []


def process_scores(result):
    process_result = {}
    for item in result:
        score = float(item[1])
        process_result[item[0]] = score
    return process_result