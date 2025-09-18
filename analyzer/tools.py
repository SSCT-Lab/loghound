import json
import re

LOG_METHODS = ['debug', 'info', 'warn', 'error', 'trace', 'fatal']


def get_json_content(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return content


def replace_placeholders(format_string):
    pattern = r'%[\w\.\+#-]+'
    return re.sub(pattern, '{}', format_string)


def contains(contents, target):
    """Check whether the target exists"""
    if target in contents:
        return True
    return False


def is_log_method(node):
    """Determine whether it is a logging method"""
    if node.qualifier and any(node.member == log_method for log_method in LOG_METHODS) and node.arguments:
        return True
    return False


def find_node_line(tokens, node):
    """Find the line number of the AST node in the source code"""
    if not tokens or not node:
        return 0

    # Try to find the token that matches the node position
    line = -1
    for token in tokens:
        if token.position and token.position.line <= node.position.line:
            line = token.position.line
        else:
            break

    return line
