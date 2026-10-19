# Media MCP

Media MCP, Claude CLI, Grok Build, Cursor, VS Code ve Windsurf içinden görsel üretmenizi sağlar. Üretim `https://studio.claude.gg` üzerinde yapılır.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `server.py` | Üç aracı tanımlar, isteği gönderir, sonuç hazır olana kadar bekler ve dosyayı indirir |
| `adapter.py` | Ortak alan adlarını her modelin beklediği gövdeye çevirir |
| `adapters.yaml` | Her modelin kabul ettiği alanları, limitleri ve yok saydığı alanları tutar |
| `models.yaml` | Görsel yedek zincirini ve studio adresini tutar |

## Nasıl kullanılır

Sohbete normal bir cümle yazmanız yeter. Claude veya Grok bu cümleyi `generate_image` alanlarına ayırır. JSON yazmanıza gerek yoktur.

Model adı söylemezseniz yedek zinciri çalışır. Ölçü söylemezseniz oran `16:9`, çözünürlük `1K`, kalite `medium` ve adet `1` olur.

| Ne söylersiniz | Hangi alana gider |
|---|---|
| Görselin tarifi | `prompt` |
| "flux-2-pro ile üret" veya "seedream ile üret" | `model` |
| "kare", "9:16", "21:9" | `aspect_ratio` |
| "4K" veya "1080p" | `resolution` |
| "yüksek kalite" | `quality`. Yalnızca Sunburst kullanır |
| "3 tane üret" | `generations_count` |
| "1024x1024" | `custom_width` ve `custom_height`. Yalnızca Sunburst kullanır |
| "seed 42" | `seed`. Yalnızca FLUX.2 Pro kullanır |
| Bir görsel adresi | `reference_images` |
| "bu görseli 4 kat büyüt" | `upscale_image` |

Örnek: "Kare formatta, 4K, pembe benekli anime bir panda üret. Modeli flux-2-pro olsun."

Tarif `prompt` alanına gider. Model adı ve oran ayrı alanlardır. Bunları tarif cümlesinin içine gömmek yerine ayrıca söylemek daha güvenilirdir.

Bir model gönderdiğiniz alanı kabul etmiyorsa o alan istekten çıkarılır ve istek hata vermez. Örneğin `4K` değeri FLUX'a giderse FLUX kendi varsayılanı olan `1080p` çözünürlüğünü kullanır. `quality` alanı FLUX'a hiç gönderilmez.

## Araçlar

### generate_image

`prompt` zorunludur. `model` boşsa zincirdeki modeller sırayla denenir. Bir model hata verirse sıradaki model çalışır. `model` doluysa yalnızca o model çağrılır.

Zincir: `gpt-image-2.5-sunburst` → `gemini-3-pro-image` → `flux-2-pro` → `bytedance-seedream-5-pro` → `recraft-v4.1` → `krea-2-large` → `runway-gen4-image`

| Alan | Kabul edilen değerler |
|---|---|
| `aspect_ratio` | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`. Varsayılan `16:9` |
| `resolution` | `1K`, `2K`, `4K`, `720p`, `1080p`. Varsayılan `1K` |
| `custom_width`, `custom_height` | 1 ile 4096 arası. Yalnızca Sunburst |
| `quality` | `low`, `medium`, `high`. Varsayılan `medium`. Yalnızca Sunburst |
| `generations_count` | 1 ile 4 arası. Varsayılan 1 |
| `reference_images` | Görsel adreslerinin listesi |
| `seed` | Sayı. Yalnızca FLUX.2 Pro |
| `enhance_prompt` | Varsayılan `false`. Yalnızca FLUX.2 Pro |

Listede olmayan bir değer, o modelin varsayılanına düşer. Referans listesi modelin limitinden uzunsa liste kesilir.

| Model | Prompt sınırı | Referans sınırı | Ek |
|---|---|---|---|
| gpt-image-2.5-sunburst | 10000 | 10 | özel ölçü, kalite, çözünürlük `1K` `2K` `4K`, oran `16:9` `4:3` `1:1` `3:4` `9:16` |
| gemini-3-pro-image | 10000 | 6 | çözünürlük `1K` `2K` `4K`, aynı beş oran |
| flux-2-pro | 10000 | 6 | `seed`, `enhance_prompt`, çözünürlük `720p` `1080p` `2K`, 14 oran (`21:9`, `5:4`, `3:2`, `2:3`, `4:5`, `8:1`, `4:1`, `1:4`, `1:8` dahil) |
| bytedance-seedream-5-pro | 2000 | 14 | çözünürlük `1K` `2K`, oran listesine `auto` eklenir |
| recraft-v4.1 | 4000 | 6 | çözünürlük yok, beş oran |
| krea-2-large | 4000 | 6 | çözünürlük yok, beş oran |
| runway-gen4-image | 4000 | | oran listesine `21:9` eklenir |

### upscale_image

Topaz modeli `topaz-image-upscale` kullanılır. `image_url` zorunludur ve tek bir görsel gider. `upscale_factor` `2` veya `4` olabilir. Varsayılan `2`dir.

### poll_result

`job_id` ile sürmekte olan bir studio işini sorgular. `generate_image` ve `upscale_image` kendi işlerini zaten bekler. Bu aracı, işi ayrıca izlemek istediğinizde kullanırsınız.

## İstek nasıl ilerler

1. İstek `POST https://studio.claude.gg/v1/images/generations` adresine gider. Yetkilendirme başlığı `Authorization: Bearer` şeklindedir.
2. Dönen iş kimliği `GET /v1/images/{id}` ile sorgulanır. Sorgular 3 saniyede bir yapılır ve en fazla 10 dakika sürer.
3. `status` değeri `succeeded` olunca dosya `MEDIA_DIR` klasörüne iner. Dönen JSON içinde `model_used`, `api`, `output` altındaki `url` ve `local_files` bulunur.

