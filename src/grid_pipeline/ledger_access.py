"""Static ledger-path IO checks, complemented by the pytest runtime audit hook.

Scan all maintained Python and shell entry points, including unexecuted code.
This is a conservative path-flow check, not a proof about arbitrary generated
code, native extensions, or intentionally obfuscated programs.
"""
import ast
import os
from pathlib import Path
import re
import sys

_INSTALLED = False


def install_runtime_guard():
    """Protect the real repository ledger in every importing Python process."""
    global _INSTALLED
    if _INSTALLED:
        return
    root = Path(__file__).resolve().parents[2]
    protected = os.path.normcase(str(root / 'ledger'))
    owner = os.path.normcase(str(root / 'src/grid_pipeline/ledger.py'))

    def external_path(value, cwd):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return False
        text = os.fsdecode(value)
        normalized = text.replace('\\', '/').casefold()
        prefix = protected.replace('\\', '/').casefold()
        if prefix in normalized:
            return True
        candidates = [text, *text.split(os.pathsep)]
        candidates.extend(next(part for part in match.groups() if part is not None)
                          for match in re.finditer(r'''"([^"]*)"|'([^']*)'|(\S+)''', text))
        for candidate in dict.fromkeys(candidates):
            if not ('/' in candidate or '\\' in candidate or candidate.casefold() in {'ledger', '.', '..'}):
                continue
            try:
                candidate = candidate.replace('\\', os.sep).replace('/', os.sep)
                absolute = os.path.normcase(os.path.realpath(os.path.join(cwd, candidate)))
            except (ValueError, OSError):
                continue
            if absolute == protected or absolute.startswith(protected + os.sep):
                return True
        return False

    def audit(event, args):
        if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'}:
            if event == 'subprocess.Popen':
                executable, arguments, cwd, environment = args
            elif event == 'os.system':
                executable, arguments, cwd, environment = '', args[0], None, None
            else:
                executable, arguments, environment = args[:3]
                cwd = None
            cwd = os.path.abspath(os.fsdecode(cwd)) if cwd is not None else os.getcwd()
            values = [executable, cwd]
            values.extend(arguments if isinstance(arguments, (list, tuple)) else [arguments])
            values.extend((os.environ if environment is None else environment).values())
            if any(external_path(value, cwd) for value in values):
                raise PermissionError('external ledger paths forbidden; pass content through stdin')
            return
        if event not in {'open', 'os.listdir', 'os.scandir', 'os.remove', 'os.rename',
                         'os.mkdir', 'os.rmdir'}:
            return
        for argument in args[:2] if event == 'os.rename' else args[:1]:
            if not isinstance(argument, (str, bytes, os.PathLike)):
                continue
            path = os.path.normcase(os.path.realpath(os.fsdecode(argument)))
            if path != protected and not path.startswith(protected + os.sep):
                continue
            frame = sys._getframe(1)
            authorized = False
            while frame:
                if os.path.normcase(os.path.abspath(frame.f_code.co_filename)) == owner:
                    authorized = True
                    break
                frame = frame.f_back
            if not authorized:
                raise PermissionError('ledger access must go through grid_pipeline.ledger')

    sys.addaudithook(audit)
    _INSTALLED = True

_SINKS = {'open', 'read_bytes', 'read_text', 'write_bytes', 'write_text', 'listdir',
          'scandir', 'glob', 'rglob', 'iterdir', 'unlink', 'remove', 'rename',
          'replace', 'mkdir', 'rmdir', 'stat', 'lstat', 'run', 'Popen', 'system',
          'call', 'check_call', 'check_output', 'exec', 'eval'}
_READ_APIS = {'read_content', 'read_definition', 'receipt_paths', 'append_forecast', 'select_receipt'}


