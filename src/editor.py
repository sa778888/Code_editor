from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import *
from jedi import Script
from jedi.api import Completion
import keyword
import pkgutil
from pathlib import Path
from lexer import PyCustomLexer
from autcompleter import AutoCompleter
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from main import MainWindow

import resources

class Editor(QsciScintilla):
    def __init__(self, main_window: "MainWindow", parent=None, path: Optional[Path] = None, is_python_file=True):
        super(Editor, self).__init__(parent)
        self.main_window: "MainWindow" = main_window
        self._current_file_changed = False
        self.first_launch = True
        self.path: Optional[Path] = path
        self.full_path: str = str(self.path.absolute()) if path else "" # Handle case where path is None
        self.is_python_file = is_python_file

        self.cursorPositionChanged.connect(self._cusorPositionChanged)
        self.textChanged.connect(self._textChanged)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.setUtf8(True)

        self.window_font = QFont("Fire Code")
        self.window_font.setPointSize(12)
        self.setFont(self.window_font)

        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        self.setIndentationGuides(True)
        self.setTabWidth(4)
        self.setIndentationsUseTabs(False)
        self.setAutoIndent(True)

        self.setAutoCompletionSource(QsciScintilla.AcsAll)
        self.setAutoCompletionThreshold(1)
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

        self.setCaretForegroundColor(QColor("#dedcdc"))
        self.setCaretLineVisible(True)
        self.setCaretWidth(2)
        self.setCaretLineBackgroundColor(QColor("#2c313c"))

        self.setEolMode(QsciScintilla.EolWindows)
        self.setEolVisibility(False)

        if self.is_python_file:
            self.pylexer = PyCustomLexer(self)
            self.pylexer.setDefaultFont(self.window_font)
            self.__api = QsciAPIs(self.pylexer)
            self.auto_completer = AutoCompleter(self.full_path, self.__api)
            self.auto_completer.finished.connect(self.loaded_autocomplete)
            self.setLexer(self.pylexer)
        else:
            self.setPaper(QColor("#1f1f1f"))
            self.setColor(QColor("#abb2bf"))

        self.setMarginType(0, QsciScintilla.NumberMargin)
        self.setMarginWidth(0, "000")
        self.setMarginsForegroundColor(QColor("#ff888888"))
        self.setMarginsBackgroundColor(QColor("#282c34"))
        self.setMarginsFont(self.window_font)

    @property
    def current_file_changed(self):
        return self._current_file_changed

    @current_file_changed.setter
    def current_file_changed(self, value: bool):
        curr_index = self.main_window.tab_view.currentIndex()
        if value:
            self.main_window.tab_view.setTabText(curr_index, "*"+self.path.name if self.path else "*untitled") # Handle case where self.path is None
            self.main_window.setWindowTitle(f"*{self.path.name} - {self.main_window.app_name}" if self.path else f"*untitled - {self.main_window.app_name}")
        else:
            tab_text = self.main_window.tab_view.tabText(curr_index)
            if tab_text.startswith("*"):
                self.main_window.tab_view.setTabText(
                    curr_index,
                    tab_text[1:]
                )
                self.main_window.setWindowTitle(self.main_window.windowTitle()[1:])
        self._current_file_changed = value

    def toggle_comment(self, text: str) -> str:
        lines = text.split('\n')
        toggled_lines = []
        for line in lines:
            if line.startswith('#'):
                toggled_lines.append(line[1:].lstrip())
            else:
                toggled_lines.append("# " + line)
        return '\n'.join(toggled_lines)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.modifiers() == Qt.ControlModifier and e.key() == Qt.Key_Space:
            if self.is_python_file:
                pos = self.getCursorPosition()
                self.auto_completer.get_completions(pos[0]+1, pos[1], self.text())
                self.autoCompleteFromAPIs()
            return

        if e.modifiers() == Qt.ControlModifier and e.key() == Qt.Key_X: # CUT SHORTCUT
            if not self.hasSelectedText():
                line, index = self.getCursorPosition()
                self.setSelection(line, 0, line, self.lineLength(line))
                self.cut()
            return

        if e.modifiers() == Qt.ControlModifier and e.text() == "/": # COMMENT SHORTCUT
            if self.hasSelectedText():
                start, srow, end, erow = self.getSelection()
                self.setSelection(start, 0, end, self.lineLength(end)) # corrected
                self.replaceSelectedText(self.toggle_comment(self.selectedText()))
                self.setSelection(start, srow, end, erow)
            else:
                line, _ = self.getCursorPosition()
                self.setSelection(line, 0, line, self.lineLength(line)) # corrected
                self.replaceSelectedText(self.toggle_comment(self.selectedText()))
            self.setSelection(-1, -1, -1, -1) # reset selection
            return

        if e.modifiers() == Qt.ControlModifier and e.key() == Qt.Key_B: # Shortcut: Ctrl + B
            self.go_to_definition()
            return

        super().keyPressEvent(e)

    def _cusorPositionChanged(self, line: int, index: int) -> None:
        if self.is_python_file:
            self.auto_completer.get_completions(line+1, index, self.text())

    def loaded_autocomplete(self):
        pass

    def _textChanged(self):
        if not self.current_file_changed and not self.first_launch:
            self.current_file_changed = True
        if self.first_launch:
            self.first_launch = False

    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        if self.is_python_file:
            go_to_def_action = menu.addAction("Go to Definition")
            go_to_def_action.triggered.connect(self.go_to_definition)
        menu.exec_(self.mapToGlobal(pos))

    def go_to_definition(self):
        if not self.is_python_file:
            return

        line, index = self.getCursorPosition()
        script = Script(self.text(), path=str(self.path))
        try:
            definitions = script.goto(line + 1, index)
            if definitions:
                definition = definitions[0] # added check
                definition_path = Path(definition.module_path)
                if definition_path.exists():
                    self.main_window.set_new_tab(definition_path)
                    editor: Editor = self.main_window.tab_view.currentWidget()
                    editor.setCursorPosition(definition.line - 1, definition.column)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not find definition: {str(e)}")
