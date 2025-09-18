import os
from docx import Document
import logging
from process import process_tools
logger = logging.getLogger(__name__)


def process_text(bug_report, language="java"):
    if bug_report.split('.')[-1] == "json":
        # json version
        logger.info("Processing json bug report: %s" % bug_report)
        data = process_tools.read_json(bug_report)

        summary = data.get('summary', '')
        description = data.get('description', '')

        # Make sure that summary and description are strings.
        summary = summary if isinstance(summary, str) else ''
        description = description if isinstance(description, str) else ''
        text_to_process = summary + ' ' + description

    elif bug_report.split('.')[-1] in ("doc", "docx"):
        # word version
        logger.info("Processing doc bug report: %s" % bug_report)
        doc = Document(bug_report)
        full_text = []
        for paragraph in doc.paragraphs:
            full_text.append(paragraph.text)
        text_to_process = "\n".join(full_text)
    else:
        # txt version
        logger.info("Processing txt bug report: %s" % bug_report)
        text_to_process = process_tools.read_txt(bug_report)
    logger.info("Processing text: %s" % text_to_process)
    logger.info("Processing Code to Token....")
    processed_tokens = process_tools.preprocess_code(text_to_process, language)
    logger.info("Processing Done!")
    return processed_tokens


def process_bug_report(bug_reports, language="java", data_type="txt"):
    """
        Process the bug_reports and save it as bug_reports_tokens.
    """
    items = os.listdir(bug_reports)
    files = [item.strip("." + data_type) for item in items if os.path.isfile(os.path.join(bug_reports, item))]
    output_dir = os.path.join('ProcessData', 'bug_reports_tokens')
    os.makedirs(output_dir, exist_ok=True)

    for name in files:
        logger.info("Processing bug report: %s" % name)
        if not os.path.exists(os.path.join(bug_reports, name + "." + data_type)):
            continue
        processed_tokens = process_text(os.path.join(bug_reports, name + "." + data_type), language)
        if processed_tokens is not None and len(processed_tokens) > 0:
            with open(os.path.join(output_dir, name + '_token.txt'), 'w', encoding='utf-8') as f:
                for processed_token in processed_tokens:
                    f.write('\n'.join(processed_token))
            logger.info(
                f"Proecss {name} bug report done and save it to {'ProcessData/bug_reports_tokens/' + name + '_token.txt'}")
    return output_dir