# Generates the API reference pages for every module in python_accounting.
# Used by the mkdocs-gen-files plugin; literate-nav stitches them into
# SUMMARY.md so the reference grows with the package automatically.

from __future__ import annotations

import pkgutil

import mkdocs_gen_files

import python_accounting

nav = mkdocs_gen_files.Nav()

root = python_accounting.__path__[0]

for module_info in sorted(
    pkgutil.walk_packages([root], prefix="python_accounting."),
    key=lambda m: m.name,
):
    if module_info.ispkg:
        continue
    module_name = module_info.name

    module_path = module_name.replace(".", "/") + ".md"
    full_doc_path = "reference/" + module_path

    parts = module_name.split(".")
    nav_parts = tuple(parts[1:])  # drop the "python_accounting" prefix for nav
    # SUMMARY.md lives inside reference/, so nav URLs are relative to it.
    nav[nav_parts] = module_path

    with mkdocs_gen_files.open(full_doc_path, "w") as f:
        ident = ".".join(parts)
        print(f"# `{ident}`", file=f)
        print(file=f)
        print(f"::: {ident}", file=f)

    mkdocs_gen_files.set_edit_path(full_doc_path, module_name.replace(".", "/") + ".py")

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
