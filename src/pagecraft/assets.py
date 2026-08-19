"""Static asset copying for Pagecraft.

Everything placed in the project's ``assets/`` directory (images, extra
CSS, JavaScript, fonts) is copied verbatim into the build output,
preserving the directory structure.
"""

from __future__ import annotations

import os
import shutil


def copy_assets(project_root: str, assets_dir: str, output_dir: str) -> list[str]:
    """Copy ``assets_dir`` from the project into ``output_dir``.

    Returns the list of destination files that were copied.
    """
    source = os.path.join(project_root, assets_dir)
    if not os.path.isdir(source):
        return []

    copied: list[str] = []
    for dirpath, _, filenames in os.walk(source):
        rel_root = os.path.relpath(dirpath, source)
        dest_root = output_dir if rel_root == "." else os.path.join(output_dir, rel_root)
        os.makedirs(dest_root, exist_ok=True)
        for name in filenames:
            src_file = os.path.join(dirpath, name)
            dst_file = os.path.join(dest_root, name)
            shutil.copy2(src_file, dst_file)
            copied.append(dst_file)
    return copied
