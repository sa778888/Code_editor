from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.Qsci import QsciAPIs
from jedi import Script
from jedi.api import Completion
from typing import List

class AutoCompleter(QThread):
    finished = pyqtSignal() # Add the finished signal
    def __init__(self, file_path: str, api: QsciAPIs):
        super(AutoCompleter, self).__init__() # Corrected init
        self.file_path = file_path
        self.script: Script = None
        self.api: QsciAPIs = api
        self.completions: List[Completion] = None
        self.line = 0
        self.index = 0
        self.text = ""

    def run(self):
        try:
            self.script = Script(self.text, path=self.file_path)
            self.completions = self.script.complete(self.line, self.index)
            self.load_autocomplete(self.completions)
        except Exception as err:
            print(f"AutoCompleter error: {err}") # More informative error
            self.finished.emit()

    def load_autocomplete(self, completions: List[Completion]):
        self.api.clear()
        [self.api.add(i.name) for i in completions]
        self.api.prepare()

    def get_completions(self, line: int, index: int, text: str):
        self.line = line
        self.index = index
        self.text = text
        self.start()
