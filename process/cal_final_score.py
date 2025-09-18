import json
import logging
import os
from process import evaluation
from process.process_tools import extract_name, process_scores, read_file_lines

logger = logging.getLogger(__name__)


def add_scores(vsm_path, log_path, path_path, output_path, alpha: float = 0.12, beta: float = 1.0,
               gamma: float = 1.0):
    vsm_files = {extract_name(file): file for file in os.listdir(vsm_path)}
    log_files = {extract_name(file): file for file in os.listdir(log_path)}
    path_files = {extract_name(file): file for file in os.listdir(path_path)}
    final_scores = []

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    for file_id, vsm_file_name in vsm_files.items():
        # Get the corresponding file path
        vsm_file = os.path.join(vsm_path, vsm_file_name)
        log_file = os.path.join(log_path, log_files[file_id]) if file_id in log_files else None
        path_file = os.path.join(path_path, path_files[file_id]) if file_id in path_files else None
        output_file = os.path.join(output_path, f"{file_id}_total_score.txt")

        # Get the score of each file
        vsm_scores = evaluation.normalize_scores(process_scores(read_file_lines(vsm_file)))
        log_scores = evaluation.normalize_scores(process_scores(read_file_lines(log_file)))
        path_scores = evaluation.normalize_scores(process_scores(read_file_lines(path_file)))

        # Accumulate the score line by line
        total_scores = {}

        # Match and accumulate st_log_scores
        for log_method_path, log_score in log_scores.items():
            log_method_path = log_method_path.replace("$", ".")
            if log_method_path not in total_scores:
                total_scores[log_method_path] = 0.0
            total_scores[log_method_path] += beta * float(log_score)

        # Match and accumulate path_scores
        for path_method, path_score in path_scores.items():
            path_method = path_method.replace("$", ".")
            if path_method not in total_scores:
                total_scores[path_method] = 0.0
            total_scores[path_method] += gamma * path_score

        for class_path, vsm_score in vsm_scores.items():
            if vsm_score == 0.0:
                continue
            method_name = class_path.replace("$", ".").split("src.java.main.")[-1].split("src.main.java.")[-1].split("src.java.")[-1]
            # The score of the initialization method path
            if method_name not in total_scores:
                total_scores[method_name] = 0.0
            total_scores[method_name] += alpha * float(vsm_score)  # 累加 VSM 分数

        # Convert to the final format [Classpath, total score]
        final_score = sorted(
            [[key, value] for key, value in total_scores.items()],
            key=lambda x: x[1],  # Sort by the second item (value)
            reverse=True  # Setting it to True indicates descending sorting, while False indicates ascending sorting
        )

        # Write the result
        write_file_lines(output_file, final_score)
        logger.info(f"Processed and saved: {output_file}")
        print(f"Processed and saved: {output_file}")

        location = []
        for item in final_score[0:5]:
            location.append(item[0])
        final_scores.append({
            "title": file_id,
            "location": location
        })

    total_score = os.path.join(output_path, "total_score.json")

    with open(total_score, 'w', encoding='utf-8') as f:
        json.dump(final_scores, f, indent=2)

    logger.info("Total score calculation completed.")
    logger.info("Total score saved to: " + total_score)
    print(f"Processed and saved: {total_score}")
    return total_score


def write_file_lines(file_path, lines):
    """
    Write the result to the file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            for line in lines:
                file.write(f"{line[0]}:{line[1]}\n")
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        print(f"Error writing to file {file_path}: {e}")


if __name__ == "__main__":
    vsm_path = os.path.join("..", "ProcessData", "vsm_result")
    log_path = os.path.join("..", "ProcessData", "st_log_methods_result")
    path_path = os.path.join("..", "ProcessData", "path_methods_results")
    output_path = os.path.join("..", "ProcessData", "methods_total_scores")

    add_scores(vsm_path, log_path, path_path, output_path, 0.11, 1, 1)
