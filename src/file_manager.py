from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import *
from pathlib import Path
import shutil
import os
import sys
import subprocess
from editor import Editor
from typing import Callable, Optional

class FileManager(QTreeView):
    def __init__(self, tab_view: QTabWidget, set_new_tab: Callable[[Path], None] = None, main_window=None):
        super(FileManager, self).__init__(None)
        self.set_new_tab = set_new_tab
        self.tab_view = tab_view
        self.main_window = main_window

        self.manager_font = QFont("FiraCode", 13)
        self.model: QFileSystemModel = QFileSystemModel()
        self.model.setRootPath(os.getcwd())

        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files | QDir.Drives)
        self.model.setReadOnly(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFont(self.manager_font)
        self.setModel(self.model)
        self.setRootIndex(self.model.index(os.getcwd()))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.clicked.connect(self.tree_view_clicked)
        self.setIndentation(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setHeaderHidden(True)
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)

        self.previous_rename_name: Optional[str] = None
        self.is_renaming = False
        self.current_edit_index: Optional[QModelIndex] = None
        self.itemDelegate().closeEditor.connect(self._on_closeEditor)

    def _on_closeEditor(self, editor: QLineEdit):
        if self.is_renaming:
            self.rename_file_with_index()

    def tree_view_clicked(self, index: QModelIndex):
        path = self.model.filePath(index)
        p = Path(path)
        if p.is_file():
            self.set_new_tab(p)

    def show_context_menu(self, pos: QPoint):
        ix = self.indexAt(pos)
        menu = QMenu()
        menu.addAction("New File")
        menu.addAction("New Folder")
        menu.addAction("Open In File Manager")
        if ix.column() == 0:
            menu.addAction("Rename")
            menu.addAction("Delete")

        action = menu.exec_(self.viewport().mapToGlobal(pos))

        if not action:
            return

        if action.text() == "Rename":
            self.action_rename(ix)
        elif action.text() == "Delete":
            self.action_delete(ix)
        elif action.text() == "New Folder":
            self.action_new_folder()
        elif action.text() == "New File":
            self.action_new_file(ix)
        elif action.text() == "Open In File Manager":
            self.action_open_in_file_manager(ix)

    def show_dialog(self, title: str, msg: str) -> int:
        dialog = QMessageBox(self)
        dialog.setFont(self.manager_font)
        dialog.font().setPointSize(14)
        dialog.setWindowTitle(title)
        dialog.setWindowIcon(QIcon(":/icons/close-icon.svg"))
        dialog.setText(msg)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.No)
        dialog.setIcon(QMessageBox.Warning)
        return dialog.exec_()

    def rename_file_with_index(self):
        new_name = self.model.fileName(self.current_edit_index)
        if self.previous_rename_name == new_name:
            return

        for editor in self.tab_view.findChildren(Editor):
            if hasattr(editor, 'path') and editor.path and editor.path.name == self.previous_rename_name:
                try:
                    new_path = editor.path.parent / new_name
                    os.rename(editor.path, new_path)  # Rename the file on disk

                    editor.path = new_path
                    self.tab_view.setTabText(self.tab_view.indexOf(editor), new_name)
                    self.tab_view.repaint()
                    editor.full_path = editor.path.absolute()
                    if self.main_window:
                        self.main_window.current_file = editor.path
                    break
                except OSError as e:
                    QMessageBox.critical(self, "Error", f"Could not rename file: {e}")
                    return

    def action_rename(self, ix: QModelIndex):
        self.edit(ix)
        self.previous_rename_name = self.model.fileName(ix)
        self.is_renaming = True
        self.current_edit_index = ix

    def delete_file(self, path: Path):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not delete {path.name}: {e}")

    def action_delete(self, ix: QModelIndex):
        file_name = self.model.fileName(ix)
        dialog = self.show_dialog(
            "Delete", f"Are you sure you want to delete {file_name}"
        )

        if dialog == QMessageBox.Yes:
            if self.selectionModel().selectedRows():
                for i in self.selectionModel().selectedRows():
                    path = Path(self.model.filePath(i))
                    self.delete_file(path)

                for editor in self.tab_view.findChildren(Editor):
                    if hasattr(editor, 'path') and editor.path and editor.path.name == path.name:
                        self.tab_view.removeTab(self.tab_view.indexOf(editor))

    def action_new_file(self, ix: QModelIndex):
        root_path = self.model.rootPath()
        if ix.column() != -1 and self.model.isDir(ix):
            self.expand(ix)
            root_path = self.model.filePath(ix)

        f = Path(root_path) / "file"
        count = 1
        while f.exists():
            f = Path(f.parent / f"file{count}")
            count += 1

        try:
            f.touch()
            idx = self.model.index(str(f.absolute()))
            self.edit(idx)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create file: {e}")

    def action_new_folder(self):
        f = Path(self.model.rootPath()) / "New Folder"
        count = 1
        while f.exists():
            f = Path(f.parent / f"New Folder{count}")
            count += 1
        try:
            idx = self.model.mkdir(self.rootIndex(), f.name)
            self.edit(idx)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create directory: {e}")

    def action_open_in_file_manager(self, ix: QModelIndex):
        path = os.path.abspath(self.model.filePath(ix))
        is_dir = self.model.isDir(ix)

        try:
            if os.name == "nt":
                if is_dir:
                    subprocess.Popen(f'explorer "{path}"')
                else:
                    subprocess.Popen(f'explorer /select,"{path}"')
            elif os.name == "posix":
                if sys.platform == "darwin":
                    if is_dir:
                        subprocess.Popen(["open", path])
                    else:
                        subprocess.Popen(["open", "-R", path])
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(path)])
            else:
                raise OSError(f"Unsupported platform {os.name}")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not open in file manager: {e}")

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent) -> None:
        root_path = Path(self.model.rootPath())
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                path = Path(url.toLocalFile())
                try:
                    if path.is_dir():
                        shutil.copytree(path, root_path / path.name)
                    else:
                        if root_path.samefile(self.model.rootPath()):
                            idx: QModelIndex = self.indexAt(e.pos())
                            if idx.column() == -1:
                                shutil.move(path, root_path / path.name)
                            else:
                                folder_path = Path(self.model.filePath(idx))
                                shutil.move(path, folder_path / path.name)
                        else:
                            shutil.copy(path, root_path / path.name)
                    e.accept()
                except OSError as e:
                    QMessageBox.critical(self, "Error", f"Could not complete drag and drop operation: {e}")
            return super().dropEvent(e)
