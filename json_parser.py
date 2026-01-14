import json
from pathlib import Path
import re

# ---------- CONFIGURATION ----------

BODY_CHARACTERISTIC_RANGE = range(1, 47)  # 1–46 inclusive
OUTPUT_FILE = "AllowedKeyValues.txt"

HAIR_COLOR_FILE = "HairColors.json"
GENERIC_COLOR_FILE = "GenericColors.json"

HAIR_COLOR_KEYS = {"haircut", "facialHair", "eyebrows"}
GENERIC_COLOR_KEYS = {
    "undertop", "underwear", "overtop", "overpants",
    "pants", "shoes", "gloves", "cape", "headAccessory",
    "faceAccessory", "earAccessory"
}

# These keys should ignore colors
IGNORE_COLOR_KEYS = {"face", "ears"}
# places these json's from the game files next to python script
SOURCE_FILES = {
    "bodyCharacteristic": "BodyCharacteristics.json",
    "face": "Faces.json",
    "eyes": "Eyes.json",
    "haircut": "Haircuts.json",
    "facialHair": "FacialHair.json",
    "eyebrows": "Eyebrows.json",
    "undertop": "Undertops.json",
    "underwear": "Underwear.json",
    "overtop": "Overtops.json",
    "overpants": "Overpants.json",
    "pants": "Pants.json",
    "shoes": "Shoes.json",
    "headAccessory": "HeadAccessory.json",
    "faceAccessory": "FaceAccessory.json",
    "ears": "Ears.json",
    "earAccessory": "EarAccessory.json",
    "skinFeature": "SkinFeatures.json",
    "gloves": "Gloves.json",
    "cape": "Capes.json",
}

# Restrict these specific items to only these colors
RESTRICTED_METAL_COLORS = [
    "Gold_Red",
    "Silver_Blue",
    "Copper_Green",
    "Brass_Purple",
    "Iron_Black",
]

# Only restrict THESE earring IDs (not all earAccessory items)
RESTRICTED_EARRING_REGEX = re.compile(r"(simpleearring|earhoops|doubleearrings)", re.IGNORECASE)

# KneePads matcher (keep from before if you already added it)
KNEEPADS_REGEX = re.compile(r"kneepad", re.IGNORECASE)



# ---------- UTILITY FUNCTIONS ----------

def load_colors(path):
    """Load JSON color file. Returns list of color IDs."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [str(item.get("Id", "Black")) for item in data if isinstance(item, dict) and "Id" in item]
    return []


def sort_human_readable(values):
    """Sort strings with numbers in human-readable order."""
    def alphanum_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split("([0-9]+)", s)]
    return sorted(values, key=alphanum_key)


def parse_file(path):
    """Parse JSON file and return list of tuples (base_id, variant_name)."""
    print(f"Parsing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize root to list
    if isinstance(data, dict):
        for key in ("Assets", "Items", "Data", "Entries"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            print(f"WARNING: {Path(path).name} has unsupported root structure")
            return []

    if not isinstance(data, list):
        print(f"WARNING: {Path(path).name} is not a list")
        return []

    values = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        base_id = entry.get("Id") or entry.get("ID") or entry.get("id") or entry.get("AssetId") or entry.get("Key")
        if not base_id:
            continue
        variants = entry.get("Variants")
        if isinstance(variants, dict):
            for variant_name in variants.keys():
                values.append((str(base_id), str(variant_name)))
        elif isinstance(variants, list):
            for variant_name in variants:
                values.append((str(base_id), str(variant_name)))
        else:
            values.append((str(base_id), None))
    return values


def generate_allowed_key_values(base_dir="."):
    """Generate ALLOWED_KEY_VALUES dictionary with all colors."""
    hair_colors = load_colors(Path(base_dir) / HAIR_COLOR_FILE)
    generic_colors = load_colors(Path(base_dir) / GENERIC_COLOR_FILE)

    result = {}

    for key, filename in SOURCE_FILES.items():
        path = Path(base_dir) / filename
        if not path.exists():
            print(f"WARNING: {filename} not found, skipping")
            continue

        base_values = parse_file(path)
        if not base_values:
            continue

        formatted_values = set()

        if key == "bodyCharacteristic":
            # Expand numeric range
            for base_id, _ in base_values:
                for i in BODY_CHARACTERISTIC_RANGE:
                    formatted_values.add(f"{base_id}.{i}")
        else:
            # Default colors per key
            default_color_list = hair_colors if key in HAIR_COLOR_KEYS else generic_colors

            for base_id, variant_name in base_values:
                # Ignore colors for certain keys
                if key in IGNORE_COLOR_KEYS:
                    if variant_name:
                        formatted_values.add(f"{base_id}.{variant_name}")
                    else:
                        formatted_values.add(base_id)
                    continue

                # --- NEW: targeted restrictions ---

                is_kneepads = bool(KNEEPADS_REGEX.search(base_id)) or (
                    bool(variant_name) and bool(KNEEPADS_REGEX.search(variant_name))
                )

                is_restricted_earring = (key == "earAccessory") and (
                    bool(RESTRICTED_EARRING_REGEX.search(base_id)) or
                    (bool(variant_name) and bool(RESTRICTED_EARRING_REGEX.search(variant_name)))
                )

                # If the JSON "Variants" are actually colors, prevent unwanted colors from appearing as variant names
                # (Only applies to the restricted earrings.)
                if is_restricted_earring and variant_name:
                    if (variant_name in generic_colors) and (variant_name not in RESTRICTED_METAL_COLORS):
                        continue

                # Choose colors
                color_list = RESTRICTED_METAL_COLORS if (is_kneepads or is_restricted_earring) else default_color_list

                for color in color_list:
                    if variant_name:
                        formatted_values.add(f"{base_id}.{color}.{variant_name}")
                    else:
                        formatted_values.add(f"{base_id}.{color}")


        result[key] = set(sort_human_readable(formatted_values))

    return result


# ---------- MAIN ----------

if __name__ == "__main__":
    allowed = generate_allowed_key_values()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("ALLOWED_KEY_VALUES = {\n")
        for key, values in allowed.items():
            if not values:
                continue
            f.write(f'    "{key}": {{\n')
            for v in sorted(values, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split("([0-9]+)", s)]):
                f.write(f'        "{v}",\n')
            f.write("    },\n")
        f.write("}\n")

    print(f"Wrote {OUTPUT_FILE}")
