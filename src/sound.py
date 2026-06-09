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
            snd = pygame.mixer.Sound(path)
            snd.set_volume(vol)
            return snd
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

# Acorde multi-frecuencia con crossfade para loop sin clics
def make_loop_chord_sound(freqs, duration, vol=0.3, name=None):
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
        s = sum(math.sin(2 * math.pi * f * t) for f in freqs) / max(1, len(freqs))
        s += 0.5 * math.sin(2 * math.pi * freqs[0] * 2 * t) / max(1, len(freqs))
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
            "shoot": make_sound(800, 0.08, vol=0.60, noise=True, name="shoot"),
            "sniper": make_sound(1500, 0.05, vol=0.60, noise=True, name="sniper"),
            "pierce": make_sound(500, 0.10, vol=0.55, noise=True, name="pierce"),
            "shotgun": make_sound(120, 0.15, vol=0.60, noise=True, name="shotgun"),
            "hit": make_sound(180, 0.15, vol=0.40, name="hit"),
            "kill": make_sound(400, 0.15, vol=0.45, name="kill"),
            "pickup": make_sound(660, 0.15, vol=0.35, name="pickup"),
            "reload": make_sound(250, 0.30, vol=1.00, name="recarga"),
            "empty": make_sound(500, 0.04, vol=0.15, name="empty"),
            "gameover": make_sound(65, 1.5, vol=0.55, noise=True, name="gameover"),
            "death": make_sound(55, 1.2, vol=0.55, noise=True, name="death"),
            "victory": make_sound(880, 0.6, vol=0.55, name="victory"),
            "wave": make_sound(520, 0.3, vol=0.45, name="wave"),
            "levelup": make_sound(700, 0.25, vol=0.45, name="levelup"),
            "boss_warn": make_sound(150, 0.5, vol=0.55, noise=True, name="boss_warn"),
            "transition": make_sound(600, 0.10, vol=0.35, name="transition"),
            "hover": make_sound(500, 0.04, vol=0.22, name="hover"),
            "click": make_sound(600, 0.07, vol=0.32, name="click"),
            "wave_clear": make_sound(880, 0.3, vol=0.45, name="wave_clear"),
            "bomb": make_sound(250, 0.15, vol=0.45, noise=True, name="bomb"),
            "explosion": make_sound(80, 0.4, vol=0.55, noise=True, name="explosion"),
            "laser": make_sound(600, 0.15, vol=0.35, name="laser"),
            "shop_open": make_sound(880, 0.10, vol=0.45, name="shop_open"),
            "guitar_riff": make_chord_sound([110, 165, 220], 0.35, vol=0.55, name="guitar_riff"),
            "eder_charge": make_loop_sound(400, 0.5, vol=0.60, name="eder_charge"),
            "eder_laser": make_sound(150, 2.0, vol=0.55, noise=True, name="eder_laser"),
            "eder_laser_loop": make_loop_chord_sound([55, 88, 132], 0.5, vol=0.70, name="eder_laser_loop"),
            "sebas_z": make_sound(300, 0.3, vol=0.55, noise=True, name="sebas_z"),

            # Q abilities
            "irvin_q": make_sound(80, 0.4, vol=0.55, noise=True, name="irvin_q"),
            "sebas_q": make_sound(400, 0.2, vol=0.50, name="sebas_q"),
            "leo_q": make_sound(1000, 0.12, vol=0.45, name="leo_q"),
            "diego_q": make_sound(200, 0.3, vol=0.50, noise=True, name="diego_q"),
            "usiel_q": make_chord_sound([330, 660], 0.3, vol=0.50, name="usiel_q"),
            "obed_q": make_sound(300, 0.25, vol=0.50, noise=True, name="obed_q"),
            "ian_q": make_sound(500, 0.2, vol=0.50, noise=True, name="ian_q"),
            "randy_q": make_sound(150, 0.3, vol=0.55, noise=True, name="randy_q"),
            "vicente_q": make_sound(1200, 0.1, vol=0.45, name="vicente_q"),

            # Z ultimates
            "irvin_z": make_sound(60, 0.6, vol=0.55, noise=True, name="irvin_z"),
            "leo_z": make_sound(1000, 0.4, vol=0.50, noise=True, name="leo_z"),
            "diego_z": make_chord_sound([150, 225, 300], 0.5, vol=0.55, name="diego_z"),
            "usiel_z": make_chord_sound([440, 550, 660], 0.5, vol=0.55, name="usiel_z"),
            "obed_z": make_chord_sound([260, 390, 520], 0.4, vol=0.55, name="obed_z"),
            "ian_z": make_sound(60, 0.5, vol=0.55, noise=True, name="ian_z"),
            "randy_z": make_sound(100, 0.5, vol=0.55, noise=True, name="randy_z"),
            "vicente_z": make_sound(800, 0.4, vol=0.55, noise=True, name="vicente_z"),

            # Domain expansions
            "irvin_domain": make_sound(150, 0.6, vol=0.55, noise=True, name="irvin_domain"),
            "sebas_domain": make_sound(300, 0.5, vol=0.55, noise=True, name="sebas_domain"),
            "leo_domain": make_sound(1000, 0.4, vol=0.50, noise=True, name="leo_domain"),
            "diego_domain": make_chord_sound([180, 270, 360], 0.5, vol=0.55, name="diego_domain"),
            "usiel_domain": make_chord_sound([440, 550, 660], 0.5, vol=0.55, name="usiel_domain"),
            "obed_domain": make_chord_sound([260, 390, 520], 0.5, vol=0.55, name="obed_domain"),
            "ian_domain": make_sound(200, 0.5, vol=0.55, noise=True, name="ian_domain"),
            "randy_domain": make_sound(100, 0.6, vol=0.55, noise=True, name="randy_domain"),
            "vicente_domain": make_sound(800, 0.5, vol=0.55, noise=True, name="vicente_domain"),
        }

        # Multiplicador global de volumen SFX (+80%)
        for snd in SFX.values():
            snd.set_volume(snd.get_volume() * 1.8)

