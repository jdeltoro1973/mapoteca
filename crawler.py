import os
import time
import socket
import pandas as pd
from osgeo import ogr, gdal
from datetime import datetime

gdal.UseExceptions()

hostname = socket.gethostname()

VECTOR_EXT = [".shp", ".geojson", ".kml", ".kmz", ".tab", ".gpkg", ".gpx"]
RASTER_EXT = [".tif", ".tiff", ".ecw", ".img", ".jpg", ".jpeg", ".sid"]

EXCLUDE_FOLDERS = ["AppData", "Temp", "Cache", "Logs", "Microsoft"]


def limpiar_texto(valor):
    if isinstance(valor, str):
        try:
            return valor.encode("utf-8", "ignore").decode("utf-8")
        except Exception:
            return ""
    return valor


def safe_getsize(path):
    try:
        return round(os.path.getsize(path) / 1024 / 1024, 2)
    except Exception:
        return None


def fechas(path):
    try:
        return {
            "creacion": time.ctime(os.path.getctime(path)),
            "modificacion": time.ctime(os.path.getmtime(path)),
            "acceso": time.ctime(os.path.getatime(path)),
        }
    except Exception:
        return {}


def restaurar_fecha_acceso(path, acceso_original):
    try:
        atime = time.mktime(time.strptime(acceso_original))
        mtime = os.path.getmtime(path)
        os.utime(path, (atime, mtime))
        return "ok"
    except PermissionError:
        return "sin_permiso"
    except FileNotFoundError:
        return "no_existe"
    except Exception:
        return "error"


# ==========================
# VECTOR
# ==========================
def analizar_vector(path):
    try:
        ds = ogr.Open(path)
        if ds is None:
            return [{"error": "No se pudo abrir"}]

        resultados = []

        for i in range(ds.GetLayerCount()):

            layer = ds.GetLayer(i)
            extent = layer.GetExtent()
            srs = layer.GetSpatialRef()
            defn = layer.GetLayerDefn()

            atributos = []

        for j in range(defn.GetFieldCount()):
            campo = defn.GetFieldDefn(j)
            atributos.append(f"{campo.GetName()} ({campo.GetTypeName()})")

            resultados.append(
                {
                    "tipo": "vector",
                    "capa": layer.GetName(),
                    "features": layer.GetFeatureCount(),
                    "geometria": ogr.GeometryTypeToName(layer.GetGeomType()),
                    "epsg": srs.GetAuthorityCode(None) if srs else None,
                    "atributos": ", ".join(atributos),
                    "num_atributos": len(atributos),
                    "xmin": extent[0],
                    "xmax": extent[1],
                    "ymin": extent[2],
                    "ymax": extent[3],
                }
            )

        return resultados

    except Exception as e:
        return [{"error": str(e)}]


# ==========================
# RASTER ✅ FINAL
# ==========================
def analizar_raster(path):

    try:
        ds = gdal.Open(path)

        # fallback seguro
        if ds is None:
            return {
                "tipo": "raster",
                "geografico": "False",
                "bandas": None,
                "width": None,
                "height": None,
                "proyeccion": None,
                "xmin": None,
                "xmax": None,
                "ymin": None,
                "ymax": None,
            }

        geotransform = ds.GetGeoTransform()
        projection = ds.GetProjection()

        # ==========================
        # VALIDACIÓN GEO ✅
        # ==========================
        tiene_geotransform = geotransform and (
            geotransform[1] != 1 or geotransform[5] != -1
        )

        tiene_proyeccion = projection is not None and projection != ""

        tiene_worldfile = False
        base = os.path.splitext(path)[0]

        for wf in [".jgw", ".pgw", ".tfw", ".wld"]:
            if os.path.exists(base + wf):
                tiene_worldfile = True

        es_geo = False
        if tiene_geotransform and (tiene_proyeccion or tiene_worldfile):
            es_geo = True

        # ==========================
        # EXTENT ✅
        # ==========================
        xmin = None
        xmax = None
        ymin = None
        ymax = None

        if es_geo and geotransform:
            gt = geotransform
            xmin = gt[0]
            ymax = gt[3]
            xmax = xmin + (gt[1] * ds.RasterXSize)
            ymin = ymax + (gt[5] * ds.RasterYSize)

        return {
            "tipo": "raster",
            "geografico": str(es_geo),
            "bandas": ds.RasterCount,
            "width": ds.RasterXSize,
            "height": ds.RasterYSize,
            "proyeccion": projection if projection else None,
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax,
        }

    except Exception:
        return {
            "tipo": "raster",
            "geografico": "False",
            "bandas": None,
            "width": None,
            "height": None,
            "proyeccion": None,
            "xmin": None,
            "xmax": None,
            "ymin": None,
            "ymax": None,
        }


