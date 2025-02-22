import os
import sys
import platform
import re
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QFont, QIcon, QKeySequence, QPixmap, QKeyEvent, QTextCharFormat, QColor, QTextCursor
from PyQt5.Qsci import QsciScintilla
from PyQt5.QtWidgets import (QAction, QApplication, QCheckBox, QFileDialog,
                                 QFrame, QHBoxLayout, QLabel, QLineEdit,
                                 QListWidget, QMessageBox, QMainWindow, QMenu,
                                 QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
                                 QTabWidget, QVBoxLayout, QWidget, QTextEdit)
from PyQt5.QtCore import QProcess

from editor import Editor
from file_manager import FileManager
from fuzzy_searcher import SearchItem, SearchWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.side_bar_clr = "#282c34"
        self.current_file: Optional[Path] = None
        self.current_side_bar: Optional[str] = None
        self.process = None
        self.terminal = None  # Terminal widget
        self.terminal_frame = None # Frame for Terminal Widget
        self.vsplit = None # Vertical Splitter
        self.current_command = "" # Store the current typed command

        self.init_ui()

    def init_ui(self):
        self.app_name = "Zrax"
        self.setWindowTitle(self.app_name)
        self.setWindowIcon(QIcon("./src/icons/logo.jpeg"))
        self.resize(1300, 900)

        try:
            with open("./src/css/style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Error: style.qss not found.")
            self.setStyleSheet("background-color: #333;")

        self.window_font = QFont("Fire Code")
        self.window_font.setPointSize(12)
        self.setFont(self.window_font)

        self.set_up_menu()
        self.set_up_body() # Crucial: Call set_up_body before any terminal-related actions
        self.set_up_status_bar()

        self.show()

    def set_up_status_bar(self):
        stat = QStatusBar(self)
        stat.setStyleSheet("color: #D3D3D3;")
        stat.showMessage("Ready", 3000)
        self.setStatusBar(stat)

    def set_up_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")

        new_file = file_menu.addAction("New")
        new_file.setShortcut("Ctrl+N")
        new_file.triggered.connect(self.new_file)

        open_file = file_menu.addAction("Open File")
        open_file.setShortcut("Ctrl+O")
        open_file.triggered.connect(self.open_file)

        open_folder = file_menu.addAction("Open Folder")
        open_folder.setShortcut("Ctrl+K")
        open_folder.triggered.connect(self.open_folder)

        file_menu.addSeparator()

        save_file = QAction("Save", self)
        file_menu.addAction(save_file) # corrected
        save_file.setShortcut("Ctrl+S")
        save_file.triggered.connect(self.save_file)

        save_as = QAction("Save As", self)
        file_menu.addAction(save_as) # corrected
        save_as.setShortcut("Ctrl+Shift+S")
        save_as.triggered.connect(self.save_as)

        edit_menu = menu_bar.addMenu("Edit")
        copy_action = edit_menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy)

        view_menu = menu_bar.addMenu("View")

        # Zoom In Action
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)

        # Zoom Out Action
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)

        # Terminal Action
        terminal_action = QAction("Terminal", self)
        terminal_action.triggered.connect(self.toggle_terminal)
        view_menu.addAction(terminal_action)

    def get_editor(self, path: Path = None, is_python_file=True) -> QsciScintilla:
        editor = Editor(self, path=path, is_python_file=is_python_file)
        return editor

    def is_binary(self, path):
        try:
            with open(path, 'rb') as f:
                return b'\0' in f.read(1024)
        except IOError:
            return True

    def set_new_tab(self, path: Path, is_new_file=False):
        if not is_new_file and self.is_binary(path):
            self.statusBar().showMessage("Cannot Open Binary File", 2000)
            return

        if path.is_dir():
            return

        editor = self.get_editor(path, path.suffix in {".py", ".pyw"})

        if is_new_file:
            self.tab_view.addTab(editor, "untitled")
            self.setWindowTitle(self.app_name)
            self.statusBar().showMessage("Opened untitled")
            self.tab_view.setCurrentIndex(self.tab_view.count() - 1)
            self.current_file = None
            return

        # check if file already open
        for i in range(self.tab_view.count()):
            if self.tab_view.tabText(i) == path.name or self.tab_view.tabText(i) == "*"+path.name:
                self.tab_view.setCurrentIndex(i)
                self.current_file = path
                return

        # create new tab
        editor = self.get_editor(path, path.suffix in {".py", ".pyw"})
        try:
            editor.setText(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            QMessageBox.warning(self, "Error", f"Could not decode file {path.name} with UTF-8.  Try opening in a different encoding.")
            return
        self.tab_view.addTab(editor, path.name)
        self.setWindowTitle(f"{path.name} - {self.app_name}")
        self.current_file = path
        self.tab_view.setCurrentIndex(self.tab_view.count() - 1)
        self.statusBar().showMessage(f"Opened {path.name}", 2000)

    def set_cursor_pointer(self, e):
        self.setCursor(Qt.PointingHandCursor)

    def set_cursor_arrow(self, e):
        self.setCursor(Qt.ArrowCursor)

    def get_side_bar_label(self, path, name):
        label = QLabel()
        label.setPixmap(QPixmap(path).scaled(QSize(30, 30)))
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        label.setFont(self.window_font)
        label.mousePressEvent = lambda e: self.show_hide_tab(e, name)
        label.enterEvent = self.set_cursor_pointer
        label.leaveEvent = self.set_cursor_arrow
        return label

    def get_frame(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.NoFrame)
        frame.setFrameShadow(QFrame.Plain)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setStyleSheet("""
            QFrame {
                background-color: #21252b;
                border-radius: 5px;
                border: none;
                padding: 5px;
                color: #D3D3D3;
            }
            QFrame:hover {
                color: white;
            }
        """)
        return frame

    def set_up_body(self):
        body_frame = QFrame()
        body_frame.setFrameShape(QFrame.NoFrame)
        body_frame.setFrameShadow(QFrame.Plain)
        body_frame.setLineWidth(0)
        body_frame.setMidLineWidth(0)
        body_frame.setContentsMargins(0, 0, 0, 0)
        body_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body_frame.setLayout(body)

        self.tab_view = QTabWidget()
        self.tab_view.setContentsMargins(0, 0, 0, 0)
        self.tab_view.setTabsClosable(True)
        self.tab_view.setMovable(True)
        self.tab_view.setDocumentMode(True)
        self.tab_view.tabCloseRequested.connect(self.close_tab)

        self.side_bar = QFrame()
        self.side_bar.setFrameShape(QFrame.StyledPanel)
        self.side_bar.setFrameShadow(QFrame.Plain)
        self.side_bar.setStyleSheet(f"""
            background-color: {self.side_bar_clr};
        """)

        side_bar_layout = QVBoxLayout()
        side_bar_layout.setContentsMargins(5, 10, 5, 0)
        side_bar_layout.setSpacing(0)
        side_bar_layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        folder_label = self.get_side_bar_label("./src/icons/folder-icon-blue.svg", "folder-icon")
        side_bar_layout.addWidget(folder_label)
        side_bar_layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        search_label = self.get_side_bar_label("./src/icons/search-icon", "search-icon")
        side_bar_layout.addWidget(search_label)
        side_bar_layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))  # Add spacing after search icon

        # Add Terminal Icon to SideBar (using term.svg)
        terminal_label = self.get_side_bar_label("./src/icons/term.svg", "terminal-icon")
        side_bar_layout.addWidget(terminal_label)
        side_bar_layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))  # Add spacing after terminal icon

        self.side_bar.setLayout(side_bar_layout)

        self.hsplit = QSplitter(Qt.Horizontal)
        self.vsplit = QSplitter(Qt.Vertical)  # Initialize vsplit here
        self.vsplit.setOrientation(Qt.Vertical)  # Make sure it's vertical

        self.file_manager_frame = self.get_frame()
        self.file_manager_frame.setMaximumWidth(400)
        self.file_manager_frame.setMinimumWidth(200)

        self.file_manager_layout = QVBoxLayout()
        self.file_manager_layout.setContentsMargins(0, 0, 0, 0)
        self.file_manager_layout.setSpacing(0)

        self.file_manager = FileManager(
            tab_view=self.tab_view,
            set_new_tab=self.set_new_tab,
            main_window=self
        )

        self.file_manager_layout.addWidget(self.file_manager)
        self.file_manager_frame.setLayout(self.file_manager_layout)

        self.search_frame = self.get_frame()
        self.search_frame.setMaximumWidth(400)
        self.search_frame.setMinimumWidth(200)

        search_layout = QVBoxLayout()
        search_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        search_layout.setContentsMargins(0, 10, 0, 0)
        search_layout.setSpacing(0)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search")
        search_input.setFont(self.window_font)
        search_input.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.search_checkbox = QCheckBox("Search in modules")
        self.search_checkbox.setFont(self.window_font)
        self.search_checkbox.setStyleSheet("""
            QListWidget {
                background-color: #21252b;
                border-radius: 5px;
                border: 1px solid #D3D3D3;
                padding: 5px;
                color: #D3D3D3;
            }
        """)
        self.search_list_view = QListWidget()
        self.search_list_view.itemClicked.connect(self.search_list_view_clicked)

        search_layout.addWidget(self.search_checkbox)
        search_layout.addWidget(search_input)
        search_layout.addSpacerItem(QSpacerItem(5, 5, QSizePolicy.Minimum, QSizePolicy.Minimum))
        search_layout.addWidget(self.search_list_view)
        self.search_frame.setLayout(search_layout)

        #--------------------- Terminal Widget ---------------------
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(False)  # Allow editing for user input
        terminal_font = QFont("Courier New", 10)  # Monospace font
        self.terminal.setFont(terminal_font)
        self.terminal.setStyleSheet("background-color: black; color: #00FF00;") #Set text color to green
        self.terminal.setFocusPolicy(Qt.StrongFocus)  # Ensure it can receive focus

        # Connect key press event to handle user input
        self.terminal.keyPressEvent = self.terminal_keyPressEvent

        self.terminal_frame = self.get_frame()  # Use the existing frame style
        terminal_layout = QVBoxLayout()
        terminal_layout.addWidget(self.terminal)
        self.terminal_frame.setLayout(terminal_layout)
        self.terminal_frame.hide() # Initially hidden

        self.hsplit.addWidget(self.file_manager_frame)
        self.hsplit.addWidget(self.vsplit) # Add the vertical splitter to hsplit
        self.vsplit.addWidget(self.tab_view) # Add tab view to the top
        self.vsplit.addWidget(self.terminal_frame) # Add terminal to the bottom

        # Set initial sizes for the vertical splitter (adjust as needed)
        self.vsplit.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)])

        body.addWidget(self.side_bar)
        body.addWidget(self.hsplit)
        body_frame.setLayout(body)

        self.setCentralWidget(body_frame)

    def search_finshed(self, items):
        self.search_list_view.clear()
        for i in items:
            self.search_list_view.addItem(i)

    def search_list_view_clicked(self, item: SearchItem):
        self.set_new_tab(Path(item.full_path))
        editor: Editor = self.tab_view.currentWidget()
        editor.setCursorPosition(item.lineno, item.end)
        editor.setFocus()

    def show_dialog(self, title, msg) -> int:
        dialog = QMessageBox(self)
        dialog.setFont(self.font())
        dialog.font().setPointSize(14)
        dialog.setWindowTitle(title)
        dialog.setWindowIcon(QIcon(":/icons/close-icon.svg"))
        dialog.setText(msg)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.No)
        dialog.setIcon(QMessageBox.Warning)
        return dialog.exec_()

    def close_tab(self, index):
        editor: Editor = self.tab_view.currentWidget()
        if editor.current_file_changed:
            dialog = self.show_dialog(
                "Close", f"Do you want to save the changes made to {self.current_file.name}?"
            )
            if dialog == QMessageBox.Yes:
                self.save_file()
        self.tab_view.removeTab(index)

    def show_hide_tab(self, e, type_):
        # Dictionary mapping sidebar icons to their respective frames
        tab_mapping = {
            "folder-icon": self.file_manager_frame,
            "search-icon": self.search_frame,
        }

        if type_ == "terminal-icon":
            self.toggle_terminal()  # Toggle terminal separately
            return

        selected_frame = tab_mapping.get(type_)

        if not selected_frame:
            return

        # Check if the frame is already in the splitter; if not, insert it
        if selected_frame not in self.hsplit.children():
            self.hsplit.insertWidget(0, selected_frame)

        # Toggle visibility without affecting other sidebars
        selected_frame.setVisible(not selected_frame.isVisible())

        # Update current active sidebar tracking
        self.current_side_bar = type_

    def new_file(self):
        self.set_new_tab(Path("untitled"), is_new_file=True)

    def save_file(self):
        if self.current_file is None and self.tab_view.count() > 0:
            self.save_as()
            return

        editor = self.tab_view.currentWidget()
        try:
            self.current_file.write_text(editor.text())
            self.statusBar().showMessage(f"Saved {self.current_file.name}", 2000)
            editor.current_file_changed = False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def save_as(self):
        editor = self.tab_view.currentWidget()
        if editor is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save As", os.getcwd())
        if not file_path:
            self.statusBar().showMessage("Cancelled", 2000)
            return

        path = Path(file_path)
        try:
            path.write_text(editor.text())
            self.tab_view.setTabText(self.tab_view.currentIndex(), path.name)
            self.statusBar().showMessage(f"Saved {path.name}", 2000)
            self.current_file = path
            editor.current_file_changed = False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def open_file(self):
        ops = QFileDialog.Options()
        ops |= QFileDialog.DontUseNativeDialog

        new_file, _ = QFileDialog.getOpenFileName(self,
            "Pick A File", "", "All Files (*);;Python Files (*.py)",
            options=ops)

        if not new_file:
            self.statusBar().showMessage("Cancelled", 2000)
            return

        f = Path(new_file)
        self.set_new_tab(f)

    def open_folder(self):
        ops = QFileDialog.Options()
        ops |= QFileDialog.DontUseNativeDialog

        new_folder = QFileDialog.getExistingDirectory(self, "Pick A Folder", "", options=ops)

        if new_folder:
            self.file_manager.model.setRootPath(new_folder)
            self.file_manager.setRootIndex(self.file_manager.model.index(new_folder))
            self.statusBar().showMessage(f"Opened {new_folder}", 2000)

    def copy(self):
        editor = self.tab_view.currentWidget()
        if editor is not None:
            editor.copy()

    def zoom_in(self):
        editor = self.tab_view.currentWidget()
        if editor:
            editor.zoomIn()

    def zoom_out(self):
        editor = self.tab_view.currentWidget()
        if editor:
            editor.zoomOut()

    def toggle_terminal(self):
        if self.terminal_frame is None:
            print("Error: Terminal frame is not initialized.")
            return

        if self.terminal_frame.isHidden():
            self.start_terminal()
            self.terminal_frame.show()
        else:
            self.stop_terminal()
            self.terminal_frame.hide()

    def start_terminal(self):
        if self.process is not None:
            return

        # Determine the shell based on the OS
        if os.name == 'nt':
            # Use PowerShell instead of CMD
            shell = 'powershell.exe'
            args = ['-NoExit', '-Command', f'echo ZenPy Terminal; cd {os.getcwd()}']  # Keep the window open and display a message
        else:
            # Linux, macOS, etc. (assuming bash is available)
            shell = 'bash'
            args = ['-i']  # Interactive mode

        print(f"Starting terminal with shell: {shell} and args: {args}")

        self.process = QProcess()
        self.process.setProgram(shell)
        self.process.setArguments(args)

        self.process.readyReadStandardOutput.connect(self.handle_output)
        self.process.readyReadStandardError.connect(self.handle_error)
        self.process.started.connect(lambda: print("Process started"))
        self.process.errorOccurred.connect(lambda error: print(f"Process error: {error}"))
        self.process.finished.connect(self.terminal_process_finished)

        self.process.setWorkingDirectory(os.getcwd())  # Set the working directory
        self.process.start()
        self.terminal.setFocus()
        QTimer.singleShot(0, self.terminal.setFocus)
        # self.process.start()
        # self.terminal.setFocus() # Set focus when terminal starts
        # QTimer.singleShot(0, self.terminal.setFocus) # Force focus

    def stop_terminal(self):
        if self.process is not None and self.process.state() == QProcess.Running:
            self.process.kill()  # Terminate the process
            self.process.waitForFinished(1000)  # Wait for it to finish
            self.process = None  # Reset the process
        print("Terminal stopped")

    def handle_output(self):
        data = self.process.readAllStandardOutput().data()
        encoding = sys.stdout.encoding or 'utf-8'  # Use system encoding or default to utf-8
        try:
            text = data.decode(encoding, errors='replace')  # Decode with error replacement

            # Remove HTML-like font tags and ANSI escape codes
            clean_text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
            clean_text = re.sub(r'\x1b\[[0-9;]*m', '', clean_text)  # Remove ANSI escape codes

            self.terminal.insertPlainText(clean_text)
            self.terminal.ensureCursorVisible()
        except Exception as e:
            print(f"Error decoding output: {e}")

    def handle_error(self):
        data = self.process.readAllStandardError().data()
        encoding = sys.stderr.encoding or 'utf-8'  # Use system encoding or default to utf-8
        try:
            text = data.decode(encoding, errors='replace')  # Decode with error replacement

            # Remove HTML-like font tags and ANSI escape codes
            clean_text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
            clean_text = re.sub(r'\x1b[[0-9;]*m', '', clean_text)  # Remove ANSI escape codes

            self.terminal.insertPlainText(clean_text)  # no red for now
            self.terminal.ensureCursorVisible()
        except Exception as e:
            print(f"Error decoding error output: {e}")

    def terminal_process_finished(self, exit_code, exit_status):
        print(f"Terminal process finished with code {exit_code} and status {exit_status}")
        self.process = None

    def terminal_keyPressEvent(self, event: QKeyEvent):
        if self.process and self.process.state() == QProcess.Running:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.process.write(b'\n')
            elif event.key() == Qt.Key_Backspace:
                # Only send backspace character to the process
                self.process.write(b'\x08')
            elif event.key() == Qt.Key_Delete:
                self.process.write(b'\x7f')
            elif event.key() == Qt.Key_Tab:
                self.process.write(b'\t')
            elif event.key() == Qt.Key_Up:  # Up arrow key
                self.process.write(b'\x1b[A')  # ANSI escape code for up arrow
            elif event.key() == Qt.Key_Down:  # Down arrow key
                self.process.write(b'\x1b[B')  # ANSI escape code for down arrow
            elif event.key() == Qt.Key_Left:  # Left arrow key
                self.process.write(b'\x1b[D')  # ANSI escape code for left arrow
            elif event.key() == Qt.Key_Right:  # Right arrow key
                self.process.write(b'\x1b[C')  # ANSI escape code for right arrow
            else:
                text = event.text()
                self.process.write(text.encode())

            event.accept()
        else:
            QTextEdit.keyPressEvent(self.terminal, event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())
