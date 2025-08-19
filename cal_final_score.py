import json
import logging
import os
import evaluation


def extract_name(file_name):
    return file_name.split("_")[0]


def read_file_lines(file_path):
    result = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for line in lines:
                l = line.strip('\n')
                l = l.split(": ")
                l[1] = float(l[1])
                result.append(l)
        return result
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


def process_vsm_scores(vsm_result):
    vsm_process_result = {}
    for item in vsm_result:
        vsm_score = float(item[1])
        vsm_process_result[item[0]] = vsm_score
    return vsm_process_result


def add_scores(alpha: float = 1.0, beta: float = 1.0, gamma: float = 1.0, kafa: float = 1.0, vsm_path=os.path.join("ProcessData", "vsm_result"), log_path=os.path.join("ProcessData", "st_methods_result"), coverage_path=os.path.join("ProcessData", "code_coverage"), path_path=os.path.join("ProcessData", "path_methods_results"), output_path=os.path.join("ProcessData", "methods_total_scores")):
    vsm_files = {extract_name(file): file for file in os.listdir(vsm_path)}
    log_files = {extract_name(file): file for file in os.listdir(log_path)}
    coverage_files = {extract_name(file): file for file in os.listdir(coverage_path)}
    path_files = {extract_name(file): file for file in os.listdir(path_path)}
    final_scores = []

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    for file_id, vsm_file_name in vsm_files.items():
        # Get the corresponding file path
        vsm_file = os.path.join(vsm_path, vsm_file_name)
        log_file = os.path.join(log_path, log_files[file_id]) if file_id in log_files else None
        coverage_file = os.path.join(coverage_path, coverage_files[file_id]) if file_id in coverage_files else None
        path_file = os.path.join(path_path, path_files[file_id]) if file_id in path_files else None
        output_file = os.path.join(output_path, f"{file_id}_total_score-v4.txt")

        # Get the score of each file
        vsm_scores = process_vsm_scores(read_file_lines(vsm_file))
        log_scores = read_file_lines(log_file) if log_file else []
        coverage_scores = read_file_lines(coverage_file) if coverage_file else []
        path_scores = read_file_lines(path_file) if path_file else []

        # Accumulate the score line by line
        total_scores = {}
        for class_path, vsm_score in vsm_scores.items():
            class_method_name = class_path.replace("$", "\\").split("\\")[-1]
            # print(class_name)

            # The score of the initialization method path
            if class_path not in total_scores:
                total_scores[class_path] = 0.0
            total_scores[class_path] += alpha * float(vsm_score)  # 累加 VSM 分数

            # Match and accumulate log_scores
            for log_class_path, log_score in log_scores:
                if log_class_path == class_path or log_class_path.replace("$", "\\").split("\\")[-1] == class_method_name:
                    total_scores[class_path] += beta * float(log_score)

            # Match and accumulate coverage_scores
            for method_name, coverage_score in coverage_scores:
                if method_name.replace("$", ".").split(".")[-1] == class_method_name:
                    score = gamma * float(coverage_score)
                    total_scores[class_path] += score

                    # Match and accumulate path_scores
            for path_class_path, path_score in path_scores:
                path_class = path_class_path.replace("$", "\\").split("\\")[-1]
                if path_class_path == class_path or path_class == class_method_name:
                    total_scores[class_path] += kafa * path_score

        # Convert to the final format [Classpath, total score]
        final_score = sorted(
            [[key, value] for key, value in total_scores.items()],
            key=lambda x: x[1],  # Sort by the second item (value)
            reverse=True  # Setting it to True indicates descending sorting, while False indicates ascending sorting
        )

        # print(final_score)

        # Write the result
        write_file_lines(output_file, final_score)
        print(f"Processed and saved: {output_file}")

        location = []
        for item in final_score[0:5]:
            location.append(item[0])
        final_scores.append({
            "title": file_id,
            "location": location
        })

    total_score = os.path.join(output_path, "total_score-v4.json")

    with open(total_score, 'w', encoding='utf-8') as f:
        json.dump(final_scores, f, indent=2)

    logging.info("Total score calculation completed.")
    logging.info("Total score saved to: " + total_score)
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
        print(f"Error writing to file {file_path}: {e}")


if __name__ == "__main__":
    vsm_path = "ProcessData/vsm_result"
    log_path = "ProcessData/st_methods_result"
    path_path = "ProcessData/path_methods_results"
    coverage_path = "ProcessData/code_coverage"
    output_path = "ProcessData/methods_total_scores"

    add_scores(0, 0.4, 1, 0.04, vsm_path, log_path, coverage_path, path_path, output_path)
