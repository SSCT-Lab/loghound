// LogRestorer.java
package org.example;

import soot.*;
import soot.jimple.*;
import soot.options.Options;
import soot.toolkits.graph.ExceptionalUnitGraph;
import soot.toolkits.scalar.SimpleLocalDefs;
import soot.util.Chain;

import java.io.File;
import java.util.*;

public class LogRestorer {
    public static void main(String[] args) {
        //TODO:跑之前执行类似命令，把lib放在当前目录libs下
        //mkdir -p /Users/linzheyuan/LogRestore/libs
        //mvn clean install -DskipTests #编译项目
        //mvn dependency:copy-dependencies -DoutputDirectory=/Users/linzheyuan/LogRestore/libs

        String base = "tgt_sys\\hadoop-0.23.0\\hadoop-hdfs-project\\hadoop-hdfs\\target\\classes";
        String libs = "LogRestore\\libs";

        File libDir = new File(libs);
        if (!libDir.exists()) {
            System.err.println("❌ Lib directory not found: " + libs);
            return;
        }

        String javaHome = System.getProperty("java.home");
        if (javaHome == null) {
            System.err.println("❌ JAVA_HOME is not set");
            return;
        }
        String rtJarPath = javaHome + "\\lib\\rt.jar";
        File rtJar = new File(rtJarPath);
        if (!rtJar.exists()) {
            System.err.println("❌ rt.jar not found at: " + rtJarPath);
            return;
        }

        StringBuilder cp = new StringBuilder();
        cp.append(base).append(";").append(rtJarPath);
        File[] jars = libDir.listFiles();
        if (jars != null) {
            for (File jar : jars) {
                if (jar.getName().endsWith(".jar")) {
                    cp.append(";").append(jar.getAbsolutePath());
                }
            }
        }

        Options.v().set_soot_classpath(cp.toString());
        Options.v().set_src_prec(Options.src_prec_class);
        Options.v().set_process_dir(Collections.singletonList(base));
        Options.v().set_prepend_classpath(true);
        Options.v().set_output_format(Options.output_format_none);
        Options.v().set_whole_program(true);
        Options.v().set_allow_phantom_refs(true);
        Scene.v().loadNecessaryClasses();

        PackManager.v().getPack("wjtp").add(new Transform("wjtp.logrestore", new SceneTransformer() {
            @Override
            protected void internalTransform(String phaseName, Map<String, String> options) {
                List<SootClass> appClasses = new ArrayList(Scene.v().getApplicationClasses());
                for (SootClass sc : appClasses) {
                    for (SootMethod method : sc.getMethods()) {
                        if (!method.isConcrete()) continue;

                        Body body;
                        try {
                            body = method.retrieveActiveBody();
                        } catch (Exception e) {
                            continue;
                        }

                        ExceptionalUnitGraph graph = new ExceptionalUnitGraph(body);
                        SimpleLocalDefs defs = new SimpleLocalDefs(graph);
                        List<Unit> unitList = new ArrayList(body.getUnits());

                        for (Unit unit : unitList) {
                            Stmt stmt = (Stmt) unit;
                            if (!stmt.containsInvokeExpr()) continue;

                            InvokeExpr invoke = stmt.getInvokeExpr();
                            if (invoke.getMethod().getDeclaringClass().getName().contains("Logger") || stmt.toString().contains("LOG.")) {
                                if (invoke.getArgCount() == 0) continue;

                                Value arg = invoke.getArg(0);
                                if (arg instanceof Local) {
                                    Set<String> fragments = new LinkedHashSet();
                                    resolveAllDefs((Local) arg, stmt, defs, fragments, new HashSet());

                                    if (!fragments.isEmpty()) {
                                        System.out.println("Method: " + method.getSignature());
                                        System.out.println("    Log Template: " +  fragments);
                                        System.out.println("-----");
                                    }
                                } else if (arg instanceof StringConstant) {
                                    System.out.println("Method: " + method.getSignature());
                                    System.out.println("    Constant Log: " + ((StringConstant) arg).value);
                                    System.out.println("-----");
                                }
                            }
                        }
                    }
                }
            }
        }));

        PackManager.v().runPacks();
    }

    // 递归拼接还原日志内容
    private static void resolveAllDefs(Local local, Unit stmt, SimpleLocalDefs defs,
                                       Set<String> fragments, Set<Unit> visited) {
        List<Unit> defUnits = defs.getDefsOfAt(local, stmt);
        for (Unit def : defUnits) {
            if (visited.contains(def)) continue;
            visited.add(def);

            if (def instanceof AssignStmt) {
                Value rhs = ((AssignStmt) def).getRightOp();

                if (rhs instanceof AddExpr) {
                    AddExpr add = (AddExpr) rhs;
                    resolveValue(add.getOp1(), def, defs, fragments, visited);
                    resolveValue(add.getOp2(), def, defs, fragments, visited);
                } else if (rhs instanceof InvokeExpr) {
                    InvokeExpr invoke = (InvokeExpr) rhs;
                    if (invoke.getMethod().getName().equals("format") && invoke.getArgCount() > 0) {
                        Value fmt = invoke.getArg(0);
                        if (fmt instanceof StringConstant) {
                            String raw = ((StringConstant) fmt).value;
                            fragments.add(raw.replaceAll("%[sd]", "<*>"));
                        }
                    } else {
                        fragments.add("<invoke>");
                    }
                } else if (rhs instanceof StringConstant) {
                    fragments.add(((StringConstant) rhs).value);
                } else if (rhs instanceof Local) {
                    resolveAllDefs((Local) rhs, def, defs, fragments, visited);
                } else {
                    fragments.add("<expr>");
                }
            }
        }
    }

    private static void resolveValue(Value val, Unit stmt, SimpleLocalDefs defs,
                                     Set<String> fragments, Set<Unit> visited) {
        if (val instanceof StringConstant) {
            fragments.add(((StringConstant) val).value);
        } else if (val instanceof Local) {
            resolveAllDefs((Local) val, stmt, defs, fragments, visited);
        } else {
            fragments.add("<*>");
        }
    }
}
