/**
 * @name TypeAliasLookup
 * @description Flat lookup table for typedef and C++11 using type aliases.
 *              Columns match Classes.csv format so get_class() can use it as a fallback.
 *              Captures types that Classes.ql misses because TypedefType and
 *              C++11 using-aliases are not NameQualifyingElement subtypes.
 * @kind table
 * @id vulnhalla/type-alias-lookup
 */
import cpp

private string getFilePath(TypedefType t) {
  if exists(t.getLocation().getFile())
  then result = t.getLocation().getFile().toString()
  else result = ""
}

private int getStartLine(TypedefType t) {
  if exists(t.getLocation().getStartLine())
  then result = t.getLocation().getStartLine()
  else result = 0
}

from TypedefType t
where
  not t.getName().matches("(unnamed%") and
  not t.getName().regexpMatch("^__.*") and     // skip compiler-internal aliases like __int64
  not t.getQualifiedName().matches("%<%")      // skip template instantiation aliases
select
  "TypeAlias" as type,
  t.getQualifiedName() as name,
  getFilePath(t) as file,
  getStartLine(t) as start_line,
  getStartLine(t) as end_line,
  t.getSimpleName() as simple_name
