# RenkSeçici — Geliştirme Notları

## Sorun: Ekrandan Okunan Renk Yanlış Çıkıyor

**Semptom:** Bluestacks üzerinde çalışan Android uygulamasından renk seçildiğinde,
uygulamamız `#1E4C47` gösterirken ColorZilla ve gerçek kaynak renk `#1B4A45` idi.

---

## Denenen Yanlış Yöntemler

### ❌ Yöntem 1: Windows GDI `GetPixel` (ctypes)

```python
hdc = gdi32.CreateDCA(b"DISPLAY", None, None, None)
colorref = gdi32.GetPixel(hdc, x, y)
```

**Neden yanlış:**
`GetPixel` Windows'un ham ekran pikselini okur. Ancak Windows Color Management
katmanı devredeyse, bu değer monitörün ICC profiline göre dönüştürülmüş olabilir.
Sonuç kaynak renkten sapıyor.

---

### ❌ Yöntem 2: Gamma düzeltmesi

```python
def correct_emulator_color(r, g, b, gamma=0.95):
    lin = srgb_to_linear(x)
    corrected = lin ** (1.0 / gamma)
    return linear_to_srgb(corrected)
```

**Neden yanlış:**
Gamma değeri sabit ve tahmine dayalı. Her monitörde, her Bluestacks versiyonunda
farklı sapma olur. Evrensel çözüm değil.

---

### ❌ Yöntem 3: Sabit RGB offset kalibrasyonu

```python
DEFAULT_OFFSET = (-3, -2, -2)  # #1E4C47 → #1B4A45 için hesaplandı

def correct_with_offset(r, g, b, dr, dg, db):
    return (r + dr, g + dg, b + db)
```

**Neden yanlış:**
Offset sadece tek bir renk örneğine göre hesaplandı. Farklı renklerde sapma
miktarı değişir, bu yüzden evrensel geçerli değil.

---

### ❌ Yöntem 4: ICC profil ters dönüşümü (GetICMProfileW)

```python
mscms = ctypes.windll.mscms
ok = mscms.GetICMProfileW(hdc, ctypes.byref(size), buf)
monitor_profile = ImageCms.getOpenProfile(icc_path)
xform = ImageCms.buildTransformFromOpenProfiles(monitor_profile, srgb_profile, ...)
```

**Neden yanlış:**
`mscms.dll` üzerinden `GetICMProfileW` bazı Windows kurulumlarında bulunamıyor
(`function 'GetICMProfileW' not found` hatası). ICC dönüşümü doğru bir yaklaşım
olsa da bu API güvenilir şekilde çalışmadı.

---

### ❌ Yöntem 5: Overlay açıkken ImageGrab

```python
# pick_window fullscreen, alpha=0.01 ile açık
img = ImageGrab.grab(bbox=(x, y, x+1, y+1), all_screens=True)
```

**Neden yanlış:**
Şeffaf gibi görünen `pick_window` (alpha=0.01) aslında ekranda var.
`ImageGrab` bu overlay'i de yakalıyor ve piksel değerini bozuyor.
`#1B4A45` olan renk `#1E4C47` olarak okunuyordu.

---

## ✅ Doğru Çözüm

**Yöntem: Overlay gizlenirken ImageGrab**

Teşhis scripti (`test_renk.py`) çalıştırıldığında şu ortaya çıktı:

```
Ham GetPixel:  #1B4A45  rgb(27,74,69)   ← DOĞRU
Pillow ImageGrab: #1B4A45  rgb(27,74,69) ← DOĞRU
```

Yani `GetPixel` ve `ImageGrab` aslında ikisi de doğru rengi veriyordu.
Sorun, ana uygulamada şeffaf overlay açıkken `ImageGrab` çağrılmasıydı.

**Çözüm kodu:**

```python
def _on_pick_move(self, event):
    # Overlay'i GİZLE → ekranı yakala → geri getir
    self.pick_window.withdraw()
    self.root.update_idletasks()

    r, g, b = get_pixel_at(x, y)  # temiz ekrandan okur

    region = ImageGrab.grab(
        bbox=(x-HALF, y-HALF, x+HALF+1, y+HALF+1),
        all_screens=True
    )

    self.pick_window.deiconify()  # overlay'i geri aç
```

**Tıklama anında da aynı:**

```python
def _finish_pick(self, x, y):
    self.pick_window.withdraw()
    self.root.update_idletasks()
    time.sleep(0.05)  # render settle için kısa bekleme
    r, g, b = get_pixel_at(x, y)
```

---

## Teşhis Aracı

`test_renk.py` scripti ile tüm yöntemleri karşılaştırabilirsin:

```
python test_renk.py
```

3 saniye içinde fareyi test etmek istediğin renge götür.
Çıktıda hangi yöntemin doğru sonuç verdiği görülür.

---

## Özet

| Yöntem | Sonuç | Sebep |
|--------|-------|-------|
| GetPixel (ctypes) | ❌ Bazen yanlış | Windows color mgmt katmanı |
| Gamma düzeltme | ❌ Yanlış | Tahmine dayalı, evrensel değil |
| RGB offset | ❌ Yanlış | Sabit offset her renkte tutmuyor |
| ICC ters dönüşüm | ❌ Çalışmadı | GetICMProfileW bulunamadı |
| ImageGrab (overlay açık) | ❌ Yanlış | Overlay pikseli bozuyor |
| **ImageGrab (overlay gizli)** | **✅ Doğru** | Temiz ekran → sRGB kaynak renk |

---

## Sonuç

En basit yöntem en doğrusu oldu: `Pillow ImageGrab` overlay gizliyken
doğrudan doğru sRGB değerini veriyor. ColorZilla ile birebir aynı sonuç.
