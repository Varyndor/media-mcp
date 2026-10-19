"""
YAML tabanlı parametre adaptörü.
adapters.yaml'daki tanımlara göre normalize edilmiş body'yi
her model'in beklediği formata çevirir.
"""
import yaml
from pathlib import Path
_ADAPTERS_PATH = Path(__file__).parent / "adapters.yaml"
_cache: dict | None = None

def _load() -> dict:
    global _cache
    if _cache is None:
        with open(_ADAPTERS_PATH) as f:
            _cache = yaml.safe_load(f).get("models", {})
    return _cache

def adapt(model_key: str, input_body: dict) -> tuple[str, str, str, dict]:
    """
    model_key   : adapters.yaml'daki key (örn. "midjourney-8-2", "voice-clone-studio")
    input_body  : normalize edilmiş kullanıcı girdisi
    Döner: (model_id, api, endpoint, adapted_body)
    """
    adapters = _load()
    defn = adapters.get(model_key)
    if defn is None:
        # Tanımsız model: body'yi olduğu gibi geçir
        return model_key, "studio", "/v1/images/generations", {**input_body, "model": model_key}
    api      = defn["api"]
    endpoint = defn["endpoint"]
    model_id = defn.get("model_id_override", model_key)
    fields   = defn.get("fields", {})
    out: dict = {}
    for norm_key, val in input_body.items():
        if val is None:
            continue
        fdef = fields.get(norm_key)
        if fdef is None:
            # YAML'da tanımsız alan: geçir (bilinmeyen ama belki çalışır)
            out[norm_key] = val
            continue
        # skip: true → bu modelde desteklenmiyor
        if fdef.get("skip"):
            continue
        to_key = fdef.get("to", norm_key)
        ftype  = fdef.get("type", "string")
        # fixed: değer sabitlenmiş, input görmezden gelinir
        if "fixed" in fdef:
            out[to_key] = fdef["fixed"]
            continue
        # tip dönüşümü
        val = _coerce(val, ftype)
        # clamp / cap
        if fdef.get("cap"):
            if "min" in fdef: val = max(fdef["min"], val) if val is not None else val
            if "max" in fdef: val = min(fdef["max"], val) if val is not None else val
        # nearest: en yakın geçerli değeri seç; eşitlik durumunda büyük değer kazanır
        if fdef.get("nearest") and "values" in fdef and val is not None:
            vals = fdef["values"]
            val  = min(vals, key=lambda x: (abs(x - float(val)), -x))
        # enum sınırı: geçersizse default'a düş
        if ftype == "enum" and "values" in fdef and val is not None:
            if val not in fdef["values"]:
                val = fdef.get("default")
        # str / int zorla
        if fdef.get("str") and val is not None:
            val = str(val)
        if fdef.get("int") and val is not None:
            val = int(val)
        # max_length: uzunsa kırp
        if "max_length" in fdef and isinstance(val, str):
            val = val[:fdef["max_length"]]
        # max_items: array uzunsa kırp
        if ftype == "array" and "max_items" in fdef and isinstance(val, list):
            val = val[:fdef["max_items"]]
        if val is not None:
            out[to_key] = val
    # required field'lar eksikse default'u ekle
    for norm_key, fdef in fields.items():
        if fdef.get("skip"):
            continue
        to_key = fdef.get("to", norm_key)
        if fdef.get("required") and to_key not in out and norm_key not in input_body:
            raise ValueError(f"{model_key}: zorunlu alan eksik: {norm_key}")
        if "default" in fdef and to_key not in out and norm_key not in input_body:
            # default sadece eksikse eklenir
            out[to_key] = fdef["default"]
    return model_id, api, endpoint, out

def _coerce(val, ftype: str):
    """Değeri beklenen tipe çevir."""
    try:
        if ftype == "integer": return int(val)
        if ftype == "number":  return float(val)
        if ftype == "boolean": return bool(val)
        if ftype == "string":  return str(val)
    except (TypeError, ValueError):
        return val
    return val

def list_model_keys() -> list[str]:
    """Tüm adapter key'lerini döner."""
    return list(_load().keys())