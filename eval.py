import argparse
from process import evaluation
import logging

logging.basicConfig(
    filename='evaluate.log',
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)


def main():
    parser = argparse.ArgumentParser(description='accept')

    parser.add_argument('-a', '--answer',
                        required=True,
                        type=str,
                        help="This is the ultimate answer path, namely ground truth")

    parser.add_argument('-n',
                        type=int,
                        help="The topN you need to evaluate")

    args = parser.parse_args()

    answer = args.answer
    n = args.n
    evaluation.eval(answer, n)


if __name__ == '__main__':
    main()