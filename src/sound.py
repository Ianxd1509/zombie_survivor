import contextlib
import io
import math
import os
import random
import struct

import pygame

# Directorio donde se almacenan los archivos de sonido (.wav)
SFX_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")

# Generación sintética de sonido como fallback si no existe el archivo .wav
# Decaimiento natural sobre la duración completa (no se corta abruptamente)
def make_sound(freq, duration, vol=0.3, noise=False, name=None):
    if name:
        path = os.path.join(SFX_DIR, name + ".wav")
        if os.path.isfile(path):
            return pygame.mixer.Sound(path)
    sr = 22050
    n = int(sr * duration)
    data = bytearray()
    for i in range(n):
        t = i / sr
        s = (random.uniform(-1, 1) if noise else math.sin(2 * math.pi * freq * t))
        env = (max(0, 1 - t * 2 / duration)) ** 2
        s *= vol * 32767 * env
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    return pygame.mixer.Sound(buf)

# Generación de acorde (power chord) con múltiples frecuencias
def make_chord_sound(freqs, duration, vol=0.3, name=None):
    if name:
        path = os.path.join(SFX_DIR, name + ".wav")
        if os.path.isfile(path):
            return pygame.mixer.Sound(path)
    sr = 22050
    n = int(sr * duration)
    data = bytearray()
    for i in range(n):
        t = i / sr
        s = sum(math.sin(2 * math.pi * f * t) for f in freqs) / max(1, len(freqs))
        env = (max(0, 1 - t * 2 / duration)) ** 2
        s *= vol * 32767 * env
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    return pygame.mixer.Sound(buf)

# Sonido sin decaimiento, con crossfade suave en los bordes para loop sin clics
def make_loop_sound(freq, duration, vol=0.3, noise=False, name=None):
    if name:
        path = os.path.join(SFX_DIR, name + ".wav")
        if os.path.isfile(path):
            return pygame.mixer.Sound(path)
    sr = 22050
    n = int(sr * duration)
    data = bytearray()
    fade_len = max(1, int(n * 0.05))
    for i in range(n):
        t = i / sr
        s = (random.uniform(-1, 1) if noise else math.sin(2 * math.pi * freq * t))
        fade = min(1.0, i / fade_len, (n - 1 - i) / fade_len)
        s *= vol * 32767 * fade
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    return pygame.mixer.Sound(buf)

# Diccionario con todos los efectos de sonido del juego (gestión de volumen incluida)
SFX = {}
if pygame.mixer.get_init():
    with contextlib.suppress(pygame.error):
        SFX = {
            "shoot": make_sound(800, 0.08, vol=0.35, noise=True, name="shoot"),
            "shotgun": make_sound(120, 0.15, vol=0.35, noise=True, name="shotgun"),
            "hit": make_sound(180, 0.15, vol=0.22, name="hit"),
            "kill": make_sound(400, 0.15, vol=0.25, name="kill"),
            "pickup": make_sound(660, 0.15, vol=0.20, name="pickup"),
            "reload": make_sound(250, 0.30, vol=0.20, name="reload"),
            "empty": make_sound(500, 0.04, vol=0.08, name="empty"),
            "gameover": make_sound(65, 1.5, vol=0.30, noise=True, name="gameover"),
            "death": make_sound(55, 1.2, vol=0.30, noise=True, name="death"),
            "victory": make_sound(880, 0.6, vol=0.30, name="victory"),
            "wave": make_sound(520, 0.3, vol=0.25, name="wave"),
            "levelup": make_sound(700, 0.25, vol=0.25, name="levelup"),
            "boss_warn": make_sound(150, 0.5, vol=0.30, noise=True, name="boss_warn"),
            "transition": make_sound(600, 0.10, vol=0.20, name="transition"),
            "hover": make_sound(500, 0.04, vol=0.12, name="hover"),
            "click": make_sound(600, 0.07, vol=0.18, name="click"),
            "wave_clear": make_sound(880, 0.3, vol=0.25, name="wave_clear"),
            "bomb": make_sound(250, 0.15, vol=0.25, noise=True, name="bomb"),
            "explosion": make_sound(80, 0.4, vol=0.30, noise=True, name="explosion"),
            "laser": make_sound(600, 0.15, vol=0.20, name="laser"),
            "shop_open": make_sound(880, 0.10, vol=0.25, name="shop_open"),
            "guitar_riff": make_chord_sound([110, 165, 220], 0.35, vol=0.30, name="guitar_riff"),
            "eder_charge": make_loop_sound(300, 0.3, vol=0.20, name="eder_charge"),
            "eder_laser": make_sound(150, 2.0, vol=0.30, noise=True, name="eder_laser"),
        }

# Variables globales para las pistas de música activas
_bg_music = None
_bg_track = 1  # alterna entre 1 (bg_music.wav) y 2 (bg_music2.wav)
_menu_music = None
_boss_music = None

# Detiene la música de fondo
def stop_bg_music():
    global _bg_music
    if _bg_music:
        _bg_music.stop()
        _bg_music = None

