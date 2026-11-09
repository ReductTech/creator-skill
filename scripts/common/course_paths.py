"""Discover one course layout without reading configuration or running course code."""
from pathlib import Path


def modules_directory(root):
    root = Path(root).resolve()
    nested = root / 'modules'
    if nested.exists() and not nested.is_dir():
        raise NotADirectoryError(f'Course modules path is not a directory: {nested}')
    flat = any(root.glob('*/outlines.json'))
    if nested.is_dir():
        if flat:
            raise ValueError('Mixed flat and modules/ course layouts; select one source root')
        result = nested.resolve()
        if not result.is_relative_to(root):
            raise ValueError('Course modules directory leaves targetRoot')
        return result
    return root if flat else nested


def outline_paths(root):
    return sorted(modules_directory(root).glob('*/outlines.json'))
