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

    def replace_var(match):
        var_name = match.group(1)
        return str(all_vars.get(var_name, ''))

    expr = re.sub(r'\$(\w+)', replace_var, expr)

    def replace_standalone_var(match):
        var_name = match.group(1)
        return str(all_vars.get(var_name, var_name))

    expr = re.sub(r'\b(\w+)\b(?![^"]*")', replace_standalone_var, expr)

    return expr


def process_loop_block(line, lines):
    global current_line
    loop_count_expr = line[line.find(":") + 1:line.find("{")].strip()
    loop_count_expr = replace_vars(loop_count_expr, {})
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

    for i in range(loop_count):
        local_vars = {"index": i}
        local_vars.update(variables)

        for body_line in loop_body.splitlines():
            processed_line = replace_vars(body_line.strip(), local_vars)
            process_line(processed_line, lines, local_vars)

def process_line(line, lines, local_vars=None):
    global current_line

    if local_vars is None:
        local_vars = {}

    # Remove comments
    line = re.sub(r'>>.*?<<', '', line)
    line = line.split('>>')[0].strip()

    if not line:
        return

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
            args = func_call[func_call.find("(") + 1:func_call.find(")")].split(",")

            return_value = execute_function(func_name, args)
            variables[var_name] = return_value
        else:
            value = replace_vars(value, local_vars)

            try:
                variables[var_name] = eval(value)
            except Exception as e:
                print(f"Error evaluating expression '{value}': {e}")
                exit(9)

        return

    for f in ["output", "input"]:
        if line.startswith(f):
            if f == 'output':
                fun_arg = line[line.find('(') + 1: line.rfind(')')].strip()
                fun_arg = replace_vars(fun_arg, local_vars)
                print(fun_arg[1:-1] if fun_arg.startswith('"') and fun_arg.endswith('"') else fun_arg)

            elif f == 'input':
                fun_arg = line[line.find('(') + 1: line.rfind(')')].strip()
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
    brace_count = 1

    if "{" in line:
        open_brace_found = True
        function_body += line[line.find("{") + 1:].strip()

    while current_line < len(lines):
        line = lines[current_line].strip()
        current_line += 1

        if not open_brace_found and "{" in line:
            open_brace_found = True
            function_body += line[line.find("{") + 1:].strip()
            brace_count += 1

        if "}" in line:
            brace_count -= 1
            function_body += line[:line.find("}")].strip()
            if brace_count == 0:
                break

        function_body += line + "\n"

    if not open_brace_found:
        print(f"Error: Missing opening curly brace in exec block at line {current_line}")
        exit(7)

    functions[func_name] = (params, function_body.strip())


def string_function(args):
    if len(args) != 1:
        print("Error: string() function takes exactly one argument.")
        exit(5)

    value = eval(args[0])
    return str(value)

def execute_function(func_name, args):
    if func_name == "string":
        return string_function(args)

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
                return_value = eval(replace_vars(return_expr, local_vars), {}, local_vars)
                break

            process_line(line, lines, local_vars)

        return return_value
    else:
        print(f"Error: Function '{func_name}' is not defined.")
        exit(6)

def safe_eval(expr, local_vars):
    try:
        if any(isinstance(eval(var, {}, local_vars), str) for var in local_vars):
            expr = ' + '.join([f'str({var})' for var in local_vars.keys()] + [f'str({var})' for var in local_vars.keys()])
        return eval(expr, {}, local_vars)
    except Exception as e:
        print(f"Error evaluating expression '{expr}': {e}")
        exit(9)

with open(script, 'r') as s:
    lines = s.readlines()
    current_line = 0
    while current_line < len(lines):
        line = lines[current_line].strip()
        current_line += 1
        process_line(line, lines)
