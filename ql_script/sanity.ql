import java

from Method m
where m.getDeclaringType().getCompilationUnit().getFile().getRelativePath().matches("src/java/%")
select m, m.getName()
