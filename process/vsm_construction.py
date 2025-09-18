import logging
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from multiprocessing import Pool
from process import process_tools, param_lib, evaluation
from process.process_tools import process_scores, read_file_lines

logger = logging.getLogger(__name__)


def get_bug_tokens(base_path):
    # Store a list of tokens for each error report
    bug_reports_tokens = []
    bug_report_names = []

    # Obtain all files under the bug_reports folder and exclude hidden files
    files = [f for f in os.listdir(base_path) if not f.startswith('.')]

    # Filter out.txt files (each txt file corresponds to an error report)
    tokens_files = [f for f in files if f.endswith('.txt')]

    # Sort by file name and ensure the order is consistent
    tokens_files.sort()
    for tokens_file in tokens_files:
        tokens_file_path = os.path.join(base_path, tokens_file)
        logging.info(f"Processing: {tokens_file}")
        # Open and read the tokens file
        with open(tokens_file_path, 'r', encoding='utf-8') as f:
            tokens = [line.strip() for line in f if line.strip()]
            if tokens:
                bug_reports_tokens.append(tokens)
                bug_report_names.append(tokens_file.replace('_tokens.txt', ''))

    return bug_reports_tokens, bug_report_names


def get_source_files(base_path, project_name):
    # Obtain all the token files under the project
    project_dir = os.path.join(base_path, project_name)
    source_files = [f for f in os.listdir(project_dir) if f.endswith('_tokens.txt') and not f.startswith('.')]
    source_files.sort()
    return source_files


def get_source_tokens(file_path):
    # Read the tokens in the source code file and return their relative paths and tokens
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        relative_path = lines[0].strip()  # The first line is the relative path of the Java file
        tokens = [line.strip() for line in lines[1:] if line.strip()]  # The remaining lines are tokens.
    return relative_path, tokens


def save_vsm_result(bug_report_name, vsm_results):
    # Create the vsm_result folder (if it doesn't exist)
    output_dir = os.path.join('ProcessData', 'vsm_result')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define the output file path
    output_file = os.path.join(output_dir, f"{bug_report_name}_vsm.txt")

    # Write the VSM results into a txt file and sort them by similarity
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in vsm_results:
            f.write(f"{result[0]}: {result[1]:.4f}\n")
    return output_file


def process_source_file(args):
    bug_report_text, source_file_path, stop_words = args
    relative_path, source_tokens = get_source_tokens(source_file_path)

    # Convert the tokens in the source code to strings
    source_code_text = ' '.join(source_tokens)

    # Build a document collection: one error report and one source code segment
    documents = [bug_report_text, source_code_text]

    # Create an instance of TfidfVectorizer
    vectorizer = TfidfVectorizer(stop_words=stop_words)

    # Calculate the TF-IDF matrix
    tfidf_matrix = vectorizer.fit_transform(documents)

    # A vector for separating error reports from source code segments
    bug_report_vector = tfidf_matrix[0]
    source_code_vector = tfidf_matrix[1]

    # Calculate similarity
    similarity = cosine_similarity(bug_report_vector, source_code_vector.reshape(1, -1)).flatten()[0]

    return relative_path, similarity


def aggregate_vsm_results_methods(vsm_results):
    """
    Aggregate according to the method
    :param vsm_results:
    :return:
    """
    # Define a dictionary for aggregating multiple token files of the same class
    aggregated_results = {}

    for relative_path, similarity in vsm_results:
        full_name = relative_path.replace("\\", ".")
        if full_name not in aggregated_results:
            aggregated_results[full_name] = (relative_path, similarity)
        else:
            if similarity > aggregated_results[full_name][1]:
                aggregated_results[full_name] = (relative_path, similarity)

    return list(aggregated_results.values())


def process_vsm_result(bug_reports_token, structuration_info):
    source_code_token = os.path.join("ProcessData", "source_code_tokens")

    # Obtain the tokens of the error report along with the corresponding project name and the name of the error report
    bug_reports_tokens, bug_report_names = get_bug_tokens(bug_reports_token)
    data = process_tools.read_json(structuration_info)
    projects = {item['title']: item['version'] for item in data}

    # Define a list of stop words
    stop_words = param_lib.stop_words

    for i, (bug_tokens, bug_report_name) in enumerate(zip(bug_reports_tokens, bug_report_names)):
        # Convert the tokens of the error report to strings
        bug_report_text = ' '.join(bug_tokens)
        # if os.path.exists(os.path.join("ProcessData", "vsm_result", f"{bug_report_name.replace('_token.txt', '')}_vsm.txt")):
        #     print(f"The VSM result of {bug_report_name} has been processed. Skipping....")
        #     logger.info(f"The VSM result of {bug_report_name} has been processed. Skipping....")
        #     continue
        print(f"Processing: {bug_report_name}")
        if os.path.exists(os.path.join("ProcessData", "vsm_result", f"{bug_report_name.replace('_token.txt', '')}_vsm.txt")):
            print(f"The VSM result of {bug_report_name} has been processed. Skipping....")
            logger.info(f"The VSM result of {bug_report_name} has been processed. Skipping....")
            continue
        project_name = projects.get(bug_report_name.replace("_token.txt", ""))
        if project_name.startswith("MAPREDUCE") or project_name.startswith("HDFS"):
            project_name = project_name.replace("MAPREDUCE", "hadoop")
            project_name = project_name.replace("HDFS", "hadoop")

        # Obtain all the source code tokens files under the corresponding project
        source_files = get_source_files(source_code_token, project_name)
        if not source_files:
            logger.info(f"The source code tokens file of the project {project_name} was not found")
            print(f"The source code tokens file of the project {project_name} was not found")
            continue

        # Prepare the list of parameters to be passed to the child process
        args_list = [
            (bug_report_text, os.path.join(source_code_token, project_name, source_file),
             stop_words)
            for source_file in source_files
        ]
        # Use a multiprocess pool to process source code files in parallel
        with Pool(processes=4) as pool:  # Adjust the number of processes according to the number of your CPU cores
            vsm_results = pool.map(process_source_file, args_list)

        # Aggregate the results by class_name#method_name, and only retain the files with the highest similarity
        aggregated_results = aggregate_vsm_results_methods(vsm_results)
        # print(aggregated_results)
        # Sort by similarity from high to low
        aggregated_results.sort(key=lambda x: x[1], reverse=True)

        # Save the result to the corresponding error report txt file in the vsm_result folder
        output_file = save_vsm_result(bug_report_name.replace("_token.txt", ""), aggregated_results)

        # output result
        logger.info(
            f"The similarity analysis of the bug report({bug_report_name}) has been completed and saved to {output_file}")
        print(
            f"The similarity analysis of the bug report({bug_report_name}) has been completed and saved to {output_file}")
    return os.path.join("ProcessData", "vsm_result")