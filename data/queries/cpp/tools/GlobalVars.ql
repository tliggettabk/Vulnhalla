import cpp

int getEndLine(GlobalOrNamespaceVariable g) {
  if exists(g.getInitializer())
  then result = g.getInitializer().getExpr().getLocation().getEndLine()
  else result = g.getLocation().getEndLine()
}

from GlobalOrNamespaceVariable g
select g.getName() as global_var_name,
       g.getLocation().getFile() as file,
       g.getLocation().getStartLine() as start_line,
       getEndLine(g) as end_line
