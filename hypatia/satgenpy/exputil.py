import os
import shutil


def parse_positive_int(value):
    result = int(str(value).strip())
    if result < 0:
        raise ValueError("Expected a positive integer")
    return result


def parse_positive_float(value):
    result = float(str(value).strip())
    if result < 0:
        raise ValueError("Expected a positive float")
    return result


class LocalShell:
    def remove_force_recursive(self, path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)

    def make_full_dir(self, path):
        os.makedirs(path, exist_ok=True)


class PropertiesConfig:
    def __init__(self, filename):
        self.properties = {}
        with open(filename, "r") as f_in:
            for line in f_in:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, value = stripped.split("=", 1)
                else:
                    parts = stripped.split(None, 1)
                    if len(parts) != 2:
                        continue
                    key, value = parts
                self.properties[key.strip()] = value.strip()

    def get_property_or_fail(self, key):
        if key not in self.properties:
            raise ValueError("Missing property: " + key)
        return self.properties[key]
