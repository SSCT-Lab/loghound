import json
import os
import docx
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


def extract_classes_and_content_from_log_with_gpt(txts, api_key, model, base_url):
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    prompt = f"""
    Information: {txts}
    Based on all the information provided to you, you need to extract their file, title, description, logs and stack traces and the log and stack traces information need to be de-duplicated， Stack information needs to be aggregated according to at, that is to say, at together form a stack, that is, they are placed in the same string。 The output format is:
    {{
        "file": "Cassandra-1011.docx",
        "title": "Cassandra-1011",
        "Description": "Exception auto-bootstrapping two nodes nodes at the same time. 3 machines in the cluster, and after starting the first node (which is the seed), the other two nodes are brought up at the same time. Then the following exception gets raised on the seed node. Looks like the seed node is assigning the same token to the subnodes at the same time",
        "logs": [],
        "stack_traces": [
          java.lang.RuntimeException: Bootstrap Token collision between /10.0.0.2 and /10.0.0.3 (token Token (bytes[4c617374204d6967726174696f6e])\nat org.apache.cassandra.locator.TokenMetadata.addBootstrapToken(TokenMetadata.java:130)\nat org.apache.cassandra.service.StorageService.handleStateBootstrap(StorageService.java:548)\nat org.apache.cassandra.service.StorageService.onChange(StorageService.java:511)\nat org.apache.cassandra.gms.Gossiper.doNotifications(Gossiper.java:705)\nat org.apache.cassandra.gms.Gossiper.applyApplicationStateLocally(Gossiper.java:670)\nat org.apache.cassandra.gms.Gossiper.applyStateLocally(Gossiper.java:624)\nat org.apache.cassandra.gms.Gossiper$GossipDigestAck2VerbHandler.doVerb(Gossiper.java:1016)\nat org.apache.cassandra.net.MessageDeliveryTask.run(MessageDeliveryTask.java:41)\nat java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1110)\nat java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:603)\nat java.lang.Thread.run(Thread.java:636)
        ]
      }}
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        extra_body={"enable_thinking": False},
    )
    results = response.choices[0].message.content
    logger.info("GPT Results: " + results)
    extract_results = json.loads(results)
    print(extract_results)
    logger.info("Extract Results: " + str(extract_results))
    return extract_results


def main():
    bug_reports = r"..\bug_reports"
    reports = os.listdir(bug_reports)
    ret = []
    for report in reports:
        # if not report.startswith('Cassandra-1011'):
        #     continue
        doc = docx.Document(os.path.join(bug_reports, report))
        txts = '\n'.join([para.text for para in doc.paragraphs])
        extract_results = extract_classes_and_content_from_log_with_gpt(txts, "sk-3e555704f5e64d7f98fc43d755443cd4",
                                                                        "qwen-turbo",
                                                                        "https://dashscope.aliyuncs.com/compatible-mode/v1")
        ret.append(extract_results)
        # print(extract_results)
    with open("structuration_info.json", "w", encoding="utf-8"):
        json.dump(ret, indent=2, ensure_ascii=False)
    print("Done")

if __name__ == '__main__':
    main()
