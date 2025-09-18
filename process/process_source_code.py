import logging
import os
import re
from process import process_tools

logger = logging.getLogger(__name__)


def extract_classes_and_methods(code_str):
    """
    Extract classes, inner classes and their methods from Java code.

    code_str (str): Java source code string.

    list: A list containing each class and its inner classes along with their methods, with each element being a tuple of (class name, method name, method code).
    """
    code_str = process_tools.remove_comments(code_str)
    method_pattern = (r'(?:public|private|protected|static|\s)+\s*[\w<>[\]\s]*\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,'
                      r'\s]+)?\s*\{')
    class_pattern = r'(?:class|interface)\s+(\w+)'
    results = []

    def find_classes_and_methods(code, class_prefix=""):
        index = 0
        while index < len(code):
            # Find the beginning of a class or interface
            class_match = re.search(class_pattern, code[index:])
            if not class_match:
                break
            class_name = class_match.group(1)
            full_class_name = f"{class_prefix}${class_name}" if class_prefix else class_name
            start_index = index + class_match.end()
            # Find the opening curly brace of the class
            brace_index = code[start_index:].find('{')
            if brace_index == -1:
                index = start_index
                continue
            start_index += brace_index
            # Use a stack to handle nested curly braces
            end_index = calculate_start_to_end(code, start_index)
            class_body = code[start_index:end_index]
            # Search for methods in the class
            method_index = 0
            while method_index < len(class_body):
                method_match = re.search(method_pattern, class_body[method_index:])
                if not method_match:
                    break
                method_name = method_match.group(1)
                method_start_index = method_index + method_match.end()
                method_end_index = calculate_start_to_end(class_body, method_start_index)
                method_code = class_body[method_index:method_end_index + 1]
                results.append((full_class_name, method_name, method_code))
                method_index = method_end_index + 1
            find_classes_and_methods(class_body, full_class_name)
            index = end_index + 1
    logger.info("Extracting classes and methods from code")
    find_classes_and_methods(code_str)
    return results


def calculate_start_to_end(class_body, end_index):
    stack = []
    while end_index < len(class_body):
        if class_body[end_index] == '{':
            stack.append('{')
        elif class_body[end_index] == '}':
            if not stack:
                break
            stack.pop()
            if not stack:
                break
        end_index += 1
    return end_index


def analyze_project_source_code_methods(source_code_directory, language):
    """
        Traverse all source code files in the specified directory and save the token of each method separately to the corresponding txt file.

        param：
        source_code_directory (str): The path of the source code directory.
        language (str): Programming languages (such as 'java').
    """
    # Create the source_code_tokens directory (if it does not exist)
    output_base_dir = os.path.join("ProcessData", "source_code_tokens")
    os.makedirs(output_base_dir, exist_ok=True)

    # Get the project name
    project_name = os.path.basename(source_code_directory)

    # Create the project directory
    project_dir = os.path.join(output_base_dir, project_name)
    if os.path.exists(project_dir):
        logger.info("The directory already exists. Skipping...")
        return
    os.makedirs(project_dir)

    # Traverse the directory and its subdirectories
    for root, dirs, files in os.walk(source_code_directory):

        for file in files:
            # Do not consider the source code test cases
            if 'test' in root.split(os.path.sep):
                continue

            if file.endswith('.' + language):
                file_path = os.path.join(root, file)

                # relative path
                relative_path = os.path.relpath(file_path, source_code_directory)

                # Processing Code
                with open(file_path, 'r', encoding='utf-8', errors="replace") as f:
                    code_str = f.read()
                    classes_and_methods = extract_classes_and_methods(code_str)

                for class_name, method_name, method_code in classes_and_methods:
                    tokens = process_tools.preprocess_code(method_code, language)

                    for j in range(len(tokens)):
                        output_file = os.path.join(project_dir, f"{class_name}#{method_name}_{j + 1}_tokens.txt")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            # Write the relative path as the first line
                            f.write('.'.join(
                                relative_path.split(os.path.sep)[:-1]) + "." + class_name + '#' + method_name + '\n')
                            # Write the processed tokens
                            f.write('\n'.join(tokens[j]))
                        logger.info(f"Processed and saved: {output_file}")
                        print(f"Processed and saved: {output_file}")
