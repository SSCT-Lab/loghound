import json
import os
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from docx import Document

# Download necessary NLTK data files
nltk.download('stopwords')
nltk.download('punkt')


def preprocess_code(code_str, language):
    """
    Analyzes source code files and error reports by tokenizing the code,
    removing programming language-specific keywords, splitting concatenated words,
    removing stop words, and performing Porter stemming.

    Parameters:
    code_str (str): The source code or error report as a string.

    Returns:
    list: A list of processed tokens.
    """
    # Step 1: Tokenize the code into a sequence of lexical tokens
    tokens = re.findall(r'\b\w+\b', code_str)

    # Step 2: Remove programming language-specific keywords

    programming_java_keywords = [
        # Java keywords (add more keywords for other languages if needed)
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
        'package', 'private', 'protected', 'public', 'return', 'short', 'static',
        'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
        'transient', 'try', 'void', 'volatile', 'while'
    ]

    go_keywords = [
        'break', 'default', 'func', 'interface', 'select', 'case', 'defer', 'go',
        'map', 'struct', 'chan', 'else', 'goto', 'package', 'switch', 'const',
        'fallthrough', 'if', 'range', 'type', 'continue', 'for', 'import',
        'return', 'var'
    ]

    javascript_keywords = [
        'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default',
        'delete', 'do', 'else', 'export', 'extends', 'finally', 'for', 'function',
        'if', 'import', 'in', 'instanceof', 'let', 'new', 'return', 'super',
        'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void', 'while', 'with',
        'yield'
    ]
    if language == 'java':
        tokens = [token for token in tokens if token.lower() not in programming_java_keywords]
    elif language == "go":
        tokens = [token for token in tokens if token.lower() not in go_keywords]
    elif language == 'js':
        tokens = [token for token in tokens if token.lower() not in javascript_keywords]

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

    return stemmed_tokens


def process_text(bug_report, language="java"):
    if bug_report.split('.')[-1] == "json":
        # json版本
        with open(bug_report, 'r', encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get('summary', '')
        description = data.get('description', '')

        # 确保 summary 和 description 为字符串
        summary = summary if isinstance(summary, str) else ''
        description = description if isinstance(description, str) else ''
        text_to_process = summary + ' ' + description

    elif bug_report.split('.')[-1] == "doc" or bug_report.split('.')[-1] == "docx":
        # word版本
        doc = Document(bug_report)
        full_text = []
        for paragraph in doc.paragraphs:
            full_text.append(paragraph.text)
        text_to_process = "\n".join(full_text)
    else:
        # txt版本
        with open(bug_report, 'r', encoding="utf-8") as f:
            text_to_process = f.read()

    processed_tokens = preprocess_code(text_to_process, language)

    return processed_tokens


if __name__ == "__main__":
    '''
        处理bug_reports并保存为bug_reports_tokens
    '''
    directory = './bug_reports'
    items = os.listdir(directory)
    files = [item.strip(".docx") for item in items if os.path.isfile(os.path.join(directory, item))]
    if not os.path.exists('ProcessData\\bug_reports_tokens'):
        os.mkdir('ProcessData\\bug_reports_tokens')

    for name in files:
        processed_tokens = process_text(os.path.join(directory, name + ".docx"), 'java')
        if processed_tokens is not None and len(processed_tokens) > 0:
            with open('ProcessData\\bug_reports_tokens\\' + name + '_token.txt', 'w') as f:
                f.write('\n'.join(processed_tokens))