def violations(source: str, suffix: str, *, test_fixtures=False) -> list[int]:
    if suffix != '.py':
        has_path = re.search(r'''(?im)ledger[/\\]|['"]ledger['"]|=\s*ledger(?:[;\s]|$)''', source)
        has_io = re.search(r'(?i)Get-FileHash|Get-Content|Set-Content|ReadAll|WriteAll|\b(cat|cp|rm|sha256sum)\b', source)
        return [source[:has_path.start()].count('\n') + 1] if has_path and has_io else []
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = set()
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    parameters = {name: {} for name in functions}
    returns = {}
    aliases = {item.asname or item.name: item.name for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) for item in node.names if item.name in _SINKS}

    def scope(nodes, inherited, function=None):
        labels = dict(inherited)
        labels.update(parameters.get(function, {}))
        if test_fixtures:
            labels.update({'tmp_path': 'temporary', 'repository': 'temporary'})

        def label(node):
            if node is None:
                return ''
            if isinstance(node, ast.Name):
                return labels.get(node.id, '')
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return 'ledger' if re.search(r'(^|[/\\\s\x22\x27])ledger($|[/\\])', node.value) else ''
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
                if name in _READ_APIS:
                    return 'temporary' if node.args and label(node.args[0]) == 'temporary' else ''
                if isinstance(node.func, ast.Name) and node.func.id in functions:
                    definition = functions[node.func.id]
                    for argument, value in zip(definition.args.args, node.args):
                        value_label = label(value)
                        if value_label:
                            parameters[node.func.id][argument.arg] = value_label
                    for argument in node.keywords:
                        if argument.arg and label(argument.value):
                            parameters[node.func.id][argument.arg] = label(argument.value)
                    return returns.get(node.func.id, '')
            child_labels = [label(child) for child in ast.iter_child_nodes(node)]
            if isinstance(node, ast.BinOp) and label(node.left) == 'temporary':
                return 'temporary'
            if 'ledger' in child_labels:
                return 'ledger'
            return 'temporary' if 'temporary' in child_labels else ''

        flat = []

        def collect(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return
            flat.append(node)
            for child in ast.iter_child_nodes(node):
                collect(child)

        for node in nodes:
            collect(node)
        for _ in range(len(flat) + 1):
            changed = False
            for node in flat:
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    value_label = label(node.value)
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            previous = labels.get(target.id, '')
                            effective = ('ledger' if 'ledger' in {previous, value_label} else
                                         'unknown' if previous == 'temporary' and not value_label else
                                         value_label or previous)
                            if effective and previous != effective:
                                labels[target.id] = effective
                                changed = True
                        if (isinstance(target, ast.Name) and isinstance(node.value, ast.Attribute)
                                and node.value.attr in _SINKS):
                            aliases[target.id] = node.value.attr
            if not changed:
                break
        for node in flat:
            if isinstance(node, ast.Return) and function:
                value_label = label(node.value)
                if value_label:
                    returns[function] = value_label
            if not isinstance(node, ast.Call):
                continue
            label(node)
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            name = aliases.get(name, name)
            if name == 'replace' and len(node.args) == 2 and all(
                    isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in node.args):
                continue  # str.replace(old, new), not Path.replace(target).
            target = node
            if isinstance(node.func, ast.Attribute) and name not in {
                    'run', 'Popen', 'system', 'call', 'check_call', 'check_output',
                    'open', 'listdir', 'scandir', 'remove', 'rename', 'stat', 'lstat'}:
                target = node.func.value
            if name not in _SINKS or label(target) != 'ledger':
                continue
            parent = parents.get(node)
            expected_denial = False
            while parent is not None:
                if isinstance(parent, ast.With):
                    expected_denial |= any(
                        isinstance(item.context_expr, ast.Call)
                        and isinstance(item.context_expr.func, ast.Attribute)
                        and item.context_expr.func.attr == 'raises'
                        and item.context_expr.args
                        and isinstance(item.context_expr.args[0], ast.Name)
                        and item.context_expr.args[0].id == 'PermissionError'
                        for item in parent.items)
                parent = parents.get(parent)
            if not expected_denial:
                found.add(node.lineno)
        for node in nodes:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    scope(child.body, labels, getattr(child, 'name', None))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scope(node.body, labels, getattr(node, 'name', None))

    for _ in range(len(functions) + 2):
        before = repr((parameters, returns))
        scope(tree.body, {})
        if repr((parameters, returns)) == before:
            break
    return sorted(found)


def check_repository(repo: Path) -> list[str]:
    repo = Path(repo)
    failures = []
    for directory in ['', 'src', 'scripts', 'tests', '.githooks', '.github']:
        paths = repo.iterdir() if directory == '' else (repo / directory).rglob('*')
        for path in sorted(paths):
            if not path.is_file() or path.suffix not in {'.py', '.ps1', '.sh', '.yml', '.yaml', ''}:
                continue
            relative = path.relative_to(repo).as_posix()
            if relative == 'src/grid_pipeline/ledger.py':
                continue
            source = path.read_text(encoding='utf-8-sig')
            lines = violations(source, path.suffix, test_fixtures=directory == 'tests')
            failures.extend(f'{relative}:{line}: direct ledger IO outside ledger.py' for line in lines)
    return failures
