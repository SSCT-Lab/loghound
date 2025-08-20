import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from datetime import datetime
import json

# 代理设置
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

# 获取网页内容
def fetch_page(url):
    start_time = time.time()  # 记录开始时间
    try:
        response = requests.get(url, proxies=proxies)
        if response.status_code == 200:
            print(f"成功获取页面：{url}")
        else:
            print(f"无法获取页面：{url}，状态码: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求错误：{e}")
        return None
    end_time = time.time()  # 记录结束时间
    print(f"fetch_page 执行时间: {end_time - start_time:.4f}秒")
    return response.text


# 保存Issue链接到本地文件
def save_links_to_file(links, file_path):
    start_time = time.time()  # 记录开始时间
    with open(file_path, 'w', encoding='utf-8') as file:
        for title, link in links:
            file.write(f"{title}\t{link}\n")
    print(f"所有链接已保存到本地文件：{file_path}")
    end_time = time.time()  # 记录结束时间
    print(f"save_links_to_file 执行时间: {end_time - start_time:.4f}秒")


# 读取本地文件
def read_local_file(file_path):
    start_time = time.time()  # 记录开始时间
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        # 将每行拆分为 (title, link) 元组
        result = []
        for line in lines:
            parts = line.strip().split('\t', 1)
            if len(parts) == 2:
                result.append((parts[0], parts[1]))
            else:
                print(f"忽略格式不正确的行: {line.strip()}")
    else:
        result = None
    end_time = time.time()  # 记录结束时间
    print(f"read_local_file 执行时间: {end_time - start_time:.4f}秒")
    return result


# 从网页中获取所有Issue链接及其标题
def fetch_issue_links(url):
    start_time = time.time()  # 记录开始时间
    response = fetch_page(url)
    issue_links = []
    if response:
        soup = BeautifulSoup(response, 'html.parser')
        # 查找所有Issue的链接及其显示的标题
        issue_links = [(link.get_text(), link['href']) for link in soup.find_all('a', href=True) if
                       'docs.google.com' in link['href']]
    end_time = time.time()  # 记录结束时间
    print(f"fetch_issue_links 执行时间: {end_time - start_time:.4f}秒")
    return issue_links


# 获取Google Docs页面的内容
def fetch_google_doc_content(url):
    start_time = time.time()  # 记录开始时间
    try:
        response = requests.get(url, proxies=proxies)
        if response.status_code == 200:
            print(f"成功获取Google文档页面：{url}")
        else:
            print(f"无法获取页面：{url}，状态码: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求错误：{e}")
        return None
    end_time = time.time()  # 记录结束时间
    print(f"fetch_google_doc_content 执行时间: {end_time - start_time:.4f}秒")
    return response.text


# 解析Google Docs页面并提取文档内容
# def parse_google_doc(content):
#     start_time = time.time()  # 记录开始时间
#     soup = BeautifulSoup(content, 'html.parser')
#     # 提取所有段落内容
#     paragraphs = soup.find_all('p')  # 提取所有段落
#     document_text = ""
#     for paragraph in paragraphs:
#         document_text += paragraph.get_text() + "\n"  # 拼接段落内容
#     end_time = time.time()  # 记录结束时间
#     print(f"parse_google_doc 执行时间: {end_time - start_time:.4f}秒")
#     return document_text

def parse_google_doc(content):
    # 先进行简单替换，将 &nbsp; 替换成普通空格
    # 如果有其他类似空格转义字符，也可以补充
    content = content.replace(u'\xa0', ' ').replace('&nbsp;', ' ')

    start_time = time.time()  # 记录开始时间
    soup = BeautifulSoup(content, 'html.parser')

    # 这里可以按照需要调整要提取的标题标签范围
    # h1, h2, h3, h4, h5, h6 都可加进来
    target_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p"]
    elements = soup.find_all(target_tags)

    # 最终的结果字典（顶层），里面可以包含多个 h1
    result = {}

    # 栈：用来追踪“当前在第几级标题下”的结构
    stack = [(result, 0)]

    # 简单写一个函数，根据标签名返回它的“层级”数值
    # 例如 h1 -> 1, h2 -> 2, h3 -> 3,...
    def get_level(tag_name):
        if tag_name.startswith("h"):
            # 假设都合法
            return int(tag_name[1:])
        return None

    for elem in elements:
        tag_name = elem.name
        # 先获取文本，strip() 去除首尾空白
        # 再用 split() + " ".join() 合并中间多余空格
        raw_text = elem.get_text(strip=True)
        text = " ".join(raw_text.split())

        # 如果是标题标签，则需要在层级关系中定位
        if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = get_level(tag_name)

            # 1) 弹出栈顶中比当前级别相等或更深的所有层级
            while stack and stack[-1][1] >= level:
                stack.pop()

            # 2) 此时栈顶的层级一定是 < 当前标题级别
            parent_dict, _ = stack[-1]

            # 3) 在 parent_dict 里，为该标题加一个 key，值是 {}
            parent_dict[text] = {}
            # 然后将这个新的子字典 push 到栈里
            stack.append((parent_dict[text], level))

        # 如果是段落标签 <p>
        elif tag_name == "p":
            # 获取当前处在栈顶的字典
            cur_dict, cur_level = stack[-1]

            # 我们把段落存到 key="p" 的列表里
            if "p" not in cur_dict:
                cur_dict["p"] = []
            cur_dict["p"].append(text)

    end_time = time.time()  # 记录结束时间
    print(f"parse_google_doc 执行时间: {end_time - start_time:.4f}秒")

    return json.dumps(result, ensure_ascii=False, indent=2)
# 保存文档内容到文件
def save_doc_to_file(content, folder, filename):
    start_time = time.time()  # 记录开始时间
    os.makedirs(folder, exist_ok=True)
    # 给文件名加上时间戳，避免文件名重复
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}".replace("/", "_").replace("\\", "_")  # 替换非法字符
    file_path = os.path.join(folder, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f"文档内容已保存到：{file_path}")
    end_time = time.time()  # 记录结束时间
    print(f"save_doc_to_file 执行时间: {end_time - start_time:.4f}秒")


# 主程序
def main():
    # 目标网页URL
    url = "https://cindyyw.github.io/DBugSet/bugSet.html"
    # 本地保存Issue链接的文件路径
    local_file_path = 'issue_links.txt'
    # 本地保存文档内容的文件夹路径
    output_folder = 'docs_output_title'

    # 检查本地是否已经保存过Issue链接
    issue_links = read_local_file(local_file_path)

    # 如果本地文件不存在，获取网页上的所有Issue链接并保存到文件
    if not issue_links:
        issue_links = fetch_issue_links(url)
        if issue_links:
            save_links_to_file(issue_links, local_file_path)

    if not issue_links:
        print("没有找到任何Issue链接。")
        return

    # 输出所有从本地读取或爬取的Issue链接及标题
    print("所有Issue链接：")
    for idx, (title, link) in enumerate(issue_links, 1):
        print(f"{idx}. {title} - {link}")

        # 获取Google Docs页面内容
        doc_content = fetch_google_doc_content(link)
        if doc_content:
            # 解析并获取Google Docs文档的内容
            document_text = parse_google_doc(doc_content)

            # 使用标题作为文件名并保存文档内容
            filename = f"{title}.txt".replace("/", "_").replace("\\", "_")  # 替换非法文件字符
            save_doc_to_file(document_text, output_folder, filename)

        print("\n" + "-" * 50 + "\n")


if __name__ == "__main__":
    main()
