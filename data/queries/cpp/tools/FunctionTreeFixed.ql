import cpp

// Final efficient approach: Join with calls but deduplicate to one row per function
from Function f
select 
    f.getName() as function_name, 
    f.getLocation().getFile() as file, 
    f.getLocation().getStartLine() as start_line, 
    f.getLocation().getFile() + ":" + f.getLocation().getStartLine() as function_id, 
    f.getBlock().getLocation().getEndLine() as end_line,
    min(FunctionCall call | call.getTarget() = f | 
        call.getEnclosingFunction().getLocation().getFile() + ":" + call.getEnclosingFunction().getLocation().getStartLine()) as caller_id