import sys
import os.path
import re

if len(sys.argv) == 1 or len(sys.argv) > 2:
    exit("Usage: python cluelang.py program.cla")

script = sys.argv[1]

if not os.path.exists(script):
    exit("Script not found: %s" % script)

functions = {}
variables = {}
current_line = 0

def replace_vars(expr, local_vars=None):
    if not expr.strip():
        return expr

    if local_vars is None:
        local_vars = {}

    all_vars = {**variables, **local_vars}

    if not all_vars:
        return expr

    expr = re.sub(r'\$\{(\w+)\}', lambda match: str(all_vars.get(match.group(1), '')), expr)

    if all_vars:
        pattern = re.compile(r'\b(' + '|'.join(re.escape(var) for var in all_vars) + r')\b')
        expr = pattern.sub(lambda match: str(all_vars.get(match.group(0), '')), expr)

    return expr

def process_loop_block(line, lines):
    global current_line
    loop_count_expr = line[line.find(":") + 1:line.find("{")].strip()
    loop_count_expr = replace_vars(loop_count_expr)
    try:
        loop_count = int(loop_count_expr)
    except ValueError:
        print(f"Error: Loop count must be an integer or a valid variable at line {current_line}")
        exit(8)

    loop_body = ""
    open_brace_found = False

    if "{" in line:
        open_brace_found = True
        loop_body += line[line.find("{") + 1:].strip()

    while current_line < len(lines):
        line = lines[current_line].strip()
        current_line += 1

        if not open_brace_found and "{" in line:
            open_brace_found = True
            line = line[line.find("{") + 1:].strip()

        if "}" in line:
            loop_body += line[:line.find("}")].strip()
            break

        loop_body += line + "\n"

    if not open_brace_found:
        print(f"Error: Missing opening curly brace in loop block at line {current_line}")
        exit(7)

    for _ in range(loop_count):
        for body_line in loop_body.splitlines():
            process_line(body_line.strip(), lines)

def process_line(line, lines):
    global current_line

    if line.startswith("exec "):
        process_exec_block(line, lines)
        return

    if line.startswith("loop:"):
        process_loop_block(line, lines)
        return

    if '=' in line:
        var_name, value = map(str.strip, line.split('=', 1))
        
        if '(' in value and ')' in value:
            func_call = value.strip()
            func_name = func_call[:func_call.find("(")]
            args = func_call[func_call.find("(")+1:func_call.find(")")].split(",")
            args = [replace_vars(arg.strip()) for arg in args]
            
            return_value = execute_function(func_name, args)
            variables[var_name] = return_value
        else:
            value = replace_vars(value)
            variables[var_name] = eval(value) 

        return

    for f in ["output", "input"]:
        if line.startswith(f):
            if f == 'output':
                fun_arg = line[line.find('(') + 1 : line.rfind(')')].strip()
                fun_arg = replace_vars(fun_arg)
                print(fun_arg[1:-1] if fun_arg.startswith('"') and fun_arg.endswith('"') else fun_arg)
                
            elif f == 'input':
                fun_arg = line[line.find('(') + 1 : line.rfind(')')].strip()
                if fun_arg.startswith('"') and fun_arg.endswith('"'):
                    prompt = fun_arg.strip('"')
                    if '->' in line:
                        _, var_name = map(str.strip, line.split('->'))
                        user_input = input(prompt)
                        variables[var_name] = user_input
                    else:
                        print(f"Error: Input command missing variable assignment at line {current_line}")
                        exit(4)

def process_exec_block(line, lines):
    global current_line

    func_name = line[5:line.find("(")].strip()
    params = line[line.find("(")+1:line.find(")")].strip().split(",")
    params = [p.strip() for p in params if p.strip()]

    function_body = ""
    open_brace_found = False

    if "{" in line:
        open_brace_found = True
        function_body += line[line.find("{") + 1:].strip()

    while current_line < len(lines):
        line = lines[current_line].strip()
        current_line += 1

        if not open_brace_found and "{" in line:
            open_brace_found = True
            line = line[line.find("{") + 1:].strip()

        if "}" in line:
            function_body += line[:line.find("}")].strip()
            break

        function_body += line + "\n"

    if not open_brace_found:
        print(f"Error: Missing opening curly brace in exec block at line {current_line}")
        exit(7)

    functions[func_name] = (params, function_body.strip())

def execute_function(func_name, args):
    if func_name in functions:
        params, func_body = functions[func_name]

        if len(params) != len(args):
            print(f"Error: Function '{func_name}' expects {len(params)} arguments but got {len(args)}.")
            exit(5)

        local_vars = dict(zip(params, args)) 
        local_vars.update(variables) 
        
        return_value = None

        for line in func_body.splitlines():
            line = replace_vars(line.strip(), local_vars) 
            
            if line.startswith("return "):
                return_expr = line[len("return "):].strip()
                return_value = eval(replace_vars(return_expr, local_vars)) 
                break
            
            process_line(line, lines)

        return return_value
    else:
        print(f"Error: Function '{func_name}' is not defined.")
        exit(6)

with open(script, 'r') as s:
    lines = s.readlines()
    current_line = 0
    while current_line < len(lines):
        line = lines[current_line].strip()
        current_line += 1
        process_line(line, lines)
