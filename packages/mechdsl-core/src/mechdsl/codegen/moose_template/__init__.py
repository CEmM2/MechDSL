"""Package marker so MOOSE template files ship with the installed wheel.

The actual template lives in ``input_template.i`` next to this file; it is
loaded by :func:`mechdsl.codegen.moose_printer.emit_input_file` via
``importlib.resources``-style path resolution.
"""