# Variables globales para las pistas de música activas
_bg_music = None
_bg_track = 1  # alterna entre 1 (bg_music.wav) y 2 (bg_music2.wav)
_menu_music = None
_boss_music = None
_shop_music = None
_domain_music = None

# Detiene la música de fondo
def stop_bg_music():
    global _bg_music
    if _bg_music:
        _bg_music.stop()
        _bg_music = None

# Reproduce la música del menú principal en bucle
def play_menu_music():
    global _menu_music, _bg_music, _boss_music, _shop_music, _domain_music
    if _domain_music:
        _domain_music.stop(); _domain_music = None
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
        _menu_music.set_volume(0.5)
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
    _menu_music.set_volume(0.5)
    _menu_music.play(-1)

# Detiene la música del menú principal
def stop_menu_music():
    global _menu_music
    if _menu_music:
        _menu_music.stop()
        _menu_music = None

# Reproduce la música de jefe en bucle (detiene cualquier otra música)
def play_boss_music():
    global _boss_music, _bg_music, _menu_music, _shop_music, _domain_music
    if _domain_music:
        _domain_music.stop(); _domain_music = None
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
        _boss_music.set_volume(0.5)
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
    _boss_music.set_volume(0.5)
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
    global _shop_music, _bg_music, _boss_music, _menu_music, _domain_music
    if _domain_music:
        _domain_music.stop(); _domain_music = None
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
        _shop_music.set_volume(0.5)
        _shop_music.play(-1)
    else:
        # Fallback sintético
        sr = 22050
        dur = 8
        n = int(sr * dur)
        buf = bytearray(n * 2)
        for i in range(n):
            t = i / sr
            phase = t * 2 * 8
            val = int((math.sin(t * 440 * math.tau) * 0.3 +
                       math.sin(t * 660 * math.tau) * 0.2 +
                       math.sin(phase * math.tau) * 0.1) * 0.7 * 32767)
            buf[i*2:i*2+2] = struct.pack("<h", max(-32768, min(32767, val)))
        _shop_music = pygame.mixer.Sound(buffer=bytes(buf))
        _shop_music.set_volume(0.5)
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
    global _bg_music, _bg_track, _menu_music, _boss_music, _shop_music, _domain_music
    if _domain_music:
        _domain_music.stop(); _domain_music = None
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
        _bg_music.set_volume(0.5)
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
    _bg_music.set_volume(0.5)
    _bg_music.play(-1)

