import json
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
LANG_PATH = os.path.join(BASE_DIR, "languages")

_CACHE = {}


def load_language(lang="te"):
    if lang not in _CACHE:
        file_path = os.path.join(LANG_PATH, f"{lang}.json")
        if not os.path.exists(file_path):
            lang = "en"
            file_path = os.path.join(LANG_PATH, "en.json")
        with open(file_path, "r", encoding="utf-8") as f:
            _CACHE[lang] = json.load(f)
    return _CACHE[lang]


def get_text(key, lang="te"):
    data = load_language(lang)
    return data.get(key, key)


def get_all_text(lang="te"):
    return load_language(lang)
