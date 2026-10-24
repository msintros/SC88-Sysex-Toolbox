"""Load the data definitions from SC88_Flashlight_a7.py without starting Pygame.

Only top-level constant tables and pure helper functions are executed, so the
tools in this folder can read the Python app's tables and formatters directly.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_SOURCE = ROOT / "SC88_Flashlight_a7.py"

# Top-level names to copy out of the app. Assignments are kept when they bind
# one of these names; functions are kept by name.
NAMES = {
    "PART_PARAM_CATEGORIES", "PART_PARAM_DEFS", "PART_PARAM_PAGE_MAP",
    "PARAMETER_PAGES", "scaleTuneNotes", "buttons",
    "_pp", "_controller_group", "default_part_param_value",
    "part_to_block", "part_param_address", "actual_part_param_address",
    "efx_part_address", "scale_tune_address",
    "format_midi_note", "format_part_param_value", "format_signed_64",
    "delay_time_center_ms", "format_delay_time_center", "format_delay_ratio",
    "format_parameter_value", "encode_parameter_data", "format_scale_tune",
    "effect_display_name", "step_efx_value", "step_parameter_value",
    "step_part_param",
}


def _binds(node):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                yield target.id
            elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                yield target.value.id
    elif isinstance(node, ast.FunctionDef):
        yield node.name


def load():
    tree = ast.parse(APP_SOURCE.read_text())
    kept = [n for n in tree.body if any(name in NAMES for name in _binds(n))]
    module = ast.Module(body=kept, type_ignores=[])
    namespace = {}
    exec(compile(module, str(APP_SOURCE), "exec"), namespace)
    return namespace
