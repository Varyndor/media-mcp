#!/usr/bin/env python3
"""
Media MCP
Görsel üretim.
"""

import os
import asyncio
import json
import time
import yaml
import re
from pathlib import Path
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from adapter import adapt

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "models.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

API_KEY = (
    os.environ.get("STUDIO_API_KEY")
    or os.environ.get("MEDIA_API_KEY")
    or os.environ.get("ANTHROPIC_API_KEY", "")
)

APIS = {
    "studio": {
        "base": "https://studio.claude.gg",
        "headers": lambda: {"Authorization": f"Bearer {API_KEY}"},
    },
}

POLL_INTERVAL = {
    "studio": 3,
}

# ─── HTTP Helpers ──────────────────────────────────────────────────────────────

async def api_post(api: str, path: str, body: dict) -> dict:
    cfg = APIS[api]
    url = cfg["base"] + path
    headers = {**cfg["headers"](), "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0)) as client:
        r = await client.post(url, json=body, headers=headers)
        r.raise_for_status()
        return r.json()

async def api_get(api: str, path: str) -> dict:
    cfg = APIS[api]
    url = cfg["base"] + path
    headers = cfg["headers"]()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

# ─── Polling ──────────────────────────────────────────────────────────────────

STUDIO_BASE = "https://studio.claude.gg"

def _normalize_studio(data: dict) -> dict:
    """
    Studio response'unu standart formata çevir.
    - status: pending/generating/completed/failed → succeeded/failed
    - url: relative → absolute
    - output: [{url, ...}] formatında döner
    """
    items  = data.get("data", [])
    # Tüm itemlar completed ise succeeded say
    statuses = [i.get("status","") for i in items]
    if all(s == "completed" for s in statuses):
        status = "succeeded"
    elif any(s == "failed" for s in statuses):
        status = "failed"
    elif any(s in ("generating","pending") for s in statuses):
        status = "running"
    else:
        status = data.get("status", "running")

    output = []
    for item in items:
        url = item.get("url") or item.get("preview_url")
        if url:
            if url.startswith("/"):
                url = STUDIO_BASE + url
            output.append({"url": url,
                            "preview_url": (STUDIO_BASE + item["preview_url"]) if item.get("preview_url","").startswith("/") else item.get("preview_url"),
                            "id": item.get("id")})

    return {**data, "status": status, "output": output}


async def poll_job(api: str, job_id: str, timeout: int = 600) -> dict:
    """Job tamamlanana kadar sorgula. succeeded/failed döner."""
    interval = POLL_INTERVAL.get(api, 3)
    deadline = time.time() + timeout

    path = f"/v1/images/{job_id}"

    while time.time() < deadline:
        await asyncio.sleep(interval)
        data = await api_get(api, path)

        if api == "studio":
            data = _normalize_studio(data)

        status = data.get("status", "")

        if status in ("succeeded", "failed", "cancelled"):
            return data
        if status == "completed":
            return {**data, "status": "succeeded"}

    return {"status": "failed", "error": {"message": f"timeout after {timeout}s"}}

# ─── Eski adapt_params kaldırıldı, adapter.py/adapters.yaml kullanılıyor ──────

def _adapter_key(model_id: str, api: str) -> str:
    """
    Önce "{model_id}-{api}", sonra "{model_id}".
    """
    from adapter import list_model_keys
    candidates = [f"{model_id}-{api}", model_id]
    keys = list_model_keys()
    for c in candidates:
        if c in keys:
            return c
    return model_id  # bulunamazsa olduğu gibi geç


# ─── Fallback Chain ────────────────────────────────────────────────────────────

def get_chain(category: str) -> list[dict]:
    """Bir kategori için primary + fallback listesini döner."""
    cat = CONFIG.get(category, {})
    chain = []
    for key in ["primary", "fallback1", "fallback2", "fallback3",
                "fallback4", "fallback5", "fallback6", "fallback7", "fallback8"]:
        if key in cat:
            chain.append(cat[key])
    return chain


async def generate_with_fallback(category: str, _unused_path: str, body: dict) -> dict:
    """
    Fallback zinciriyle üretim yap.
    Her model için adapters.yaml üzerinden parametre çevirisi yapılır.
    """
    chain = get_chain(category)
    last_error = None

    for model_cfg in chain:
        model_id = model_cfg["id"]
        api_hint = model_cfg["api"]

        # adapters.yaml'dan doğru key, endpoint ve adapted body al
        adapter_key = _adapter_key(model_id, api_hint)
        try:
            real_model_id, api, path, adapted = adapt(adapter_key, body)
        except ValueError as e:
            last_error = f"adapter hatası ({model_id}): {e}"
            continue

        adapted["model"] = real_model_id

        try:
            result = await api_post(api, path, adapted)
            job_id = (result.get("id") or result.get("batchId") or
                      result.get("job_id") or result.get("prediction_id"))
            if job_id:
                final = await poll_job(api, job_id)
                if final.get("status") == "succeeded":
                    return {"model_used": real_model_id, "api": api, **final}
                last_error = final.get("error", {}).get("message", "generation failed")
            else:
                # Senkron yanıt (studio müzik streaming vb.)
                return {"model_used": real_model_id, "api": api, **result}
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            last_error = str(e)

    return {"status": "failed", "error": last_error or "all models failed"}


async def generate_with_model(adapter_key: str, body: dict) -> dict:
    """Fallback olmadan direkt model kullan."""
    try:
        real_model_id, api, path, adapted = adapt(adapter_key, body)
    except ValueError as e:
        return {"status": "failed", "error": str(e)}

    adapted["model"] = real_model_id
    try:
        result = await api_post(api, path, adapted)
        job_id = (result.get("id") or result.get("batchId") or
                  result.get("job_id") or result.get("prediction_id"))
        if job_id:
            final = await poll_job(api, job_id)
            return {"model_used": real_model_id, "api": api, **final}
        return {"model_used": real_model_id, "api": api, **result}
    except httpx.HTTPStatusError as e:
        return {"status": "failed", "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ─── MCP Server ───────────────────────────────────────────────────────────────

server = Server("media-mcp")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="generate_image",
            description=(
                "Gorsel uret. model yoksa zincir: gpt-image-2.5-sunburst, "
                "gemini-3-pro-image, flux-2-pro, bytedance-seedream-5-pro, "
                "recraft-v4.1, krea-2-large, runway-gen4-image."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Gorsel aciklamasi"},
                    "model": {
                        "type": "string",
                        "description": "Direkt model (opsiyonel)",
                        "enum": [
                            "gpt-image-2.5-sunburst",
                            "gemini-3-pro-image",
                            "flux-2-pro",
                            "bytedance-seedream-5-pro",
                            "recraft-v4.1",
                            "krea-2-large",
                            "runway-gen4-image",
                        ],
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "default": "16:9",
                        "enum": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
                    },
                    "resolution": {
                        "type": "string",
                        "default": "1K",
                        "enum": ["1K", "2K", "4K", "720p", "1080p"],
                    },
                        "custom_width": {"type": "integer", "minimum": 1, "maximum": 4096},
                        "custom_height": {"type": "integer", "minimum": 1, "maximum": 4096},
                    "quality": {
                        "type": "string",
                        "default": "medium",
                        "enum": ["low", "medium", "high"],
                    },
                    "generations_count": {
                        "type": "integer",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 4,
                    },
                    "reference_images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Referans gorsel URL listesi",
                    },
                    "seed": {"type": "integer"},
                    "enhance_prompt": {"type": "boolean", "default": False},
                },
                "required": ["prompt"],
            },
        ),
        types.Tool(
            name="upscale_image",
            description="Gorseli 2x veya 4x buyutur. Topaz.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {"type": "string"},
                    "upscale_factor": {"type": "integer", "default": 2, "enum": [2, 4]},
                },
                "required": ["image_url"],
            },
        ),
        types.Tool(
            name="poll_result",
            description="Baslatilmis bir studio isinin sonucunu sorgular.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        ),
    ]



