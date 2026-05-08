import os
import pandas as pd
from datetime import datetime
from qgis.PyQt.QtGui import QIcon


from qgis.PyQt.QtWidgets import (
    QAction,
    QMessageBox,
    QFileDialog,
    QProgressDialog,
    QPushButton
)

from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QUrl


from qgis.core import Qgis

from .worker import Worker


class Mapoteca:

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.worker = None
        self.progress = None
        self.cancelado = False

    # ==========================
    # UI
    # ==========================
    def initGui(self):

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")

        self.action = QAction(
            QIcon(icon_path),
            "Mapoteca - GeoCrawl",
            self.iface.mainWindow()
        )

        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("Mapoteca", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("Mapoteca", self.action)
        self.iface.removeToolBarIcon(self.action)

    # ==========================
    # EJECUCIÓN PRINCIPAL
    # ==========================
    def run(self):

        self.cancelado = False

        carpeta = QFileDialog.getExistingDirectory(
            self.iface.mainWindow(),
            "Selecciona carpeta para inventariar Mapoteca"
        )

        if not carpeta:
            return

        self.progress = QProgressDialog(
            "Ejecutando Mapoteca...",
            "Cancelar",
            0,
            0,
            self.iface.mainWindow()
        )

        self.progress.setWindowTitle("Mapoteca")
        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)

        self.worker = Worker([carpeta])

        self.worker.finished.connect(self.proceso_terminado)
        self.worker.error.connect(self.proceso_error)
        self.progress.canceled.connect(self.solicitar_cancelacion)

        self.worker.start()

# ==========================
# CUANDO TERMINA
# ==========================
    def proceso_terminado(self, df):

        if self.progress:
            try:
                self.progress.canceled.disconnect()
            except Exception:
                pass
            self.progress.close()

        if self.cancelado:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Mapoteca",
                "Proceso cancelado"
            )
            return

        if df is None or len(df) == 0:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Mapoteca",
                "No se encontraron datos."
            )
            return

        # ==========================
        # NOMBRE
        # ==========================
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_sugerido = "mapoteca_" + fecha + ".csv"

        # ==========================
        # GUARDAR
        # ==========================
        output_path, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Guardar Mapoteca",
            nombre_sugerido,
            "CSV (*.csv)"
        )

        if not output_path:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Mapoteca",
                "Guardado cancelado"
            )
            return

        if not output_path.lower().endswith(".csv"):
            output_path += ".csv"

        try:
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error al guardar",
                str(e)
            )
            return

        # ==========================
        # RESUMEN ✅ (AHORA BIEN UBICADO)
        # ==========================

        total = len(df)
        vector = len(df[df["tipo"] == "vector"])
        raster = len(df[df["tipo"] == "raster"])

        if "geografico" in df.columns:
            raster_geo = len(
                df[(df["tipo"] == "raster") & (df["geografico"] == "True")]
            )
            raster_no_geo = len(
                df[(df["tipo"] == "raster") & (df["geografico"] == "False")]
            )
        else:
            raster_geo = 0
            raster_no_geo = 0

        antiguos = 0
        if "dias_sin_uso" in df.columns:
            antiguos = len(
                df[pd.to_numeric(df["dias_sin_uso"], errors="coerce") > 1095]
            )

        shp = len(df[df["extension"] == "shp"]) \
            if "extension" in df.columns else 0

        gpkg = len(df[df["extension"] == "gpkg"]) \
            if "extension" in df.columns else 0

        formato_dominante = "SHP" if shp >= gpkg else "GPKG"

        mensaje = f"""📊 MAPOTECA COMPLETADA

        🔍 Archivos analizados: {total}

        🗂️ Vectorial: {vector}
        🖼️ Raster: {raster}

        🌍 Georreferenciados: {raster_geo}
        ⚠️ Sin georreferencia: {raster_no_geo}

        🧊 Sin uso (>3 años): {antiguos}

        📁 Formato dominante: {formato_dominante}

        📄 Archivo:
        {output_path}
        """

        QMessageBox.information(
            self.iface.mainWindow(),
            "Mapoteca",
            mensaje
        )

        # ==========================
        # BARRA AZUL ✅ (DENTRO DEL MÉTODO)
        # ==========================
        msg = self.iface.messageBar().createMessage(
            "Mapoteca",
            "Mapoteca generada correctamente"
        )

        btn_csv = QPushButton("Abrir CSV")
        btn_csv.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
        )

        btn_folder = QPushButton("Abrir carpeta")
        btn_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(output_path))
            )
        )

        msg.layout().addWidget(btn_csv)
        msg.layout().addWidget(btn_folder)

        self.iface.messageBar().pushWidget(
            msg,
            level=Qgis.Success,
            duration=60
        )

    # ==========================
    # ERROR
    # ==========================
    def proceso_error(self, mensaje):

        if self.progress:
            try:
                self.progress.close()
            except Exception:
                pass

        QMessageBox.critical(
            self.iface.mainWindow(),
            "Error Mapoteca",
            str(mensaje)
        )

    # ==========================
    # CANCELAR
    # ==========================
    def solicitar_cancelacion(self):
        self.cancelado = True

        if self.worker:
            try:
                self.worker.terminate()
                self.worker.wait()
            except Exception:
                pass

        QMessageBox.information(
            self.iface.mainWindow(),
            "Mapoteca",
            "Proceso cancelado"
        )
