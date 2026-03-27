/**
 * @name EnumLookup
 * @description Flat lookup table for all enum/enum-class types.
 *              Columns match Classes.csv format so get_class() can use it as a fallback.
 * @kind problem
 * @id vulnhalla/enum-lookup
 */
import cpp

from Enum e
where not e.getName() = "(unnamed enum)"
select
  "Enum" as type,
  e.getQualifiedName() as name,
  e.getLocation().getFile() as file,
  e.getLocation().getStartLine() as start_line,
  e.getLocation().getStartLine() as end_line,   // placeholder — fix_enum_endlines.py patches this
  e.getSimpleName() as simple_name
