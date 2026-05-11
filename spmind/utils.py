import importlib
import os


def read_module2api():
    fields = [
        "imaging",
        "phenoimager2mc",
        "basic_illumination",
        "background_subtraction",
        "unetcoreograph",
        "segmentation_unmicst",
        "segmentation_s3segmenter",
        "quantification",
        "clustering",
        "bioimaging",
    ]

    module2api = {}
    for field in fields:
        module_name = f"spmind.tool.tool_description.{field}"
        module = importlib.import_module(module_name)
        module2api[f"spmind.tool.{field}"] = module.description
    return module2api


def get_tool_decorated_functions(relative_path):
    import ast
    import importlib.util

    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, relative_path)

    with open(file_path) as file:
        tree = ast.parse(file.read(), filename=file_path)

    tool_function_names = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Name)
                    and decorator.id == "tool"
                    or (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Name)
                        and decorator.func.id == "tool"
                    )
                ):
                    tool_function_names.append(node.name)

    package_path = os.path.relpath(file_path, start=current_dir)
    module_name = package_path.replace(os.path.sep, ".").rsplit(".", 1)[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tool_functions = [getattr(module, name) for name in tool_function_names]

    return tool_functions
