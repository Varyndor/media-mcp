# media-mcp

stdio MCP sunucusu. Claude CLI ve Grok Build `server.py` sürecini açar. Görsel üretimi `https://studio.claude.gg` üzerinden yapılır.

## Dosyalar

| Dosya | İş |
|---|---|
| `server.py` | Üç aracı sunar, isteği atar, bitene kadar bekler, dosyayı indirir |
| `adapter.py` | Ortak alan adını modelin beklediği gövdeye çevirir |
| `adapters.yaml` | Her modelin kabul ettiği alan, limit ve atlanan alan |
| `models.yaml` | Görsel zinciri ve studio adresi |

## Kullanım

Sohbete normal cümle yazılır. Claude veya Grok cümleyi `generate_image` alanlarına böler. JSON yazılmaz.

Model adı yoksa zincir çalışır. Ayar yoksa oran `16:9`, çözünürlük `1K`, kalite `medium`, adet `1` olur.

| Söylenen | Alan |
|---|---|
| Görselin tarifi | `prompt` |
| "flux-2-pro ile" veya "seedream ile" | `model` |
| "kare", "9:16", "21:9" | `aspect_ratio` |
| "4K", "1080p" | `resolution` |
| "high" | `quality`. Yalnız Sunburst |
| "3 tane" | `generations_count` |
| "1024x1024" | `custom_width`, `custom_height`. Yalnız Sunburst |
| "seed 42" | `seed`. Yalnız FLUX.2 Pro |
| Bir görsel URL'si | `reference_images`. Runway kabul etmez |
| "bu görseli 4 kat büyüt" | `upscale_image` |

Örnek: "Kare, 4K, pembe benekli anime panda. Modeli flux-2-pro yap."

Tarif `prompt` alanına gider. Model ve oran ayrı alanlardır. Onları tarifin içine gömmek yerine ayrıca söylemek daha sağlamdır.

Model bir alanı kabul etmiyorsa o alan isteğe konmaz. İstek hata vermez. `4K` FLUX'a gidince FLUX'un varsayılanı `1080p` olur. `quality` FLUX'a hiç gitmez.

## Araçlar

### generate_image

`prompt` zorunlu. `model` boşsa zincir sırayla denenir. Bir model hata verirse sıradaki çalışır. `model` doluysa yalnız o model çağrılır.

Zincir: `gpt-image-2.5-sunburst` → `gemini-3-pro-image` → `flux-2-pro` → `bytedance-seedream-5-pro` → `recraft-v4.1` → `krea-2-large` → `runway-gen4-image`

| Alan | Değer |
|---|---|
| `aspect_ratio` | `16:9` `4:3` `1:1` `3:4` `9:16` `21:9`. Varsayılan `16:9` |
| `resolution` | `1K` `2K` `4K` `720p` `1080p`. Varsayılan `1K` |
| `custom_width`, `custom_height` | 1–4096. Yalnız Sunburst |
| `quality` | `low` `medium` `high`. Varsayılan `medium`. Yalnız Sunburst |
| `generations_count` | 1–4. Varsayılan 1 |
| `reference_images` | URL listesi |
| `seed` | Sayı. Yalnız FLUX.2 Pro |
| `enhance_prompt` | Varsayılan `false`. Yalnız FLUX.2 Pro |

Model bu alanı kabul etmiyorsa alan isteğe konmaz. Geçersiz enum, modelin varsayılanına düşer. Referans listesi modelin limitinde kesilir.

| Model | Prompt | Referans | Ek |
|---|---|---|---|
| gpt-image-2.5-sunburst | 10000 | 10 | ölçü, kalite, çözünürlük `1K` `2K` `4K`, oran `16:9` `4:3` `1:1` `3:4` `9:16` |
| gemini-3-pro-image | 10000 | 6 | çözünürlük `1K` `2K` `4K`, aynı beş oran |
| flux-2-pro | 10000 | 6 | `seed`, `enhance_prompt`, çözünürlük `720p` `1080p` `2K`, 14 oran (`21:9` `5:4` `3:2` `2:3` `4:5` `8:1` `4:1` `1:4` `1:8` dahil) |
| bytedance-seedream-5-pro | 2000 | 14 | çözünürlük `1K` `2K`, orana `auto` eklenir |
| recraft-v4.1 | 4000 | 6 | çözünürlük yok, beş oran |
| krea-2-large | 4000 | 6 | çözünürlük yok, beş oran |
| runway-gen4-image | 4000 | yok | yalnız metin, orana `21:9` eklenir |

### upscale_image

Topaz `topaz-image-upscale`. `image_url` zorunlu, tek görsel gider. `upscale_factor` `2` veya `4`, varsayılan `2`.

### poll_result

`job_id` ile açık studio işini sorgular. `generate_image` ve `upscale_image` işi kendi bekler. Bu araç, istemci işi ayrıca izlemek isterse durur.

## Akış

