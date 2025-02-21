from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QListWidgetItem
import os
from pathlib import Path
import re
from typing import List, Tuple

class SearchItem(QListWidgetItem):
    def __init__(self, name: str, full_path: str, lineno: int, end: int, line: str):
        self.name = name
        self.full_path = full_path
        self.lineno = lineno
        self.end = end
        self.line = line
        self.formatted = f'{self.name}:{self.lineno}:{self.end} - {self.line} ...'
        super().__init__(self.formatted)

    def __str__(self):
        return self.formatted

    def __repr__(self):
        return self.formatted

class SearchWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self):
        super(SearchWorker, self).__init__(None)
        self.items: List[SearchItem] = []
        self.search_path: str = None
        self.search_text: str = None
        self.search_project: bool = None

    def is_binary(self, path: str) -> bool:
        '''Check if file is binary'''
        try:
            with open(path, 'rb') as f:
                return b'\0' in f.read(1024)
        except IOError: # More specific exception
            return True  # Treat files that can't be opened as binary

    def walkdir(self, path: str, exclude_dirs: List[str], exclude_files: List[str]):
        for root, dirs, files, in os.walk(path, topdown=True):
            # filtering
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            files[:] = [f for f in files if Path(f).suffix not in exclude_files]
            yield root, dirs, files

    def search(self):
        self.items = []
        exclude_dirs = {".git", ".svn", ".hg", ".bzr", ".idea", "__pycache__", "venv"}
        if self.search_project:
            exclude_dirs.remove("venv")
        exclude_files = {".svg", ".png", ".exe", ".pyc", ".qm"}

        for root, _, files in self.walkdir(self.search_path, exclude_dirs, exclude_files):
            if len(self.items) > 5_000:
                break

            for file_ in files:
                full_path = os.path.join(root, file_)
                if self.is_binary(full_path):
                    continue # use continue instead of break

                try:
                    with open(full_path, 'r', encoding='utf8') as f:
                        reg = re.compile(self.search_text, re.IGNORECASE)
                        for i, line in enumerate(f):
                            if m := reg.search(line):
                                fd = SearchItem(
                                    file_,
                                    full_path,
                                    i,
                                    m.end(),
                                    line[m.start():].strip()[:50]
                                )
                                self.items.append(fd)
                except (re.error, UnicodeDecodeError) as e: # Combined exceptions
                    print(f"SearchWorker error: {e}")
                    continue
                except Exception as e:
                    print(f"SearchWorker error: {e}")
                    continue

        self.finished.emit(self.items)

    def run(self):
        self.search()

    def update(self, pattern: str, path: str, search_project: bool):
        self.search_text = pattern
        self.search_path = path
        self.search_project = search_project
        self.start()
