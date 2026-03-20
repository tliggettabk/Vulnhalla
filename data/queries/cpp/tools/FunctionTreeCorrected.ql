import cpp

// Union approach: functions with callers + functions without callers
from Function f, string caller_id
where 
  // Functions with callers - pick one caller using min()
  (exists(FunctionCall call | call.getTarget() = f) and
   caller_id = min(FunctionCall call | call.getTarget() = f | 
                   call.getEnclosingFunction().getLocation().getFile() + ":" + call.getEnclosingFunction().getLocation().getStartLine()))
  or
  // Functions without callers - empty caller_id  
  (not exists(FunctionCall call | call.getTarget() = f) and caller_id = "")
select 
    f.getName() as function_name, 
    f.getLocation().getFile() as file, 
    f.getLocation().getStartLine() as start_line, 
    f.getLocation().getFile() + ":" + f.getLocation().getStartLine() as function_id, 
    f.getBlock().getLocation().getEndLine() as end_line,
    caller_id