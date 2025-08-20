/**
 * 静态覆盖率汇总（buildless 友好）
 * 输出列：
 * - filePath:  生产方法所在源文件
 * - methodSig: 生产方法签名
 * - internalCovered: 该方法体内“被测命中”的内部调用点数（见下述判定）
 * - internalTotal:   该方法体内的内部调用点总数
 * - internalCoveragePct: internalCovered/internalTotal * 100（分母为0则为0）
 * - coverType: 覆盖类型（direct | transitive）
 * - coveringTest: 触达该方法的一个测试（多行呈现全部测试）
 */

import java

/** Cassandra */
predicate isCassandra(File f) { f.getRelativePath().matches("cassandra-%") }

predicate isMainFileCassandra(File f) { f.getRelativePath().matches("src/java/%") }

predicate isTestFileCassandra(File f) { f.getRelativePath().matches("test/%") }

/** hadoop */
predicate isHadoop021(File f) { f.getRelativePath().matches("hadoop-0.21%") }

predicate isMainFileHadoop021(File f) {
  f.getRelativePath().matches("common/src/java/%") or
  f.getRelativePath().matches("hdfs/src/java/%") or
  f.getRelativePath().matches("mapred/src/java/%")
}

predicate isTestFileHadoop021(File f) {
  f.getRelativePath().matches("common/src/test/%") or
  f.getRelativePath().matches("hdfs/src/test/%") or
  f.getRelativePath().matches("mapred/src/test/%")
}

predicate isHadoop023(File f) {
  f.getRelativePath().matches("hadoop-0.23%") or
  f.getRelativePath().matches("hadoop-1.%") or
  f.getRelativePath().matches("hadoop-2.%")
}

predicate isMainFileHadoop023(File f) { f.getRelativePath().matches("%/src/main/java/%") }

predicate isTestFileHadoop023(File f) { f.getRelativePath().matches("%/src/test/java/%") }

/** hbase */
predicate isHbase9094(File f) {
  f.getRelativePath().matches("hbase-0.90%") or
  f.getRelativePath().matches("hbase-0.92%") or
  f.getRelativePath().matches("hbase-0.94%")
}

predicate isMainFileHbase9094(File f) { f.getRelativePath().matches("src/main/java/%") }

predicate isTestFileHbase9094(File f) { f.getRelativePath().matches("src/test/java/%") }

predicate isHbase95(File f) {
  f.getRelativePath().matches("hbase-0.95%") or
  f.getRelativePath().matches("hbase-0.96%") or
  f.getRelativePath().matches("hbase-0.98%")
}

predicate isMainFileHbase95(File f) { f.getRelativePath().matches("%/src/main/java/%") }

predicate isTestFileHbase95(File f) { f.getRelativePath().matches("%/src/test/java/%") }

/** zookeeper */
predicate isZookeeper(File f) { f.getRelativePath().matches("zookeeper-%") }

predicate isMainFileZookeeper(File f) {
  f.getRelativePath().matches("src/java/main/%") or
  f.getRelativePath().matches("src/java/generated/%")
}

predicate isTestFileZookeeper(File f) {
  f.getRelativePath().matches("src/java/test/%") or
  f.getRelativePath().matches("src/java/systest/%")
}

/** Unified entry */
predicate isMainFile(File f) { isMainFileHadoop023(f) }

predicate isTestFile(File f) { isTestFileHadoop023(f) }

predicate isMainMethod(Method m) {
  exists(CompilationUnit cu |
    cu = m.getDeclaringType().getCompilationUnit() and isMainFile(cu.getFile())
  )
}

predicate isTestCallable(Callable c) {
  exists(CompilationUnit cu |
    cu = c.getDeclaringType().getCompilationUnit() and isTestFile(cu.getFile())
  )
}

// ---------- 调用图边：方法调用 + 构造调用 ----------
predicate directEdge(Callable caller, Callable callee) {
  // 方法调用
  exists(MethodCall ma |
    ma.getEnclosingCallable() = caller and
    callee instanceof Method and
    ma.getMethod() = callee
  )
  or
  // 构造调用
  exists(ClassInstanceExpr cie |
    cie.getEnclosingCallable() = caller and
    callee instanceof Constructor and
    cie.getConstructor() = callee
  )
}

// 传递可达（自反闭包）
predicate reaches(Callable caller, Callable callee) {
  caller = callee
  or
  exists(Callable mid | directEdge(caller, mid) and reaches(mid, callee))
}

// ---------- 方法体内的“内部调用点”抽象 ----------
class InternalCallSite extends Expr {
  InternalCallSite() { this instanceof MethodCall or this instanceof ClassInstanceExpr }

  Callable getCallee() {
    result instanceof Method and
    this instanceof MethodCall and
    result = this.(MethodCall).getMethod()
    or
    result instanceof Constructor and
    this instanceof ClassInstanceExpr and
    result = this.(ClassInstanceExpr).getConstructor()
  }

  Callable getEnclosingCallable_() { result = this.getEnclosingCallable() }
}

// 某个内部调用点是否“被测命中”（静态近似判定）
// 规则：其被调目标（callee）曾被至少一个测试“直接调用”过
predicate callSiteHitBySomeTest(InternalCallSite cs) {
  exists(Callable t | isTestCallable(t) and directEdge(t, cs.getCallee()))
}

// 构造方法签名字符串（更易读）
string methodSigOf(Method m) {
  result = m.getDeclaringType().getQualifiedName() + "." + m.getSignature()
}

// 测试标识（用于输出）
string labelOfTest(Callable t) {
  result =
    t.getDeclaringType().getQualifiedName() + "." + t.getName() + "@" +
      t.getLocation().getStartLine().toString()
}

// ---------- 主查询 ----------
from Method m, Callable t, int total, int hit
where
  isMainMethod(m) and
  isTestCallable(t) and
  // 测试能够到达该方法（direct 或 transitive）
  reaches(t, m) and
  // 统计总内部调用点
  total = count(InternalCallSite cs | cs.getEnclosingCallable_() = m) and
  // 统计“被测命中”的内部调用点（见上面的判定）
  hit = count(InternalCallSite cs | cs.getEnclosingCallable_() = m and callSiteHitBySomeTest(cs))
select m.getDeclaringType().getCompilationUnit().getFile().getRelativePath() as filePath,
  methodSigOf(m) as methodSig, hit as internalCovered, total as internalTotal,
  labelOfTest(t) as coveringTest order by filePath, methodSig, coveringTest
// from File f
// select f.getRelativePath()
