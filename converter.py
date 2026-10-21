import os
import re

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# te vervangen regels in de [MODEL] sectie
MODEL_LINES = {
    "Calculation type": "0 : Calculation type = Darcy",
    "Model": "1 : Model = NEN - Bjerrum",
    "Strain type": "0 : Strain type = Linear",
}


def normalize_code(code):
    """Verwijder dubbele spaties"""
    return re.sub(r"\s+", " ", code.strip())


def read_conversies(filename=os.path.join(DATA_DIR, "conversie_lijst.csv")):
    """Lees de conversielijst (grondsoort code -> zand, klei of veen)"""
    lines = open(filename, "r").readlines()

    conversies = {}
    for line in lines[1:]:
        args = [a.strip() for a in line.split("|")]
        conversies[normalize_code(args[0])] = args[1]
    return conversies


def read_nenbjerrum(filename=os.path.join(DATA_DIR, "ivinfra.csv")):
    """Lees de grondsoorten van de iv infra rapportage"""
    nenbjerrum = {}
    lines = open(filename, "r").readlines()
    for line in lines[1:]:
        args = [a.strip() for a in line.split(",")]
        soil_class = args[0]
        soil_code = args[1]
        nenbjerrum[soil_code] = {
            "soil_class": soil_class,
            "code": soil_code,
            "rr": float(args[3]),
            "cr": float(args[4]),
            "calpha": float(args[5]),
            "ysmin": float(args[-2]),
            "ysmax": float(args[-1]),
        }
    return nenbjerrum


def get_nenbjerrum(nenbjerrum, soil_class, ys):
    for _, v in nenbjerrum.items():
        if v["soil_class"] == soil_class:
            if v["ysmin"] <= ys and ys <= v["ysmax"]:
                return v
    raise ValueError(
        f"Kan '{soil_class}' met ys={ys} niet omzetten naar een NEN Bjerrum grondsoort"
    )


def get_used_soils(content):
    """Lees de grondsoorten uit de inhoud van een sli bestand en geef alleen de
    grondsoorten terug die ook in de [LAYERS] sectie gebruikt worden.

    Returns:
        dict: {soilcode: {"ys": SoilGamWet}}
    """
    lines = [l.strip() for l in content.splitlines()]

    # alle grondsoorten uit de [SOIL] secties
    soils = {}
    code = None
    for i, line in enumerate(lines):
        if line == "[SOIL]":
            code = lines[i + 1]
            soils[code] = {}
        elif line == "[END OF SOIL]":
            code = None
        elif code is not None and line.startswith("SoilGamWet="):
            soils[code]["ys"] = float(line.split("=")[1])

    # grondsoorten die in de lagen gebruikt worden
    used = set()
    in_layers = False
    for i, line in enumerate(lines):
        if line == "[LAYERS]":
            in_layers = True
        elif line == "[END OF LAYERS]":
            break
        elif in_layers and line.endswith("next line is material of layer"):
            used.add(lines[i + 1])

    return {code: params for code, params in soils.items() if code in used}


def write_converted(content, converted_soils):
    """Geef de inhoud van het sli bestand terug met NEN Bjerrum model en parameters"""
    # keepends zodat de originele regeleindes behouden blijven
    lines = content.splitlines(keepends=True)

    result = []
    in_model = False
    code = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        eol = line[len(line.rstrip("\r\n")) :]

        if stripped == "[MODEL]":
            in_model = True
        elif stripped == "[END OF MODEL]":
            in_model = False
        elif stripped == "[SOIL]":
            code = lines[i + 1].strip()
        elif stripped == "[END OF SOIL]":
            code = None
        elif in_model and ":" in stripped and "=" in stripped:
            key = stripped.split(":", 1)[1].split("=")[0].strip()
            if key in MODEL_LINES:
                line = MODEL_LINES[key] + eol
        elif code in converted_soils:
            soil = converted_soils[code]
            if stripped.startswith("SoilRRatio="):
                line = f"SoilRRatio={soil['rr']:.7f}{eol}"
            elif stripped.startswith("SoilCRatio="):
                line = f"SoilCRatio={soil['cr']:.7f}{eol}"
            elif stripped.startswith("SoilCa="):
                line = f"SoilCa={soil['calpha']:.7f}{eol}"

        result.append(line)

    return "".join(result)


def convert(content, conversies, nenbjerrum):
    """Converteer de inhoud van een sli bestand naar NEN Bjerrum

    Returns:
        tuple: (geconverteerde inhoud of None, lijst met meldingen, dict met omgezette grondsoorten)
    """
    # 1. haal alle gebruikte grondsoorten op
    soils = get_used_soils(content)

    # 2. converteer maar check of alle grondsoort codes in de conversielijst staan (sommige zijn niet te herleiden naar zand, veen of klei)
    converted_soils = {}
    messages = []

    for code, v in soils.items():
        soil_class = conversies.get(normalize_code(code), "")
        if soil_class == "":
            messages.append(
                f"Grondsoort '{code}' kan niet worden omgezet naar zand, klei of veen omdat dat niet in de conversielijst is gedefinieerd."
            )
            continue

        try:
            converted_soils[code] = get_nenbjerrum(nenbjerrum, soil_class, v["ys"])
        except ValueError as e:
            messages.append(f"Grondsoort '{code}': {e}")

    # 3. geef het geconverteerde bestand terug (alleen als alle grondsoorten zijn omgezet)
    if len(converted_soils) != len(soils):
        return None, messages, converted_soils

    return write_converted(content, converted_soils), messages, converted_soils
