from __future__ import annotations
import csv
import os
import hashlib
import base64
import posixpath
#from pathlib import PurePosixPath
from typing import Optional, Dict, List, Union


class VFSException(Exception):
    pass


class VEntry:
    """Базовый класс для VFS"""
    def __init__(self, name: str, parent: Optional["VDirectory"] = None):
        self.name = name
        self.parent = parent

    def path(self) -> str:
        parts = []
        node: Optional[VEntry] = self
        while node is not None and node.parent is not None:
            parts.append(node.name)
            node = node.parent
        if not parts:
            return "/"
        return "/" + "/".join(reversed(parts))


class VFile(VEntry):
    """Для виртуальных файлов с содержанием строкового типа"""
    def __init__(self, name: str, content: str = "", parent: Optional["VDirectory"] = None):
        super().__init__(name, parent)
        self.content = content

    def read(self, decode_base64: bool = False) -> bytes:
        if decode_base64:
            return base64.b64decode(self.content)
        return self.content.encode("utf-8")


class VDirectory(VEntry):
    """виртуальные директории"""
    def __init__(self, name: str, parent: Optional["VDirectory"] = None):
        super().__init__(name, parent)
        self.children: Dict[str, VEntry] = {}

    def add_child(self, entry: VEntry) -> None:
        entry.parent = self
        self.children[entry.name] = entry

    def get_child(self, name: str) -> Optional[VEntry]:
        return self.children.get(name)


class VirtualFileSystem:
    def __init__(self, csv_path: str):
        self.source_path = csv_path
        self.source_bytes: Optional[bytes] = None
        self.sha256: Optional[str] = None

        self.root = VDirectory(name="")
        self.cwd = "/"

        # Load CSV and build tree
        self._load_csv(csv_path)

    # Утилиты
    def _compute_sha256(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _normalize_posix(self, p: str, allow_relative: bool = False) -> str:
        if not p:
            return self.cwd
        # Replace backslashes for safety
        p = p.replace("\\", "/")
        if p.startswith("/"):
            norm = posixpath.normpath(p)
        else:
            # relative to cwd
            norm = posixpath.normpath(posixpath.join(self.cwd, p))
        if norm == ".":
            return "/"
        if not norm.startswith("/"):
            norm = "/" + norm
        return norm

    # Загрузка CSV
    def _load_csv(self, csv_path: str) -> None:
        if not os.path.isfile(csv_path):
            raise VFSException(f"CSV file not found: {csv_path}")

        with open(csv_path, "rb") as bf:
            data = bf.read()
            self.source_bytes = data
            self.sha256 = self._compute_sha256(data)

        # Parse CSV text (assume UTF-8; if fails, raise)
        text = self.source_bytes.decode("utf-8", errors="replace").splitlines()
        reader = csv.reader(text)
        rows = list(reader)
        header_present = False
        header = []
        if rows:
            first = [c.strip().lower() for c in rows[0]]
            if "path" in first and "type" in first:
                header_present = True
                header = first
                data_rows = rows[1:]
            else:
                data_rows = rows
        else:
            data_rows = []

        # Построение дерева
        for row in data_rows:
            if not row or all((not cell.strip()) for cell in row):
                continue
            if header_present:
                d = {header[i]: row[i].strip() if i < len(row) else "" for i in range(len(header))}
                path = d.get("path", "")
                typ = d.get("type", "").lower()
                content = d.get("content", "")
            else:
                path = row[0].strip() if len(row) > 0 else ""
                typ = row[1].strip().lower() if len(row) > 1 else ""
                content = row[2].strip() if len(row) > 2 else ""

            if not path:
                continue
            path = path.replace("\\", "/")
            if not path.startswith("/"):
                path = "/" + path

            if typ == "dir":
                self._ensure_dir(path)
            elif typ == "file":
                parent_dir = posixpath.dirname(path)
                self._ensure_dir(parent_dir)
                name = posixpath.basename(path)
                parent_node = self._get_node(parent_dir)
                if not isinstance(parent_node, VDirectory):
                    raise VFSException(f"Parent {parent_dir} is not a directory for file {path}")
                f = VFile(name=name, content=content)
                parent_node.add_child(f)
            else:

                parent_dir = posixpath.dirname(path)
                self._ensure_dir(parent_dir)
                name = posixpath.basename(path)
                parent_node = self._get_node(parent_dir)
                f = VFile(name=name, content=content)
                parent_node.add_child(f)

    #Обработка дерева
    def _ensure_dir(self, abs_path: str) -> VDirectory:
        abs_path = self._normalize_posix(abs_path)
        if abs_path == "/":
            return self.root

        parts = [p for p in abs_path.split("/") if p]
        node: VDirectory = self.root
        for seg in parts:
            child = node.get_child(seg)
            if child is None:
                newdir = VDirectory(name=seg)
                node.add_child(newdir)
                node = newdir
            else:
                if isinstance(child, VDirectory):
                    node = child
                else:
                    raise VFSException(f"Path conflict: {child.path()} exists as file when directory expected")
        return node

    def _get_node(self, abs_path: str) -> Optional[VEntry]:
        abs_path = self._normalize_posix(abs_path)
        if abs_path == "/":
            return self.root
        parts = [p for p in abs_path.split("/") if p]
        node: VEntry = self.root
        for seg in parts:
            if not isinstance(node, VDirectory):
                return None
            node = node.get_child(seg)
            if node is None:
                return None
        return node

    def vfs_info(self) -> Dict[str, Optional[str]]:
        return {
            "filename": os.path.basename(self.source_path) if self.source_path else None,
            "sha256": self.sha256
        }

    def pwd(self) -> str:
        return self.cwd

    def ls(self, path: Optional[str] = None) -> List[str]:
        target = self.cwd if path is None else path
        node = self._get_node(target)
        if node is None:
            raise VFSException(f"No such file or directory: {target}")
        if isinstance(node, VDirectory):
            return sorted(node.children.keys())
        else:
            return [node.name]

    def cd(self, path: str) -> None:
        if not path:
            self.cwd = "/"
            return
        abs_path = self._normalize_posix(path)
        node = self._get_node(abs_path)
        if node is None:
            raise VFSException(f"No such directory: {path}")
        if not isinstance(node, VDirectory):
            raise VFSException(f"Not a directory: {path}")
        self.cwd = abs_path

    def read_file(self, path: str, decode_base64: bool = False) -> bytes:
        abs_path = self._normalize_posix(path)
        node = self._get_node(abs_path)
        if node is None:
            raise VFSException(f"No such file: {path}")
        if not isinstance(node, VFile):
            raise VFSException(f"Path is not a file: {path}")
        return node.read(decode_base64=decode_base64)

    def tree(self, path: Optional[str] = None, max_depth: Optional[int] = None) -> str:
        start_path = self.cwd if path is None else path
        node = self._get_node(start_path)
        if node is None:
            raise VFSException(f"No such path: {start_path}")
        lines: List[str] = []

        def _recurse(n: VEntry, prefix: str, depth: int):
            name = n.name if n.parent is not None else "/"
            lines.append(f"{prefix}{name}")
            if isinstance(n, VDirectory):
                if max_depth is not None and depth >= max_depth:
                    return
                for child_name in sorted(n.children.keys()):
                    child = n.children[child_name]
                    _recurse(child, prefix + "  ", depth + 1)

        _recurse(node, "", 0)
        return "\n".join(lines)

    def get_node(self, path: str) -> Optional[VEntry]:
        return self._get_node(path)
