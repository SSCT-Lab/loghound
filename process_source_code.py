import json
import os
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

# Download necessary NLTK data files
nltk.download('stopwords')
nltk.download('punkt')


def remove_comments(code_str):
    """
    去除 Java 代码中的注释
    """
    # 去除单行注释
    code_str = re.sub(r'//.*', '', code_str)
    # 去除多行注释
    code_str = re.sub(r'/\*.*?\*/', '', code_str, flags=re.DOTALL)
    return code_str


def preprocess_code(code_str, language, segment_size):
    """
    对源代码进行预处理，进行标记化、去除特定语言关键词、分割拼接单词、去除停用词以及Porter词干提取。

    参数:
    code_str (str): 源代码字符串或错误报告字符串。
    language (str): 编程语言（如 'java'、'go'、'js'）。

    返回:
    list: 处理后的tokens列表。
    """
    # Step 1: Tokenize the code into a sequence of lexical tokens
    tokens = re.findall(r'\b\w+\b', code_str)

    # Step 2: Remove programming language-specific keywords
    programming_java_keywords = [
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
        'package', 'private', 'protected', 'public', 'return', 'short', 'static',
        'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
        'transient', 'try', 'void', 'volatile', 'while'
    ]

    if language == 'java':
        tokens = [token for token in tokens if token.lower() not in programming_java_keywords]

    # Step 3: Split concatenated words based on camelCase and underscores
    split_tokens = []
    for token in tokens:
        # Split by underscores (snake_case)
        subtokens = re.split(r'_', token)
        for subtoken in subtokens:
            # Split camelCase words
            camel_case_tokens = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', subtoken)
            split_tokens.extend(camel_case_tokens)

    # Convert all tokens to lowercase
    split_tokens = [token.lower() for token in split_tokens]

    # Step 4: Remove stop words using NLTK's stop words list
    stop_words = set(stopwords.words('english'))
    tokens_no_stopwords = [token for token in split_tokens if token not in stop_words]

    # Step 5: Perform Porter stemming to derive the common base form
    porter = PorterStemmer()
    stemmed_tokens = [porter.stem(token) for token in tokens_no_stopwords]

    # Split the stemmed_tokens into segments
    segmented_tokens = [stemmed_tokens[i:i + segment_size] for i in range(0, len(stemmed_tokens), segment_size)]

    return segmented_tokens


def extract_classes_and_methods(code_str):
    """
    从 Java 代码中提取类和内部类及其方法。

    参数:
    code_str (str): Java 源代码字符串。

    返回:
    list: 包含每个类和内部类及其方法的列表，每个元素为 (类名, 方法名, 方法代码) 元组。
    """
    code_str = remove_comments(code_str)
    results = []

    def find_classes_and_methods(code, class_prefix=""):
        index = 0
        while index < len(code):
            # 查找类或接口的开始
            class_match = re.search(r'(?:class|interface)\s+(\w+)', code[index:])
            if not class_match:
                break
            class_name = class_match.group(1)
            full_class_name = f"{class_prefix}${class_name}" if class_prefix else class_name
            start_index = index + class_match.end()
            # 查找类的开始大括号
            brace_index = code[start_index:].find('{')
            if brace_index == -1:
                index = start_index
                continue
            start_index += brace_index + 1
            # 使用栈来处理嵌套的大括号
            stack = ["{"]
            end_index = start_index
            while end_index < len(code):
                if code[end_index] == '{':
                    stack.append('{')
                elif code[end_index] == '}':
                    if not stack:
                        break
                    stack.pop()
                    if not stack:
                        break
                end_index += 1
            class_body = code[start_index:end_index]
            # 查找类中的方法
            method_index = 0
            while method_index < len(class_body):
                method_match = re.search(
                    r'(?:public|private|protected|static|\s)+\s*[\w<>[\]\s]*\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
                    class_body[method_index:])
                if not method_match:
                    break
                method_name = method_match.group(1)
                method_start_index = method_index + method_match.end()
                method_stack = []
                method_end_index = method_start_index
                while method_end_index < len(class_body):
                    if class_body[method_end_index] == '{':
                        method_stack.append('{')
                    elif class_body[method_end_index] == '}':
                        if not method_stack:
                            break
                        method_stack.pop()
                        if not method_stack:
                            break
                    method_end_index += 1
                method_code = class_body[method_index:method_end_index + 1]
                results.append((full_class_name, method_name, method_code))
                method_index = method_end_index + 1
            # 递归处理内部类
            find_classes_and_methods(class_body, full_class_name)
            index = end_index + 1

    find_classes_and_methods(code_str)
    return results


