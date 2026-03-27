/**
 * @name FunctionLookup
 * @description Flat function lookup table with qualified names for direct name-based search.
 *              Unlike FunctionTree.ql (which is a call-tree with caller_id), this query
 *              produces a simple lookup table: qualified_name, function_name, file, start_line, end_line.
 *              Used by the orchestrated analysis engine's lookup_function() method.
 * @kind problem
 * @id cpp/function-lookup
 */
import cpp

from Function f
where exists(f.getBlock())
select
    f.getQualifiedName() as qualified_name,
    f.getName() as function_name,
    f.getLocation().getFile() as file,
    f.getLocation().getStartLine() as start_line,
    f.getBlock().getLocation().getEndLine() as end_line