# ==========================
# CRAWLER
# ==========================
def ejecutar_crawler(rutas, progress_signal=None):

    resultados = []
    total_archivos = 0

    for ruta in rutas:
        for root, dirs, files in os.walk(ruta):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
            total_archivos += len(files)

    procesados = 0

    for ruta in rutas:
        print("Escaneando:", ruta)

        for root, dirs, files in os.walk(ruta):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]

            for file in files:

                path = os.path.join(root, file)

                ext = file.lower()
                extension = os.path.splitext(file)[1].lower().replace(".", "")

                try:
                    info_fechas = fechas(path)

                    dias_sin_uso = None

                    try:
                        fecha_acceso = datetime.fromtimestamp(
                            os.path.getatime(path)
                        )
                        hoy = datetime.now()
                        dias_sin_uso = (hoy - fecha_acceso).days
                    except Exception:
                        pass

                    acceso_original = info_fechas.get("acceso")

                    base = {
                        "archivo": limpiar_texto(file),
                        "ruta": limpiar_texto(path),
                        "extension": extension,
                        "equipo": hostname,
                        "tamano_mb": safe_getsize(path),
                        "dias_sin_uso": dias_sin_uso,
                        **info_fechas,
                    }

                    if any(ext.endswith(e) for e in VECTOR_EXT):

                        infos = analizar_vector(path)

                        for info in infos:

                            if acceso_original:
                                estado = restaurar_fecha_acceso(
                                    path, acceso_original
                                )
                            else:
                                estado = "sin_dato"

                            fila = {
                                **base,
                                **info,
                                "restauracion_acceso": estado
                            }
                            fila = {
                                k: limpiar_texto(v)
                                for k, v in fila.items()
                            }

                            resultados.append(fila)

                    elif any(ext.endswith(e) for e in RASTER_EXT):
                        info = analizar_raster(path)

                    else:
                        procesados += 1
                        continue

                    if acceso_original:
                        estado = restaurar_fecha_acceso(path, acceso_original)
                    else:
                        estado = "sin_dato"

                    fila = {**base, **info, "restauracion_acceso": estado}

                    fila = {k: limpiar_texto(v) for k, v in fila.items()}

                    resultados.append(fila)

                except Exception as e:
                    resultados.append(
                        {
                            "archivo": limpiar_texto(file),
                            "ruta": limpiar_texto(path),
                            "extension": extension,
                            "error": limpiar_texto(str(e)),
                            "restauracion_acceso": "error",
                            "geografico": "False",
                        }
                    )

                procesados += 1

                if progress_signal and total_archivos > 0:
                    porcentaje = int((procesados / total_archivos) * 100)
                    progress_signal.emit(porcentaje)

    df = pd.DataFrame(resultados)
    df = df.astype(str)

    return df


# ==========================
# RESUMEN ROBUSTO ✅
# ==========================


def generar_resumen(df):

    total = len(df)

    vector = len(df[df["tipo"] == "vector"]) if "tipo" in df.columns else 0
    raster = len(df[df["tipo"] == "raster"]) if "tipo" in df.columns else 0

    if "geografico" in df.columns:
        raster_geo = len(
            df[(df["tipo"] == "raster") & (df["geografico"] == "True")])
        raster_no_geo = len(
            df[(df["tipo"] == "raster") & (df["geografico"] == "False")]
        )
    else:
        raster_geo = 0
        raster_no_geo = 0

    fallos = (
        len(df[df["restauracion_acceso"] != "ok"])
        if "restauracion_acceso" in df.columns
        else 0
    )

    return f"""Total: {total}
Vectores: {vector}
Raster: {raster}
Geografico: {raster_geo}
No geografico: {raster_no_geo}
Fallos restauracion: {fallos}"""
