"""Quick check: why do both parsers skip these 10 cases?"""
import csv, re, sys, zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
src_zip = db + "\\src.zip"

cases = [
    ("Bind", "D_/mapped_drives/cod/trunk/code/src/qcommon/com_keys.h", 22),
    ("D3D12_MESSAGE_ID", "C_/vendor/visual_studio/17.13.35806.99/windows_kits/10/Include/10.0.26100.0/um/d3d12sdklayers.h", 2362),
    ("WorkerCmdType", "D_/mapped_drives/cod/trunk/code/src/qcommon/sys_workercmds_decl.h", 541),
    ("Type", "D_/mapped_drives/cod/trunk/code/external/libs/battlenet/2022.10.1/packages/tact/3.6.45/src/file_streamer/file_streamer.h", 67),
    ("ValueType", "D_/mapped_drives/cod/trunk/code/external/libs/battlenet/2022.10.1/packages/snowcrypt/2.6.8/src/Utility/Internal.h", 1276),
]

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    for name, zp, start in cases:
        if zp not in znames:
            # Try finding it
            for z in znames:
                if z.endswith(zp.split("/")[-1]):
                    zp = z
                    break
        if zp not in znames:
            print(f"'{name}': file not found in zip")
            continue
        fl = zf.read(zp).decode("utf-8", "replace").replace("\r\n", "\n").split("\n")
        idx = start - 1
        
        # Show lines around start
        print(f"=== '{name}' L{start} in ...{zp[-60:]} ===")
        for i in range(max(0, idx-1), min(idx+5, len(fl))):
            print(f"  {i+1:>6}: {fl[i].rstrip()[:140]}")
        
        # Find the { and count to }
        brace_line = None
        for i in range(idx, min(idx + 10, len(fl))):
            if '{' in fl[i]:
                brace_line = i
                break
        
        if brace_line is None:
            print(f"  -> No {{ within 10 lines of start!")
        else:
            # Count to closing }
            depth = 0
            opened = False
            for i in range(brace_line, len(fl)):
                for ch in fl[i]:
                    if ch == '{':
                        depth += 1
                        opened = True
                    elif ch == '}':
                        depth -= 1
                        if opened and depth == 0:
                            span = i - idx + 1
                            print(f"  -> {{ at L{brace_line+1}, }} at L{i+1}  span={span} lines")
                            break
                if opened and depth == 0:
                    break
            else:
                print(f"  -> Unmatched braces!")
        print()
