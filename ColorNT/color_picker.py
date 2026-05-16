"""
RenkSeçici — Masaüstü Renk Analiz Aracı
Gereksinimler: pip install pillow pyperclip
Python 3.8+, Windows

Piksel okuma: Pillow ImageGrab overlay gizliyken → doğru sRGB değeri (ColorZilla ile aynı).
Bkz: GELISTIRME_NOTLARI.md — yanlış yöntemler ve çözüm detaylı anlatılmıştır.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json, os, colorsys, platform, time
from datetime import datetime

IS_WINDOWS = platform.system() == "Windows"

# ─── Pillow ──────────────────────────────────────────────────────────────────
PIL_OK = False
try:
    from PIL import ImageGrab, Image
    PIL_OK = True
except ImportError:
    pass

try:
    import ctypes, ctypes.wintypes
    _user32 = ctypes.windll.user32
    def _cursor_pos():
        pt = ctypes.wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
except Exception:
    def _cursor_pos(): return 0, 0

def get_pixel_at(x, y):
    if PIL_OK:
        img = ImageGrab.grab(bbox=(x, y, x+1, y+1), all_screens=True)
        return img.getpixel((0, 0))[:3]
    return 0, 0, 0

try:
    import pyperclip
    def _copy_to_clip(text): pyperclip.copy(text)
except ImportError:
    def _copy_to_clip(text):
        r = tk.Tk(); r.withdraw()
        r.clipboard_clear(); r.clipboard_append(text)
        r.after(500, r.destroy); r.mainloop()

# ─── Veri ────────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renkseçici_data.json")

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"history": [], "favorites": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ─── Renk yardımcıları ───────────────────────────────────────────────────────
def rgb_to_hex(r, g, b):   return f"#{r:02X}{g:02X}{b:02X}"
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb_to_hsl(r, g, b):
    hh, ll, ss = colorsys.rgb_to_hls(r/255, g/255, b/255)
    return round(hh*360), round(ss*100), round(ll*100)
def rgb_to_hsv(r, g, b):
    hh, ss, vv = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    return round(hh*360), round(ss*100), round(vv*100)
def is_dark(r, g, b):      return (r*299+g*587+b*114)/1000 < 128
def luminance(r, g, b):
    def c(x):
        x /= 255
        return x/12.92 if x <= 0.04045 else ((x+0.055)/1.055)**2.4
    return 0.2126*c(r)+0.7152*c(g)+0.0722*c(b)
def contrast(r1,g1,b1,r2,g2,b2):
    l1,l2 = luminance(r1,g1,b1), luminance(r2,g2,b2)
    a,b_ = max(l1,l2), min(l1,l2)
    return (a+0.05)/(b_+0.05)
def wcag(ratio):
    if ratio>=7:   return "AAA ✓","#1a7a1a"
    if ratio>=4.5: return "AA ✓","#2d862d"
    if ratio>=3:   return "AA Büyük ✓","#b36200"
    return "Başarısız ✗","#c0392b"
def complementary(r,g,b):
    h,s,v = rgb_to_hsv(r,g,b); hc=(h+180)%360
    rr,gg,bb = colorsys.hsv_to_rgb(hc/360,s/100,v/100)
    return int(rr*255),int(gg*255),int(bb*255)
def analogous(r,g,b):
    h,s,v=rgb_to_hsv(r,g,b); out=[]
    for off in [-30,30]:
        hh=(h+off)%360; rr,gg,bb=colorsys.hsv_to_rgb(hh/360,s/100,v/100)
        out.append((int(rr*255),int(gg*255),int(bb*255)))
    return out
def triadic(r,g,b):
    h,s,v=rgb_to_hsv(r,g,b); out=[]
    for off in [120,240]:
        hh=(h+off)%360; rr,gg,bb=colorsys.hsv_to_rgb(hh/360,s/100,v/100)
        out.append((int(rr*255),int(gg*255),int(bb*255)))
    return out

# ═══════════════════════════════════════════════════════════════════════════════
class RenkSecici:
    def __init__(self, root):
        self.root = root
        self.root.title("🎨 RenkSeçici")
        self.root.geometry("860x680")
        self.root.minsize(720,560)
        self.root.configure(bg="#1e1e2e")
        self.root.resizable(True, True)

        self.data = load_data()
        self.current_rgb = (70, 130, 180)
        self.picking = False
        self.pick_window = None
        self.mag_win = None

        self._build_ui()
        self._update_all(*self.current_rgb)

        if not PIL_OK:
            messagebox.showwarning("Pillow Eksik",
                "pip install pillow\nEkran seçimi için gerekli.")

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        C = self._C = dict(
            bg="#1e1e2e", card="#2a2a3e", acc="#7c5cbf",
            fg="#cdd6f4", fg2="#a6adc8", entry="#313244",
            green="#a6e3a1", red="#f38ba8", yellow="#f9e2af"
        )
        top = tk.Frame(self.root, bg=C["bg"], pady=10)
        top.pack(fill="x", padx=16)
        tk.Label(top, text="🎨 RenkSeçici", font=("Segoe UI",16,"bold"),
                 bg=C["bg"], fg=C["fg"]).pack(side="left")
        tk.Button(top, text="⊕  Ekrandan Seç",
                  font=("Segoe UI",11,"bold"), bg=C["acc"], fg="white",
                  relief="flat", padx=18, pady=6, cursor="hand2",
                  activebackground="#6a4aad", activeforeground="white",
                  command=self._start_pick).pack(side="right")

        style = ttk.Style(); style.theme_use("clam")
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["card"], foreground=C["fg2"],
                        padding=[14,6], font=("Segoe UI",10))
        style.map("TNotebook.Tab",
                  background=[("selected",C["acc"])],
                  foreground=[("selected","white")])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=16, pady=(0,12))

        self.tab_renk   = tk.Frame(nb, bg=C["bg"])
        self.tab_gecmis = tk.Frame(nb, bg=C["bg"])
        self.tab_favori = tk.Frame(nb, bg=C["bg"])
        self.tab_palet  = tk.Frame(nb, bg=C["bg"])
        self.tab_export = tk.Frame(nb, bg=C["bg"])

        nb.add(self.tab_renk,   text="  🎨 Renk  ")
        nb.add(self.tab_gecmis, text="  🕐 Geçmiş  ")
        nb.add(self.tab_favori, text="  ♥ Favoriler  ")
        nb.add(self.tab_palet,  text="  🌈 Palet  ")
        nb.add(self.tab_export, text="  📤 Export  ")

        self._build_renk_tab()
        self._build_gecmis_tab()
        self._build_favori_tab()
        self._build_palet_tab()
        self._build_export_tab()

    # ── RENK SEKMESİ ──────────────────────────────────────────────────────────
    def _build_renk_tab(self):
        C = self._C; tab = self.tab_renk

        left = tk.Frame(tab, bg=C["bg"])
        left.pack(side="left", fill="y", padx=(8,4), pady=8)

        self.prev_canvas = tk.Canvas(left, width=170, height=170,
                                      highlightthickness=0, bg=C["bg"])
        self.prev_canvas.pack()
        self.prev_rect = self.prev_canvas.create_rectangle(0,0,170,170,
                                                            fill="#4682b4", outline="")
        self.prev_hex = tk.Label(left, text="#4682B4",
            font=("Consolas",14,"bold"), bg=C["bg"], fg=C["fg"])
        self.prev_hex.pack(pady=(6,0))

        wf = tk.Frame(left, bg=C["bg"]); wf.pack(pady=(8,0))
        tk.Label(wf, text="Beyaz üzerine:", font=("Segoe UI",9),
                 bg=C["bg"], fg=C["fg2"]).grid(row=0,column=0,sticky="w")
        self.wcag_w = tk.Label(wf, text="—", font=("Segoe UI",9,"bold"),
                                bg=C["bg"], fg=C["fg"])
        self.wcag_w.grid(row=1,column=0,sticky="w")
        tk.Label(wf, text="Siyah üzerine:", font=("Segoe UI",9),
                 bg=C["bg"], fg=C["fg2"]).grid(row=2,column=0,sticky="w",pady=(4,0))
        self.wcag_b = tk.Label(wf, text="—", font=("Segoe UI",9,"bold"),
                                bg=C["bg"], fg=C["fg"])
        self.wcag_b.grid(row=3,column=0,sticky="w")

        tk.Button(left, text="♥  Favoriye Ekle",
                  font=("Segoe UI",9,"bold"), bg=C["card"], fg=C["fg"],
                  relief="flat", cursor="hand2", padx=10, pady=5,
                  activebackground=C["acc"], activeforeground="white",
                  command=self._open_fav_dialog).pack(pady=(14,0), fill="x")

        self.copy_lbl = tk.Label(left, text="", font=("Segoe UI",9),
                                  bg=C["bg"], fg=C["green"])
        self.copy_lbl.pack(pady=(6,0))

        right = tk.Frame(tab, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(4,8), pady=8)

        for label, vname in [("HEX","hex_var"),("RGB","rgb_var"),("RGBA","rgba_var"),
                               ("HSL","hsl_var"),("HSLA","hsla_var"),("HSV","hsv_var")]:
            setattr(self, vname, tk.StringVar())
            row = tk.Frame(right, bg=C["bg"]); row.pack(fill="x", pady=3)
            tk.Label(row, text=label, width=6, anchor="w",
                     font=("Consolas",10,"bold"), bg=C["bg"], fg=C["acc"]
                     ).pack(side="left")
            tk.Entry(row, textvariable=getattr(self,vname),
                     font=("Consolas",10), bg=C["entry"], fg=C["fg"],
                     relief="flat", readonlybackground=C["entry"],
                     state="readonly", insertbackground=C["fg"]
                     ).pack(side="left", fill="x", expand=True, ipady=5, padx=(0,6))
            tk.Button(row, text="Kopyala",
                      font=("Segoe UI",9), bg=C["card"], fg=C["fg2"],
                      relief="flat", cursor="hand2", padx=8, pady=3,
                      activebackground=C["acc"], activeforeground="white",
                      command=lambda v=vname: self._copy(getattr(self,v).get())
                      ).pack(side="right")

        ar = tk.Frame(right, bg=C["bg"]); ar.pack(fill="x", pady=(10,2))
        tk.Label(ar, text="Opaklık (α)", font=("Segoe UI",10),
                 bg=C["bg"], fg=C["fg2"]).pack(side="left")
        self.alpha_lbl2 = tk.Label(ar, text="1.00",
            font=("Consolas",10,"bold"), bg=C["bg"], fg=C["fg"])
        self.alpha_lbl2.pack(side="right")
        self.alpha_var = tk.DoubleVar(value=1.0)
        tk.Scale(right, from_=0, to=1, resolution=0.01,
                 orient="horizontal", variable=self.alpha_var,
                 bg=C["bg"], fg=C["fg"], troughcolor=C["entry"],
                 highlightthickness=0, showvalue=False,
                 command=self._on_alpha).pack(fill="x")

        tk.Frame(right, bg="#3a3a52", height=1).pack(fill="x", pady=8)
        hr = tk.Frame(right, bg=C["bg"]); hr.pack(fill="x")
        tk.Label(hr, text="HEX gir:", font=("Segoe UI",9),
                 bg=C["bg"], fg=C["fg2"]).pack(side="left")
        self.hex_input = tk.Entry(hr, width=10, font=("Consolas",11),
                                   bg=C["entry"], fg=C["fg"],
                                   relief="flat", insertbackground=C["fg"])
        self.hex_input.pack(side="left", padx=6, ipady=4)
        self.hex_input.bind("<Return>", self._on_hex_input)
        tk.Button(hr, text="Uygula", font=("Segoe UI",9),
                  bg=C["card"], fg=C["fg2"], relief="flat", cursor="hand2",
                  padx=8, pady=3,
                  command=self._on_hex_input).pack(side="left")

    # ── GEÇMİŞ SEKMESİ ───────────────────────────────────────────────────────
    def _build_gecmis_tab(self):
        C = self._C; tab = self.tab_gecmis
        bar = tk.Frame(tab, bg=C["bg"]); bar.pack(fill="x", padx=8, pady=8)
        tk.Label(bar, text="Son 100 seçilen renk",
                 font=("Segoe UI",11,"bold"), bg=C["bg"], fg=C["fg"]
                 ).pack(side="left")
        tk.Button(bar, text="Tümünü Temizle",
                  font=("Segoe UI",9), bg=C["card"], fg=C["fg2"],
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  command=self._clear_history).pack(side="right")

        outer = tk.Frame(tab, bg=C["bg"]); outer.pack(fill="both",expand=True,padx=8)
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.hist_frame = tk.Frame(cv, bg=C["bg"])
        self.hist_frame.bind("<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.hist_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True)
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120),"units"))
        self._refresh_gecmis()

    # ── FAVORİLER SEKMESİ ────────────────────────────────────────────────────
    def _build_favori_tab(self):
        C = self._C; tab = self.tab_favori
        bar = tk.Frame(tab, bg=C["bg"]); bar.pack(fill="x", padx=8, pady=8)
        tk.Label(bar, text="Favori Renkler",
                 font=("Segoe UI",11,"bold"), bg=C["bg"], fg=C["fg"]
                 ).pack(side="left")
        tk.Button(bar, text="+ Mevcut Rengi Ekle",
                  font=("Segoe UI",9,"bold"), bg=C["acc"], fg="white",
                  relief="flat", cursor="hand2", padx=10, pady=3,
                  activebackground="#6a4aad",
                  command=self._open_fav_dialog).pack(side="right")

        # Başlık satırı
        hdr = tk.Frame(tab, bg=C["card"], pady=5); hdr.pack(fill="x", padx=8)
        for txt, w in [("  Renk",5),("İsim",22),("HEX",10),("Not",30),("İşlemler",16)]:
            tk.Label(hdr, text=txt, width=w, anchor="w",
                     font=("Segoe UI",9,"bold"), bg=C["card"], fg=C["fg2"]
                     ).pack(side="left", padx=3)

        outer = tk.Frame(tab, bg=C["bg"]); outer.pack(fill="both",expand=True,padx=8)
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.fav_frame = tk.Frame(cv, bg=C["bg"])
        self.fav_frame.bind("<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.fav_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True)
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120),"units"))
        self._refresh_favori()

    # ── PALET SEKMESİ ─────────────────────────────────────────────────────────
    def _build_palet_tab(self):
        C = self._C; tab = self.tab_palet
        tk.Label(tab, text="Renk Harmonisi",
                 font=("Segoe UI",11,"bold"), bg=C["bg"], fg=C["fg"]
                 ).pack(padx=8, pady=(10,2), anchor="w")
        tk.Label(tab, text="Renk karelerine tıklayarak seç",
                 font=("Segoe UI",9), bg=C["bg"], fg=C["fg2"]
                 ).pack(padx=8, anchor="w")
        self.harmony_frame = tk.Frame(tab, bg=C["bg"])
        self.harmony_frame.pack(fill="x", padx=8, pady=8)
        tk.Frame(tab, bg="#3a3a52", height=1).pack(fill="x", padx=8, pady=4)
        tk.Label(tab, text="Mono Tonlar",
                 font=("Segoe UI",10,"bold"), bg=C["bg"], fg=C["fg"]
                 ).pack(padx=8, pady=(4,2), anchor="w")
        self.mono_frame = tk.Frame(tab, bg=C["bg"])
        self.mono_frame.pack(fill="x", padx=8, pady=4)
        self._refresh_palet()

    # ── EXPORT SEKMESİ ────────────────────────────────────────────────────────
    def _build_export_tab(self):
        C = self._C; tab = self.tab_export
        tk.Label(tab, text="Dışa Aktar — Favoriler",
                 font=("Segoe UI",11,"bold"), bg=C["bg"], fg=C["fg"]
                 ).pack(padx=8, pady=(10,2), anchor="w")
        tk.Label(tab, text="Favori listedeki renkleri farklı formatlarda kopyalayın.",
                 font=("Segoe UI",9), bg=C["bg"], fg=C["fg2"]
                 ).pack(padx=8, anchor="w")
        bf = tk.Frame(tab, bg=C["bg"]); bf.pack(fill="x", padx=8, pady=8)
        for txt, cmd in [("CSS Değişkenleri",self._exp_css),
                          ("Tailwind Config",self._exp_tailwind),
                          ("SCSS",self._exp_scss),("JSON",self._exp_json)]:
            tk.Button(bf, text=txt, font=("Segoe UI",10),
                      bg=C["card"], fg=C["fg"], relief="flat",
                      cursor="hand2", padx=14, pady=7,
                      activebackground=C["acc"], activeforeground="white",
                      command=cmd).pack(side="left", padx=(0,8))
        tk.Button(bf, text="📋 Kopyala",
                  font=("Segoe UI",10,"bold"), bg=C["acc"], fg="white",
                  relief="flat", cursor="hand2", padx=14, pady=7,
                  command=lambda: self._copy(self.exp_text.get("1.0","end"))
                  ).pack(side="right")
        tk.Label(tab, text="Önizleme:", font=("Segoe UI",9),
                 bg=C["bg"], fg=C["fg2"]).pack(padx=8, pady=(2,2), anchor="w")
        self.exp_text = tk.Text(tab, font=("Consolas",10),
                                 bg=C["entry"], fg=C["fg"], relief="flat",
                                 wrap="none", insertbackground=C["fg"], height=20)
        self.exp_text.pack(fill="both", expand=True, padx=8, pady=(0,8))

    # ── EKRANDAN SEÇİM ────────────────────────────────────────────────────────
    def _start_pick(self):
        if not PIL_OK:
            messagebox.showerror("Hata","pip install pillow"); return
        self.root.withdraw()
        self.pick_window = tk.Toplevel(self.root)
        self.pick_window.attributes("-fullscreen",True)
        self.pick_window.attributes("-alpha",0.01)
        self.pick_window.attributes("-topmost",True)
        self.pick_window.configure(cursor="crosshair")

        self.mag_win = tk.Toplevel(self.root)
        self.mag_win.overrideredirect(True)
        self.mag_win.attributes("-topmost",True)
        self.mag_canvas = tk.Canvas(self.mag_win,width=195,height=195,highlightthickness=0)
        self.mag_canvas.pack()
        self.mag_info = tk.Label(self.mag_win,text="",font=("Consolas",9),
                                  bg="#1e1e2e",fg="#cdd6f4")
        self.mag_info.pack(fill="x",ipady=3)
        self.mag_win.geometry("195x225")

        self.pick_window.bind("<Motion>",   self._on_pick_move)
        self.pick_window.bind("<Button-1>", self._on_pick_click)
        self.pick_window.bind("<Button-3>", self._cancel_pick)
        self.pick_window.bind("<Escape>",   self._cancel_pick)
        self.picking = True

    def _on_pick_move(self, event):
        if not self.picking: return
        x = self.pick_window.winfo_pointerx()
        y = self.pick_window.winfo_pointery()
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        mx = x+22 if x+222<sw else x-220
        my = y+22 if y+230<sh else y-235
        self.mag_win.geometry(f"195x225+{mx}+{my}")
        try:
            # KRITIK: overlay gizle → temiz ekran → geri aç
            self.pick_window.withdraw()
            self.root.update_idletasks()
            r,g,b = get_pixel_at(x,y)
            ZOOM,HALF = 13,6
            region = ImageGrab.grab(bbox=(x-HALF,y-HALF,x+HALF+1,y+HALF+1),all_screens=True)
            self.pick_window.deiconify()
            self.mag_canvas.delete("all")
            for dy in range(13):
                for dx in range(13):
                    pr,pg,pb = region.getpixel((dx,dy))[:3]
                    self.mag_canvas.create_rectangle(
                        dx*ZOOM,dy*ZOOM,dx*ZOOM+ZOOM,dy*ZOOM+ZOOM,
                        fill=f"#{pr:02x}{pg:02x}{pb:02x}",outline="")
            mid=HALF*ZOOM
            self.mag_canvas.create_rectangle(mid,mid,mid+ZOOM,mid+ZOOM,outline="white",width=2)
            self.mag_canvas.create_rectangle(mid-1,mid-1,mid+ZOOM+1,mid+ZOOM+1,outline="black",width=1)
            hex_str=rgb_to_hex(r,g,b)
            fg="#000000" if not is_dark(r,g,b) else "#ffffff"
            self.mag_info.config(text=f"  {hex_str}  rgb({r},{g},{b})",bg=hex_str,fg=fg)
        except Exception:
            try: self.pick_window.deiconify()
            except: pass

    def _on_pick_click(self, event):
        self._finish_pick(self.pick_window.winfo_pointerx(),
                          self.pick_window.winfo_pointery())

    def _finish_pick(self, x, y):
        self.picking = False
        try:
            self.pick_window.withdraw(); self.root.update_idletasks(); time.sleep(0.05)
            r,g,b = get_pixel_at(x,y)
            self._update_all(r,g,b); self._add_history(r,g,b)
        except Exception as e:
            messagebox.showerror("Hata",str(e))
        finally:
            for w in [self.mag_win, self.pick_window]:
                try: w.destroy()
                except: pass
            self.mag_win=self.pick_window=None
            self.root.deiconify()

    def _cancel_pick(self, event=None):
        self.picking = False
        for w in [self.mag_win, self.pick_window]:
            try: w.destroy()
            except: pass
        self.mag_win=self.pick_window=None; self.root.deiconify()

    # ── RENK GÜNCELLEME ───────────────────────────────────────────────────────
    def _update_all(self, r, g, b):
        self.current_rgb=(r,g,b)
        a = self.alpha_var.get() if hasattr(self,"alpha_var") else 1.0
        hex_str=rgb_to_hex(r,g,b); h,s,l=rgb_to_hsl(r,g,b); h2,s2,v=rgb_to_hsv(r,g,b)
        self.prev_canvas.itemconfig(self.prev_rect,fill=hex_str)
        self.prev_hex.config(text=hex_str)
        self.hex_var.set(hex_str)
        self.rgb_var.set(f"rgb({r},{g},{b})")
        self.rgba_var.set(f"rgba({r},{g},{b},{a:.2f})")
        self.hsl_var.set(f"hsl({h},{s}%,{l}%)")
        self.hsla_var.set(f"hsla({h},{s}%,{l}%,{a:.2f})")
        self.hsv_var.set(f"hsv({h2},{s2}%,{v}%)")
        rw=contrast(r,g,b,255,255,255); rb2=contrast(r,g,b,0,0,0)
        wt,wc=wcag(rw); bt,bc=wcag(rb2)
        self.wcag_w.config(text=f"{wt} ({rw:.1f}:1)",fg=wc)
        self.wcag_b.config(text=f"{bt} ({rb2:.1f}:1)",fg=bc)
        if hasattr(self,"harmony_frame"): self._refresh_palet()

    def _on_alpha(self, val):
        a=float(val); self.alpha_lbl2.config(text=f"{a:.2f}")
        r,g,b=self.current_rgb; h,s,l=rgb_to_hsl(r,g,b)
        self.rgba_var.set(f"rgba({r},{g},{b},{a:.2f})")
        self.hsla_var.set(f"hsla({h},{s}%,{l}%,{a:.2f})")

    def _on_hex_input(self, event=None):
        try:
            h=self.hex_input.get().strip()
            if not h.startswith("#"): h="#"+h
            r,g,b=hex_to_rgb(h); self._update_all(r,g,b); self.hex_input.delete(0,"end")
        except Exception:
            self.hex_input.config(fg=self._C["red"])
            self.root.after(800,lambda:self.hex_input.config(fg=self._C["fg"]))

    # ── KOPYALAMA ─────────────────────────────────────────────────────────────
    def _copy(self, text):
        _copy_to_clip(text)
        self.copy_lbl.config(text="✓ Kopyalandı")
        self.root.after(2000,lambda:self.copy_lbl.config(text=""))

    # ── GEÇMİŞ ───────────────────────────────────────────────────────────────
    def _add_history(self, r, g, b):
        hex_str=rgb_to_hex(r,g,b)
        self.data["history"]=[h for h in self.data["history"] if h["hex"]!=hex_str]
        self.data["history"].insert(0,{"hex":hex_str,"rgb":[r,g,b],
            "time":datetime.now().strftime("%H:%M:%S %d.%m")})
        self.data["history"]=self.data["history"][:100]
        save_data(self.data); self._refresh_gecmis()

    def _refresh_gecmis(self):
        C=self._C
        for w in self.hist_frame.winfo_children(): w.destroy()
        if not self.data["history"]:
            tk.Label(self.hist_frame,text="Henüz renk seçilmedi.",
                     font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]).pack(pady=20); return
        for item in self.data["history"]:
            r,g,b=item["rgb"]; hex_str=item["hex"]
            row=tk.Frame(self.hist_frame,bg=C["card"],
                         highlightbackground="#3a3a52",highlightthickness=1)
            row.pack(fill="x",pady=2)
            sw=tk.Canvas(row,width=42,height=42,highlightthickness=0,bg=C["bg"])
            sw.pack(side="left",padx=(6,4),pady=3)
            sw.create_rectangle(0,0,42,42,fill=hex_str,outline="")
            info=tk.Frame(row,bg=C["card"]); info.pack(side="left",fill="x",expand=True)
            tk.Label(info,text=hex_str,font=("Consolas",11,"bold"),
                     bg=C["card"],fg=C["fg"]).pack(anchor="w")
            tk.Label(info,text=f"rgb({r},{g},{b})  {item.get('time','')}",
                     font=("Consolas",9),bg=C["card"],fg=C["fg2"]).pack(anchor="w")
            btns=tk.Frame(row,bg=C["card"]); btns.pack(side="right",padx=4)
            tk.Button(btns,text="Kopyala",font=("Segoe UI",9),
                      bg=C["bg"],fg=C["fg2"],relief="flat",cursor="hand2",padx=8,pady=2,
                      command=lambda h=hex_str:self._copy(h)).pack(side="left",padx=2)
            tk.Button(btns,text="Seç",font=("Segoe UI",9),
                      bg=C["acc"],fg="white",relief="flat",cursor="hand2",padx=8,pady=2,
                      command=lambda rr=r,gg=g,bb=b:self._update_all(rr,gg,bb)
                      ).pack(side="left",padx=2)
            tk.Button(btns,text="♥",font=("Segoe UI",10),
                      bg=C["bg"],fg=C["red"],relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda rr=r,gg=g,bb=b:self._open_fav_dialog(rr,gg,bb)
                      ).pack(side="left",padx=2)

    def _clear_history(self):
        if messagebox.askyesno("Onayla","Geçmiş temizlensin mi?"):
            self.data["history"]=[]; save_data(self.data); self._refresh_gecmis()

    # ── FAVORİLER ─────────────────────────────────────────────────────────────
    def _open_fav_dialog(self, r=None, g=None, b=None):
        if r is None: r,g,b=self.current_rgb
        hex_str=rgb_to_hex(r,g,b); C=self._C
        dlg=tk.Toplevel(self.root); dlg.title("Favoriye Ekle")
        dlg.configure(bg=C["bg"]); dlg.resizable(False,False); dlg.grab_set()

        pv=tk.Canvas(dlg,width=64,height=64,highlightthickness=0); pv.pack(pady=(16,4))
        pv.create_rectangle(0,0,64,64,fill=hex_str,outline="")
        tk.Label(dlg,text=hex_str,font=("Consolas",13,"bold"),bg=C["bg"],fg=C["fg"]).pack()

        tk.Label(dlg,text="İsim:",font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]
                 ).pack(anchor="w",padx=20,pady=(12,0))
        name_var=tk.StringVar(value=hex_str)
        name_e=tk.Entry(dlg,textvariable=name_var,width=32,font=("Segoe UI",10),
                        bg=C["entry"],fg=C["fg"],relief="flat",insertbackground=C["fg"])
        name_e.pack(padx=20,ipady=5); name_e.select_range(0,"end"); name_e.focus()

        tk.Label(dlg,text="Not (opsiyonel):",font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]
                 ).pack(anchor="w",padx=20,pady=(8,0))
        note_e=tk.Text(dlg,width=32,height=3,font=("Segoe UI",10),
                       bg=C["entry"],fg=C["fg"],relief="flat",insertbackground=C["fg"])
        note_e.pack(padx=20,pady=(0,10))

        def save():
            name=name_var.get().strip() or hex_str
            note=note_e.get("1.0","end").strip()
            self.data["favorites"].append({"hex":hex_str,"rgb":[r,g,b],
                "name":name,"note":note,"time":datetime.now().strftime("%d.%m.%Y")})
            save_data(self.data); self._refresh_favori(); dlg.destroy()

        bf=tk.Frame(dlg,bg=C["bg"]); bf.pack(pady=(0,16))
        tk.Button(bf,text="İptal",font=("Segoe UI",10),bg=C["card"],fg=C["fg2"],
                  relief="flat",cursor="hand2",padx=16,pady=6,
                  command=dlg.destroy).pack(side="left",padx=6)
        tk.Button(bf,text="♥ Kaydet",font=("Segoe UI",10,"bold"),bg=C["acc"],fg="white",
                  relief="flat",cursor="hand2",padx=16,pady=6,
                  command=save).pack(side="left",padx=6)
        dlg.bind("<Return>",lambda e:save())

    def _refresh_favori(self):
        C=self._C
        for w in self.fav_frame.winfo_children(): w.destroy()
        if not self.data["favorites"]:
            tk.Label(self.fav_frame,
                     text="Henüz favori yok. Renk sekmesinden ♥ ile ekleyin.",
                     font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]).pack(pady=20); return

        for i,item in enumerate(self.data["favorites"]):
            r,g,b=item["rgb"]; hex_str=item["hex"]
            row=tk.Frame(self.fav_frame,bg=C["card"],
                         highlightbackground="#3a3a52",highlightthickness=1)
            row.pack(fill="x",pady=2)

            sw=tk.Canvas(row,width=48,height=48,highlightthickness=0,bg=C["bg"])
            sw.pack(side="left",padx=(6,4),pady=4)
            sw.create_rectangle(0,0,48,48,fill=hex_str,outline="")

            # Bilgi sütunu
            info=tk.Frame(row,bg=C["card"]); info.pack(side="left",fill="x",expand=True,pady=4)
            top_row=tk.Frame(info,bg=C["card"]); top_row.pack(fill="x")
            tk.Label(top_row,text=item.get("name",hex_str),
                     font=("Segoe UI",10,"bold"),bg=C["card"],fg=C["fg"]).pack(side="left")
            tk.Label(top_row,text=f"  {hex_str}",
                     font=("Consolas",9),bg=C["card"],fg=C["fg2"]).pack(side="left")
            tk.Label(top_row,text=f"  {item.get('time','')}",
                     font=("Segoe UI",8),bg=C["card"],fg=C["fg2"]).pack(side="left")
            if item.get("note"):
                tk.Label(info,text=item["note"],font=("Segoe UI",9),
                         bg=C["card"],fg=C["fg2"],wraplength=300,justify="left"
                         ).pack(anchor="w")

            # Butonlar
            btns=tk.Frame(row,bg=C["card"]); btns.pack(side="right",padx=6)
            tk.Button(btns,text="Kopyala",font=("Segoe UI",8),
                      bg=C["bg"],fg=C["fg2"],relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda h=hex_str:self._copy(h)).pack(side="left",padx=2)
            tk.Button(btns,text="Seç",font=("Segoe UI",8),
                      bg=C["acc"],fg="white",relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda rr=r,gg=g,bb=b:self._update_all(rr,gg,bb)
                      ).pack(side="left",padx=2)
            tk.Button(btns,text="Düzenle",font=("Segoe UI",8),
                      bg=C["card"],fg=C["fg2"],relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda ii=i:self._edit_fav(ii)).pack(side="left",padx=2)
            tk.Button(btns,text="✕",font=("Segoe UI",9),
                      bg=C["card"],fg=C["red"],relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda ii=i:self._del_fav(ii)).pack(side="left",padx=2)

    def _edit_fav(self, idx):
        C=self._C; item=self.data["favorites"][idx]
        r,g,b=item["rgb"]; hex_str=item["hex"]
        dlg=tk.Toplevel(self.root); dlg.title("Düzenle")
        dlg.configure(bg=C["bg"]); dlg.resizable(False,False); dlg.grab_set()
        pv=tk.Canvas(dlg,width=64,height=64,highlightthickness=0); pv.pack(pady=(16,4))
        pv.create_rectangle(0,0,64,64,fill=hex_str,outline="")
        tk.Label(dlg,text=hex_str,font=("Consolas",13,"bold"),bg=C["bg"],fg=C["fg"]).pack()
        tk.Label(dlg,text="İsim:",font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]
                 ).pack(anchor="w",padx=20,pady=(12,0))
        name_var=tk.StringVar(value=item.get("name",""))
        name_e=tk.Entry(dlg,textvariable=name_var,width=32,font=("Segoe UI",10),
                        bg=C["entry"],fg=C["fg"],relief="flat",insertbackground=C["fg"])
        name_e.pack(padx=20,ipady=5); name_e.focus()
        tk.Label(dlg,text="Not:",font=("Segoe UI",10),bg=C["bg"],fg=C["fg2"]
                 ).pack(anchor="w",padx=20,pady=(8,0))
        note_e=tk.Text(dlg,width=32,height=3,font=("Segoe UI",10),
                       bg=C["entry"],fg=C["fg"],relief="flat",insertbackground=C["fg"])
        note_e.insert("1.0",item.get("note","")); note_e.pack(padx=20,pady=(0,10))
        def save():
            self.data["favorites"][idx]["name"]=name_var.get().strip() or hex_str
            self.data["favorites"][idx]["note"]=note_e.get("1.0","end").strip()
            save_data(self.data); self._refresh_favori(); dlg.destroy()
        bf=tk.Frame(dlg,bg=C["bg"]); bf.pack(pady=(0,16))
        tk.Button(bf,text="İptal",font=("Segoe UI",10),bg=C["card"],fg=C["fg2"],
                  relief="flat",cursor="hand2",padx=16,pady=6,
                  command=dlg.destroy).pack(side="left",padx=6)
        tk.Button(bf,text="💾 Kaydet",font=("Segoe UI",10,"bold"),bg=C["acc"],fg="white",
                  relief="flat",cursor="hand2",padx=16,pady=6,
                  command=save).pack(side="left",padx=6)

    def _del_fav(self, idx):
        if messagebox.askyesno("Sil","Bu favori silinsin mi?"):
            del self.data["favorites"][idx]; save_data(self.data); self._refresh_favori()

    # ── PALET ─────────────────────────────────────────────────────────────────
    def _refresh_palet(self):
        C=self._C
        for w in self.harmony_frame.winfo_children(): w.destroy()
        for w in self.mono_frame.winfo_children(): w.destroy()
        r,g,b=self.current_rgb
        for label,colors in [("Ana",[(r,g,b)]),("Tamamlayıcı",[complementary(r,g,b)]),
                               ("Analog",analogous(r,g,b)),("Üçlü",triadic(r,g,b))]:
            col=tk.Frame(self.harmony_frame,bg=C["bg"]); col.pack(side="left",padx=10)
            tk.Label(col,text=label,font=("Segoe UI",8),bg=C["bg"],fg=C["fg2"]).pack()
            for cr,cg,cb in colors:
                h2=rgb_to_hex(cr,cg,cb)
                cv=tk.Canvas(col,width=56,height=56,
                             highlightthickness=1,highlightbackground="#3a3a52",cursor="hand2")
                cv.pack(pady=2)
                cv.create_rectangle(0,0,56,56,fill=h2,outline="")
                cv.bind("<Button-1>",lambda e,rr=cr,gg=cg,bb=cb:self._update_all(rr,gg,bb))
                tk.Label(col,text=h2,font=("Consolas",7),bg=C["bg"],fg=C["fg2"]).pack()
        hh,ss,vv=rgb_to_hsv(r,g,b)
        for lv in [15,35,55,75,92]:
            cr2,cg2,cb2=colorsys.hsv_to_rgb(hh/360,ss/100,lv/100)
            cr2,cg2,cb2=int(cr2*255),int(cg2*255),int(cb2*255)
            h2=rgb_to_hex(cr2,cg2,cb2)
            col=tk.Frame(self.mono_frame,bg=C["bg"]); col.pack(side="left",padx=6)
            cv=tk.Canvas(col,width=56,height=56,
                         highlightthickness=1,highlightbackground="#3a3a52",cursor="hand2")
            cv.pack()
            cv.create_rectangle(0,0,56,56,fill=h2,outline="")
            cv.bind("<Button-1>",lambda e,rr=cr2,gg=cg2,bb=cb2:self._update_all(rr,gg,bb))
            tk.Label(col,text=h2,font=("Consolas",7),bg=C["bg"],fg=C["fg2"]).pack()

    # ── EXPORT ────────────────────────────────────────────────────────────────
    def _set_exp(self, t):
        self.exp_text.delete("1.0","end"); self.exp_text.insert("1.0",t)

    def _exp_css(self):
        lines=["/* RenkSeçici CSS Değişkenleri */",":root {"]
        for f in self.data["favorites"]:
            n=f["name"].lower().replace(" ","-")
            note=f"  /* {f['note']} */" if f.get("note") else ""
            lines.append(f"  --color-{n}: {f['hex']};{note}")
        lines.append("}"); self._set_exp("\n".join(lines))

    def _exp_tailwind(self):
        lines=["// tailwind.config.js","module.exports = {","  theme: {",
               "    extend: {","      colors: {"]
        for f in self.data["favorites"]:
            n=f["name"].lower().replace(" ","-")
            lines.append(f"        '{n}': '{f['hex']}',")
        lines+=["      }","    }","  }","}"]; self._set_exp("\n".join(lines))

    def _exp_scss(self):
        lines=["// RenkSeçici SCSS Değişkenleri"]
        for f in self.data["favorites"]:
            n=f["name"].lower().replace(" ","-")
            note=f"  // {f['note']}" if f.get("note") else ""
            lines.append(f"${n}: {f['hex']};{note}")
        self._set_exp("\n".join(lines))

    def _exp_json(self):
        import json as _j
        out={f["name"]:{"hex":f["hex"],"note":f.get("note","")}
             for f in self.data["favorites"]}
        self._set_exp(_j.dumps({"palette":out},ensure_ascii=False,indent=2))


# ─── Başlat ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = RenkSecici(root)
    root.mainloop()
