# complie_system.py
import os
import subprocess
import logging
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import re


class BuildTool:
    def __init__(self, workspace: str = "./tgt_sys"):
        self.workspace = Path(workspace)
        self.workspace.mkdir(exist_ok=True)
        self.setup_logging()

        # 项目配置
        self.projects = {
            "cassandra": {
                "build_cmd": ["ant"],
                "test_cmd": ["ant", "test"],
                "clean_cmd": ["ant", "clean"],
                "requirements": ["java", "ant"]
            },
            "hbase": {
                "build_cmd": ["mvn", "clean", "install", "-DskipTests"],
                "test_cmd": ["mvn", "test"],
                "clean_cmd": ["mvn", "clean"],
                "copy_deps_cmd": ["mvn", "dependency:copy-dependencies",
                                  f"-DoutputDirectory={os.path.join('LogRestore', 'libs')}"],
                "requirements": ["java", "maven"]
            },
            "hadoop_pre_0_23": {
                "build_cmd": ["ant", "jar"],
                "test_cmd": ["ant", "test"],
                "clean_cmd": ["ant", "clean"],
                "copy_deps_cmd": ["ant", "ivy:retrieve",
                                  f"-Divy.retrieve.pattern={os.path.join('..', 'LogRestore', 'libs', '[artifact]-[revision].[ext]')}"],
                "requirements": ["java", "ant", "ivy"]
            },
            "hadoop_post_0_23": {
                "build_cmd": ["mvn", "clean", "install", "-Pdist", "-DskipTests", "-Dmaven.javadoc.skip=true"],
                "test_cmd": ["mvn", "test"],
                "clean_cmd": ["mvn", "clean"],
                "copy_deps_cmd": ["mvn", "dependency:copy-dependencies",
                                  f"-DoutputDirectory={os.path.join('LogRestore', 'libs')}"],
                "requirements": ["java", "maven", "protoc"]
            },
            "zookeeper": {
                "build_cmd": ["mvn", "clean", "install", "-DskipTests"],
                "test_cmd": ["mvn", "test"],
                "clean_cmd": ["mvn", "clean"],
                "copy_deps_cmd": ["mvn", "dependency:copy-dependencies",
                                  f"-DoutputDirectory={os.path.join('LogRestore', 'libs')}"],
                "requirements": ["java", "maven"]
            }
        }

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.workspace / 'build.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def check_requirements(self, project_name: str) -> bool:
        """检查项目依赖"""
        if project_name not in self.projects:
            self.logger.error(f"Unknown project: {project_name}")
            return False

        requirements = self.projects[project_name]["requirements"]
        for req in requirements:
            if not shutil.which(req):
                self.logger.error(f"Missing requirement: {req}")
                return False
        return True

    def find_project_directory(self, project_name: str) -> Optional[Path]:
        """查找项目目录（以项目名作为前缀的目录）"""
        if not self.workspace.exists():
            self.logger.error(f"Workspace {self.workspace} does not exist")
            return None

        # 查找以项目名开头的目录
        for item in self.workspace.iterdir():
            if item.is_dir() and item.name.startswith(project_name):
                return item

        self.logger.error(f"Project directory for {project_name} not found in {self.workspace}")
        return None

    def extract_version(self, project_name: str, project_path: Path) -> Optional[str]:
        """从项目中提取版本号"""
        # 尝试从不同文件中获取版本信息
        version_files = []

        if project_name == "hadoop":
            # Hadoop版本信息可能在以下文件中
            version_files = [
                project_path / "ivy.xml",
                project_path / "pom.xml",
                project_path / "src" / "java" / "overview.html",
                project_path / "build.xml"
            ]

        version_pattern = r'[0-9]+\.[0-9]+\.[0-9]+'

        for version_file in version_files:
            if version_file.exists():
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match = re.search(version_pattern, content)
                        if match:
                            return match.group(0)
                except Exception as e:
                    self.logger.debug(f"Could not read {version_file}: {e}")
                    continue

        # 尝试从目录名中提取版本
        dir_name = project_path.name
        match = re.search(r'[0-9]+\.[0-9]+\.[0-9]+', dir_name)
        if match:
            return match.group(0)

        return None

    def determine_hadoop_build_type(self, project_path: Path) -> str:
        """确定Hadoop项目的构建类型"""
        # 检查是否存在pom.xml文件（Maven）
        pom_file = project_path / "pom.xml"
        build_file = project_path / "build.xml"

        if pom_file.exists():
            # 存在pom.xml，检查版本确定构建类型
            version = self.extract_version("hadoop", project_path)
            if version:
                # 比较版本号，0.23.0之前的版本使用Ant+Ivy
                try:
                    version_parts = list(map(int, version.split('.')))
                    if len(version_parts) >= 2:
                        major, minor = version_parts[0], version_parts[1]
                        if major == 0 and minor < 23:
                            self.logger.info(f"Hadoop {version} uses Ant+Ivy build system")
                            return "hadoop_pre_0_23"
                except ValueError:
                    pass

            self.logger.info("Hadoop project with pom.xml uses Maven build system")
            return "hadoop_post_0_23"
        elif build_file.exists():
            self.logger.info("Hadoop project with build.xml uses Ant+Ivy build system")
            return "hadoop_pre_0_23"
        else:
            # 默认使用Maven（较新版本）
            self.logger.warning("No build file found, defaulting to Maven build system")
            return "hadoop_post_0_23"

    def copy_dependencies(self, project_name: str, hadoop_type: str = None) -> bool:
        """复制项目依赖到libs目录"""
        # 对于Hadoop项目，使用特定的构建类型
        if project_name == "hadoop" and hadoop_type:
            actual_project_name = hadoop_type
        else:
            actual_project_name = project_name

        if actual_project_name not in self.projects:
            self.logger.error(f"Unknown project: {actual_project_name}")
            return False

        # 只有需要复制依赖的项目才执行此操作
        if "copy_deps_cmd" not in self.projects[actual_project_name]:
            self.logger.info(f"{actual_project_name} does not require dependency copying")
            return True

        project_path = self.find_project_directory(project_name if project_name != "hadoop" else "hadoop")
        if not project_path:
            return False

        # 创建libs目录
        libs_dir = Path("LogRestore") / "libs"
        libs_dir.mkdir(parents=True, exist_ok=True)

        copy_deps_cmd = self.projects[actual_project_name]["copy_deps_cmd"]
        self.logger.info(f"Copying dependencies for {actual_project_name} with command: {' '.join(copy_deps_cmd)}")
        try:
            subprocess.run(copy_deps_cmd, cwd=project_path, check=True)
            self.logger.info(f"Successfully copied dependencies for {actual_project_name}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to copy dependencies for {actual_project_name}: {e}")
            return False

    def build_project(self, project_name: str, run_tests: bool = False, copy_deps: bool = False) -> bool:
        """编译项目"""
        # 特殊处理Hadoop项目
        if project_name == "hadoop":
            return self.build_hadoop_project(run_tests, copy_deps)

        if project_name not in self.projects:
            self.logger.error(f"Unknown project: {project_name}")
            return False

        # 检查依赖
        if not self.check_requirements(project_name):
            self.logger.error(f"Requirements check failed for {project_name}")
            return False

        # 查找项目目录
        project_path = self.find_project_directory(project_name)
        if not project_path:
            return False

        # 执行编译
        build_cmd = self.projects[project_name]["build_cmd"]

        self.logger.info(f"Building {project_name} in {project_path} with command: {' '.join(build_cmd)}")
        try:
            env = os.environ.copy()
            # 设置JAVA_HOME（如果需要）
            if "JAVA_HOME" not in env:
                java_path = shutil.which("java")
                if java_path:
                    env["JAVA_HOME"] = str(Path(java_path).parent.parent)

            subprocess.run(build_cmd, cwd=project_path, check=True, env=env)
            self.logger.info(f"Successfully built {project_name}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build {project_name}: {e}")
            return False

        # 复制依赖（可选）
        if copy_deps:
            if not self.copy_dependencies(project_name):
                return False

        # 运行测试（可选）
        if run_tests:
            test_cmd = self.projects[project_name]["test_cmd"]
            self.logger.info(f"Running tests for {project_name} with command: {' '.join(test_cmd)}")
            try:
                subprocess.run(test_cmd, cwd=project_path, check=True)
                self.logger.info(f"Tests passed for {project_name}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Tests failed for {project_name}: {e}")
                return False

        return True

    def build_hadoop_project(self, run_tests: bool = False, copy_deps: bool = False) -> bool:
        """构建Hadoop项目（自动检测构建类型）"""
        project_path = self.find_project_directory("hadoop")
        if not project_path:
            return False

        # 确定Hadoop构建类型
        hadoop_build_type = self.determine_hadoop_build_type(project_path)

        # 检查依赖
        if not self.check_requirements(hadoop_build_type):
            self.logger.error(f"Requirements check failed for Hadoop ({hadoop_build_type})")
            return False

        # 执行编译
        build_cmd = self.projects[hadoop_build_type]["build_cmd"]

        self.logger.info(f"Building Hadoop ({hadoop_build_type}) in {project_path} with command: {' '.join(build_cmd)}")
        try:
            env = os.environ.copy()
            # 设置JAVA_HOME（如果需要）
            if "JAVA_HOME" not in env:
                java_path = shutil.which("java")
                if java_path:
                    env["JAVA_HOME"] = str(Path(java_path).parent.parent)

            subprocess.run(build_cmd, cwd=project_path, check=True, env=env)
            self.logger.info(f"Successfully built Hadoop ({hadoop_build_type})")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build Hadoop ({hadoop_build_type}): {e}")
            return False

        # 复制依赖（可选）
        if copy_deps:
            if not self.copy_dependencies("hadoop", hadoop_build_type):
                return False

        # 运行测试（可选）
        if run_tests:
            test_cmd = self.projects[hadoop_build_type]["test_cmd"]
            self.logger.info(f"Running tests for Hadoop ({hadoop_build_type}) with command: {' '.join(test_cmd)}")
            try:
                subprocess.run(test_cmd, cwd=project_path, check=True)
                self.logger.info(f"Tests passed for Hadoop ({hadoop_build_type})")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Tests failed for Hadoop ({hadoop_build_type}): {e}")
                return False

        return True

    def build_all(self, run_tests: bool = False, copy_deps: bool = False) -> Dict[str, bool]:
        """编译所有项目"""
        results = {}
        for project_name in ["cassandra", "hbase", "hadoop", "zookeeper"]:
            results[project_name] = self.build_project(project_name, run_tests, copy_deps)
        return results

    def clean_project(self, project_name: str) -> bool:
        """清理项目构建产物"""
        # 特殊处理Hadoop项目
        if project_name == "hadoop":
            project_path = self.find_project_directory("hadoop")
            if not project_path:
                return False

            hadoop_build_type = self.determine_hadoop_build_type(project_path)
            clean_cmd = self.projects[hadoop_build_type]["clean_cmd"]
        else:
            if project_name not in self.projects:
                self.logger.error(f"Unknown project: {project_name}")
                return False

            project_path = self.find_project_directory(project_name)
            if not project_path:
                return False

            clean_cmd = self.projects[project_name]["clean_cmd"]

        self.logger.info(f"Cleaning {project_name} with command: {' '.join(clean_cmd)}")
        try:
            subprocess.run(clean_cmd, cwd=project_path, check=True)
            self.logger.info(f"Successfully cleaned {project_name}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to clean {project_name}: {e}")
            return False

    def get_project_info(self, project_name: str) -> Optional[Dict]:
        """获取项目信息"""
        return self.projects.get(project_name)


def main():
    workspace = "./tgt_sys"
    tool = BuildTool(workspace)

    # 编译所有找到的项目
    projects_built = 0
    projects_success = 0

    for item in os.listdir(workspace):
        item_path = Path(workspace) / item
        if item_path.is_dir():
            if item.startswith("cassandra"):
                # projects_built += 1
                # success = tool.build_project("cassandra", run_tests=False, copy_deps=False)
                # if success:
                #     projects_success += 1
                continue
            elif item.startswith("hbase"):
                projects_built += 1
                success = tool.build_project("hbase", run_tests=False, copy_deps=True)
                if success:
                    projects_success += 1
            elif item.startswith("hadoop"):
                projects_built += 1
                success = tool.build_project("hadoop", run_tests=False, copy_deps=True)
                if success:
                    projects_success += 1
            elif item.startswith("zookeeper"):
                projects_built += 1
                success = tool.build_project("zookeeper", run_tests=False, copy_deps=True)
                if success:
                    projects_success += 1

    print(f"Build completed: {projects_success}/{projects_built} projects successful")
    exit(0 if projects_success == projects_built else 1)


if __name__ == "__main__":
    main()