Studio kotası günde 500 istektir. Sayaç her gün 03:00 Türkiye saatinde sıfırlanır.

## Kurulum

```powershell
pip install -r requirements.txt
```

Anahtar dosyaya yazılmaz. İndirme klasörünü şöyle belirleyebilirsiniz:

```powershell
$env:MEDIA_DIR = "$env:USERPROFILE\media"
```

Anahtar sırası şöyledir: `STUDIO_API_KEY`, `MEDIA_API_KEY`, `ANTHROPIC_API_KEY`. Sunucu bu değerleri bilgisayarınızın ortam değişkenlerinden okur. MCP kaydına anahtar eklemeniz gerekmez. `MEDIA_DIR` tanımlı değilse dosyalar `~/media` klasörüne iner.

## İstemciye ekleme

Aşağıdaki kayıtların hepsi aynı işi yapar. `command` bilgisayarınızdaki Python programıdır. `args` bu depodaki `server.py` dosyasıdır. Kayda anahtar yazmayın. Python süreci, bilgisayarda tanımlı `STUDIO_API_KEY`, `MEDIA_API_KEY` veya `ANTHROPIC_API_KEY` değerini kendisi alır.

Bir üretim en fazla 10 dakika sürebilir. İstemcinin araç zaman aşımı bundan kısa olmamalıdır. Claude CLI kaydına `"timeout": 600000` ekleyin. Grok Build kaydına `tool_timeout_sec = 700` ekleyin.

Zincir veya araç listesi değişince istemciyi yeniden açın. Açık oturum eski araç listesini kullanmaya devam eder.

Örneklerdeki `D:\media-mcp\server.py` yolunu, dosyayı koyduğunuz yolla değiştirin.

### Claude CLI

Bu komut kaydı tüm projeleriniz için ekler:

```powershell
claude mcp add --transport stdio --scope user media-mcp -- python D:\media-mcp\server.py
```

Kapsam vermezseniz kayıt yalnızca bulunduğunuz projeye yazılır. Komut bu kaydı `~/.claude.json` dosyasına koyar.

Projeyle birlikte paylaşmak için kayıt depo kökündeki `.mcp.json` dosyasına gider. Anahtarı bu dosyaya düz metin olarak yazmayın:

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

`.mcp.json` ilk açılışta onay ister. Kaydı `claude mcp get media-mcp` ile, oturum içinde de `/mcp` ile kontrol edebilirsiniz.

### Claude Desktop

Code sekmesi, Claude CLI ile aynı ayarı okur. Yukarıdaki kullanıcı veya proje kaydı Desktop'ta da bağlanır. Connectors menüsü uzak servisler içindir. Media MCP yerelde çalışan bir programdır ve o menüden eklenmez.

### Grok Build

Kayıt `~/.grok/config.toml` dosyasındadır. Windows'ta yol `%USERPROFILE%\.grok\config.toml` şeklindedir.

```toml
[mcp_servers.media-mcp]
command = "python"
args = ["D:\\media-mcp\\server.py"]
tool_timeout_sec = 700
```

Aynı bloğu bir deponun `.grok/config.toml` dosyasına yazarsanız yalnızca o proje görür. Proje dosyası, kullanıcı dosyasının önüne geçer.

Komutla eklemek için:

```powershell
grok mcp add media-mcp -- python D:\media-mcp\server.py
```

`compat.claude.mcps` açıksa Grok, Claude kaydını da tarar. Aynı isim iki yerde varsa `config.toml` kazanır. Kontrol için `grok mcp doctor media-mcp` çalıştırın.

### Cursor

Tüm projeler için dosya `~/.cursor/mcp.json` yolundadır. Tek bir proje için depo köküne `.cursor/mcp.json` koyun.

```json
{
  "mcpServers": {
    "media-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"]
    }
  }
}
```

Bu dosyayı Cursor ayarlarındaki MCP bölümünden de açabilirsiniz. Sunucu açılmazsa Output panelinde MCP Logs kaydına bakın.

### VS Code

Copilot için Command Palette'ten `MCP: Add Server` seçin, ardından `Command (stdio)` seçin. Komut `python`, argüman `D:\media-mcp\server.py`, ad `media-mcp` olsun. Global seçerseniz kayıt `~/.copilot/mcp-config.json` dosyasına gider.

Dosyayı elle workspace içindeki `.vscode/mcp.json` yoluna yazacaksanız üst anahtar `servers` olmalıdır:

```json
{
  "servers": {
    "media-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"]
    }
  }
}
```

Depo kökündeki `.mcp.json` dosyasında üst anahtar `mcpServers` kalır. Bu iki biçimi birbirinin yerine kopyalamayın.

### Windsurf

Cascade panelinde sağ üstteki `...` menüsünden `Open MCP config file` seçin. Windows'ta dosya `%APPDATA%\devin\mcp_config.json` yolundadır.

```json
{
  "mcpServers": {
    "media-mcp": {
      "command": "python",
      "args": ["D:\\media-mcp\\server.py"]
    }
  }
}
```

Bu kayıt eski Cascade ajanı içindir. Devin Local ajanı MCP kaydını Devin CLI yapılandırma dosyasından okur. Takım izin listesi açıksa `media-mcp` adı listeye eklenmeden sunucu başlamaz.
