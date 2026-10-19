# Media MCP

Görseller `https://studio.claude.gg` adresinde üretilir.

Model seçilmezse sıra şöyledir:

`gpt-image-2.5-sunburst` → `gemini-3-pro-image` → `flux-2-pro` → `bytedance-seedream-5-pro` → `recraft-v4.1` → `krea-2-large` → `runway-gen4-image`

Büyütme modeli `topaz-image-upscale`dir.

Anahtar koda yazılmaz. Okuma sırası `STUDIO_API_KEY`, `MEDIA_API_KEY`, `ANTHROPIC_API_KEY` şeklindedir. Değer bilgisayarın ortam değişkenlerinden gelir. MCP kaydına anahtar eklenmez.

Müzik, ses, video ve 3D isteklerinde üretim denenmez.