1. İstek `POST https://studio.claude.gg/v1/images/generations` adresine gider. Başlık `Authorization: Bearer`.
2. Dönen iş kimliği `GET /v1/images/{id}` ile sorulur. Aralık 3 saniye, üst süre 10 dakika.
3. `status` `succeeded` olunca URL `MEDIA_DIR` altına iner. Dönen JSON `model_used`, `api`, `output` içindeki `url` ve `local_files` alanlarını taşır.

Studio kotası günde 500 istek. Sayaç 03:00 TR'de sıfırlanır.

## Kurulum

```powershell
pip install -r requirements.txt
```

Anahtar dosyaya yazılmaz.

```powershell
$env:MEDIA_DIR = "$env:USERPROFILE\media"
```

Anahtar sırası: `STUDIO_API_KEY`, `MEDIA_API_KEY`, `ANTHROPIC_API_KEY`. Sunucu bunları PC ortamından okur. MCP kaydına anahtar eklenmez. `MEDIA_DIR` yoksa dosya `~/media` altına iner.

## İstemci

Hepsi aynı stdio kaydıdır. `command` makinedeki Python, `args` bu depodaki `server.py`. Kayıtlara anahtar konmaz. Python süreci PC'de tanımlı `STUDIO_API_KEY`, `MEDIA_API_KEY` veya `ANTHROPIC_API_KEY` değerini alır.

Üretim en fazla 10 dakika sürer. İstemcinin araç zaman aşımı bundan kısa olmamalı. Claude CLI kaydına `"timeout": 600000` eklenir. Grok Build kaydına `tool_timeout_sec = 700` eklenir.

Zincir veya araç değişince istemci yeniden açılır. Açık oturum eski araç listesini tutar.

### Claude CLI

Kullanıcı kapsamı, tüm projeler:

```powershell
claude mcp add --transport stdio --scope user media-mcp -- python D:\media-mcp\server.py
```

Yerel kapsam yalnız o projeye yazılır. `--scope` verilmezse varsayılan odur. Komut kaydı `~/.claude.json` içine koyar.

Proje kapsamı, depo kökündeki `.mcp.json`. Anahtar bu dosyaya düz yazılmaz:

```powershell
claude mcp add --transport stdio --scope project media-mcp -- python D:\media-mcp\server.py
```

```json
{
  "mcpServers": {
    "media-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"],
      "timeout": 600000
    }
  }
}
```

`.mcp.json` ilk açılışta onay ister. Kontrol: `claude mcp get media-mcp` ve oturum içinde `/mcp`.

### Claude Desktop

Code sekmesi CLI ile aynı ayarı okur. Yukarıdaki user veya project kaydı Desktop'ta da bağlanır. Connectors menüsü uzak servisler içindir. Bu sunucu yerel süreçtir, oradan eklenmez.

### Grok Build

`~/.grok/config.toml`. Windows'ta `%USERPROFILE%\.grok\config.toml`.

```toml
[mcp_servers.media-mcp]
command = "python"
args = ["D:\\media-mcp\\server.py"]
tool_timeout_sec = 700
```

Aynı blok bir deponun `.grok/config.toml` dosyasına yazılırsa yalnız o proje görür. Proje dosyası user dosyasının önüne geçer.

Komutla:

```powershell
grok mcp add media-mcp -- python D:\media-mcp\server.py
```

Grok, `compat.claude.mcps` açıkken Claude kaydını da tarar. Aynı isim varsa `config.toml` kazanır. Kontrol: `grok mcp doctor media-mcp`.

### Cursor

Tüm projeler için `~/.cursor/mcp.json`. Tek proje için depo kökünde `.cursor/mcp.json`.

```json
{
  "mcpServers": {
    "media-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"],
    }
  }
}
```

Cursor bu dosyayı Settings içindeki MCP bölümünden de açar. Sunucu açılmazsa Output panelinde MCP Logs bakılır.

### VS Code

Copilot agent için Command Palette: `MCP: Add Server`, sonra `Command (stdio)`. Komut `python`, argüman `D:\media-mcp\server.py`, ad `media-mcp`. Global seçilirse kayıt `~/.copilot/mcp-config.json` içine gider.

Elle yazılacak dosya workspace `.vscode/mcp.json` ise anahtar `servers` olur:

```json
{
  "servers": {
    "media-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"],
    }
  }
}
```

Depo kökündeki `.mcp.json` anahtarı `mcpServers` kalır. İki biçim birbirinin yerine kopyalanmaz.

### Windsurf

Cascade paneli, sağ üst `...`, `Open MCP config file`. Dosya Windows'ta `%APPDATA%\devin\mcp_config.json`.

```json
{
  "mcpServers": {
    "media-mcp": {
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"],
    }
  }
}
```

Bu kayıt eski Cascade ajanı içindir. Devin Local ajanı MCP kaydını Devin CLI yapılandırma dosyasından okur. Takım allowlist'i açıksa `media-mcp` adı listeye eklenmeden sunucu başlamaz.