# ─── Tool Handlers ─────────────────────────────────────────────────────────────

MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", str(Path.home() / "media")))

def _ext_from_url(url: str, default: str = ".bin") -> str:
    """URL'den uzantı çıkar."""
    path = url.split("?")[0].split("#")[0]
    m = re.search(r"(\.\w{2,5})$", path)
    return m.group(1).lower() if m else default

def _category_ext(name: str) -> str:
    """Tool adına göre varsayılan uzantı."""
    return ".png"

async def _download_url(url: str, dest: Path) -> bool:
    """URL'yi diske indir. Başarılıysa True döner."""
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return True
    except Exception:
        return False

def _collect_urls(result: Any) -> list[str]:
    """Sonuçtan tüm medya URL'lerini topla."""
    urls = []
    if not isinstance(result, dict):
        return urls
    for item in result.get("output") or []:
        if isinstance(item, dict):
            for key in ("url", "preview_url"):
                v = item.get(key)
                if v and isinstance(v, str) and v.startswith("http"):
                    urls.append(v)
                    break
        elif isinstance(item, str) and item.startswith("http"):
            urls.append(item)
    for key in ("url", "preview_url"):
        v = result.get(key)
        if v and isinstance(v, str) and v.startswith("http"):
            urls.append(v)
    return urls