def analyze_project_source_code_methods(source_code_directory, language):
    """
        遍历指定目录中的所有源代码文件，将每个方法的token单独保存到对应的txt文件中。

        参数：
        source_code_directory (str): 源代码目录的路径。
        language (str): 编程语言（如 'java'）。
    """
    segment_size = 800
    # 创建 source_code_tokens 目录（如果不存在）
    output_base_dir = 'ProcessData/source_code_methods_tokens'
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(source_code_directory):
        for file in files:
            # 不考虑源代码测试用例
            if 'test' in root.split(os.path.sep):
                continue

            if file.endswith('.' + language):
                file_path = os.path.join(root, file)

                # 相对路径
                relative_path = os.path.relpath(file_path, source_code_directory)

                # 处理代码
                with open(file_path, 'r', encoding='utf-8', errors="replace") as f:
                    code_str = f.read()
                    classes_and_methods = extract_classes_and_methods(code_str)

                # 获取项目名称
                project_name = os.path.basename(source_code_directory)

                # 创建项目目录
                project_dir = os.path.join(output_base_dir, project_name)
                if not os.path.exists(project_dir):
                    os.makedirs(project_dir)

                for class_name, method_name, method_code in classes_and_methods:
                    tokens = preprocess_code(method_code, language, segment_size)

                    for j in range(len(tokens)):
                        output_file = os.path.join(project_dir, f"{class_name}#{method_name}_{j + 1}_tokens.txt")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            # 写入相对路径作为第一行
                            f.write('\\'.join(relative_path.split('\\')[:-1]) + "\\" + class_name + '#' + method_name + '\n')
                            # 写入处理后的 tokens
                            f.write('\n'.join(tokens[j]))

                        print(f"已处理并保存：{output_file}")


def analyze_project_source_code(source_code_directory, language):
    """
    遍历指定目录中的所有源代码文件，将每个文件的token单独保存到对应的txt文件中。

    参数：
    source_code_directory (str): 源代码目录的路径。
    language (str): 编程语言（如 'java'）。
    """
    segment_size = 800
    # 创建 source_code_tokens 目录（如果不存在）
    output_base_dir = 'ProcessData/source_code_tokens'
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(source_code_directory):
        for file in files:
            # 不考虑源代码测试用例
            if 'test' in root.split(os.path.sep):
                continue

            if file.endswith('.' + language):
                file_path = os.path.join(root, file)

                # 相对路径
                relative_path = os.path.relpath(file_path, source_code_directory)

                # 处理代码
                with open(file_path, 'r', encoding='utf-8', errors="replace") as f:
                    code_str = f.read()
                    tokens = preprocess_code(code_str, language, segment_size)

                # 获取项目名称和类名
                project_name = os.path.basename(source_code_directory)
                class_name = os.path.splitext(file)[0]

                # 创建项目目录
                project_dir = os.path.join(output_base_dir, project_name)
                if not os.path.exists(project_dir):
                    os.makedirs(project_dir)

                # 创建类名_tokens.txt 文件
                for i in range(len(tokens)):
                    output_file = os.path.join(project_dir, f"{class_name}_{i + 1}_tokens.txt")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        # 写入相对路径作为第一行
                        f.write(relative_path + '\n')
                        # 写入处理后的tokens
                        f.write('\n'.join(tokens[i]))

                print(f"已处理并保存：{output_file}")


if __name__ == "__main__":
    # 指定源代码的目录路径
    src = "project_sc"
    for project in os.listdir(src):
        # if project != 'hadoop-0.22.0':
        #     continue
        source_code_directory = os.path.join(src, project)
        language = 'java'
        # 分析并处理源代码
        # analyze_project_source_code(source_code_directory, language)

        # 分析并处理源代码（方法级别）
        analyze_project_source_code_methods(source_code_directory, language)
