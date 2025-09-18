import logging
import os
import pandas as pd

logger = logging.getLogger(__name__)


def normalize_scores(vsm_scores):
    """
    Normalize the VSMScore to between 0 and 1.
    Args:
        vsm_scores (dict): Mapping file path -> VSMScore.
    Returns:
        dict: The normalized VSMScore's mapping.
    """
    min_score = min(vsm_scores.values())
    max_score = max(vsm_scores.values())

    if max_score == min_score:
        return {file: 1.0 for file in vsm_scores}

    # Normalization formula: N(x) = (x - min) / (max - min)
    return {file: (score - min_score) / (max_score - min_score) for file, score in vsm_scores.items() if score != 0}


def calculate_top_n(rank_list, target_methods, n):
    rank_list = [item[0].split(".")[-1] for item in rank_list]
    top_n_files = rank_list[:n]
    target_methods_set = set([method.split("/")[-1] for method in target_methods])

    # Accuracy@N
    if len(set(top_n_files) & target_methods_set) > 0:
        return 1
    else:
        return 0


def average_precision(rank_list, target_methods):
    correct_files = 0
    precision_sum = 0.0
    rank_list = [item[0].split(".")[-1] for item in rank_list]
    buggy_files = set([method.split("/")[-1] for method in target_methods])
    for idx, generate_method in enumerate(rank_list):
        if generate_method in buggy_files:
            correct_files += 1
            precision_sum += correct_files / (idx + 1)
            break
    return precision_sum


def calculate_reciprocal_rank(rank_list, target_methods):
    rank_list = [item[0].split(".")[-1] for item in rank_list]
    target_methods = set([method.split("/")[-1] for method in target_methods])
    for idx, generate_method in enumerate(rank_list):
        if generate_method in target_methods:
            return 1 / (idx + 1)
    return 0.0


def compute_project_metrics(total_score_path, part, reference_data, project_names, n):
    project_metrics = {project: {"Accuracy@N": 0.0, "MRR": 0.0, "Count": 0}
                       for project in project_names}
    for report_name, target_methods in reference_data.items():
        prefix = report_name.split("-")[0]
        rank_list = []
        with open(os.path.join(total_score_path, f"{report_name}_{part}.txt"), 'r', encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                rank_list.append(line.split(":"))

            TopN = calculate_top_n(rank_list, target_methods, n)

            rr = calculate_reciprocal_rank(rank_list, target_methods)

            project_metrics[prefix]["Accuracy@N"] += TopN
            project_metrics[prefix]["MRR"] += rr
            project_metrics[prefix]["Count"] += 1

    total = 0
    precision_all = 0
    for project in project_names:
        count = project_metrics[project]["Count"]
        total += count
        if count > 0:
            precision_all += project_metrics[project]["Accuracy@N"]
            project_metrics["Overall"]["MRR"] += project_metrics[project]["MRR"]
            project_metrics[project]["Accuracy@N"] /= count
            project_metrics[project]["MRR"] /= count
    project_metrics["Overall"]["Accuracy@N"] = precision_all / total
    project_metrics["Overall"]["Count"] = total
    project_metrics["Overall"]["MRR"] /= total
    return project_metrics


def process_excel_file(file_path):
    try:
        df = pd.read_excel(file_path)

        if 'title' not in df.columns or 'Methods' not in df.columns:
            raise ValueError("The 'title' or 'Methods' column was not found in the Excel file.")

        result = []

        for index, row in df.iterrows():
            title = row['title']

            methods_str = str(row['Methods'])
            methods_list = [item.strip() for item in methods_str.split(',') if item.strip()]

            result.append({
                "title": title,
                "methods": methods_list
            })

        return result

    except FileNotFoundError:
        print(f"Error: File '{file_path}' was not found")
        return []
    except Exception as e:
        print(f"Error occurred:{e}")
        return []


def print_metrics(metrics):
    logger.info(f"{'System':<12} {'Count':<8} {'Accuracy@N':<12} {'MRR':<12}")
    logger.info("-" * 50)
    print(f"{'System':<12} {'Count':<8} {'Accuracy@N':<12} {'MRR':<12}")
    print("-" * 50)

    systems_order = ["Cassandra", "HBase", "HDFS", "MapReduce", "ZooKeeper", "Overall"]

    for system in systems_order:
        if system in metrics:
            stats = metrics[system]
            logger.info(f"{system:<12} {stats['Count']:<10} {stats['Accuracy@N']:<10.4f} {stats['MRR']:<8.4f}")
            print(
                f"{system:<12} {stats['Count']:<10} {stats['Accuracy@N']:<10.4f} {stats['MRR']:<8.4f}")


def eval(ref_file_path, n=5):
    reference_data = process_excel_file(ref_file_path)
    reference_dict = {item['title']: item.get('methods', []) for item in reference_data}
    project_names = ["Cassandra", "HBase", "HDFS", "MapReduce", "ZooKeeper", "Overall"]
    ret = compute_project_metrics(os.path.join("ProcessData", "methods_total_scores"), 'total_score',
                                  reference_dict,
                                  project_names, n=n)
    print_metrics(ret)