def play_domain_music(char_id):
    global _domain_music, _bg_music, _menu_music, _boss_music, _shop_music
    if _domain_music is not None:
        return
    if _bg_music:
        _bg_music.stop(); _bg_music = None
    if _menu_music:
        _menu_music.stop(); _menu_music = None
    if _boss_music:
        _boss_music.stop(); _boss_music = None
    if _shop_music:
        _shop_music.stop(); _shop_music = None
    path = os.path.join(SFX_DIR, f"{char_id}_domain.wav")
    if os.path.isfile(path):
        _domain_music = pygame.mixer.Sound(path)
        _domain_music.set_volume(0.5)
        _domain_music.play(-1)
        return

    sr = 22050
    bpm = 150
    beat_len = 60.0 / bpm
    duration = beat_len * 16
    n = int(sr * duration)
    data = bytearray()
    fade_len = max(1, int(n * 0.06))
    notes = [
        (329.63, 0.0), (392.00, 0.5), (440.00, 1.0), (493.88, 1.5),
        (523.25, 2.0), (587.33, 2.5), (659.25, 3.0), (587.33, 3.5),
        (523.25, 4.0), (493.88, 4.5), (440.00, 5.0), (392.00, 5.5),
        (329.63, 6.0), (261.63, 6.5), (329.63, 7.0), (392.00, 7.5),
        (440.00, 8.0), (493.88, 8.5), (440.00, 9.0), (392.00, 9.5),
        (329.63, 10.0), (392.00, 10.5), (440.00, 11.0), (493.88, 11.5),
        (587.33, 12.0), (659.25, 12.5), (587.33, 13.0), (523.25, 13.5),
        (493.88, 14.0), (440.00, 14.5), (392.00, 15.0), (329.63, 15.5),
    ]
    for i in range(n):
        t = i / sr
        beat = t / beat_len
        s = 0.0
        for j in range(len(notes)):
            freq, start = notes[j]
            end = notes[(j + 1) % len(notes)][1] if j + 1 < len(notes) else duration / beat_len
            if start <= beat < end:
                local = (beat - start) / (end - start)
                env = math.sin(math.pi * local)
                raw = math.sin(2 * math.pi * freq * t * (1 + 0.008 * math.sin(6 * math.pi * t)))
                raw += 0.5 * math.sin(2 * math.pi * freq * 2 * t)
                raw += 0.3 * math.sin(2 * math.pi * freq * 3 * t)
                sq = 1.0 if raw > 0 else -1.0
                s += sq * 0.35 * env
        low = math.sin(2 * math.pi * 82.41 * t) * 0.08
        low += math.sin(2 * math.pi * 110.0 * t) * 0.06
        s += low
        fade = min(1.0, i / fade_len, (n - 1 - i) / fade_len)
        s *= 32767 * fade
        data += struct.pack("<h", int(max(-32767, min(32767, s))))
    buf = io.BytesIO()
    ds = len(data)
    buf.write(b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data" + struct.pack("<I", ds) + bytes(data))
    buf.seek(0)
    _domain_music = pygame.mixer.Sound(buf)
    _domain_music.set_volume(0.5)
    _domain_music.play(-1)
def stop_domain_music():
    global _domain_music
    if _domain_music:
        _domain_music.stop()
        _domain_music = None
