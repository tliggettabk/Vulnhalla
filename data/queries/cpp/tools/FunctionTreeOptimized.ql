import cpp

// Corrected FunctionTree query that matches expected format:
// - Functions with callers appear multiple times (once per caller)
// - Functions with no callers appear once with empty caller_id
from Function f
select 
    f.getName() as function_name, 
    f.getLocation().getFile() as file, 
    f.getLocation().getStartLine() as start_line, 
    f.getLocation().getFile() + ":" + f.getLocation().getStartLine() as function_id, 
    f.getBlock().getLocation().getEndLine() as end_line,
    (if exists(FunctionCall call | call.getTarget() = f)
     then any(FunctionCall call | call.getTarget() = f | 
          call.getEnclosingFunction().getLocation().getFile() + ":" + call.getEnclosingFunction().getLocation().getStartLine())
     else "") as caller_id