# Виртуальная файловая система для эмулятора
# Всё хранится в памяти, загрузка из CSV

from __future__ import annotations
import csv
import os
import hashlib
import base64
import posixpath
from typing import Optional, Dict, List


class VFSException(Exception):
    pass


class VEntry:
    # Общая база для файла и каталога
    def __init__(self, name: str, parent: Optional["VDirectory"] = None, mode: Optional[int] = None):
        self.name = name
        self.parent = parent
        self.mode = mode or 0o755

    def path(self) -> str:
        # Возвращает абсолютный путь элемента
        parts = []
        node = self
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts))


class VFile(VEntry):
    # Представление файла
    def __init__(self, name: str, content: str = "", parent: Optional["VDirectory"] = None, mode: Optional[int] = None):
        super().__init__(name, parent, mode or 0o644)
        self.content = content

    def read(self, decode_base64: bool = False) -> bytes:
        # Возвращает содержимое файла (опционально декодируя base64)
        if decode_base64:
            return base64.b64decode(self.content)
        return self.content.encode("utf-8")


class VDirectory(VEntry):
    # Каталог с дочерними элементами
    def __init__(self, name: str, parent: Optional["VDirectory"] = None, mode: Optional[int] = None):
        super().__init__(name, parent, mode or 0o755)
        self.children: Dict[str, VEntry] = {}

    def add_child(self, entry: VEntry):
        entry.parent = self
        self.children[entry.name] = entry

    def get_child(self, name: str) -> Optional[VEntry]:
        return self.children.get(name)


def format_mode(mode_int: int) -> str:
    # Преобразует числовые права в rwx-строку
    s = ""
    for shift in (6, 3, 0):
        v = (mode_int >> shift) & 0o7
        s += "r" if v & 4 else "-"
        s += "w" if v & 2 else "-"
        s += "x" if v & 1 else "-"
    return s


class VirtualFileSystem:
    def __init__(self, csv_path: str):
        self.source_path = csv_path
        self.root = VDirectory("")
        self.cwd = "/"
        self.sha256 = None
        self._load_csv(csv_path)

    #вспомогательные
    def _normalize_posix(self, p: str) -> str:
        # Нормализация пути в POSIX-формате
        p = p.replace("\\", "/")
        if not p.startswith("/"):
            p = posixpath.join(self.cwd, p)
        norm = posixpath.normpath(p)
        return "/" if norm == "." else norm

    def _compute_sha256(self, data: bytes) -> str:
        # Хэш содержимого CSV
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    #загрузка CSV
    def _load_csv(self, csv_path: str):
        if not os.path.isfile(csv_path):
            raise VFSException(f"CSV not found: {csv_path}")
        with open(csv_path, "rb") as bf:
            data = bf.read()
            self.sha256 = self._compute_sha256(data)
        lines = data.decode("utf-8").splitlines()
        reader = csv.reader(lines)
        rows = list(reader)
        if rows and "path" in rows[0]:
            rows = rows[1:]  # пропускаем заголовок
        for row in rows:
            if len(row) < 2:
                continue
            path, typ = row[0].strip(), row[1].strip().lower()
            content = row[2].strip() if len(row) > 2 else ""
            if not path.startswith("/"):
                path = "/" + path
            if typ == "dir":
                self._ensure_dir(path)
            elif typ == "file":
                parent_dir = posixpath.dirname(path)
                name = posixpath.basename(path)
                parent = self._ensure_dir(parent_dir)
                parent.add_child(VFile(name, content))

    def _ensure_dir(self, abs_path: str) -> VDirectory:
        # Создаёт недостающие каталоги по пути
        abs_path = self._normalize_posix(abs_path)
        if abs_path == "/":
            return self.root
        parts = [p for p in abs_path.split("/") if p]
        node = self.root
        for seg in parts:
            child = node.get_child(seg)
            if child is None:
                newdir = VDirectory(seg)
                node.add_child(newdir)
                node = newdir
            elif isinstance(child, VDirectory):
                node = child
            else:
                raise VFSException(f"Path conflict at {seg}")
        return node

    def _get_node(self, abs_path: str) -> Optional[VEntry]:
        # Возвращает объект по абсолютному пути
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

    #  команды
    def vfs_info(self):
        return {"filename": os.path.basename(self.source_path), "sha256": self.sha256}

    def ls(self, path: Optional[str] = None) -> List[str]:
        target = self.cwd if path is None else path
        node = self._get_node(target)
        if node is None:
            raise VFSException(f"No such file or directory: {target}")
        if isinstance(node, VDirectory):
            return sorted(node.children.keys())
        return [node.name]

    def cd(self, path: str):
        abs_path = self._normalize_posix(path or "/")
        node = self._get_node(abs_path)
        if node is None or not isinstance(node, VDirectory):
            raise VFSException(f"No such directory: {path}")
        self.cwd = abs_path

    def tree(self, path: Optional[str] = None) -> str:
        # Рекурсивно строит дерево каталогов
        start = self._get_node(path or self.cwd)
        if start is None:
            raise VFSException("No such path")
        lines = []

        def _recurse(n: VEntry, prefix=""):
            name = n.name if n.parent else "/"
            lines.append(prefix + name)
            if isinstance(n, VDirectory):
                for k in sorted(n.children.keys()):
                    _recurse(n.children[k], prefix + "  ")

        _recurse(start)
        return "\n".join(lines)

    def read_file(self, path: str) -> bytes:
        node = self._get_node(path)
        if not node or not isinstance(node, VFile):
            raise VFSException(f"Not a file: {path}")
        return node.read()

    # chmod и rm
    def _parse_mode(self, mode_str: str) -> int:
        # Конвертирует строку вида '644' или 'rwxr-xr-x' в число
        s = mode_str.strip()
        if s.isdigit() or s.startswith("0o"):
            return int(s, 8)
        if len(s) == 9 and all(c in "rwx-" for c in s):
            vals = []
            for i in range(0, 9, 3):
                trip = s[i:i+3]
                v = (4 if trip[0]=="r" else 0) | (2 if trip[1]=="w" else 0) | (1 if trip[2]=="x" else 0)
                vals.append(v)
            return (vals[0]<<6)|(vals[1]<<3)|vals[2]
        raise VFSException("Invalid mode format")

    def chmod(self, path: str, mode_str: str):
        node = self._get_node(path)
        if node is None:
            raise VFSException(f"No such file or directory: {path}")
        node.mode = self._parse_mode(mode_str)

    def rm(self, path: str, recursive=False):
        abs_path = self._normalize_posix(path)
        if abs_path == "/":
            raise VFSException("Cannot remove root")
        node = self._get_node(abs_path)
        if node is None:
            raise VFSException(f"No such file or directory: {path}")
        parent_path = posixpath.dirname(abs_path)
        parent = self._get_node(parent_path)
        if not isinstance(parent, VDirectory):
            raise VFSException("Parent not directory")
        if isinstance(node, VFile):
            del parent.children[node.name]
        elif isinstance(node, VDirectory):
            if node.children and not recursive:
                raise VFSException(f"Directory not empty: {path}")
            if recursive:
                self._remove_recursive(node)
            del parent.children[node.name]

    def _remove_recursive(self, node: VDirectory):
        # Удаляет каталог со всем содержимым
        for child in list(node.children.values()):
            if isinstance(child, VDirectory):
                self._remove_recursive(child)
        node.children.clear()
