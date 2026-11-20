from pathlib import Path

from motor_extractos.nucleo.config import SERVIDOR

RAIZ = Path(__file__).resolve().parent.parent

RUTA_ACTUALIZACIONES = SERVIDOR + r"\Extractor PDF"

URL_MANUAL = "https://drive.google.com/file/d/1ZB5-3KT_-2bJmo7G-uYIlwJhnN-BihQP/view?usp=sharing"


def ruta_asset(*partes):
    return str(RAIZ.joinpath("assets", *partes))