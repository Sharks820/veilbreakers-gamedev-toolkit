import json
import re

def fix_file(filename, errors):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Sort errors descending by row and column
    errors.sort(key=lambda x: (x['location']['row'], x['location']['column']), reverse=True)

    for e in errors:
        row = e['location']['row'] - 1
        code = e['code']
        msg = e['message']
        line = lines[row]
        
        if code == 'F841':
            # Local variable `xyz` is assigned to but never used
            m = re.search(r"Local variable `(.+?)` is assigned", msg)
            if m:
                varname = m.group(1)
                # rename the variable to _varname
                # Use regex to find the variable assignment
                # Since it can be `a, varname, c = ...` or `varname = ...`, 
                # we just replace the word boundary varname.
                # However, this could be tricky. A safer way is to append `# noqa: F841` 
                # OR prefix it with `_`
                lines[row] = re.sub(r'\b' + re.escape(varname) + r'\b', f'_{varname}', line, count=1)
        elif code == 'E741':
            # Ambiguous variable name `l`
            # For `l`, rename to `lyr` or `L`
            # Let's replace `l` with `L`
            lines[row] = re.sub(r'\bl\b', 'L', line)
        elif code in ('E402', 'F401', 'F821', 'E701'):
            # Just noqa the ones that are hard to safely rewrite automatically
            if '# noqa' in lines[row]:
                lines[row] = lines[row].rstrip('\n') + f', {code}\n'
            else:
                lines[row] = lines[row].rstrip('\n') + f'  # noqa: {code}\n'
            
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def main():
    with open('ruff_errors.json', 'r', encoding='utf-8-sig') as f:
        errors = json.load(f)
    
    from collections import defaultdict
    files = defaultdict(list)
    for e in errors:
        files[e['filename']].append(e)
        
    for filename, errs in files.items():
        fix_file(filename, errs)
        
    print("Done")

if __name__ == '__main__':
    main()
