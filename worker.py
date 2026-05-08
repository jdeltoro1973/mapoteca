from qgis.PyQt.QtCore import QThread, pyqtSignal
from .crawler import ejecutar_crawler


class Worker(QThread):

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, rutas):
        super().__init__()
        self.rutas = rutas

    def run(self):
        try:
            df = ejecutar_crawler(self.rutas)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))
