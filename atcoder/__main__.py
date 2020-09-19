import argparse
import ast
import importlib
import inspect
import re
from typing import List, Optional


class ImportInfo:
    def __init__(self, lineno: int, end_lineno: int,
                 import_from: Optional[str] = None,
                 name: Optional[str] = None,
                 asname: Optional[str] = None) -> None:
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.import_from = import_from
        self.name = name
        self.asname = asname


def iter_child_nodes(
        node: ast.AST,
        import_info: Optional[ImportInfo] = None) -> List[ImportInfo]:
    result = []

    if isinstance(node, ast.alias):
        if import_info:
            result.append(ImportInfo(
                import_info.lineno, import_info.end_lineno,
                import_info.import_from, node.name, node.asname))
        return result

    if isinstance(node, ast.Import):
        for name in node.names:
            if re.match(r'^atcoder\.?', name.name):
                import_info = ImportInfo(node.lineno, node.end_lineno)
    elif isinstance(node, ast.ImportFrom):
        import_info = ImportInfo(node.lineno, node.end_lineno, node.module)

    for child in ast.iter_child_nodes(node):
        result += iter_child_nodes(child, import_info)
    return result


class ModuleImporter:
    def __init__(self) -> None:
        self.imported_modules = []

    def import_module(self, import_from: Optional[str], name: str,
                      asname: Optional[str] = None) -> str:
        result = ''

        if import_from is None:
            module_name = name
        else:
            try:
                module_name = import_from + '.' + name
                importlib.import_module(module_name)
            except ImportError:
                module_name = import_from

        if module_name not in self.imported_modules:
            self.imported_modules.append(module_name)

            module = importlib.import_module(module_name)
            source = inspect.getsource(module)
            lines = source.split('\n')
            imports = iter_child_nodes(ast.parse(source))

            import_lines = []
            import_list = []
            for import_info in imports:
                result += self.import_module(
                    import_info.import_from, import_info.name,
                    import_info.asname)
                for line in range(import_info.lineno - 1,
                                  import_info.end_lineno):
                    import_lines.append(line)

                if import_info.import_from is None:
                    import_list.append(import_info.name)
                else:
                    import_list.append(import_info.import_from)

            for lineno, line in enumerate(lines):
                if lineno not in import_lines:
                    continue
                lines[lineno] = '# ' + line  # TODO(not): indent

            modules = module_name.split('.')
            for i in range(len(modules) - 1):
                result += self.import_module(None, '.'.join(modules[:i + 1]))

            code = '_' + module_name.replace('.', '_') + '_code'
            result += f'{code} = """\n'
            result += '\n'.join(lines)
            result += '"""\n\n'
            result += f"{module_name} = types.ModuleType('{module_name}')\n"
            result += f'exec({code}, {module_name}.__dict__)\n'

            imported = []
            for import_ in import_list:
                modules = import_.split('.')
                for i in range(len(modules)):
                    import_name = '.'.join(modules[:i + 1])
                    if import_name in imported:
                        continue
                    imported.append(import_name)
                    result += f"{module_name}.__dict__['{import_name}']" \
                        f" = {import_name}\n"

        if import_from is None:
            if asname is None:
                if name != module_name:
                    result += f'{name} = {module_name}\n'
            else:
                result += f'{asname} = {module_name}\n'
        else:
            if asname is None:
                if name != import_from + '.' + name:
                    result += f'{name} = {import_from}.{name}\n'
            else:
                result += f'{asname} = {import_from}.{name}\n'

        return result + '\n'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('src', help='Source code')
    parser.add_argument('-o', '--output', help='Single combined code')
    args = parser.parse_args()

    with open(args.src) as f:
        lines = f.readlines()
    imports = iter_child_nodes(ast.parse(''.join(lines)))

    importer = ModuleImporter()
    result = 'import types\n\n'
    import_lines = []
    for import_info in imports:
        result += importer.import_module(
            import_info.import_from, import_info.name, import_info.asname)
        for line in range(import_info.lineno - 1, import_info.end_lineno):
            import_lines.append(line)

    for lineno, line in enumerate(lines):
        if lineno not in import_lines:
            continue
        lines[lineno] = '# ' + line  # TODO(not): indent
    result += ''.join(lines)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(result)
    else:
        print(result, end='')


if __name__ == '__main__':
    main()