async def _download_results(result: dict, tool_name: str) -> dict:
    """Sonuçtaki URL'leri MEDIA_DIR altına indir, local_files ekle."""
    urls = _collect_urls(result)
    if not urls:
        return result
    local_files = []
    ts = int(time.time())
    for i, url in enumerate(urls):
        ext = _ext_from_url(url, _category_ext(tool_name))
        suffix = f"_{i}" if i > 0 else ""
        filename = f"{tool_name}_{ts}{suffix}{ext}"
        dest = MEDIA_DIR / filename
        ok = await _download_url(url, dest)
        if ok:
            local_files.append(str(dest))
    if local_files:
        result = {**result, "local_files": local_files}
    return result

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
        if isinstance(result, dict) and result.get("status") != "failed":
            result = await _download_results(result, name)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def _dispatch(name: str, args: dict) -> Any:
    # _dispatch: normalize edilmiş body oluşturur.
    # Alan adı çevirisi adapters.yaml + adapter.py üzerinden yapılır.

    # ── generate_image ──────────────────────────────────────────────────────
    if name == "generate_image":
        model = args.get("model")
        body = {k: v for k, v in {
            "prompt":            args.get("prompt"),
            "aspect_ratio":      args.get("aspect_ratio"),
            "resolution":        args.get("resolution"),
            "custom_width": args.get("custom_width"),
            "custom_height": args.get("custom_height"),
            "quality":           args.get("quality"),
            "generations_count": args.get("generations_count"),
            "reference_images":  args.get("reference_images"),
            "seed":              args.get("seed"),
            "enhance_prompt":    args.get("enhance_prompt"),
        }.items() if v is not None}
        if model:
            return await generate_with_model(_adapter_key(model, ""), body)
        return await generate_with_fallback("image", "", body)

    # ── upscale_image ───────────────────────────────────────────────────────
    elif name == "upscale_image":
        body = {"reference_images": [args["image_url"]],
            "upscale_factor": args.get("upscale_factor", 2)}
        return await generate_with_model("topaz-image-upscale", body)

    # ── poll_result ─────────────────────────────────────────────────────────
    elif name == "poll_result":
        return await poll_job("studio", args["job_id"])

    else:
        return {"error": f"Bilinmeyen tool: {name}"}

# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())








