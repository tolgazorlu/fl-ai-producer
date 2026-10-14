# Kurulum (Türkçe)

Bu dosya, Claude'un FL Studio ile konuşabilmesi için gereken adımları anlatır.
Otomatik adımlar `scripts/setup_windows.ps1` ile yapılır. Aşağıdaki **tek seferlik**
adımı FL Studio'nun içinde senin yapman gerekir (FL bu ayarı dışarıdan değiştirmeye izin vermiyor).

## Otomatik yapılanlar (yapıldı)

- Python 3.11/3.12 (uv ile), iki sanal ortam: `.venv` (analiz, GPU'lu PyTorch) ve `.venv-flmcp` (MCP sunucusu)
- loopMIDI kuruldu, `FLStudioMCP RX` ve `FLStudioMCP TX` portları oluşturuldu
- FL kontrolcü scripti kopyalandı: `Documents\Image-Line\FL Studio\Settings\Hardware\FLStudioMCP\device_FLStudioMCP.py`
- Piano roll scripti eklendi: `Settings\Piano roll scripts\MCP_Apply.pyscript`
- Claude Code MCP kaydı: `.mcp.json`

## Tek seferlik: FL Studio MIDI ayarı

1. FL Studio'yu aç. Üst menüden **Options > MIDI Settings** (kısayol: F10).
2. Pencerenin **alt yarısı Input** listesi. Orada **sadece** `FLStudioMCP RX` satırını seç:
   - **Enable** kutusunu işaretle.
   - **Controller type** açılır listesinden **FLStudioMCP** seç.
   - Sağdaki **Port** kutusunu **42** yap. Bu kutuya yazılmaz: üzerine gelip **mouse tekerleğini** çevir
     veya tıklayıp yukarı sürükle.
   - `FLStudioMCP TX` satırı Input listesinde **etkin olmasın**.
3. Pencerenin **üst yarısı Output** listesi. Orada `FLStudioMCP TX` satırını seç:
   - **Enable** işaretle, **Port** kutusunu tekerlekle **42** yap (Input ile aynı numara).
4. Pencereyi kapat. **View > Script output** penceresinde `[FLStudioMCP] Ready` yazısını görmelisin.

Eğer `FLStudioMCP` listede çıkmıyorsa FL Studio'yu tamamen kapatıp tekrar aç.

Doğrulama: Claude'da `fl_ping` çağrısı `alive: true` dönmeli. (14 Ekim 2026'da bu kurulum tamamlandı ve doğrulandı.)

## Her oturumda (her FL açılışında)

- **Piano roll** penceresini aç, sol üstteki ok menüsünden **Scripting > MCP_Apply** scriptini bir kez çalıştır.
  Bu, Claude'un nota yazma köprüsünü "kurar". Yapmazsan nota yazma sessizce çalışmaz.
- Köprü servisi (daemon) çalışıyor olmalı. Claude bunu kendisi başlatır; elle başlatmak için:

```powershell
.\.venv-flmcp\Scripts\python.exe -m fl_studio_mcp.daemon
```

## Bilinen kısıtlar

- Windows **Smart App Control** imzasız .exe dosyalarını engelliyor. Bu yüzden sunucu `.exe` yerine
  `python -m fl_studio_mcp.server` olarak çalışır (`.mcp.json` bunu yapar). pywin32 gibi paketler de engellenir.
- FL'in script API'si plugin yükleyemez, playlist'e clip koyamaz, ses dosyası çıkaramaz.
  Bu yüzden pluginleri önceden yüklü **şablon projeler** (templates/) kullanılır; Export'u sen yaparsın.
- loopMIDI kapanırsa portlar kaybolur. loopMIDI'yi açık bırak (tepsi simgesinden "Autostart" açabilirsin).
