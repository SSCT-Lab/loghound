import json
import os
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from docx import Document
import logging

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
    logging.info("Tokenizing code...")
    tokens = re.findall(r'\b\w+\b', code_str)

    # Step 2: Remove programming language-specific keywords
    logging.info("Removing programming language-specific keywords...")
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
    logging.info("Splitting concatenated words...")
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
    logging.info("Removing stop words...")
    stop_words = set(stopwords.words('english'))
    tokens_no_stopwords = [token for token in split_tokens if token not in stop_words]

    # Step 5: Perform Porter stemming to derive the common base form
    logging.info("Performing Porter stemming...")
    porter = PorterStemmer()
    stemmed_tokens = [porter.stem(token) for token in tokens_no_stopwords]

    return stemmed_tokens


def process_text(bug_report, language="java"):
    if bug_report.split('.')[-1] == "json":
        # json version
        logging.info("Processing json bug report: %s" % bug_report)
        with open(bug_report, 'r', encoding="utf-8") as f:
            data = json.load(f)

        summary = data.get('summary', '')
        description = data.get('description', '')

        # Make sure that summary and description are strings.
        summary = summary if isinstance(summary, str) else ''
        description = description if isinstance(description, str) else ''
        text_to_process = summary + ' ' + description

    elif bug_report.split('.')[-1] == "doc" or bug_report.split('.')[-1] == "docx":
        # word version
        logging.info("Processing doc bug report: %s" % bug_report)
        doc = Document(bug_report)
        full_text = []
        for paragraph in doc.paragraphs:
            full_text.append(paragraph.text)
        text_to_process = "\n".join(full_text)
    else:
        # txt version
        logging.info("Processing txt bug report: %s" % bug_report)
        with open(bug_report, 'r', encoding="utf-8") as f:
            text_to_process = f.read()
    logging.info("Processing text: %s" % text_to_process)
    logging.info("Processing Code to Token....")
    processed_tokens = preprocess_code(text_to_process, language)
    logging.info("Processing Done!")
    return processed_tokens


def process_bug_report(bug_reports, language="java", data_type="txt"):
    """
        Process the bug_reports and save it as bug_reports_tokens.
    """
    items = os.listdir(bug_reports)
    files = [item.strip("." + data_type) for item in items if os.path.isfile(os.path.join(bug_reports, item))]
    output_dir = os.path.join('ProcessData', 'bug_reports_tokens')
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    for name in files:
        logging.info("Processing bug report: %s" % name)
        processed_tokens = process_text(os.path.join(bug_reports, name + "." + data_type), language)
        if processed_tokens is not None and len(processed_tokens) > 0:
            with open(output_dir + os.sep + name + '_token.txt', 'w') as f:
                f.write('\n'.join(processed_tokens))
            logging.info(f"Proecss {name} bug report done and save it to {'ProcessData/bug_reports_tokens/' + name + '_token.txt'}")
