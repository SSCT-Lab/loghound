/**
 * 方法级静态覆盖率（source-only 友好）：
 * 为每个 src/main/java 的方法，列出命中的测试方法（src/test/java），
 * 区分直接调用 / 传递调用，并给出（直接调用时）测试调用位置。
 *
 * 结果列：
 * - 生产方法
 * - 测试方法
 * - 覆盖类型：direct / transitive
 * - 直接调用位置（文件:行）若为 direct
 */

import java

// ------ 帮助谓词：路径归属 ------
predicate isMainFile(File f) { f.getRelativePath().matches("src/java/%") }
predicate isTestFile(File f) { f.getRelativePath().matches("src/test/unit/%") }

predicate isMainMethod(Method m) {
  exists(CompilationUnit cu | cu = m.getDeclaringType().getCompilationUnit() and isMainFile(cu.getFile()))
}

predicate isTestCallable(Callable c) {
  exists(CompilationUnit cu | cu = c.getDeclaringType().getCompilationUnit() and isTestFile(cu.getFile()))
}

// ------ 统一“直接调用边”：方法调用 + 构造调用 ------
predicate directCalls(Callable caller, Callable callee) {
  // 方法调用：foo.bar()
  exists(MethodAccess ma |
    ma.getEnclosingCallable() = caller and
    callee instanceof Method and
    ma.getMethod() = callee
  )
  or
  // 构造调用：new X(...)
  exists(ClassInstanceExpr cie |
    cie.getEnclosingCallable() = caller and
    callee instanceof Constructor and
    cie.getConstructor() = callee
  )
}

// 递归闭包：caller 经由0+条边到达 callee（自反传递闭包）
predicate reaches(Callable caller, Callable callee) {
  caller = callee or
  exists(Callable mid | directCalls(caller, mid) and reaches(mid, callee))
}

// 是否存在“直接测试调用”
predicate hasDirectTestCall(Method m, Callable test) {
  isMainMethod(m) and isTestCallable(test) and
  // 直接一跳
  directCalls(test, m)
}

// 是否存在“传递测试调用”
predicate hasTransitiveTestCall(Method m, Callable test) {
  isMainMethod(m) and isTestCallable(test) and
  // 至少两跳：test -> ... -> m 且不是直接
  reaches(test, m) and not directCalls(test, m)
}

// 定位一个直接测试调用的位置（若存在）
class ADirectTestCall extends MethodAccess {
  ADirectTestCall() { exists(Callable test, Method m |
    this.getEnclosingCallable() = test and
    this.getMethod() = m and
    isTestCallable(test) and isMainMethod(m)
  ) }
}

from Method m, Callable test
where isMainMethod(m) and isTestCallable(test) and reaches(test, m)
select
  m,                                          // 生产方法
  test,                                       // 测试方法
  case
    when directCalls(test, m) then "direct"
    else "transitive"
  end,
  // 如果是直接调用，给出测试中某个调用点的位置；否则留空
  any(ADirectTestCall c |
      c.getMethod() = m and c.getEnclosingCallable() = test
  ).getFile().getRelativePath()
  + ":"
  + toString(any(ADirectTestCall c |
      c.getMethod() = m and c.getEnclosingCallable() = test
  ).getLocation().getStartLine())
  as directCallSite