# Reproduce la música del menú principal en bucle
def play_menu_music():
    global _menu_music, _bg_music, _boss_music, _shop_music
    if _menu_music is not None:
        return
    # Detiene cualquier otra música
    if _bg_music:
        _bg_music.stop(); _bg_music = None
    if _boss_music:
        _boss_music.stop(); _boss_music = None
    if _shop_music:
        _shop_music.stop(); _shop_music = None
    path = os.path.join(SFX_DIR, "menu_music.wav")
    if os.path.isfile(path):
        _menu_music = pygame.mixer.Sound(path)
        _menu_music.play(-1)
        return
    sr = 22050
    duration = 3.0
    n = int(sr * duration)
    data = bytearray()
    for i in range(n):
        t = i / sr
        chord = (math.sin(2 * math.pi * 130.81 * t) * 0.04 +
                 math.sin(2 * math.pi * 164.81 * t) * 0.03 +
                 math.sin(2 * math.pi * 196.00 * t) * 0.02)
        s = chord * max(0, 1 - t / duration)
        s += math.sin(2 * math.pi * 261.63 * t * 0.5) * 0.03 * max(0, math.sin(t * math.pi / duration * 2))
        s *= 32767
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    _menu_music = pygame.mixer.Sound(buf)
    _menu_music.play(-1)

# Detiene la música del menú principal
def stop_menu_music():
    global _menu_music
    if _menu_music:
        _menu_music.stop()
        _menu_music = None

# Reproduce la música de jefe en bucle (detiene cualquier otra música)
def play_boss_music():
    global _boss_music, _bg_music, _menu_music, _shop_music
    if _bg_music:
        _bg_music.stop(); _bg_music = None
    if _menu_music:
        _menu_music.stop(); _menu_music = None
    if _shop_music:
        _shop_music.stop(); _shop_music = None
    if _boss_music is not None:
        return
    path = os.path.join(SFX_DIR, "boss_music.wav")
    if os.path.isfile(path):
        _boss_music = pygame.mixer.Sound(path)
        _boss_music.play(-1)
        return
    sr = 22050
    duration = 4.0
    n = int(sr * duration)
    data = bytearray()
    for i in range(n):
        t = i / sr
        s = 0
        s += math.sin(2 * math.pi * 65.41 * t) * 0.08
        s += math.sin(2 * math.pi * 82.41 * t) * 0.06
        s += math.sin(2 * math.pi * 98.00 * t) * 0.04
        s += math.sin(2 * math.pi * 130.81 * t) * 0.03 * max(0, math.sin(t * 2))
        for h in range(1, 5):
            s += math.sin(2 * math.pi * 65.41 * h * t) * 0.008 / h
        beat = int(i * 2 / sr) % 2
        if beat == 0:
            s += math.sin(2 * math.pi * 200 * t) * 0.06 * max(0, math.sin(math.pi * (t % 0.5) * 4))
        s *= 32767
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    _boss_music = pygame.mixer.Sound(buf)
    _boss_music.play(-1)

# Detiene la música de jefe
def stop_boss_music():
    global _boss_music
    if _boss_music:
        _boss_music.stop()
        _boss_music = None

# Variables globales para música de tienda
_shop_music = None

# Reproduce la música de tienda (Vicente → Shop.wav, Oscar → Hip Shop.wav)
def play_shop_music(vendor="vicente"):
    global _shop_music, _bg_music, _boss_music, _menu_music
    if _shop_music is not None:
        return
    # Detiene cualquier otra música
    if _bg_music:
        _bg_music.stop(); _bg_music = None
    if _boss_music:
        _boss_music.stop(); _boss_music = None
    if _menu_music:
        _menu_music.stop(); _menu_music = None
    fname = "shop_vicente.wav" if vendor == "vicente" else "shop_oscar.wav"
    path = os.path.join(SFX_DIR, fname)
    if os.path.isfile(path):
        _shop_music = pygame.mixer.Sound(path)
        _shop_music.play(-1)

# Detiene la música de tienda y reanuda la de fondo
def stop_shop_music():
    global _shop_music
    if _shop_music:
        _shop_music.stop()
        _shop_music = None
    update_bg_music()

# Reproduce la música de fondo según la oleada actual (alterna entre bg_music.wav y bg_music2.wav)
def update_bg_music(wave=1, intensity=0.0):
    global _bg_music, _bg_track, _menu_music, _boss_music, _shop_music
    # If already playing, don't restart — let it play through
    if _bg_music is not None:
        return
    # Detiene cualquier otra música
    if _menu_music:
        _menu_music.stop(); _menu_music = None
    if _boss_music:
        _boss_music.stop(); _boss_music = None
    if _shop_music:
        _shop_music.stop(); _shop_music = None
    fname = "bg_music2.wav" if _bg_track == 2 else "bg_music.wav"
    path = os.path.join(SFX_DIR, fname)
    if os.path.isfile(path):
        _bg_music = pygame.mixer.Sound(path)
        _bg_music.play(-1)
        _bg_track = 2 if _bg_track == 1 else 1
        return
    # Fallback sintético
    _bg_track = 2 if _bg_track == 1 else 1
    sr = 22050
    duration = 2.0
    n = int(sr * duration)
    data = bytearray()
    base_freq = 55 + wave * 3
    for i in range(n):
        t = i / sr
        s = math.sin(2 * math.pi * base_freq * t) * 0.06
        s += math.sin(2 * math.pi * base_freq * 0.5 * t) * 0.04
        s += math.sin(2 * math.pi * base_freq * 2 * t) * 0.025 * min(1, intensity)
        s *= 32767
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    _bg_music = pygame.mixer.Sound(buf)
    _bg_music.play(-1)
