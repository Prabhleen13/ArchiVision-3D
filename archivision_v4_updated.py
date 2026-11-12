"""
ARCHIVISION 3D  -  Real-World Architectural Studio  (version 3)
MSc IT Semester 3 - Python Computer Graphics project
Python 3.12 + Ursina Engine 8.x

Run with:   python archivision_v3.py

What is new compared with version 2
  * CLEAN START: only the house is on screen. Click the TOOLS strip on the LEFT edge to open the
    build tools, the STYLE strip on the RIGHT edge for colours / lighting / camera, and the FILE
    strip at the BOTTOM for save / load / sun / photo studio.  (F1 / F2 / F3 also toggle them.)
  * More realistic materials: plaster walls, stone cladding, wood grain, fabric, granite, foliage,
    muted natural colours, a time-of-day sun (soft shadows, warm light at sunrise / sunset).
  * Full camera movement: pan left / right / up / down / forward / back, orbit, tilt, zoom -
    keys, on-screen pad and mouse (middle-drag = pan, right-drag = orbit, wheel = zoom).
  * Furniture can be moved left / right / forward / back (drag or I J K L) AND raised / lowered.
  * REAL ROOM PHOTO DESIGN: trace wall/floor regions on a classroom photo and preview colour changes.
  * APPROXIMATE 3D ROOM: build an editable room shell around the captured reference image,
    with adjustable width/depth/height and simple classroom desks.
  * ORIGINAL VILLA, furniture, lighting, save/load, building photo studio and camera controls remain.

Folders created next to this file on first launch:
    saved_designs/   JSON design files
    screenshots/     screenshots taken with the P key (UI hidden automatically)
    photos/          captured/imported room and building photos, edited photo outputs
"""
from ursina import *
from ursina.shaders import lit_with_shadows_shader
from panda3d.core import loadPrcFileData, AntialiasAttrib, Texture as PandaTexture
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from PIL import Image as PILImage, ImageDraw, ImageFilter
import json
import math
import random
import re

# =====================================================================
# QUALITY SETTINGS  (change these if needed)
# =====================================================================
USE_SHADERS = True        # True = real lighting and shadows.  False = flat colours (fastest)
SHADOW_RES = 4096         # 1024 = faster, 4096 = sharper shadows
SUN_DAY = (1.00, 0.95, 0.86)       # sun colour / strength in day mode
SUN_NIGHT = (0.20, 0.24, 0.42)     # moon light
AMB_DAY = (0.52, 0.55, 0.62)       # ambient (fill) light in day mode
AMB_NIGHT = (0.20, 0.24, 0.38)
PHOTO_FLIP = False        # set True if an imported photo shows upside-down on the facade

# =====================================================================
# 1. APPLICATION WINDOW
# =====================================================================
loadPrcFileData('', 'framebuffer-multisample 1\nmultisamples 4\n')
app = Ursina(title='ArchiVision 3D - Real-World Architectural Studio',
             borderless=False, fullscreen=False)
window.title = 'ArchiVision 3D - Real-World Architectural Studio'
for _name in ('cog_button', 'exit_button', 'fps_counter'):
    try:
        getattr(window, _name).enabled = False
    except Exception:
        pass
try:
    scene.set_antialias(AntialiasAttrib.MAuto)
except Exception:
    pass
try:
    Texture.default_filtering = 'mipmap'
except Exception:
    pass

PROJECT_NAME = 'My Modern Villa'
BASE_DIR = Path(__file__).resolve().parent
SAVE_DIR = BASE_DIR / 'saved_designs'
SHOT_DIR = BASE_DIR / 'screenshots'
PHOTO_DIR = BASE_DIR / 'photos'
for _d in (SAVE_DIR, SHOT_DIR, PHOTO_DIR):
    _d.mkdir(exist_ok=True)

# =====================================================================
# 2. CONSTANTS, PALETTE AND DATA TABLES
# =====================================================================
WALL_H = 3.0
WALL_T = 0.2
WALL_Y0 = 0.1
STOREY = 3.4                      # height difference between the two floors
LEVEL_Y = {0: 0.0, 1: STOREY}
FLOOR_TOP = 0.14                  # top surface of the ground floor
HOUSE = (-8, 8, -6, 6)            # x0, x1, z0, z1 of the building
EXT = {'S': -6, 'N': 6, 'W': -8, 'E': 8}
STAIR = (1.4, 6.0, -1.0, 1.0)     # staircase / stair opening  x0, x1, z0, z1
ROOF_Y = WALL_Y0 + STOREY + WALL_H            # underside of the roof slab
RENDER_COL = (238, 235, 227)      # exterior render (plaster) colour


def floor_y(level):
    return FLOOR_TOP + LEVEL_Y[level]


PALETTE = {
    'warm_white': ('Warm White', (240, 234, 220)),
    'light_grey': ('Light Grey', (192, 194, 198)),
    'beige':      ('Beige',      (222, 204, 172)),
    'soft_blue':  ('Soft Blue',  (160, 192, 218)),
    'sage_green': ('Sage Green', (158, 186, 160)),
    'charcoal':   ('Charcoal',   (78, 82, 92)),
    'oak':        ('Oak',        (214, 176, 132)),
    'walnut':     ('Walnut',     (150, 108, 78)),
}
PALETTE_KEYS = list(PALETTE.keys())

ROOF_COLS = [('Terracotta', (158, 84, 60)), ('Slate', (70, 76, 88)), ('Charcoal', (52, 54, 60)),
             ('Brown', (98, 70, 54)), ('Sand', (196, 176, 140)), ('White', (226, 226, 222))]

ROOMS = {
    # ground floor
    'living_room':    dict(label='Living Room',      level=0, rect=(-8, 1, -6, -1), tex='tile'),
    'home_office':    dict(label='Home Office',      level=0, rect=(1, 8, -6, -1),  tex='wood'),
    'kitchen':        dict(label='Kitchen & Dining', level=0, rect=(-8, 2, 1, 6),   tex='tile'),
    'guest_bath':     dict(label='Guest Bathroom',   level=0, rect=(2, 8, 1, 6),    tex='tile'),
    'hallway':        dict(label='Hallway & Stairs', level=0, rect=(-8, 8, -1, 1),  tex='tile'),
    # upper floor
    'master_bedroom': dict(label='Master Bedroom',   level=1, rect=(-8, 1, -6, -1), tex='wood'),
    'bedroom_2':      dict(label='Bedroom 2',        level=1, rect=(1, 8, -6, -1),  tex='wood'),
    'lounge':         dict(label='Family Lounge',    level=1, rect=(-8, 2, 1, 6),   tex='wood'),
    'bathroom':       dict(label='Bathroom',         level=1, rect=(2, 8, 1, 6),    tex='tile'),
    'landing':        dict(label='Landing',          level=1, rect=(-8, 8, -1, 1),  tex='wood'),
}
LEVEL_ROOMS = {
    0: ['living_room', 'home_office', 'kitchen', 'guest_bath', 'hallway'],
    1: ['master_bedroom', 'bedroom_2', 'lounge', 'bathroom', 'landing'],
}
NO_NS = ('hallway', 'landing')    # corridor rooms: only the W and E walls are their own

DEFAULT_COLORS = {
    'living_room': ('warm_white', 'beige'),   'home_office': ('sage_green', 'oak'),
    'kitchen': ('warm_white', 'light_grey'),  'guest_bath': ('soft_blue', 'light_grey'),
    'hallway': ('warm_white', 'beige'),
    'master_bedroom': ('beige', 'oak'),       'bedroom_2': ('sage_green', 'oak'),
    'lounge': ('warm_white', 'walnut'),       'bathroom': ('warm_white', 'charcoal'),
    'landing': ('warm_white', 'oak'),
}

# (room, side) -> [(kind, centre along the wall, width)]   S = low z, N = high z, W = low x, E = high x
OPENINGS = {
    ('living_room', 'S'): [('tall_window', -6.4, 2.0), ('main_door', -3.2, 1.3), ('tall_window', -0.7, 1.0)],
    ('living_room', 'W'): [('tall_window', -3.5, 2.4)],
    ('living_room', 'N'): [('doorway', -4.5, 1.2)],
    ('home_office', 'S'): [('window', 3.4, 2.2), ('window', 6.4, 1.6)],
    ('home_office', 'N'): [('doorway', 7.0, 1.0)],
    ('home_office', 'E'): [('window', -3.5, 1.6)],
    ('kitchen', 'S'):     [('doorway', -5.0, 1.2)],
    ('kitchen', 'N'):     [('window', -5.0, 2.4), ('glass_door', -0.8, 2.0)],
    ('kitchen', 'W'):     [('window', 3.5, 1.6)],
    ('guest_bath', 'S'):  [('doorway', 7.0, 1.0)],
    ('guest_bath', 'N'):  [('high_window', 5.0, 1.0)],
    ('guest_bath', 'E'):  [('high_window', 3.5, 0.9)],
    ('hallway', 'W'):     [('window', 0.0, 0.9)],
    ('hallway', 'E'):     [('glass_door', 0.0, 1.8)],
    ('master_bedroom', 'S'): [('glass_door', -4.6, 3.2), ('window', -0.6, 0.8)],
    ('master_bedroom', 'W'): [('tall_window', -3.5, 2.2)],
    ('master_bedroom', 'N'): [('doorway', -4.5, 1.1)],
    ('bedroom_2', 'S'):   [('window', 3.4, 2.0), ('window', 6.3, 1.6)],
    ('bedroom_2', 'E'):   [('window', -3.5, 1.6)],
    ('bedroom_2', 'N'):   [('doorway', 7.0, 1.0)],
    ('lounge', 'S'):      [('doorway', -5.0, 1.2)],
    ('lounge', 'N'):      [('tall_window', -5.0, 2.4), ('tall_window', -1.0, 1.6)],
    ('bathroom', 'S'):    [('doorway', 7.0, 1.0)],
    ('bathroom', 'N'):    [('high_window', 5.0, 1.0)],
    ('bathroom', 'E'):    [('high_window', 3.5, 0.9)],
    ('landing', 'W'):     [('window', 0.0, 0.9)],
    ('landing', 'E'):     [('window', 0.0, 1.4)],
}
OPEN_Z = {'window': (0.9, 2.2), 'tall_window': (0.12, 2.55), 'high_window': (1.6, 2.3),
          'doorway': (0.0, 2.2), 'main_door': (0.0, 2.2), 'glass_door': (0.0, 2.4)}

# (type, x, z, rotation_y, level)   front of an item faces local +z
DEFAULT_FURNITURE = [
    # living room
    ('tv_unit', -7.45, -3.5, 90, 0), ('sectional_sofa', -1.3, -3.5, -90, 0),
    ('coffee_table', -3.6, -3.5, 90, 0), ('rug', -3.6, -3.5, 90, 0),
    ('armchair', -3.0, -1.9, 180, 0), ('armchair', -3.6, -5.15, 0, 0),
    ('bookshelf', -6.0, -1.42, 180, 0), ('floor_lamp', -0.3, -1.8, 0, 0),
    ('plant', -7.3, -5.3, 0, 0), ('plant', -7.3, -1.8, 0, 0),
    # home office
    ('desk', 4.5, -5.43, 0, 0), ('office_chair', 4.5, -4.4, 180, 0),
    ('bookshelf', 7.58, -3.0, -90, 0), ('plant', 1.6, -5.3, 0, 0), ('floor_lamp', 7.4, -5.3, 0, 0),
    # kitchen & dining
    ('kitchen_counter', -6.3, 5.43, 180, 0), ('sink_counter', -3.8, 5.43, 180, 0),
    ('fridge', 1.35, 5.38, 180, 0), ('kitchen_island', -5.0, 3.5, 0, 0),
    ('bar_stool', -5.7, 2.6, 0, 0), ('bar_stool', -5.0, 2.6, 0, 0), ('bar_stool', -4.3, 2.6, 0, 0),
    ('dining_table', -0.8, 3.3, 0, 0), ('plant', -7.3, 1.8, 0, 0),
    # guest bathroom
    ('shower', 7.0, 5.05, 180, 0), ('washbasin', 7.5, 2.4, -90, 0), ('toilet', 7.45, 3.5, -90, 0),
    ('plant', 2.7, 5.3, 0, 0),
    # hallway
    ('plant', -7.3, 0.0, 0, 0), ('floor_lamp', 0.5, 0.6, 0, 0),
    # master bedroom
    ('bed', -6.68, -3.5, 90, 1), ('bedside_table', -7.5, -4.85, 90, 1), ('bedside_table', -7.5, -2.15, 90, 1),
    ('rug', -4.7, -3.5, 90, 1), ('wardrobe', -1.8, -1.52, 180, 1), ('tv_unit', 0.55, -3.5, -90, 1),
    ('floor_lamp', -1.0, -5.3, 0, 1),
    # bedroom 2
    ('bed', 6.6, -3.5, -90, 1), ('bedside_table', 7.5, -4.8, -90, 1), ('bedside_table', 7.5, -2.2, -90, 1),
    ('wardrobe', 1.52, -4.5, 90, 1), ('desk', 4.0, -5.43, 0, 1), ('office_chair', 4.0, -4.5, 180, 1),
    # family lounge
    ('tv_unit', -7.45, 3.5, 90, 1), ('sectional_sofa', -2.8, 3.5, -90, 1),
    ('coffee_table', -5.2, 3.5, 90, 1), ('rug', -5.0, 3.5, 90, 1),
    ('bookshelf', 1.55, 4.5, -90, 1), ('plant', -7.3, 5.3, 0, 1), ('plant', -7.3, 1.8, 0, 1),
    ('floor_lamp', 1.2, 1.8, 0, 1),
    # bathroom
    ('bathtub', 3.3, 5.35, 180, 1), ('shower', 7.0, 5.05, 180, 1),
    ('washbasin', 7.5, 2.4, -90, 1), ('toilet', 7.45, 3.5, -90, 1),
    # landing
    ('plant', -7.2, 0.0, 0, 1), ('floor_lamp', 0.3, 0.7, 0, 1),
]
ADD_LIST = ['sofa', 'sectional_sofa', 'armchair', 'coffee_table', 'rug', 'floor_lamp',
            'bookshelf', 'desk', 'office_chair', 'dining_table', 'bed', 'wardrobe',
            'plant', 'bedside_table']
BUTTON_LABEL = {'sectional_sofa': 'L-SHAPE SOFA', 'floor_lamp': 'FLOOR LAMP',
                'office_chair': 'OFFICE CHAIR', 'bedside_table': 'BEDSIDE TABLE'}

# more natural, slightly muted colours (less "toy-like" than pure primaries)
DARK = (38, 44, 56)
WOOD = (176, 134, 96)
WOOD_DARK = (104, 74, 52)
STEEL = (176, 184, 194)
WHITE = (238, 238, 234)
GOLD = (200, 168, 100)
GREEN = (66, 98, 56)
GREEN_L = (92, 124, 70)
GREEN_D = (46, 72, 44)
GLASS_DAY = (150, 200, 225, 105)
GLASS_NIGHT = (255, 214, 140, 200)

UI_PANEL = (16, 22, 36, 232)
UI_BAR = (10, 14, 24, 245)
UI_BTN = (38, 52, 78)
UI_HOVER = (70, 120, 190)
UI_ACTIVE = (36, 118, 200)
UI_ACCENT = (90, 180, 255)
UI_TEXT = (235, 238, 245)

# colour -> (texture, tile)  : furniture parts get a material automatically from their colour
AUTO_TEX = {}


def _reg(tex, tile, *cols):
    for c in cols:
        AUTO_TEX[tuple(c)] = (tex, tile)


_reg('wood', (1, 1), WOOD, WOOD_DARK, (214, 176, 112), (180, 140, 100), (190, 150, 110))
_reg('fabric', (3, 3), (112, 118, 128), (130, 136, 146), (214, 204, 190), (206, 196, 180),
     (150, 136, 120), (150, 112, 80), (200, 168, 128), (176, 138, 100), (88, 112, 148),
     (240, 236, 228), (252, 250, 244), (128, 134, 146))
_reg('granite', (1, 1), (50, 54, 62))
_reg('foliage', (2, 2), GREEN, GREEN_L, GREEN_D)

# =====================================================================
# 3. PROCEDURAL TEXTURES  (generated with Pillow, no files needed)
# =====================================================================
TEX = {}


def _noise_l(size, sigma, lo, hi, blur=1.0):
    n = PILImage.effect_noise((size, size), sigma)
    if blur:
        n = n.filter(ImageFilter.GaussianBlur(blur))
    return n.point(lambda v: int(lo + (hi - lo) * v / 255))


def _to_rgb(l_img):
    return PILImage.merge('RGB', (l_img, l_img, l_img))


def _blend_coarse(fine, size, cells, sigma, blur, lo, hi, alpha):
    coarse = PILImage.effect_noise((cells, cells), sigma).resize((size, size), PILImage.BILINEAR)
    coarse = coarse.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(lo + (hi - lo) * v / 255))
    return PILImage.blend(fine, coarse, alpha)


def _tex_wood():
    rnd = random.Random(7)
    size, ph = 1024, 128
    img = PILImage.new('RGB', (size, size), (150, 150, 150))
    d = ImageDraw.Draw(img)
    for row in range(size // ph):
        y0 = row * ph
        x = -rnd.randint(0, 400)
        while x < size:
            ln = rnd.randint(440, 720)
            g = rnd.randint(205, 245)
            d.rectangle([x, y0, x + ln - 4, y0 + ph - 4], fill=(g, g - 4, g - 9))
            for _ in range(14):                          # fine grain lines
                gy = rnd.randint(y0 + 4, y0 + ph - 8)
                gg = g - rnd.randint(6, 26)
                d.line([x + 3, gy, x + ln - 7, gy + rnd.randint(-2, 2)], fill=(gg, gg - 4, gg - 9))
            x += ln
    return img.filter(ImageFilter.GaussianBlur(0.7))


def _tex_tile():
    rnd = random.Random(11)
    size = 1024
    img = _to_rgb(_noise_l(size, 30, 230, 252, 2.0))
    d = ImageDraw.Draw(img)
    for _ in range(10):                                 # soft marble veins
        x, y = rnd.randint(0, size), rnd.randint(0, size)
        pts = [(x, y)]
        for _ in range(16):
            x += rnd.randint(-50, 62)
            y += rnd.randint(-50, 62)
            pts.append((x, y))
        d.line(pts, fill=(204, 204, 210), width=2)
    img = img.filter(ImageFilter.GaussianBlur(2.2))
    d = ImageDraw.Draw(img)
    for t in (0, size // 2):                            # grout lines
        d.line([(t, 0), (t, size)], fill=(160, 160, 164), width=6)
        d.line([(0, t), (size, t)], fill=(160, 160, 164), width=6)
    return img


def _tex_slats():
    rnd = random.Random(5)
    img = PILImage.new('RGB', (256, 256), (60, 52, 44))
    d = ImageDraw.Draw(img)
    for x in range(0, 256, 16):
        g = rnd.randint(190, 238)
        d.rectangle([x + 1, 0, x + 14, 255], fill=(g, g - 6, g - 14))
        for _ in range(5):
            gx = x + rnd.randint(3, 12)
            d.line([gx, 0, gx, 255], fill=(g - 18, g - 24, g - 30))
    return img.filter(ImageFilter.GaussianBlur(0.4))


def _tex_deck():
    rnd = random.Random(3)
    img = PILImage.new('RGB', (256, 256), (80, 70, 60))
    d = ImageDraw.Draw(img)
    for y in range(0, 256, 32):
        g = rnd.randint(196, 238)
        d.rectangle([0, y + 1, 255, y + 29], fill=(g, g - 5, g - 12))
        for _ in range(5):
            gy = y + rnd.randint(4, 26)
            d.line([0, gy, 255, gy], fill=(g - 16, g - 21, g - 28))
    return img


def _tex_grass():
    fine = _noise_l(256, 70, 150, 240, 0.6)
    return _to_rgb(_blend_coarse(fine, 256, 32, 55, 4, 160, 245, 0.5))


def _tex_water():
    return _to_rgb(_noise_l(256, 45, 205, 255, 3))


def _tex_concrete():
    return _to_rgb(_noise_l(256, 40, 205, 238, 0.8))


def _tex_plaster():
    fine = _noise_l(512, 40, 232, 252, 0.8)
    return _to_rgb(_blend_coarse(fine, 512, 16, 60, 6, 224, 254, 0.5))


def _tex_stone():
    rnd = random.Random(21)
    size = 512
    img = PILImage.new('RGB', (size, size), (110, 110, 108))
    d = ImageDraw.Draw(img)
    y = 0
    while y < size:
        h = rnd.choice((48, 64, 80))
        x = -rnd.randint(0, 100)
        while x < size:
            w = rnd.randint(110, 220)
            g = rnd.randint(176, 228)
            d.rectangle([x + 3, y + 3, x + w - 3, y + h - 3], fill=(g, g - 3, g - 7))
            x += w
        y += h
    img = PILImage.blend(img, _to_rgb(_noise_l(size, 45, 150, 235, 0.8)), 0.35)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def _tex_fabric():
    return _to_rgb(_noise_l(128, 60, 192, 252, 0.4))


def _tex_granite():
    return _to_rgb(_noise_l(256, 95, 140, 240, 0.3))


def _tex_foliage():
    fine = _noise_l(256, 80, 120, 255, 0.6)
    return _to_rgb(_blend_coarse(fine, 256, 24, 70, 5, 110, 250, 0.55))


def make_textures():
    for name, fn in (('wood', _tex_wood), ('tile', _tex_tile), ('slats', _tex_slats),
                     ('deck', _tex_deck), ('grass', _tex_grass), ('water', _tex_water),
                     ('concrete', _tex_concrete), ('plaster', _tex_plaster), ('stone', _tex_stone),
                     ('fabric', _tex_fabric), ('granite', _tex_granite), ('foliage', _tex_foliage)):
        try:
            TEX[name] = Texture(fn().convert('RGBA'))
        except Exception as exc:
            print(f'[texture {name} skipped: {exc}]')
            TEX[name] = None


make_textures()

# =====================================================================
# 4. GLOBAL STATE
# =====================================================================
state = dict(night=False, brightness=1.0, roof=True, upper=True, level=0,
             room='living_room', item=None, popup=None, help=False,
             view='exterior', cut=True, snap=True, drag=None, sun_t=0.32, photo=False)
room_rt = {k: dict(walls=[], floors=[],
                   wall_color=DEFAULT_COLORS[k][0], floor_color=DEFAULT_COLORS[k][1])
           for k in ROOMS}
ITEMS = []
LIT = {}                  # everything that follows day / night / brightness
WALLS = []                # (entity, meta) for the interior "cutaway" feature
FACADE_SKINS = []         # exterior render pieces (recoloured by the photo studio)
WATERS = []
BUILD_PARENT = [None]
drag_off = [0.0, 0.0]
cut_active = [False]
sun = None
amb = None
sky = None
water_t = [0.0]

world = Entity()
level_root = {0: Entity(parent=world), 1: Entity(parent=world)}
roof_group = Entity(parent=world)
photo_root = Entity(enabled=False)
real_room_root = Entity(enabled=False)
REAL_ROOM = dict(active=False, kind='classroom', width=8.0, depth=7.0, height=3.2, photo_path=None, photo_texture=None, wall_color=(232, 229, 220), floor_color=(190, 185, 174))


# =====================================================================
# 5. COLOUR / LIGHTING HELPERS
# =====================================================================
def rgba(t):
    a = t[3] if len(t) > 3 else 255
    return color.Color(t[0] / 255, t[1] / 255, t[2] / 255, a / 255)


def light_mult():
    if USE_SHADERS:                      # real lights do the dimming; only add a night tint
        return (0.80, 0.86, 1.0) if state['night'] else (1.0, 1.0, 1.0)
    base = (0.30, 0.34, 0.52) if state['night'] else (1.0, 0.98, 0.94)
    return tuple(c * state['brightness'] for c in base)


def paint(e):
    if e.ab_emissive:
        day, night = e.ab_emissive
        e.color = rgba(night if state['night'] else day)
        return
    m = light_mult()
    if e.ab_photo:                       # photo facade is unlit: keep its true colours
        f = min(1.25, state['brightness'])
        m = tuple(c * f for c in ((0.36, 0.40, 0.58) if state['night'] else (1.0, 1.0, 1.0)))
    r, g, b = e.ab_base[:3]
    a = e.ab_base[3] if len(e.ab_base) > 3 else 255
    e.color = color.Color(min(1.0, r / 255 * m[0]), min(1.0, g / 255 * m[1]),
                          min(1.0, b / 255 * m[2]), a / 255)


def paint_all():
    for e in LIT.values():
        paint(e)


def sun_dir():
    """Direction the sunlight travels, from the time-of-day slider (0 = morning, 1 = evening)."""
    t = state['sun_t']
    el = math.radians(14 + 52 * math.sin(math.pi * t))
    az = math.radians(-70 + 140 * t)
    return Vec3(-math.sin(az) * math.cos(el), -math.sin(el), math.cos(az) * math.cos(el))


def aim_sun():
    if sun is None:
        return
    try:
        sun.look_at(sun_dir())
    except Exception:
        pass
    try:
        sun.update_bounds(photo_root if state['photo'] else world)
    except Exception:
        pass


def apply_lighting():
    n, b = state['night'], state['brightness']
    h = math.sin(math.pi * state['sun_t'])           # 0 = low sun .. 1 = high sun
    if sun is not None:
        try:
            if n:
                s, k = SUN_NIGHT, 1.0
            else:
                warm = 1.0 - h
                s = (SUN_DAY[0], SUN_DAY[1] - 0.22 * warm, SUN_DAY[2] - 0.42 * warm)
                k = 0.65 + 0.35 * h
            a = AMB_NIGHT if n else AMB_DAY
            sun.color = color.Color(s[0] * b * k, s[1] * b * k, s[2] * b * k, 1)
            amb.color = color.Color(a[0] * b, a[1] * b, a[2] * b, 1)
        except Exception:
            pass
    if sky is not None:
        k = min(1.0, b)
        sky.color = rgba((int(26 * k), int(34 * k), int(70 * k)) if n else (255, 255, 255))
    window.color = rgba((10, 14, 30) if n else (150, 195, 235))
    stars_root.enabled = n
    moon.enabled = n
    paint_all()


def mk(pos, scl, col, parent=None, model='cube', emissive=None, collider=None,
       tex=None, tile=None, lit=True, meta=None, photo=False, **kw):
    """Create one scene entity that follows the lighting system."""
    par = parent if parent is not None else (BUILD_PARENT[0] if BUILD_PARENT[0] is not None else world)
    e = Entity(model=model, parent=par, position=pos, scale=scl, **kw)
    t = TEX.get(tex) if tex else None
    if t is not None:
        e.texture = t
        if tile:
            e.texture_scale = Vec2(tile[0], tile[1])
    translucent = len(col) > 3 and col[3] < 250
    if USE_SHADERS and lit and not emissive and not translucent and not photo:
        e.shader = lit_with_shadows_shader
    if collider:
        e.collider = collider
    e.ab_base = col
    e.ab_emissive = emissive
    e.ab_photo = photo
    LIT[id(e)] = e
    if meta is not None:
        WALLS.append((e, meta))
    paint(e)
    return e


def rect_piece(x0, x1, z0, z1, y, h, col, tex=None, ts=2.2, **kw):
    return mk(((x0 + x1) / 2, y, (z0 + z1) / 2), (x1 - x0, h, z1 - z0), col,
              tex=tex, tile=((x1 - x0) / ts, (z1 - z0) / ts), **kw)


# =====================================================================
# 6. HOUSE CONSTRUCTION
# =====================================================================
def wall_pos(orient, plane, a, y, length, h, thick):
    if orient == 'x':
        return (a, y, plane), (length, h, thick)
    return (plane, y, a), (thick, h, length)


def skin_style(level, side, mid):
    """Facade finish for exterior walls: (colour, texture)."""
    render, stone, wood = RENDER_COL, (150, 146, 140), (196, 150, 108)
    if level == 0:
        if side == 'S':
            return (stone, 'stone') if mid < 1 else (wood, 'slats')
        return render, 'plaster'
    if side == 'S':
        return (render, 'plaster') if mid < 1 else ((70, 74, 82), 'concrete')
    if side in ('E', 'W'):
        return wood, 'slats'
    return render, 'plaster'


def fill_opening(kind, orient, plane, inward, c, w, yb, yt, meta):
    ym, h = (yb + yt) / 2, yt - yb
    ft = 0.06
    fd = WALL_T + 0.17

    def bar(a, y, length, hh, thick=fd, col=DARK):
        pos, scl = wall_pos(orient, plane, a, y, length, hh, thick)
        return mk(pos, scl, col, meta=meta)

    if kind in ('window', 'tall_window', 'high_window', 'glass_door'):
        pos, scl = wall_pos(orient, plane, c, ym, w - 2 * ft, h - 2 * ft, 0.05)
        mk(pos, scl, GLASS_DAY, emissive=(GLASS_DAY, GLASS_NIGHT), meta=meta)
        bar(c, yt - ft / 2, w, ft)
        bar(c, yb + ft / 2, w, ft)
        bar(c - w / 2 + ft / 2, ym, ft, h)
        bar(c + w / 2 - ft / 2, ym, ft, h)
        if w > 1.5:
            bar(c, ym, 0.04, h - 2 * ft, thick=0.08)
        if kind == 'glass_door':
            bar(c + 0.12, ym, 0.03, 0.9, thick=0.12, col=STEEL)       # handle
    else:
        bar(c - w / 2 + ft / 2, ym, ft, h, col=WOOD_DARK)
        bar(c + w / 2 - ft / 2, ym, ft, h, col=WOOD_DARK)
        bar(c, yt - ft / 2, w, ft, col=WOOD_DARK)
        if kind == 'main_door':
            pos, scl = wall_pos(orient, plane, c, ym - ft / 2, w - 2 * ft, h - ft, 0.07)
            mk(pos, scl, WOOD, tex='slats', tile=(1, 1), meta=meta)
            pos, scl = wall_pos(orient, plane - inward * 0.07, c + w / 2 - 0.2, ym, 0.04, 0.9, 0.05)
            mk(pos, scl, STEEL, meta=meta)


def build_wall(key, side, orient, fixed, a0, a1, inward, openings):
    L = ROOMS[key]['level']
    ly = LEVEL_Y[L]
    plane = fixed + inward * WALL_T / 2
    y0, y1 = WALL_Y0 + ly, WALL_Y0 + ly + WALL_H
    col = PALETTE[room_rt[key]['wall_color']][1]
    exterior = abs(fixed - EXT[side]) < 1e-6
    meta = dict(level=L, orient=orient, plane=plane, a0=a0, a1=a1)

    def seg(s0, s1, ya, yb):
        if s1 - s0 < 0.02 or yb - ya < 0.02:
            return
        pos, scl = wall_pos(orient, plane, (s0 + s1) / 2, (ya + yb) / 2, s1 - s0, yb - ya, WALL_T)
        room_rt[key]['walls'].append(mk(pos, scl, col, tex='plaster',
                                        tile=((s1 - s0) / 2.5, (yb - ya) / 2.5), meta=meta))
        if exterior:
            e0, e1 = s0, s1
            if orient == 'x':
                if abs(s0 - HOUSE[0]) < 1e-6:
                    e0 -= 0.07
                if abs(s1 - HOUSE[1]) < 1e-6:
                    e1 += 0.07
            else:
                if abs(s0 - (HOUSE[2] + WALL_T)) < 1e-6:
                    e0 -= WALL_T
                if abs(s1 - (HOUSE[3] - WALL_T)) < 1e-6:
                    e1 += WALL_T
            sp = fixed - inward * 0.035
            pos, scl = wall_pos(orient, sp, (e0 + e1) / 2, (ya + yb) / 2, e1 - e0, yb - ya, 0.07)
            scol, stex = skin_style(L, side, (s0 + s1) / 2)
            div = 2.5 if stex == 'plaster' else 2.0
            sk = mk(pos, scl, scol, tex=stex,
                    tile=((e1 - e0) / div, (yb - ya) / div) if stex else None, meta=meta)
            if stex == 'plaster':
                FACADE_SKINS.append(sk)

    cursor = a0
    for kind, c, w in sorted(openings, key=lambda o: o[1]):
        o0, o1 = c - w / 2, c + w / 2
        bz, tz = OPEN_Z[kind]
        bottom, top = y0 + bz, y0 + tz
        seg(cursor, o0, y0, y1)
        if bottom > y0:
            seg(o0, o1, y0, bottom)
        seg(o0, o1, top, y1)
        fill_opening(kind, orient, plane, inward, c, w, bottom, top, meta)
        cursor = o1
    seg(cursor, a1, y0, y1)


def build_room(key):
    cfg = ROOMS[key]
    L = cfg['level']
    BUILD_PARENT[0] = level_root[L]
    x0, x1, z0, z1 = cfg['rect']
    spans = [(x0, x1)]
    if key == 'landing':                       # the stair opening has no floor
        spans = [(x0, STAIR[0]), (STAIR[1], x1)]
    for a, b in spans:
        fl = mk(((a + b) / 2, 0.12 + LEVEL_Y[L], (z0 + z1) / 2), (b - a, 0.04, z1 - z0),
                PALETTE[room_rt[key]['floor_color']][1], collider='box',
                tex=cfg['tex'], tile=((b - a) / 2.4, (z1 - z0) / 2.4))
        fl.ab_room = key
        room_rt[key]['floors'].append(fl)
        if L == 1:                             # structural slab = ceiling of the room below
            mk(((a + b) / 2, 3.3, (z0 + z1) / 2), (b - a, 0.4, z1 - z0), (232, 230, 224),
               tex='plaster', tile=((b - a) / 2.5, (z1 - z0) / 2.5))
    has_ns = key not in NO_NS
    trim = WALL_T if has_ns else 0.0
    sides = {'S': ('x', z0, x0, x1, 1), 'N': ('x', z1, x0, x1, -1),
             'W': ('z', x0, z0 + trim, z1 - trim, 1), 'E': ('z', x1, z0 + trim, z1 - trim, -1)}
    for side in ('S', 'N', 'W', 'E'):
        if not has_ns and side in ('S', 'N'):
            continue
        orient, fixed, a0, a1, inward = sides[side]
        build_wall(key, side, orient, fixed, a0, a1, inward, OPENINGS.get((key, side), []))


def build_stairs():
    BUILD_PARENT[0] = level_root[0]
    n = 17
    xs, xe = STAIR[1], STAIR[0]
    td, rise = (xs - xe) / n, STOREY / n
    for i in range(n):
        top = FLOOR_TOP + (i + 1) * rise
        xc = xs - (i + 0.5) * td
        h = top - FLOOR_TOP
        mk((xc, FLOOR_TOP + (h - 0.06) / 2, 0), (td, h - 0.06, 1.96), (236, 234, 228),
           tex='plaster', tile=(1, 1))
        mk((xc, top - 0.03, 0), (td + 0.04, 0.06, 1.96), (190, 146, 104), tex='wood', tile=(1, 1))
    BUILD_PARENT[0] = level_root[1]                # glass guard at the far end of the opening
    y = floor_y(1)
    mk((STAIR[1] + 0.02, y + 0.5, 0), (0.04, 1.0, 1.96), GLASS_DAY, emissive=(GLASS_DAY, GLASS_NIGHT))
    mk((STAIR[1] + 0.02, y + 1.02, 0), (0.06, 0.04, 1.96), STEEL)


def build_balcony():
    BUILD_PARENT[0] = level_root[1]
    mk((-3.5, 3.39, -7.0), (9.8, 0.3, 2.0), (242, 240, 234), tex='plaster', tile=(4, 1))   # slab
    gy = floor_y(1) + 0.55
    mk((-3.5, gy, -7.95), (9.7, 1.1, 0.04), GLASS_DAY, emissive=(GLASS_DAY, GLASS_NIGHT))
    mk((-3.5, gy + 0.56, -7.95), (9.76, 0.04, 0.07), STEEL)
    for sx in (-8.35, 1.35):
        mk((sx, gy, -7.0), (0.04, 1.1, 1.9), GLASS_DAY, emissive=(GLASS_DAY, GLASS_NIGHT))
        mk((sx, gy + 0.56, -7.0), (0.07, 0.04, 1.96), STEEL)
    for lx in (-7.2, -4.6, -2.0, 0.4):                                              # down-lights
        mk((lx, 3.235, -7.0), (0.26, 0.03, 0.26), (236, 236, 228), model='sphere',
           emissive=((236, 236, 228), (255, 226, 160)))
    BUILD_PARENT[0] = level_root[0]
    for cx in (-8.2, 1.2):                                                          # porch columns
        mk((cx, 1.66, -7.85), (0.18, 3.16, 0.18), (236, 236, 232), tex='plaster', tile=(1, 3))


def build_roof():
    BUILD_PARENT[0] = roof_group
    top = ROOF_Y
    mk((0, top + 0.15, 0), (17.0, 0.3, 13.0), (78, 82, 90), tex='concrete', tile=(6, 5))
    fc = (244, 242, 236)
    for sz in (-1, 1):
        mk((0, top + 0.1, sz * 6.65), (17.6, 0.42, 0.3), fc, tex='plaster', tile=(6, 1))
    for sx in (-1, 1):
        mk((sx * 8.65, top + 0.1, 0), (0.3, 0.42, 13.0), fc, tex='plaster', tile=(1, 5))
    for k in range(3):                                                              # solar panels
        for j in range(2):
            mk((-4.5 + k * 3.0, top + 0.36, 1.6 + j * 2.0), (2.6, 0.05, 1.8), (24, 42, 86),
               rotation_x=-12)
    mk((5.0, top + 0.33, -3.0), (2.4, 0.06, 1.6), GLASS_DAY, emissive=(GLASS_DAY, GLASS_NIGHT))


def build_ceiling_lights():
    for key, cfg in ROOMS.items():
        L = cfg['level']
        x0, x1, z0, z1 = cfg['rect']
        par = level_root[1] if L == 0 else roof_group
        y = 3.085 if L == 0 else ROOF_Y - 0.015
        w, d = x1 - x0, z1 - z0
        nx, nz = max(1, round(w / 3.0)), max(1, round(d / 3.0))
        if key in NO_NS:
            nz = 1
        for i in range(nx):
            for j in range(nz):
                x, z = x0 + w * (i + 0.5) / nx, z0 + d * (j + 0.5) / nz
                if key == 'hallway' and STAIR[0] - 0.2 < x < STAIR[1] + 0.2:
                    continue
                mk((x, y, z), (0.3, 0.03, 0.3), (236, 236, 228), parent=par, model='sphere',
                   emissive=((236, 236, 228), (255, 226, 160)))


# ---------------- outdoor world ----------------
POOL = (11.6, 16.6, -5.0, 4.0)
DECK = (8.0, 21.0, -8.0, 7.5)
GRASS = (104, 138, 84)


def tree(x, z, s=1.0):
    rnd = random.Random(int(x * 13 + z * 7))
    mk((x, 1.25 * s, z), (0.28 * s, 2.6 * s, 0.28 * s), WOOD_DARK, tex='wood', tile=(1, 2))
    shades = [GREEN, GREEN_L, GREEN_D]
    for i in range(8):                                   # irregular canopy of overlapping blobs
        a, r = rnd.uniform(0, 6.283), rnd.uniform(0.15, 1.0) * s
        sc = rnd.uniform(1.3, 2.3) * s
        mk((x + math.cos(a) * r, (2.9 + rnd.uniform(-0.2, 1.4)) * s, z + math.sin(a) * r),
           (sc, sc * 0.88, sc), shades[i % 3], model='sphere', tex='foliage', tile=(2, 2))


def lounger(x, z, rot):
    r = Entity(parent=world, position=(x, 0.08, z), rotation_y=rot)
    mk((0, 0.18, 0), (0.7, 0.05, 1.9), (236, 236, 232), parent=r, tex='fabric', tile=(2, 4))
    for i in range(4):                                       # stepped, reclined backrest
        mk((0, 0.26 + i * 0.07, -0.5 - i * 0.14), (0.7, 0.07, 0.3), (246, 246, 242), parent=r,
           tex='fabric', tile=(2, 1))
    mk((0, 0.08, 0.4), (0.62, 0.16, 0.06), (150, 154, 160), parent=r)
    mk((0, 0.08, -0.4), (0.62, 0.16, 0.06), (150, 154, 160), parent=r)


def parasol(x, z):
    mk((x, 1.2, z), (0.06, 2.4, 0.06), STEEL)
    mk((x, 2.4, z), (2.8, 0.22, 2.8), (236, 228, 210), model='sphere', tex='fabric', tile=(4, 4))


def car(x, z):
    mk((x, 0.55, z), (1.9, 0.6, 4.4), (46, 50, 58))
    mk((x, 1.1, z - 0.1), (1.7, 0.5, 2.3), (30, 42, 62))
    for sx in (-0.95, 0.95):
        for sz in (-1.4, 1.4):
            mk((x + sx, 0.1, z + sz), (0.3, 0.72, 0.72), (22, 22, 26), model='sphere')
    for sx in (-0.6, 0.6):
        mk((x + sx, 0.6, z - 2.2), (0.3, 0.1, 0.05), (255, 244, 220), emissive=((240, 236, 224), (255, 240, 190)))


def build_ground(L, hole=None, col=GRASS, y=-0.3):
    if hole is None:
        rects = [(-L, L, -L, L)]
    else:
        px0, px1, pz0, pz1 = hole
        rects = [(-L, px0, -L, L), (px1, L, -L, L), (px0, px1, -L, pz0), (px0, px1, pz1, L)]
    for a, b, c, d in rects:
        mk(((a + b) / 2, y, (c + d) / 2), (b - a, 1, d - c), col, model='plane',
           tex='grass', tile=((b - a) / 3, (d - c) / 3))


def build_pool(pool, deck):
    """Swimming pool with deck, basin, coping, water surface and underwater lights."""
    px0, px1, pz0, pz1 = pool
    dx0, dx1, dz0, dz1 = deck
    dcol = (190, 148, 106)
    for r in ((dx0, px0, dz0, dz1), (px1, dx1, dz0, dz1), (px0, px1, dz0, pz0), (px0, px1, pz1, dz1)):
        rect_piece(*r[:4], 0.0, 0.16, dcol, tex='deck')
    mk(((px0 + px1) / 2, -1.25, (pz0 + pz1) / 2), (px1 - px0, 0.1, pz1 - pz0), (110, 205, 224),
       emissive=((110, 205, 224), (50, 160, 205)))
    cw = 0.3
    for cx, cz, sx, sz in ((px0 - cw / 2, (pz0 + pz1) / 2, cw, pz1 - pz0 + 2 * cw),
                           (px1 + cw / 2, (pz0 + pz1) / 2, cw, pz1 - pz0 + 2 * cw),
                           ((px0 + px1) / 2, pz0 - cw / 2, px1 - px0, cw),
                           ((px0 + px1) / 2, pz1 + cw / 2, px1 - px0, cw)):
        mk((cx, -0.6, cz), (sx, 1.4, sz), (232, 238, 238), tex='plaster', tile=(2, 1))
    w = mk(((px0 + px1) / 2, -0.12, (pz0 + pz1) / 2), (px1 - px0, 1, pz1 - pz0), (255, 255, 255, 170),
           model='plane', tex='water', tile=(3, 4),
           emissive=((120, 205, 228, 165), (50, 150, 205, 185)))
    zm = (pz0 + pz1) / 2
    for lz in (zm - 3.0, zm, zm + 3.0):
        mk((px0 + 0.03, -0.7, lz), (0.05, 0.22, 0.4), (255, 255, 255),
           emissive=((200, 240, 250), (110, 235, 255)))
        mk((px1 - 0.03, -0.7, lz), (0.05, 0.22, 0.4), (255, 255, 255),
           emissive=((200, 240, 250), (110, 235, 255)))
    return w


def build_environment():
    BUILD_PARENT[0] = world
    build_ground(45, hole=POOL)
    far = Entity(model='plane', scale=(900, 1, 900), position=(0, -0.32, 0))      # horizon ground
    far.color = rgba((82, 112, 72))
    mk((0, -0.1, 0), (17, 0.4, 13), (150, 150, 146), tex='concrete', tile=(6, 5))   # plinth
    mk((-3.2, 0.0, -6.7), (2.4, 0.2, 1.0), (188, 186, 180), tex='stone', tile=(1, 1))   # entrance steps
    mk((-3.2, -0.27, -12.5), (2.2, 0.05, 11), (206, 202, 190), tex='concrete', tile=(1, 5))
    mk((-12.5, -0.27, -8), (5.2, 0.04, 17), (62, 64, 70), tex='concrete', tile=(2, 6))
    mk((-3, 0.0, 7.2), (11, 0.16, 2.4), (190, 186, 176), tex='concrete', tile=(4, 1))   # back patio
    WATERS.append(build_pool(POOL, DECK))
    for lz in (-5.0, -2.0, 1.0):
        lounger(18.5, lz, 90)
    parasol(19.9, -3.5)
    parasol(19.9, 2.5)
    mk((14.1, 0.35, 6.7), (3.0, 0.4, 0.9), (84, 90, 100), tex='fabric', tile=(3, 1))
    mk((14.1, 0.8, 7.0), (3.0, 0.55, 0.25), (96, 102, 112), tex='fabric', tile=(3, 1))
    for sx in (-1.4, 1.4):
        mk((14.1 + sx, 0.55, 6.7), (0.2, 0.5, 0.9), (84, 90, 100))
    mk((14.1, 0.28, 5.0), (1.1, 0.32, 1.1), (58, 60, 66), tex='stone', tile=(1, 1))   # fire pit
    mk((14.1, 0.5, 5.0), (0.6, 0.18, 0.6), (255, 150, 60), model='sphere',
       emissive=((120, 90, 70), (255, 150, 60)))
    mk((9.8, 0.55, -4.8), (0.9, 0.05, 0.9), WOOD, model='sphere', tex='wood')        # bistro set
    mk((9.8, 0.3, -4.8), (0.06, 0.5, 0.06), DARK)
    for cz in (-5.7, -3.9):
        mk((9.8, 0.35, cz), (0.45, 0.06, 0.45), (210, 205, 195))
        mk((9.8, 0.17, cz), (0.05, 0.3, 0.05), DARK)
    for bx in (12.5, 15.7):                                                       # planters
        mk((bx, 0.45, -7.2), (0.9, 0.7, 0.9), (70, 74, 82), tex='concrete', tile=(1, 1))
        mk((bx, 1.1, -7.2), (1.0, 1.0, 1.0), GREEN, model='sphere', tex='foliage', tile=(2, 2))
    for hx, hz, sx, sz in ((-9.3, 0.0, 0.7, 11), (-9.3, 6.5, 0.7, 1.5), (9.0, 8.6, 18, 0.8)):
        mk((hx, 0.55, hz), (sx, 1.1, sz), GREEN_D, tex='foliage', tile=(max(sx, sz) / 1.5, 1))
    for tx, tz, ts in ((-14, 4, 1.2), (-12, 13, 1.1), (-15, -8, 1.0), (26, -4, 1.2), (27, 8, 1.1),
                       (24, -16, 1.0), (-4, 17, 1.3), (6, 18, 1.0), (14, 16, 1.2), (-22, -2, 1.3)):
        tree(tx, tz, ts)
    for lx, lz in ((-4.7, -9.5), (-1.7, -9.5), (-4.7, -14.5), (-1.7, -14.5)):
        mk((lx, 0.35, lz), (0.12, 0.7, 0.12), DARK)
        mk((lx, 0.78, lz), (0.2, 0.2, 0.2), (240, 236, 224), model='sphere',
           emissive=((240, 236, 224), (255, 214, 140)))
    for lx, lz in ((-9.8, 11.2), (21.5, 8.0), (21.5, -8.0)):
        mk((lx, 0.4, lz), (0.2, 0.8, 0.2), (240, 236, 224), emissive=((240, 236, 224), (255, 214, 140)))
    car(-12.5, -9.0)


# =====================================================================
# 7. FURNITURE  (each item = one logical object built from primitives)
# =====================================================================
FOOT = {
    'sofa': (2.2, 0.95), 'sectional_sofa': (2.9, 1.7), 'armchair': (0.9, 0.9),
    'coffee_table': (1.2, 0.7), 'tv_unit': (1.8, 0.5), 'rug': (2.8, 1.9), 'floor_lamp': (0.4, 0.4),
    'plant': (0.6, 0.6), 'bookshelf': (1.6, 0.4), 'desk': (1.5, 0.7), 'office_chair': (0.6, 0.6),
    'bed': (2.0, 2.2), 'bedside_table': (0.5, 0.45), 'wardrobe': (2.0, 0.6),
    'kitchen_counter': (3.0, 0.65), 'sink_counter': (2.0, 0.65), 'fridge': (0.8, 0.75),
    'kitchen_island': (2.2, 0.9), 'bar_stool': (0.4, 0.4), 'dining_table': (1.7, 2.0),
    'chair': (0.5, 0.5), 'washbasin': (0.6, 0.5), 'toilet': (0.5, 0.7), 'shower': (1.4, 1.4),
    'bathtub': (1.7, 0.8),
}
LABEL = {k: k.replace('_', ' ').title() for k in FOOT}


def half_extents(kind, rot):
    w, d = FOOT[kind]
    r = math.radians(rot)
    return (abs(math.cos(r)) * w / 2 + abs(math.sin(r)) * d / 2,
            abs(math.sin(r)) * w / 2 + abs(math.cos(r)) * d / 2)


class Item:
    """A furniture item: one root entity + several child parts."""

    def __init__(self, kind, x, z, rot=0.0, level=0, elev=0.0):
        self.kind, self.level = kind, level
        self.elev = elev
        self.root = Entity(parent=level_root[level], position=(x, floor_y(level) + elev, z), rotation_y=rot)
        self.tx, self.tz, self.trot = x, z, rot % 360
        self.parts = []
        BUILDERS[kind](self)
        w, d = FOOT[kind]
        self.marker = mk((0, 0.04, 0), (w + 0.35, 0.02, d + 0.35), (255, 205, 70),
                         parent=self.root, emissive=((255, 205, 70), (255, 205, 70)))
        self.marker.enabled = False
        ITEMS.append(self)

    def part(self, pos, scl, col, model='cube', emissive=None):
        tex = tile = None
        if not emissive and len(col) == 3:
            hit = AUTO_TEX.get(tuple(col))
            if hit:
                tex, tile = hit
        e = mk(pos, scl, col, parent=self.root, model=model, emissive=emissive, collider='box',
               tex=tex, tile=tile)
        e.ab_item = self
        self.parts.append(e)
        return e

    def set_selected(self, flag):
        self.marker.enabled = flag

    def set_colliders(self, flag):
        for e in self.parts:
            try:
                e.collision = flag
            except Exception:
                pass

    def destroy_all(self):
        for e in self.parts + [self.marker]:
            LIT.pop(id(e), None)
        destroy(self.root)


def _chair(it, x, z, back):
    P = it.part
    P((x, 0.45, z), (0.42, 0.06, 0.42), (214, 176, 112))
    P((x, 0.72, z + back * 0.2), (0.42, 0.5, 0.05), (214, 176, 112))
    for lx in (-0.17, 0.17):
        for lz in (-0.17, 0.17):
            P((x + lx, 0.21, z + lz), (0.05, 0.42, 0.05), DARK)


def b_sofa(it):
    P = it.part
    c1, c2, cu = (112, 118, 128), (130, 136, 146), (214, 204, 190)
    P((0, 0.18, 0), (2.2, 0.36, 0.95), (60, 64, 72))
    P((0, 0.46, 0.08), (1.9, 0.2, 0.75), c2)
    P((0, 0.72, -0.38), (2.2, 0.6, 0.2), c1)
    for sx in (-1, 1):
        P((sx * 1.02, 0.5, 0), (0.16, 0.55, 0.95), c1)
    for sx in (-0.5, 0.5):
        P((sx, 0.62, -0.22), (0.6, 0.34, 0.14), cu)


def b_sectional_sofa(it):
    P = it.part
    c1, c2, cu = (112, 118, 128), (130, 136, 146), (214, 204, 190)
    P((0, 0.18, -0.375), (2.9, 0.36, 0.95), (60, 64, 72))
    P((0.975, 0.18, 0.475), (0.95, 0.36, 0.75), (60, 64, 72))
    P((-0.1, 0.46, -0.28), (2.5, 0.2, 0.75), c2)
    P((0.975, 0.46, 0.47), (0.8, 0.2, 0.7), c2)
    P((0, 0.72, -0.75), (2.9, 0.6, 0.2), c1)
    P((-1.38, 0.5, -0.375), (0.16, 0.55, 0.95), c1)
    P((1.37, 0.5, 0.475), (0.16, 0.5, 0.75), c1)
    for sx in (-0.9, 0.0, 0.9):
        P((sx, 0.62, -0.58), (0.7, 0.34, 0.14), cu)


def b_armchair(it):
    P = it.part
    P((0, 0.18, 0), (0.9, 0.36, 0.9), (150, 112, 80))
    P((0, 0.45, 0.08), (0.7, 0.18, 0.65), (200, 168, 128))
    P((0, 0.7, -0.36), (0.9, 0.55, 0.18), (176, 138, 100))
    for sx in (-0.38, 0.38):
        P((sx, 0.5, 0), (0.14, 0.5, 0.9), (176, 138, 100))


def b_coffee_table(it):
    P = it.part
    P((0, 0.4, 0), (1.2, 0.05, 0.7), (236, 236, 232))
    P((0, 0.16, 0), (1.0, 0.04, 0.5), (60, 64, 72))
    for sx in (-1, 1):
        P((sx * 0.45, 0.2, 0), (0.05, 0.36, 0.5), GOLD)
    P((-0.2, 0.44, 0.05), (0.3, 0.03, 0.22), (70, 100, 140))
    P((0.3, 0.5, -0.1), (0.14, 0.14, 0.14), GREEN, model='sphere')


def b_tv_unit(it):
    P = it.part
    P((0, 0.3, 0), (1.8, 0.4, 0.45), WOOD)
    for sx in (-0.8, 0.8):
        P((sx, 0.05, 0), (0.05, 0.1, 0.4), DARK)
    P((0, 1.1, -0.1), (1.4, 0.8, 0.04), (14, 16, 22), emissive=((14, 16, 22), (40, 62, 96)))


def b_rug(it):
    P = it.part
    P((0, 0.012, 0), (2.8, 0.024, 1.9), (206, 196, 180))
    P((0, 0.026, 0), (2.5, 0.016, 1.6), (150, 136, 120))
    P((0, 0.036, 0), (2.2, 0.016, 1.3), (214, 204, 190))


def b_floor_lamp(it):
    P = it.part
    P((0, 0.015, 0), (0.3, 0.03, 0.3), DARK, model='sphere')
    P((0, 0.75, 0), (0.03, 1.5, 0.03), DARK)
    P((0, 1.5, 0), (0.38, 0.32, 0.38), (245, 232, 200), model='sphere',
      emissive=((240, 226, 192), (255, 214, 120)))


def b_plant(it):
    P = it.part
    P((0, 0.2, 0), (0.4, 0.4, 0.4), (176, 104, 74))
    P((0, 0.75, 0), (0.7, 0.8, 0.7), GREEN, model='sphere')
    P((0.1, 1.1, 0.05), (0.45, 0.5, 0.45), GREEN_L, model='sphere')


def b_bookshelf(it):
    P = it.part
    P((0, 1.0, -0.185), (1.6, 2.0, 0.03), WOOD_DARK)
    for sx in (-0.78, 0.78):
        P((sx, 1.0, 0), (0.04, 2.0, 0.4), WOOD)
    cols = [(150, 60, 56), (70, 100, 140), (210, 190, 140), (80, 120, 90), (200, 200, 196)]
    for i, y in enumerate((0.04, 0.55, 1.05, 1.55, 1.98)):
        P((0, y, 0), (1.56, 0.04, 0.38), WOOD)
        if i < 4:
            for j in range(2):
                P((-0.4 + j * 0.8, y + 0.15, 0), (0.5 + 0.1 * j, 0.26, 0.22), cols[(i + j) % 5])


def b_desk(it):
    P = it.part
    P((0, 0.74, 0), (1.5, 0.04, 0.7), WOOD)
    for sx in (-0.72, 0.72):
        P((sx, 0.36, 0), (0.04, 0.72, 0.64), (230, 228, 222))
    P((0, 0.5, -0.3), (1.4, 0.4, 0.03), (230, 228, 222))
    P((0, 1.0, -0.2), (0.7, 0.4, 0.03), (14, 16, 22), emissive=((14, 16, 22), (50, 80, 120)))
    P((0, 0.85, -0.2), (0.05, 0.2, 0.05), STEEL)
    P((0, 0.765, 0.1), (0.4, 0.015, 0.14), (50, 54, 62))


def b_office_chair(it):
    P = it.part
    P((0, 0.08, 0), (0.55, 0.04, 0.55), DARK, model='sphere')
    P((0, 0.3, 0), (0.05, 0.34, 0.05), STEEL)
    P((0, 0.5, 0), (0.5, 0.08, 0.5), (60, 64, 72))
    P((0, 0.85, -0.25), (0.5, 0.6, 0.07), (60, 64, 72))


def b_bed(it):
    P = it.part
    P((0, 0.2, 0), (2.0, 0.3, 2.2), WOOD_DARK)
    P((0, 0.47, 0.05), (1.9, 0.24, 2.05), (240, 236, 228))
    P((0, 0.8, -1.05), (2.0, 1.2, 0.12), (128, 134, 146))
    for sx in (-1, 1):
        P((sx * 0.45, 0.68, -0.75), (0.7, 0.14, 0.4), (252, 250, 244))
    P((0, 0.61, 0.5), (1.92, 0.05, 1.1), (88, 112, 148))


def b_bedside_table(it):
    P = it.part
    P((0, 0.25, 0), (0.5, 0.5, 0.45), WOOD)
    P((0, 0.6, 0), (0.14, 0.18, 0.14), (255, 240, 200), emissive=((235, 225, 190), (255, 214, 120)))


def b_wardrobe(it):
    P = it.part
    P((0, 1.1, 0), (2.0, 2.2, 0.6), (232, 230, 224))
    for sx in (-0.5, 0.5):
        P((sx, 1.1, 0.31), (0.98, 2.1, 0.03), (190, 150, 110))
    for sx in (-0.06, 0.06):
        P((sx, 1.1, 0.34), (0.03, 0.5, 0.03), DARK)


def b_kitchen_counter(it):
    P = it.part
    P((0, 0.45, 0), (3.0, 0.9, 0.65), (232, 230, 224))
    P((0, 0.93, 0), (3.05, 0.06, 0.7), (50, 54, 62))
    for x in (-1.0, 0.0, 1.0):
        P((x, 0.45, 0.33), (0.02, 0.8, 0.02), DARK)
    P((-0.8, 0.97, 0), (0.5, 0.02, 0.4), (28, 28, 32))
    P((0.8, 1.45, -0.3), (0.9, 0.5, 0.04), (64, 68, 78))


def b_sink_counter(it):
    P = it.part
    P((0, 0.45, 0), (2.0, 0.9, 0.65), (232, 230, 224))
    P((0, 0.93, 0), (2.05, 0.06, 0.7), (50, 54, 62))
    P((0, 0.96, 0), (0.7, 0.03, 0.4), STEEL)
    P((0, 1.08, -0.2), (0.04, 0.25, 0.04), STEEL)
    P((0, 1.2, -0.1), (0.04, 0.04, 0.25), STEEL)


def b_fridge(it):
    P = it.part
    P((0, 0.95, 0), (0.8, 1.9, 0.75), (208, 212, 216))
    P((0, 1.35, 0.38), (0.78, 0.02, 0.02), DARK)
    P((0.3, 1.6, 0.39), (0.04, 0.4, 0.04), STEEL)
    P((0.3, 0.95, 0.39), (0.04, 0.4, 0.04), STEEL)


def b_kitchen_island(it):
    P = it.part
    P((0, 0.45, 0), (2.2, 0.9, 0.9), (232, 230, 224))
    P((0, 0.93, 0), (2.3, 0.06, 1.0), (50, 54, 62))
    P((0, 0.45, 0.46), (2.0, 0.7, 0.04), WOOD)


def b_bar_stool(it):
    P = it.part
    P((0, 0.02, 0), (0.36, 0.03, 0.36), DARK, model='sphere')
    P((0, 0.33, 0), (0.04, 0.65, 0.04), STEEL)
    P((0, 0.68, 0), (0.38, 0.07, 0.38), (60, 64, 72), model='sphere')


def b_dining_table(it):
    P = it.part
    P((0, 0.76, 0), (1.6, 0.05, 0.9), (180, 140, 100))
    for sx in (-1, 1):
        P((sx * 0.7, 0.38, 0), (0.07, 0.76, 0.7), DARK)
    for cx in (-0.45, 0.45):
        _chair(it, cx, 0.75, +1)
        _chair(it, cx, -0.75, -1)


def b_chair(it):
    _chair(it, 0, 0, -1)


def b_washbasin(it):
    P = it.part
    P((0, 0.4, 0), (0.45, 0.8, 0.4), (236, 234, 228))
    P((0, 0.85, 0.02), (0.6, 0.1, 0.45), WHITE)
    P((0, 1.02, -0.15), (0.04, 0.16, 0.04), STEEL)
    P((0, 1.5, -0.23), (0.6, 0.6, 0.03), (205, 228, 240), emissive=((205, 228, 240), (240, 240, 220)))


def b_toilet(it):
    P = it.part
    P((0, 0.45, -0.28), (0.4, 0.55, 0.18), WHITE)
    P((0, 0.22, 0.0), (0.38, 0.4, 0.55), WHITE)
    P((0, 0.43, 0.05), (0.4, 0.04, 0.5), (246, 246, 244))


def b_bathtub(it):
    P = it.part
    P((0, 0.27, 0), (1.7, 0.55, 0.8), WHITE)
    P((0, 0.56, 0), (1.5, 0.02, 0.6), (206, 230, 240))
    P((0.72, 0.8, -0.3), (0.04, 0.25, 0.04), STEEL)


def b_shower(it):
    P = it.part
    glass = (150, 205, 235, 90)
    P((0, 0.04, 0), (1.4, 0.08, 1.4), (200, 205, 210))
    P((0, 1.0, 0.68), (1.36, 1.9, 0.04), glass, emissive=(glass, (210, 230, 240, 120)))
    P((0.68, 1.0, 0), (0.04, 1.9, 1.36), glass, emissive=(glass, (210, 230, 240, 120)))
    P((-0.55, 1.1, -0.62), (0.04, 2.0, 0.04), STEEL)
    P((-0.55, 2.0, -0.45), (0.25, 0.04, 0.25), STEEL)


BUILDERS = {
    'sofa': b_sofa, 'sectional_sofa': b_sectional_sofa, 'armchair': b_armchair,
    'coffee_table': b_coffee_table, 'tv_unit': b_tv_unit, 'rug': b_rug, 'floor_lamp': b_floor_lamp,
    'plant': b_plant, 'bookshelf': b_bookshelf, 'desk': b_desk, 'office_chair': b_office_chair,
    'bed': b_bed, 'bedside_table': b_bedside_table, 'wardrobe': b_wardrobe,
    'kitchen_counter': b_kitchen_counter, 'sink_counter': b_sink_counter, 'fridge': b_fridge,
    'kitchen_island': b_kitchen_island, 'bar_stool': b_bar_stool, 'dining_table': b_dining_table,
    'chair': b_chair, 'washbasin': b_washbasin, 'toilet': b_toilet, 'shower': b_shower,
    'bathtub': b_bathtub,
}
assert set(BUILDERS) == set(FOOT), 'every furniture type needs a builder and a footprint'


# =====================================================================
# 8. SCENE ACTIONS (selection, views, colours, lighting, furniture editing)
# =====================================================================
def clampf(v, lo, hi):
    return (lo + hi) / 2 if lo > hi else max(lo, min(hi, v))


def room_at(x, z, level=0):
    best, bd = LEVEL_ROOMS[level][-1], 1e9
    for key in LEVEL_ROOMS[level]:
        x0, x1, z0, z1 = ROOMS[key]['rect']
        dx, dz = max(x0 - x, 0, x - x1), max(z0 - z, 0, z - z1)
        dd = dx * dx + dz * dz
        if dd == 0:
            return key
        if dd < bd:
            best, bd = key, dd
    return best


def constrain(it, x, z, rot):
    """Keep an item inside the room that its centre is in, clear of walls and stairs."""
    hw, hd = half_extents(it.kind, rot)
    key = room_at(x, z, it.level)
    x0, x1, z0, z1 = ROOMS[key]['rect']
    mx = WALL_T + 0.02
    mz = 0.02 if key in NO_NS else WALL_T + 0.02
    x = clampf(x, x0 + mx + hw, x1 - mx - hw)
    z = clampf(z, z0 + mz + hd, z1 - mz - hd)
    if key in NO_NS and STAIR[0] - hw < x < STAIR[1] + hw:
        left, right = STAIR[0] - hw, STAIR[1] + hw
        x = left if (right > x1 - mx - hw or abs(x - left) < abs(x - right)) else right
        x = clampf(x, x0 + mx + hw, x1 - mx - hw)
    return x, z


def set_status(msg):
    if 'status_text' in globals():
        status_text.text = msg


def focus_room(key):
    x0, x1, z0, z1 = ROOMS[key]['rect']
    cam['tx_t'], cam['tz_t'] = (x0 + x1) / 2, (z0 + z1) / 2
    cam['ty_t'] = LEVEL_Y[ROOMS[key]['level']] + 1.0
    cam['dist_t'] = 6 + max(x1 - x0, z1 - z0) * 0.8
    cam['pitch_t'] = 42


def focus_exterior():
    cam['tx_t'], cam['ty_t'], cam['tz_t'] = 4.0, 2.0, 0.0
    cam['dist_t'], cam['pitch_t'], cam['yaw_t'] = 34.0, 26.0, 24.0


def focus_photo():
    cam['tx_t'], cam['ty_t'], cam['tz_t'] = 0.0, 3.0, 0.0
    cam['dist_t'], cam['pitch_t'], cam['yaw_t'] = max(24.0, PHOTO['w'] * 1.9), 14.0, 0.0


def reset_view():
    if state['photo']:
        focus_photo()
    elif state['view'] == 'room':
        focus_room(state['room'])
    else:
        focus_exterior()


def pan_camera(right=0.0, fwd=0.0, up=0.0):
    """Move the point the camera looks at (right / forward on the ground plane, up in height)."""
    yaw = math.radians(cam['yaw'])
    cam['tx_t'] = max(-45, min(45, cam['tx_t'] + math.cos(yaw) * right - math.sin(yaw) * fwd))
    cam['tz_t'] = max(-45, min(45, cam['tz_t'] + math.sin(yaw) * right + math.cos(yaw) * fwd))
    cam['ty_t'] = max(0.2, min(10.0, cam['ty_t'] + up))


def apply_visibility():
    room_view = state['view'] == 'room'
    lvl = ROOMS[state['room']]['level']
    upper = state['upper'] and not (room_view and lvl == 0)
    level_root[1].enabled = upper
    roof_group.enabled = state['roof'] and upper and not room_view


def update_cutaway():
    """Hide the walls between the camera and the focused room (room view only)."""
    if state['photo'] or not (state['view'] == 'room' and state['cut']):
        if cut_active[0]:
            for e, _ in WALLS:
                if not e.enabled:
                    e.enabled = True
            cut_active[0] = False
        return
    cut_active[0] = True
    key = state['room']
    x0, x1, z0, z1 = ROOMS[key]['rect']
    lvl = ROOMS[key]['level']
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    camx, camz = camera.x, camera.z
    for e, m in WALLS:
        hide = False
        if m['level'] == lvl:
            if m['orient'] == 'x':
                lo, hi = sorted((camz, cz))
                hide = lo < m['plane'] < hi and min(m['a1'], x1) - max(m['a0'], x0) > 0.3
            else:
                lo, hi = sorted((camx, cx))
                hide = lo < m['plane'] < hi and min(m['a1'], z1) - max(m['a0'], z0) > 0.3
        if e.enabled == hide:
            e.enabled = not hide


def select_room(key, announce=True):
    state['room'] = key
    state['level'] = ROOMS[key]['level']
    x0, x1, z0, z1 = ROOMS[key]['rect']
    y, t = floor_y(state['level']) + 0.02, 0.08
    spec = [((x0 + x1) / 2, z0 + t / 2, x1 - x0, t), ((x0 + x1) / 2, z1 - t / 2, x1 - x0, t),
            (x0 + t / 2, (z0 + z1) / 2, t, z1 - z0), (x1 - t / 2, (z0 + z1) / 2, t, z1 - z0)]
    for e, (px, pz, sx, sz) in zip(room_marker, spec):
        e.position = (px, y, pz)
        e.scale = (sx, 0.02, sz)
        e.parent = level_root[state['level']]
        e.enabled = True
    if state['view'] == 'room':
        focus_room(key)
    apply_visibility()
    refresh_ui()
    if announce:
        set_status(f'Selected room: {ROOMS[key]["label"]}')


def set_level(level):
    if level == 1 and not state['upper']:
        state['upper'] = True
    it = state['item']
    if it is not None and it.level != level:
        select_item(None, announce=False)
    key = state['room'] if ROOMS[state['room']]['level'] == level else LEVEL_ROOMS[level][0]
    select_room(key, announce=False)
    set_status('Ground floor' if level == 0 else 'Upper floor')


def toggle_view():
    state['view'] = 'exterior' if state['view'] == 'room' else 'room'
    if state['view'] == 'room':
        focus_room(state['room'])
        set_status(f'Inside: {ROOMS[state["room"]]["label"]}  (drag furniture, right-drag to look around)')
    else:
        focus_exterior()
        set_status('Exterior view')
    apply_visibility()
    update_cutaway()
    refresh_ui()


def toggle_cut():
    state['cut'] = not state['cut']
    update_cutaway()
    refresh_ui()
    set_status('Wall cutaway ON' if state['cut'] else 'Wall cutaway OFF')


def toggle_snap():
    state['snap'] = not state['snap']
    refresh_ui()
    set_status('Snap to 25 cm grid: ' + ('ON' if state['snap'] else 'OFF'))


def toggle_upper():
    state['upper'] = not state['upper']
    if not state['upper'] and state['level'] == 1:
        set_level(0)
    apply_visibility()
    refresh_ui()
    set_status('Upper floor shown' if state['upper'] else 'Upper floor hidden')


def select_item(it, announce=True):
    old = state['item']
    if old is not None and old in ITEMS:
        old.set_selected(False)
    state['item'] = it
    if it is not None:
        it.set_selected(True)
        key = room_at(it.root.x, it.root.z, it.level)
        if key != state['room']:
            select_room(key, announce=False)
        if announce:
            set_status(f'Selected: {LABEL[it.kind]}  - drag it, or I J K L to move, Q E to rotate, X to remove')
    refresh_ui()


def set_room_color(key, which, ckey, announce=True):
    rt = room_rt[key]
    rt[which + '_color'] = ckey
    col = PALETTE[ckey][1]
    for e in (rt['walls'] if which == 'wall' else rt['floors']):
        e.ab_base = col
        paint(e)
    refresh_ui()
    if announce:
        set_status(f'{ROOMS[key]["label"]} {which}s: {PALETTE[ckey][0]}')


def set_facade_color(rgb):
    for e in FACADE_SKINS:
        e.ab_base = tuple(rgb)
        paint(e)


def set_night(flag):
    state['night'] = flag
    apply_lighting()
    refresh_ui()
    set_status('Night mode' if flag else 'Day mode')


def set_brightness(value):
    state['brightness'] = round(max(0.5, min(1.5, value)), 2)
    apply_lighting()
    refresh_ui()
    set_status(f'Brightness {int(state["brightness"] * 100)}%')


def set_sun(value, announce=True):
    state['sun_t'] = round(max(0.0, min(1.0, value)), 2)
    aim_sun()
    apply_lighting()
    if announce:
        t = state['sun_t']
        set_status('Sun: morning' if t < 0.25 else 'Sun: midday' if t < 0.65 else 'Sun: evening')


def set_roof(flag):
    state['roof'] = flag
    apply_visibility()
    refresh_ui()
    set_status('Roof visible' if flag else 'Roof hidden')


def remove_item(it, announce=True):
    if it not in ITEMS:
        return
    if state['item'] is it:
        state['item'] = None
    if state['drag'] is it:
        state['drag'] = None
    ITEMS.remove(it)
    it.destroy_all()
    refresh_ui()
    if announce:
        set_status(f'Removed {LABEL[it.kind]}')


def clear_items():
    for it in ITEMS[:]:
        remove_item(it, announce=False)


def find_free_spot(kind, room, level):
    x0, x1, z0, z1 = ROOMS[room]['rect']
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    dummy = SimpleNamespace(kind=kind, level=level)
    hw, hd = half_extents(kind, 0)
    cands = []
    x = x0
    while x <= x1:
        z = z0
        while z <= z1:
            cands.append((x, z))
            z += 0.5
        x += 0.5
    cands.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cz) ** 2)
    for px, pz in cands:
        px, pz = constrain(dummy, px, pz, 0)
        if room_at(px, pz, level) != room:
            continue
        free = True
        if kind != 'rug':
            for o in ITEMS:
                if o.level != level or o.kind == 'rug':
                    continue
                ow, od = half_extents(o.kind, o.trot)
                if abs(px - o.tx) < hw + ow and abs(pz - o.tz) < hd + od:
                    free = False
                    break
        if free:
            return px, pz
    return constrain(dummy, cx, cz, 0)


def add_item(kind):
    level = state['level']
    room = state['room'] if ROOMS[state['room']]['level'] == level else LEVEL_ROOMS[level][0]
    x, z = find_free_spot(kind, room, level)
    it = Item(kind, x, z, 0, level)
    select_item(it, announce=False)
    set_status(f'Added {LABEL[kind]} to {ROOMS[room]["label"]} - drag it with the mouse')


def duplicate_selected():
    it = state['item']
    if it is None:
        set_status('Select a furniture item first (click it)')
        return
    room = room_at(it.tx, it.tz, it.level)
    x, z = find_free_spot(it.kind, room, it.level)
    new = Item(it.kind, x, z, it.trot, it.level, it.elev)
    select_item(new, announce=False)
    set_status(f'Duplicated {LABEL[it.kind]}')


def set_target(it, x, z):
    it.tx, it.tz = constrain(it, x, z, it.trot)


def rotate_item(deg):
    it = state['item']
    if it is not None:
        it.trot = (it.trot + deg) % 360
        set_target(it, it.tx, it.tz)


def rotate_button(deg):
    if state['item'] is None:
        set_status('Select a furniture item first (click it)')
        return
    rotate_item(deg)


def elevate_item(delta):
    it = state['item']
    if it is None:
        set_status('Select a furniture item first (click it)')
        return
    it.elev = max(0.0, min(2.2, round(it.elev + delta, 2)))
    set_status(f'{LABEL[it.kind]} height above floor: {it.elev:.1f} m')


def remove_selected():
    if state['item'] is None:
        set_status('Select a furniture item first (click it)')
        return
    remove_item(state['item'])


def build_default_furniture():
    for kind, x, z, rot, lvl in DEFAULT_FURNITURE:
        Item(kind, x, z, rot, lvl)


def reset_scene():
    end_drag()
    if state['photo']:
        exit_photo_mode()
    clear_items()
    state['item'] = None
    for key in ROOMS:
        set_room_color(key, 'wall', DEFAULT_COLORS[key][0], announce=False)
        set_room_color(key, 'floor', DEFAULT_COLORS[key][1], announce=False)
    set_facade_color(RENDER_COL)
    state.update(night=False, brightness=1.0, sun_t=0.32, roof=True, upper=True, view='exterior', cut=True)
    build_default_furniture()
    aim_sun()
    apply_lighting()
    select_room('living_room', announce=False)
    focus_exterior()
    update_cutaway()
    set_status('Design reset to the default arrangement')


# ---- drag & drop ----
def start_drag(it):
    state['drag'] = it
    wp = getattr(mouse, 'world_point', None)
    drag_off[0] = drag_off[1] = 0.0
    if wp is not None:
        ox, oz = it.tx - wp.x, it.tz - wp.z
        if abs(ox) < 2.5 and abs(oz) < 2.5:
            drag_off[0], drag_off[1] = ox, oz
    it.set_colliders(False)


def end_drag():
    it = state['drag']
    if it is not None:
        if it in ITEMS:
            it.set_colliders(True)
        state['drag'] = None


# =====================================================================
# 9. SAVE / LOAD (JSON) and screenshots
# =====================================================================
def design_to_dict():
    return {
        'project_name': PROJECT_NAME,
        'version': 3,
        'lighting': 'night' if state['night'] else 'day',
        'brightness': state['brightness'],
        'sun_time': state['sun_t'],
        'roof_visible': state['roof'],
        'upper_visible': state['upper'],
        'rooms': {k: {'wall_color': rt['wall_color'], 'floor_color': rt['floor_color']}
                  for k, rt in room_rt.items()},
        'furniture': [{
            'type': it.kind,
            'level': it.level,
            'room': room_at(it.tx, it.tz, it.level),
            'position': [round(it.tx, 3), round(floor_y(it.level), 3), round(it.tz, 3)],
            'elevation': round(it.elev, 2),
            'rotation': [0, round(it.trot % 360, 2), 0],
            'scale': [1, 1, 1],
        } for it in ITEMS],
    }


def validate_design(data):
    if not isinstance(data, dict):
        return 'not a design file'
    for key in ('lighting', 'brightness', 'roof_visible', 'rooms', 'furniture'):
        if key not in data:
            return f'missing "{key}"'
    if data['lighting'] not in ('day', 'night'):
        return 'invalid lighting value'
    if not isinstance(data['brightness'], (int, float)) or isinstance(data['brightness'], bool):
        return 'invalid brightness'
    if not isinstance(data['roof_visible'], bool):
        return 'invalid roof_visible'
    if not isinstance(data['rooms'], dict) or not isinstance(data['furniture'], list):
        return 'invalid rooms/furniture section'
    for rk, cfg in data['rooms'].items():
        if rk not in ROOMS:
            continue                                   # rooms from older versions are ignored
        if not isinstance(cfg, dict):
            return f'invalid room "{rk}"'
        for field in ('wall_color', 'floor_color'):
            if cfg.get(field) not in PALETTE:
                return f'unknown colour in room "{rk}"'
    for f in data['furniture']:
        if not isinstance(f, dict) or f.get('type') not in BUILDERS:
            return 'unknown furniture type'
        if f.get('level', 0) not in (0, 1):
            return 'invalid furniture level'
        pos, rot = f.get('position'), f.get('rotation', [0, 0, 0])
        if not (isinstance(pos, list) and len(pos) == 3 and all(isinstance(v, (int, float)) for v in pos)):
            return 'invalid furniture position'
        if not (isinstance(rot, list) and len(rot) == 3 and all(isinstance(v, (int, float)) for v in rot)):
            return 'invalid furniture rotation'
        if not isinstance(f.get('elevation', 0), (int, float)):
            return 'invalid furniture elevation'
    return None


def apply_design(data):
    end_drag()
    clear_items()
    state['item'] = None
    for rk, cfg in data['rooms'].items():
        if rk in ROOMS:
            set_room_color(rk, 'wall', cfg['wall_color'], announce=False)
            set_room_color(rk, 'floor', cfg['floor_color'], announce=False)
    state['night'] = data['lighting'] == 'night'
    state['brightness'] = round(max(0.5, min(1.5, float(data['brightness']))), 2)
    sun_time = data.get('sun_time', 0.45)
    state['sun_t'] = round(max(0.0, min(1.0, float(sun_time))), 2) if isinstance(sun_time, (int, float)) else 0.45
    state['roof'] = data['roof_visible']
    state['upper'] = bool(data.get('upper_visible', True))
    for f in data['furniture']:
        lvl = int(f.get('level', 0))
        it = Item(f['type'], float(f['position'][0]), float(f['position'][2]),
                  float(f.get('rotation', [0, 0, 0])[1]), lvl,
                  max(0.0, min(2.2, float(f.get('elevation', 0.0)))))
        it.tx, it.tz = constrain(it, it.tx, it.tz, it.trot)
        it.root.x, it.root.z = it.tx, it.tz
    aim_sun()
    apply_lighting()
    select_room(state['room'], announce=False)


def save_design():
    try:
        slug = re.sub(r'[^a-z0-9]+', '_', PROJECT_NAME.lower()).strip('_')
        path = SAVE_DIR / f'{slug}_{datetime.now():%Y%m%d_%H%M%S}.json'
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(design_to_dict(), fh, indent=2)
        set_status(f'Design saved: saved_designs/{path.name}')
        return path
    except Exception as exc:
        set_status(f'Save failed: {exc}')
        return None


def load_design(path):
    close_popup()
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception as exc:
        set_status(f'Load failed: {exc}')
        return False
    error = validate_design(data)
    if error:
        set_status(f'Load failed: {error}')
        return False
    apply_design(data)
    set_status(f'Design loaded: {Path(path).name}')
    return True


def saved_files():
    return sorted(SAVE_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)


def close_popup():
    if state['popup'] is not None:
        destroy(state['popup'])
        state['popup'] = None


def open_menu(title, entries):
    """Generic pop-up list: entries = [(label, callback), ...]."""
    close_popup()
    n = len(entries)
    box = Entity(parent=camera.ui)
    Entity(parent=box, model='quad', position=(0, 0, 0.5), scale=(0.62, 0.1 + 0.058 * (n + 1)),
           color=rgba(UI_PANEL))
    top = 0.05 + 0.029 * (n + 1)
    Text(title, parent=box, position=(-0.27, top - 0.012), origin=(-.5, .5), scale=1.0, color=rgba(UI_ACCENT))
    for i, (label, cb) in enumerate(entries):
        make_button(label, 0, top - 0.075 - i * 0.058, cb, w=0.56, parent=box)
    make_button('CLOSE', 0, top - 0.075 - n * 0.058, close_popup, w=0.56, parent=box)
    state['popup'] = box


def open_load_menu():
    files = saved_files()[:8]
    if not files:
        close_popup()
        set_status('No saved designs found - press SAVE first')
        return
    open_menu('LOAD DESIGN', [(p.name[:42], (lambda q=p: load_design(q))) for p in files])


def take_screenshot():
    ui_was = camera.ui.enabled
    try:
        path = SHOT_DIR / f'archivision_{datetime.now():%Y%m%d_%H%M%S}.png'
        camera.ui.enabled = False                       # clean picture without panels
        application.base.graphicsEngine.renderFrame()
        application.base.graphicsEngine.renderFrame()
        application.base.screenshot(namePrefix=str(path), defaultFilename=False)
        camera.ui.enabled = ui_was
        set_status(f'Screenshot saved: screenshots/{path.name}')
    except Exception as exc:
        camera.ui.enabled = ui_was
        set_status(f'Screenshot failed: {exc}')


# =====================================================================
# 10. CAMERA (orbit around a target; exterior view and room view)
# =====================================================================
camera.fov = 60
camera.clip_plane_far = 1500
camera.clip_plane_near = 0.1
cam = dict(yaw=24.0, pitch=26.0, dist=34.0, tx=4.0, ty=2.0, tz=0.0,
           yaw_t=24.0, pitch_t=26.0, dist_t=34.0, tx_t=4.0, ty_t=2.0, tz_t=0.0)


def apply_camera():
    yaw, pitch = math.radians(cam['yaw']), math.radians(cam['pitch'])
    tx, ty, tz = cam['tx'], cam['ty'], cam['tz']
    camera.position = (tx + cam['dist'] * math.cos(pitch) * math.sin(yaw),
                       ty + cam['dist'] * math.sin(pitch),
                       tz - cam['dist'] * math.cos(pitch) * math.cos(yaw))
    camera.look_at(Vec3(tx, ty, tz))


# =====================================================================
# 11. BUILD THE SCENE
# =====================================================================
build_environment()
for _key in ROOMS:
    build_room(_key)
build_stairs()
build_balcony()
build_roof()
build_ceiling_lights()
room_marker = [Entity(model='cube', color=rgba((255, 205, 70)), parent=level_root[0], enabled=False)
               for _ in range(4)]
build_default_furniture()

# sky, stars, moon, lights
try:
    sky = Sky()
except Exception:
    sky = None
stars_root = Entity()
_rnd = random.Random(42)
for _ in range(160):
    _a, _b = _rnd.uniform(0, 2 * math.pi), _rnd.uniform(0.15, 1.45)
    _s = _rnd.uniform(0.6, 1.6)
    Entity(parent=stars_root, model='cube', scale=_s, color=color.white,
           position=(500 * math.cos(_b) * math.cos(_a), 500 * math.sin(_b), 500 * math.cos(_b) * math.sin(_a)))
stars_root.enabled = False
moon = Entity(model='sphere', scale=26, position=(-260, 330, 260), color=rgba((225, 232, 248)))
moon.enabled = False

if USE_SHADERS:
    try:
        try:
            sun = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(SHADOW_RES, SHADOW_RES))
        except Exception:
            sun = DirectionalLight(shadows=True)
        amb = AmbientLight()
        aim_sun()
    except Exception as exc:
        print('[lighting setup failed, using flat colours:', exc, ']')
        sun = amb = None
apply_lighting()
cam.update(yaw=24.0, pitch=26.0, dist=34.0, tx=4.0, ty=2.0, tz=0.0)
apply_camera()


# =====================================================================
# 12. PHOTO STUDIO  (turn a photo of any building into an editable 3D model)
# =====================================================================
PHOTO = dict(img=None, name='', tex=None, colors=[], avg=(200, 196, 188), tint=None, side=None,
             roof='gabled', roof_col=ROOF_COLS[0][1], garden=True, pool=False,
             w=12.0, h=7.0, d=9.0, facade=None, source_path=None)
PHOTO_WATERS = []


def clear_photo_root():
    for ch in photo_root.children[:]:
        LIT.pop(id(ch), None)
        destroy(ch)
    PHOTO_WATERS.clear()
    PHOTO['facade'] = None


def lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def nearest_palette(rgb):
    return min(PALETTE_KEYS, key=lambda k: sum((a - b) ** 2 for a, b in zip(PALETTE[k][1], rgb)))


def analyse_photo():
    img = PHOTO['img']
    q = img.resize((120, 120)).quantize(colors=6)
    pal = q.getpalette()
    cols = [tuple(pal[i * 3:i * 3 + 3]) for _, i in sorted(q.getcolors(), reverse=True)]
    PHOTO['colors'] = cols[:6]
    w, h = img.size
    mid = img.crop((int(w * .15), int(h * .35), int(w * .85), int(h * .95))).resize((1, 1), PILImage.BOX)
    PHOTO['avg'] = tuple(int(v) for v in mid.getpixel((0, 0)))
    PHOTO['w'] = round(max(7.0, min(22.0, 7.0 * w / h)), 1)
    PHOTO['h'], PHOTO['d'] = 7.0, 9.0
    darkest = min(PHOTO['colors'], key=lum)
    PHOTO['roof_col'] = min(ROOF_COLS, key=lambda rc: sum((a - b) ** 2 for a, b in zip(rc[1], darkest)))[1]
    PHOTO['tint'], PHOTO['side'] = None, None


def load_photo(path):
    close_popup()
    try:
        img = PILImage.open(path).convert('RGB')
    except Exception as exc:
        set_status(f'Could not open photo: {exc}')
        return False
    img.thumbnail((1600, 1600))
    PHOTO['img'] = img
    PHOTO['name'] = Path(path).name
    PHOTO['source_path'] = str(path)
    REAL_ROOM['photo_path'] = str(path)
    try:
        REAL_ROOM['photo_texture'] = Texture(img.convert('RGBA'))
    except Exception:
        REAL_ROOM['photo_texture'] = None
    try:
        PHOTO['tex'] = Texture(img.convert('RGBA'))
    except Exception as exc:
        set_status(f'Photo texture failed: {exc}')
        return False
    analyse_photo()
    build_photo_building()
    enter_photo_mode()
    set_status(f'Photo loaded: {PHOTO["name"]} - restyle it with the panel on the left')
    return True


def build_photo_building():
    clear_photo_root()
    BUILD_PARENT[0] = photo_root
    W, H, D = PHOTO['w'], PHOTO['h'], PHOTO['d']
    pool = None
    if PHOTO['pool']:
        px0 = W / 2 + 4.5
        pool = (px0, px0 + 5.0, -4.0, 4.0)
    build_ground(40, hole=pool)
    if pool:
        PHOTO_WATERS.append(build_pool(pool, (W / 2 + 2.5, pool[1] + 2.5, -6.5, 6.5)))
    mk((0, -0.02, 0), (W + 2, 0.2, D + 2), (150, 150, 146), tex='concrete', tile=((W + 2) / 3, (D + 2) / 3))
    side = PHOTO['side'] or tuple(int(c * 0.92) for c in PHOTO['avg'])
    mk((0, 0.1 + H / 2, 0), (W, H, D), side, tex='plaster', tile=(W / 3, H / 3))
    f = mk((0, 0.1 + H / 2, -D / 2 - 0.02), (W, H, 1), (255, 255, 255), model='quad', photo=True, lit=False)
    f.texture = PHOTO['tex']
    if PHOTO_FLIP:
        f.texture_scale = Vec2(1, -1)
        f.texture_offset = Vec2(0, 1)
    PHOTO['facade'] = f
    set_photo_tint(PHOTO['tint'], announce=False)
    top = 0.1 + H
    rc = PHOTO['roof_col']
    if PHOTO['roof'] == 'flat':
        mk((0, top + 0.15, 0), (W + 0.6, 0.3, D + 0.6), rc, tex='concrete', tile=(W / 3, D / 3))
        for sz in (-1, 1):
            mk((0, top + 0.4, sz * (D / 2 + 0.2)), (W + 0.6, 0.35, 0.2), (236, 234, 228), tex='plaster', tile=(4, 1))
    elif PHOTO['roof'] == 'gabled':
        run = D / 2 + 0.5
        rise = D * 0.28
        ang = math.degrees(math.atan2(rise, run))
        ln = math.hypot(run, rise)
        for sz, rot in ((-1, -ang), (1, ang)):
            mk((0, top + rise / 2 + 0.1, sz * run / 2), (W + 0.9, 0.22, ln), rc,
               tex='concrete', tile=(W / 2, ln / 2), rotation_x=rot)
        mk((0, top + rise + 0.14, 0), (W + 0.95, 0.18, 0.35), rc)
        steps = 8                                       # fill the two triangular gable ends
        for sx in (-1, 1):
            for i in range(steps):
                span = D * (1 - (i + 0.5) / steps)
                mk((sx * (W / 2 - 0.1), top + (i + 0.5) * rise / steps, 0), (0.2, rise / steps + 0.01, span),
                   side, tex='plaster', tile=(1, 1))
    if PHOTO['garden']:
        for tx, tz, ts in ((-W / 2 - 5, 2, 1.2), (-W / 2 - 3.5, -8, 0.9), (W / 2 + 4, 10, 1.2),
                           (-4, D / 2 + 7, 1.3), (-W / 2 - 8, 12, 1.1)):
            tree(tx, tz, ts)
        mk((0, 0.5, -D / 2 - 2.6), (W + 2, 1.0, 0.8), GREEN_D, tex='foliage', tile=((W + 2) / 1.5, 1))
        mk((0, -0.27, -D / 2 - 8), (2.4, 0.05, 11), (206, 202, 190), tex='concrete', tile=(1, 5))
        for lz in (-D / 2 - 4, -D / 2 - 9):
            for lx in (-1.9, 1.9):
                mk((lx, 0.35, lz), (0.12, 0.7, 0.12), DARK)
                mk((lx, 0.78, lz), (0.2, 0.2, 0.2), (240, 236, 224), model='sphere',
                   emissive=((240, 236, 224), (255, 214, 140)))
        car(-W / 2 - 4, -D / 2 - 6)
    BUILD_PARENT[0] = world
    refresh_photo_ui()


def set_photo_tint(key, announce=True):
    PHOTO['tint'] = key
    f = PHOTO['facade']
    if f is not None:
        f.ab_base = PALETTE[key][1] if key else (255, 255, 255)
        paint(f)
    refresh_photo_ui()
    if announce:
        set_status('Facade tint: ' + (PALETTE[key][0] if key else 'original photo'))


def photo_set(**kw):
    if PHOTO['img'] is None:
        return
    PHOTO.update(kw)
    build_photo_building()


def photo_dim(name, delta):
    lim = {'w': (5.0, 30.0), 'h': (4.0, 14.0), 'd': (5.0, 20.0)}[name]
    photo_set(**{name: round(max(lim[0], min(lim[1], PHOTO[name] + delta)), 1)})


def photo_side_from_swatch(i):
    if i < len(PHOTO['colors']):
        photo_set(side=PHOTO['colors'][i])
        set_status('Side walls recoloured from the photo')


def apply_photo_to_villa():
    if PHOTO['img'] is None:
        set_status('Load a photo first')
        return
    wall_key = nearest_palette(PHOTO['avg'])
    for key in ROOMS:
        set_room_color(key, 'wall', wall_key, announce=False)
    set_facade_color(tuple(min(255, int(c * 1.06)) for c in PHOTO['avg']))
    set_status(f'Villa walls and facade now follow the photo ({PALETTE[wall_key][0]})')


def enter_photo_mode():
    if PHOTO['img'] is None:
        open_photo_menu()
        return
    end_drag()
    select_item(None, announce=False)
    state['photo'] = True
    world.enabled = False
    photo_root.enabled = True
    focus_photo()
    aim_sun()
    set_panel('left', True)
    refresh_ui()


def exit_photo_mode():
    state['photo'] = False
    photo_root.enabled = False
    world.enabled = True
    reset_view()
    aim_sun()
    sync_panels()
    refresh_ui()
    set_status('Back to the villa')


def browse_photo():
    close_popup()
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askopenfilename(
            title='Choose a photo of a building',
            filetypes=[('Images', '*.jpg *.jpeg *.png *.webp *.bmp'), ('All files', '*.*')])
        root.destroy()
    except Exception as exc:
        set_status(f'File dialog unavailable - copy photos into the photos/ folder ({exc})')
        return
    if path:
        load_photo(path)


def close_photo_studio_image():
    """Close/clear the currently loaded Photo Studio image without picking a new one."""
    PHOTO['img'] = None
    PHOTO['tex'] = None
    PHOTO['name'] = ''
    PHOTO['source_path'] = None
    clear_photo_root()
    refresh_photo_ui()
    set_status('Photo closed. Choose LOAD / CHANGE PHOTO to open another.')


# ---------------------------------------------------------------------
# REAL-WORLD ROOM WORKFLOW
# ---------------------------------------------------------------------
ROOM_EDIT_PALETTE = [
    ('Warm white', (242, 235, 220)), ('Sage', (151, 171, 139)),
    ('Soft blue', (145, 177, 205)), ('Charcoal', (75, 79, 86)),
    ('Sand', (205, 183, 150)), ('Terracotta', (185, 112, 82)),
]
PHOTO_POLYGONS = []


def edit_real_room_photo(path=None):
    """Polygon-based photograph editor for classroom/bedroom wall and floor regions."""
    try:
        import cv2
        import numpy as np
    except Exception:
        set_status('Photo editing needs OpenCV and NumPy: python -m pip install opencv-python numpy')
        return
    if path is None:
        path = PHOTO.get('source_path') or (PHOTO_DIR / PHOTO['name'] if PHOTO['name'] else None)
    if not path or not Path(path).exists():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            chosen = filedialog.askopenfilename(title='Choose a classroom / room photograph',
                filetypes=[('Images', '*.jpg *.jpeg *.png *.webp *.bmp'), ('All files', '*.*')])
            root.destroy()
            path = chosen if chosen else None
        except Exception:
            path = None
    if not path:
        set_status('No classroom photograph selected')
        return
    original = cv2.imread(str(path))
    if original is None:
        set_status('Could not read the selected room photograph')
        return
    h, w = original.shape[:2]
    scale = min(1.0, 1300 / max(w, h))
    base = cv2.resize(original, (int(w * scale), int(h * scale))) if scale < 1 else original.copy()
    points, regions = [], []
    target = 'WALL'
    palette_index = 0
    title = 'ArchiVision - PHOTO DESIGN | click points, ENTER apply, 1-6 colour, W wall, F floor, S save, ESC exit'
    def redraw():
        canvas = base.copy()
        for poly, color_bgr, label in regions:
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [np.array(poly, dtype=np.int32)], color_bgr)
            canvas = cv2.addWeighted(overlay, 0.42, canvas, 0.58, 0)
            cv2.polylines(canvas, [np.array(poly, dtype=np.int32)], True, (40, 220, 190), 2)
        if points:
            cv2.polylines(canvas, [np.array(points, dtype=np.int32)], False, (40, 220, 190), 2)
            for pt in points:
                cv2.circle(canvas, tuple(pt), 4, (40, 220, 190), -1)
        name, rgb = ROOM_EDIT_PALETTE[palette_index]
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 64), (24, 29, 39), -1)
        cv2.putText(canvas, f'{target} REGION  |  COLOUR: {name}  |  CLICK TO TRACE, ENTER TO APPLY',
                    (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (235, 242, 248), 1, cv2.LINE_AA)
        cv2.putText(canvas, 'W wall  F floor  1-6 colours  U undo region  C clear points  S save  ESC finish',
                    (14, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (145, 205, 195), 1, cv2.LINE_AA)
        return canvas
    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(title, on_mouse)
    saved = False
    while True:
        cv2.imshow(title, redraw())
        key = cv2.waitKey(20) & 0xFF
        if key in (ord('w'), ord('W')): target = 'WALL'
        elif key in (ord('f'), ord('F')): target = 'FLOOR'
        elif key in [ord(str(i)) for i in range(1, 7)]: palette_index = key - ord('1')
        elif key in (ord('c'), ord('C')): points.clear()
        elif key in (ord('u'), ord('U')):
            if regions: regions.pop()
        elif key in (10, 13):
            if len(points) >= 3:
                rgb = ROOM_EDIT_PALETTE[palette_index][1]
                regions.append((points.copy(), (rgb[2], rgb[1], rgb[0]), target))
                points.clear()
        elif key in (ord('s'), ord('S')):
            result = base.copy()
            for poly, color_bgr, label in regions:
                overlay = result.copy()
                cv2.fillPoly(overlay, [np.array(poly, dtype=np.int32)], color_bgr)
                result = cv2.addWeighted(overlay, 0.42, result, 0.58, 0)
            out = PHOTO_DIR / f'room_design_{datetime.now():%Y%m%d_%H%M%S}.jpg'
            cv2.imwrite(str(out), result, [int(cv2.IMWRITE_JPEG_QUALITY), 96])
            saved = True
            set_status(f'Room photo design saved: {out.name}')
        elif key == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()
    if saved:
        out_path = max(PHOTO_DIR.glob('room_design_*.jpg'), key=lambda q: q.stat().st_mtime)
        load_photo(out_path)


def build_real_room():
    """Build an editable classroom/interior approximation in its own 3D workspace."""
    for ch in real_room_root.children[:]:
        LIT.pop(id(ch), None)
        destroy(ch)
    old_parent = BUILD_PARENT[0]
    BUILD_PARENT[0] = real_room_root
    w, d, h = REAL_ROOM['width'], REAL_ROOM['depth'], REAL_ROOM['height']
    wall = REAL_ROOM.get('wall_color', (232, 229, 220))
    floor = REAL_ROOM.get('floor_color', (190, 185, 174))

    # Floor, walls and open-front ceiling for an inspectable room model.
    mk((0, -0.12, 0), (w, 0.24, d), floor, tex='wood', tile=(w / 2, d / 2))
    mk((-w/2, h/2, 0), (0.16, h, d), wall, tex='plaster', tile=(1, 2))
    mk((w/2, h/2, 0), (0.16, h, d), wall, tex='plaster', tile=(1, 2))
    mk((0, h/2, d/2), (w, h, 0.16), wall, tex='plaster', tile=(2, 2))
    mk((0, h + 0.08, 0), (w, 0.16, d), (218, 220, 218), tex='plaster')

    # Reference photo stays inside this independent room, never on the villa.
    if REAL_ROOM.get('photo_texture') is not None:
        photo_plane = mk((0, h/2, d/2 - 0.095), (w*0.96, h*0.94, 0.025),
                         (255, 255, 255), model='quad', lit=False, photo=True)
        photo_plane.texture = REAL_ROOM['photo_texture']

    # Side windows with dark frames and pale blue glazing.
    glass = (157, 197, 213)
    frame = (75, 82, 88)
    for side in (-1, 1):
        for z in (-d * 0.27, d * 0.27):
            x = side * (w/2 - 0.105)
            mk((x, h * 0.61, z), (0.035, 1.05, 1.55), glass,
               emissive=(glass, (95, 120, 160)))
            mk((x, h * 0.61, z - 0.80), (0.06, 1.15, 0.07), frame, tex='metal')
            mk((x, h * 0.61, z + 0.80), (0.06, 1.15, 0.07), frame, tex='metal')
            mk((x, h * 0.61 - 0.55, z), (0.06, 0.07, 1.65), frame, tex='metal')
            mk((x, h * 0.61 + 0.55, z), (0.06, 0.07, 1.65), frame, tex='metal')
            mk((x, h * 0.61, z), (0.07, 1.0, 0.045), frame, tex='metal')

    if REAL_ROOM.get('kind', 'classroom') == 'classroom':
        # Front-facing teaching wall, board and teacher station.
        mk((0, 1.55, -d/2 + 0.18), (3.2, 1.25, 0.12), (35, 78, 70), tex='granite')
        mk((0, 0.78, -d/2 + 0.45), (2.2, 0.10, 0.85), (125, 91, 62), tex='wood')
        mk((0, 0.48, -d/2 + 0.45), (1.8, 0.55, 0.08), (65, 70, 76), tex='metal')

        # Three rows of student desks with chairs; all are real 3D primitives.
        for row, z in enumerate((-1.65, 0.25, 2.05)):
            for col, x in enumerate((-w * 0.27, 0.0, w * 0.27)):
                if abs(x) + 0.75 > w/2 - 0.25:
                    continue
                # Desk top and apron
                mk((x, 0.82, z), (1.18, 0.12, 0.68), (166, 132, 94), tex='wood', tile=(2, 1))
                mk((x, 0.70, z), (1.02, 0.12, 0.55), (118, 91, 66), tex='wood')
                for dx in (-0.49, 0.49):
                    for dz in (-0.25, 0.25):
                        mk((x + dx, 0.39, z + dz), (0.065, 0.66, 0.065), (63, 69, 75), tex='metal')
                # Student chair behind each desk
                cz = z + 0.62
                mk((x, 0.48, cz), (0.58, 0.10, 0.54), (55, 83, 112), tex='fabric')
                mk((x, 0.84, cz + 0.22), (0.58, 0.66, 0.09), (55, 83, 112), tex='fabric')
                for dx in (-0.23, 0.23):
                    for dz in (-0.20, 0.20):
                        mk((x + dx, 0.25, cz + dz), (0.055, 0.48, 0.055), (63, 69, 75), tex='metal')

        # Ceiling LED panels and a central projector detail.
        for x in (-w * 0.28, 0, w * 0.28):
            for z in (-d * 0.28, d * 0.20):
                mk((x, h - 0.035, z), (1.15, 0.035, 0.42), (239, 238, 224),
                   emissive=((239, 238, 224), (110, 120, 150)))
        mk((0, h - 0.18, 0.25), (0.38, 0.16, 0.34), (80, 87, 96), tex='metal')

    else:
        # Premium, ready-furnished living-room arrangement.  These are real
        # editable 3D primitives, not a flat illustration or a photo pasted on
        # the villa.  The open front keeps every item easy to inspect.
        # Large soft rug.
        mk((0, 0.025, 0.45), (w * 0.58, 0.045, d * 0.48),
           (205, 196, 178), tex='fabric')
        # Three-seat sofa along the back half of the room.
        sofa_x, sofa_z = 0.0, 1.15
        sofa_col = (177, 166, 151)
        mk((sofa_x, 0.48, sofa_z), (3.25, 0.62, 0.92), sofa_col, tex='fabric')
        mk((sofa_x, 0.91, sofa_z + 0.30), (3.25, 0.78, 0.30),
           (190, 179, 164), tex='fabric')
        for sx in (-1.48, 1.48):
            mk((sx, 0.72, sofa_z - 0.02), (0.34, 0.68, 0.98),
               (157, 145, 132), tex='fabric')
        for sx in (-0.92, 0.0, 0.92):
            mk((sx, 0.72, sofa_z - 0.13), (0.78, 0.62, 0.18),
               (207, 197, 182), tex='fabric')
            mk((sx, 1.03, sofa_z + 0.13), (0.66, 0.55, 0.16),
               (211, 201, 187), tex='fabric')
        # Coffee table with a warm wood top and slim metal legs.
        mk((0, 0.43, -0.35), (1.75, 0.12, 0.88), (139, 98, 66), tex='wood')
        for sx in (-0.72, 0.72):
            for sz in (-0.31, 0.31):
                mk((sx, 0.22, -0.35 + sz), (0.055, 0.42, 0.055),
                   (55, 60, 66), tex='metal')
        # TV feature wall and floating media console.
        mk((0, 1.72, -d/2 + 0.20), (2.55, 1.48, 0.12),
           (74, 79, 82), tex='granite')
        mk((0, 1.78, -d/2 + 0.115), (1.85, 1.08, 0.045),
           (20, 24, 29), lit=False)
        mk((0, 0.42, -d/2 + 0.58), (2.75, 0.48, 0.52),
           (128, 88, 58), tex='wood')
        # Tall wardrobe on one side, with two door panels and handles.
        wardrobe_x = w/2 - 0.62
        mk((wardrobe_x, 1.35, -0.10), (1.05, 2.70, 1.05),
           (190, 181, 165), tex='wood')
        for dx in (-0.25, 0.25):
            mk((wardrobe_x + dx, 1.36, -0.645), (0.48, 2.56, 0.035),
               (205, 196, 180), tex='wood')
            mk((wardrobe_x + dx + (0.17 if dx < 0 else -0.17), 1.35, -0.68),
               (0.035, 0.20, 0.035), (65, 61, 55), tex='metal')
        # Side table and decorative lamp.
        mk((-w/2 + 0.72, 0.46, 1.20), (0.72, 0.10, 0.65),
           (132, 91, 60), tex='wood')
        mk((-w/2 + 0.72, 0.78, 1.20), (0.055, 0.55, 0.055),
           (65, 68, 72), tex='metal')
        mk((-w/2 + 0.72, 1.10, 1.20), (0.36, 0.34, 0.36),
           (235, 218, 177), emissive=((235, 218, 177), (90, 80, 60)))
        # Indoor plants in two corners.
        for px, pz in ((-w/2 + 0.48, -d/2 + 0.55), (w/2 - 0.48, d/2 - 0.55)):
            mk((px, 0.22, pz), (0.48, 0.42, 0.48), (126, 86, 59), tex='wood')
            for leaf in range(5):
                ang = leaf * (math.pi * 2 / 5)
                lx, lz = px + math.cos(ang) * 0.22, pz + math.sin(ang) * 0.22
                mk((lx, 0.85 + (leaf % 2) * 0.12, lz), (0.24, 0.80, 0.24),
                   (74, 125 + leaf * 3, 79), tex='fabric')
        # Warm ceiling pendant.
        mk((0, h - 0.30, 0.25), (0.08, 0.55, 0.08), (65, 68, 72), tex='metal')
        mk((0, h - 0.60, 0.25), (0.62, 0.22, 0.62),
           (238, 218, 176), emissive=((238, 218, 176), (105, 90, 65)))

    # Skirting boards add a finished architectural edge.
    for side in (-1, 1):
        mk((side * (w/2 - 0.10), 0.12, 0), (0.045, 0.20, d), (115, 112, 105), tex='wood')
    mk((0, 0.12, d/2 - 0.10), (w, 0.20, 0.045), (115, 112, 105), tex='wood')

    BUILD_PARENT[0] = old_parent
    REAL_ROOM['active'] = True


def enter_real_room_mode():
    if PHOTO['img'] is None:
        open_photo_menu()
        return
    end_drag()
    select_item(None, announce=False)
    world.enabled = False
    photo_root.enabled = False
    build_real_room()
    real_room_root.enabled = True
    state['photo'] = True
    cam['tx_t'], cam['ty_t'], cam['tz_t'] = 0, 1.5, 0
    cam['dist_t'], cam['pitch_t'], cam['yaw_t'] = 12.5, 18, 0
    set_status('REAL ROOM MODE | orbit/zoom | 1-6 wall finish | 7 floor finish | +/- width | [ ] depth | PgUp/PgDn height | T room type | Esc exit')


def exit_real_room_mode():
    REAL_ROOM['active'] = False
    real_room_root.enabled = False
    state['photo'] = False
    world.enabled = True
    reset_view()
    sync_panels()
    refresh_ui()
    set_status('Returned to ArchiVision villa studio')


def adjust_real_room(axis, delta):
    limits = {'width': (4.0, 16.0), 'depth': (4.0, 16.0), 'height': (2.4, 5.0)}
    lo, hi = limits[axis]
    REAL_ROOM[axis] = round(max(lo, min(hi, REAL_ROOM[axis] + delta)), 1)
    build_real_room()
    real_room_root.enabled = True
    set_status(f'3D room {axis}: {REAL_ROOM[axis]:.1f} m')



def open_photo_menu():
    files = [p for p in PHOTO_DIR.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.bmp')]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    entries = [(p.name[:42], (lambda q=p: load_photo(q))) for p in files[:5]]
    entries.append(('BROWSE COMPUTER FOR A PHOTO...', browse_photo))
    if PHOTO['img'] is not None:
        entries.append(('CLOSE CURRENT PHOTO', close_photo_studio_image))
    entries.append(('EDIT REAL ROOM PHOTO (WALLS / FLOOR)', edit_real_room_photo))
    entries.append(('BUILD EDITABLE 3D CLASSROOM / ROOM', enter_real_room_mode))
    open_menu('PHOTO STUDIO - CHOOSE A BUILDING PHOTO', entries)


# =====================================================================
# 13. USER INTERFACE  (three slide-in panels: LEFT tools, RIGHT style, BOTTOM file)
# =====================================================================
UI_PARENT = [camera.ui]
TL, TR, BL, BR = window.top_left, window.top_right, window.bottom_left, window.bottom_right


def make_panel(x, y, w, h, col=UI_PANEL):
    return Entity(parent=UI_PARENT[0], model='quad', position=(x, y, 1), scale=(w, h), color=rgba(col))


def make_label(txt, x, y, size=0.9, col=UI_TEXT, parent=None):
    return Text(txt, parent=parent if parent is not None else UI_PARENT[0],
                position=(x, y), origin=(-.5, .5), scale=size, color=rgba(col))


def make_button(txt, x, y, cb, w=0.26, h=0.034, parent=None, col=UI_BTN):
    b = Button(parent=parent if parent is not None else UI_PARENT[0], text=txt, position=(x, y),
               scale=(w, h), color=rgba(col), highlight_color=rgba(UI_HOVER),
               pressed_color=rgba(UI_ACTIVE), on_click=cb)
    b.text_size = 0.66
    return b


left_ui = Entity(parent=camera.ui, enabled=False)
right_ui = Entity(parent=camera.ui, enabled=False)
bottom_ui = Entity(parent=camera.ui, enabled=False)
photo_ui = Entity(parent=camera.ui, enabled=False)
ui_open = dict(left=False, right=False, bottom=False)
PAD = []                                    # on-screen camera pad: (button, function(dt))

LX = TL.x + 0.16
RX = TR.x - 0.16
PANEL_Y, PANEL_H = 0.01, 0.83

# ---- always visible: tiny title + mode ----
UI_PARENT[0] = camera.ui
make_label('ARCHIVISION 3D', TL.x + 0.075, TL.y - 0.014, 1.2, UI_TEXT)
make_label('REAL-WORLD DESIGN STUDIO', TL.x + 0.075, TL.y - 0.045, 0.65, UI_ACCENT)
top_mode = make_label('', TR.x - 0.30, TL.y - 0.02, 0.7, UI_ACCENT)

# ---- LEFT panel: level, rooms, view, add furniture, edit ----
UI_PARENT[0] = left_ui
make_panel(LX, PANEL_Y, 0.30, PANEL_H)
make_label('FLOOR', LX - 0.13, 0.405, 0.8, UI_ACCENT)
level_btns = [make_button('GROUND FLOOR', LX - 0.0725, 0.372, lambda: set_level(0), w=0.139),
              make_button('UPPER FLOOR', LX + 0.0725, 0.372, lambda: set_level(1), w=0.139)]
make_label('ROOMS', LX - 0.13, 0.335, 0.8, UI_ACCENT)
room_btns = []
for _i in range(5):
    room_btns.append(make_button('', LX, 0.303 - _i * 0.038,
                                 (lambda i=_i: (select_item(None, announce=False),
                                                select_room(LEVEL_ROOMS[state['level']][i])))))
view_btn = make_button('ENTER ROOM VIEW', LX, 0.102, toggle_view, col=(30, 90, 70))

make_label('ADD FURNITURE', LX - 0.13, 0.068, 0.8, UI_ACCENT)
for _i, _k in enumerate(ADD_LIST):
    make_button(BUTTON_LABEL.get(_k, LABEL[_k].upper()),
                LX + (-0.0725 if _i % 2 == 0 else 0.0725), 0.036 - (_i // 2) * 0.038,
                (lambda k=_k: add_item(k)), w=0.139)

make_label('EDIT SELECTED ITEM', LX - 0.13, -0.222, 0.8, UI_ACCENT)
make_button('ROTATE L', LX - 0.0725, -0.255, lambda: rotate_button(-15), w=0.139)
make_button('ROTATE R', LX + 0.0725, -0.255, lambda: rotate_button(15), w=0.139)
make_button('DUPLICATE', LX - 0.0725, -0.293, duplicate_selected, w=0.139)
make_button('REMOVE', LX + 0.0725, -0.293, remove_selected, w=0.139, col=(110, 40, 48))
make_button('RAISE', LX - 0.0725, -0.331, lambda: elevate_item(0.1), w=0.139)
make_button('LOWER', LX + 0.0725, -0.331, lambda: elevate_item(-0.1), w=0.139)
snap_btn = make_button('SNAP GRID: ON', LX, -0.369, toggle_snap)

# ---- RIGHT panel: selection, colours, lighting, visibility, camera ----
UI_PARENT[0] = right_ui
make_panel(RX, PANEL_Y, 0.30, PANEL_H)
make_label('SELECTION', RX - 0.13, 0.405, 0.8, UI_ACCENT)
info_text = make_label('', RX - 0.13, 0.382, 0.7)


def swatch_row(items, y, cb, cx=None):
    """items = [(key, rgb)]; returns {key: Button}."""
    cx = RX if cx is None else cx
    row = {}
    n = len(items)
    for i, (k, rgb) in enumerate(items):
        row[k] = Button(parent=UI_PARENT[0], position=(cx + (i - (n - 1) / 2) * 0.0345, y), scale=(0.03, 0.03),
                        color=rgba(rgb), highlight_color=rgba(rgb), pressed_color=rgba((255, 255, 255)),
                        on_click=(lambda c=k: cb(c)))
    return row


PAL_ITEMS = [(k, PALETTE[k][1]) for k in PALETTE_KEYS]
make_label('WALL COLOUR', RX - 0.13, 0.212, 0.8, UI_ACCENT)
wall_swatches = swatch_row(PAL_ITEMS, 0.176, lambda c: set_room_color(state['room'], 'wall', c))
make_label('FLOOR COLOUR', RX - 0.13, 0.138, 0.8, UI_ACCENT)
floor_swatches = swatch_row(PAL_ITEMS, 0.102, lambda c: set_room_color(state['room'], 'floor', c))

make_label('LIGHTING', RX - 0.13, 0.064, 0.8, UI_ACCENT)
mode_btn = make_button('MODE: DAY', RX, 0.030, lambda: set_night(not state['night']))
make_button('-', RX - 0.1, -0.012, lambda: set_brightness(state['brightness'] - 0.1), w=0.07)
make_button('+', RX + 0.1, -0.012, lambda: set_brightness(state['brightness'] + 0.1), w=0.07)
bright_text = Text('BRIGHTNESS 100%', parent=UI_PARENT[0], position=(RX, -0.012), origin=(0, 0),
                   scale=0.75, color=rgba(UI_TEXT))

make_label('VISIBILITY', RX - 0.13, -0.050, 0.8, UI_ACCENT)
roof_btn = make_button('ROOF: VISIBLE', RX, -0.086, lambda: set_roof(not state['roof']))
upper_btn = make_button('UPPER FLOOR: SHOWN', RX, -0.124, toggle_upper)
cut_btn = make_button('WALL CUTAWAY: ON', RX, -0.162, toggle_cut)

make_label('CAMERA', RX - 0.13, -0.200, 0.8, UI_ACCENT)
make_button('RESET VIEW', RX - 0.0725, -0.232, reset_view, w=0.139)
make_button('SCREENSHOT', RX + 0.0725, -0.232, take_screenshot, w=0.139)


def _pad(txt, x, y, fn):
    b = make_button(txt, x, y, lambda: None, w=0.043)
    PAD.append((b, fn))


def _pan_fn(r=0.0, f=0.0, u=0.0):
    def fn(dt):
        s = cam['dist'] * 0.9 * dt
        pan_camera(r * s, f * s, u * 6 * dt)
    return fn


def _orbit_fn(dyaw=0.0, dpitch=0.0):
    def fn(dt):
        cam['yaw_t'] += dyaw * 60 * dt
        cam['pitch_t'] += dpitch * 35 * dt
    return fn


def _zoom_fn(sign):
    def fn(dt):
        cam['dist_t'] += sign * (8 if state['view'] == 'room' else 18) * dt
    return fn


make_label('MOVE VIEW (hold): LT left  FW fwd  BK back  RT right  UP  DN', RX - 0.13, -0.256, 0.5)
for _i, (_t, _f) in enumerate((('LT', _pan_fn(r=-1)), ('FW', _pan_fn(f=1)), ('BK', _pan_fn(f=-1)),
                               ('RT', _pan_fn(r=1)), ('UP', _pan_fn(u=1)), ('DN', _pan_fn(u=-1)))):
    _pad(_t, RX + (_i - 2.5) * 0.047, -0.290, _f)
make_label('OL / OR orbit   T+ / T- tilt   + / - zoom', RX - 0.13, -0.322, 0.5)
for _i, (_t, _f) in enumerate((('OL', _orbit_fn(dyaw=-1)), ('OR', _orbit_fn(dyaw=1)),
                               ('T+', _orbit_fn(dpitch=1)), ('T-', _orbit_fn(dpitch=-1)),
                               ('+', _zoom_fn(-1)), ('-', _zoom_fn(1)))):
    _pad(_t, RX + (_i - 2.5) * 0.047, -0.356, _f)
make_label('Middle-drag: pan   Right-drag: orbit   Wheel: zoom', RX - 0.13, -0.384, 0.5)

# ---- BOTTOM bar: file, sun, photo studio ----
UI_PARENT[0] = bottom_ui
make_panel(0, BL.y + 0.045, window.aspect_ratio + 0.2, 0.09, UI_BAR)
make_button('SAVE', -0.62, BL.y + 0.045, save_design, w=0.14)
make_button('LOAD', -0.46, BL.y + 0.045, open_load_menu, w=0.14)
make_button('RESET', -0.30, BL.y + 0.045, reset_scene, w=0.14, col=(110, 40, 48))
make_button('HELP', -0.14, BL.y + 0.045, lambda: toggle_help(), w=0.14)
make_button('MENU', 0.02, BL.y + 0.045, lambda: open_main_menu(), w=0.14, col=(60, 50, 90))
make_label('TIME OF DAY', 0.19, BL.y + 0.070, 0.6, UI_ACCENT)
make_button('SUN -', 0.22, BL.y + 0.038, lambda: set_sun(state['sun_t'] - 0.1), w=0.1)
make_button('SUN +', 0.33, BL.y + 0.038, lambda: set_sun(state['sun_t'] + 0.1), w=0.1)
make_button('REAL-WORLD DESIGN STUDIO', 0.56, BL.y + 0.045, lambda: open_real_world_workspace(), w=0.30, col=(30, 90, 70))

# ---- PHOTO STUDIO panel (shown in the left slot while photo mode is on) ----
UI_PARENT[0] = photo_ui
make_panel(LX, PANEL_Y, 0.30, PANEL_H)
make_label('REAL-WORLD DESIGN', LX - 0.13, 0.405, 0.82, UI_ACCENT)
photo_info = make_label('', LX - 0.13, 0.380, 0.65)
make_label('COLOURS FOUND (click = side walls)', LX - 0.13, 0.300, 0.6, UI_ACCENT)
photo_found = swatch_row([(i, (90, 90, 90)) for i in range(6)], 0.268, photo_side_from_swatch, cx=LX)
make_button('LOAD / CHANGE PHOTO', LX - 0.0725, 0.226, open_photo_menu, w=0.139)
make_button('CLOSE PHOTO', LX + 0.0725, 0.226, close_photo_studio_image, w=0.139, col=(110, 40, 48))
make_button('COPY PHOTO COLOURS TO VILLA', LX, 0.188, apply_photo_to_villa)
make_label('FACADE TINT (preview a new colour)', LX - 0.13, 0.150, 0.6, UI_ACCENT)
make_button('ORIGINAL PHOTO', LX, 0.118, lambda: set_photo_tint(None))
photo_tints = swatch_row(PAL_ITEMS, 0.080, set_photo_tint, cx=LX)
make_label('ROOF', LX - 0.13, 0.044, 0.8, UI_ACCENT)
roof_style_btns = {s: make_button(s.upper(), LX + (i - 1) * 0.095, 0.012,
                                  (lambda s=s: photo_set(roof=s)), w=0.09)
                   for i, s in enumerate(('flat', 'gabled', 'none'))}
photo_roofs = swatch_row([(i, rc[1]) for i, rc in enumerate(ROOF_COLS)], -0.026,
                         lambda i: photo_set(roof_col=ROOF_COLS[i][1]), cx=LX)
make_label('BUILDING SIZE', LX - 0.13, -0.066, 0.8, UI_ACCENT)
for _r, (_n, _t) in enumerate((('w', 'WIDTH'), ('h', 'HEIGHT'), ('d', 'DEPTH'))):
    make_button(_t + ' -', LX - 0.0725, -0.100 - _r * 0.038, (lambda n=_n: photo_dim(n, -1.0)), w=0.139)
    make_button(_t + ' +', LX + 0.0725, -0.100 - _r * 0.038, (lambda n=_n: photo_dim(n, 1.0)), w=0.139)
make_label('SURROUNDINGS', LX - 0.13, -0.222, 0.8, UI_ACCENT)
garden_btn = make_button('GARDEN: ON', LX - 0.0725, -0.255, lambda: photo_set(garden=not PHOTO['garden']), w=0.139)
pool_btn = make_button('POOL: OFF', LX + 0.0725, -0.255, lambda: photo_set(pool=not PHOTO['pool']), w=0.139)
make_button('SNAPSHOT (PNG)', LX, -0.300, take_screenshot)
make_button('BACK TO VILLA', LX, -0.345, exit_photo_mode, col=(30, 90, 70))
make_label('PHOTO + 3D ROOM WORKFLOW', LX - 0.13, -0.382, 0.48)

# ---- edge strips + status ----
UI_PARENT[0] = camera.ui
left_tab = make_button('≡', TL.x + 0.030, TL.y - 0.075, lambda: toggle_panel('left'), w=0.038, h=0.052,
                       col=(16, 22, 36, 225))
right_tab = make_button('◈', TR.x - 0.030, TR.y + 0.075, lambda: toggle_panel('right'), w=0.038, h=0.052,
                        col=(16, 22, 36, 225))
bottom_tab = make_button('FILE  ▴', 0, BL.y + 0.025, lambda: toggle_panel('bottom'),
                         w=0.105, h=0.026, col=(16, 22, 36, 225))
status_text = Text('F1 TOOLS   F2 STYLE   F3 FILE   |   H HELP',
                   parent=camera.ui, position=(0, BL.y + 0.055), origin=(0, 0),
                   scale=0.58, color=rgba(UI_ACCENT))


def sync_panels():
    left_ui.enabled = ui_open['left'] and not state['photo']
    photo_ui.enabled = ui_open['left'] and state['photo']
    right_ui.enabled = ui_open['right']
    bottom_ui.enabled = ui_open['bottom']
    lo, ro, bo = ui_open['left'], ui_open['right'], ui_open['bottom']
    left_tab.x = TL.x + (0.335 if lo else 0.025)
    left_tab.text = '×' if lo else '≡'
    right_tab.x = TR.x - (0.335 if ro else 0.025)
    right_tab.text = '×' if ro else '◈'
    bottom_tab.y = BL.y + (0.108 if bo else 0.018)
    bottom_tab.text = 'HIDE' if bo else 'FILE  ▴'
    status_text.y = BL.y + (0.145 if bo else 0.062)


def set_panel(which, flag):
    ui_open[which] = flag
    sync_panels()


def toggle_panel(which):
    set_panel(which, not ui_open[which])


def close_panels():
    for k in ui_open:
        ui_open[k] = False
    sync_panels()


# ---- help overlay ----
help_panel = Entity(parent=camera.ui, enabled=False)
Entity(parent=help_panel, model='quad', position=(0, 0, 0.4), scale=(0.95, 0.88), color=rgba(UI_PANEL))
make_label('KEYBOARD AND MOUSE CONTROLS', -0.43, 0.40, 1.0, UI_ACCENT, parent=help_panel)
make_label(
    'PANELS\n'
    '  Click the TOOLS strip (left), STYLE strip (right), FILE strip (bottom)   F1 / F2 / F3\n\n'
    'MOVE THE VIEW\n'
    '  Arrow keys : move left / right / forward / back      Shift + Up / Down : camera up / down\n'
    '  A / D : orbit     W / S : tilt     Wheel or , / . : zoom     V : reset view\n'
    '  Middle-drag : pan     Right-drag : orbit     (or hold the pad buttons in the STYLE panel)\n\n'
    'VIEWS\n'
    '  F : enter / leave the selected room (walls in front are cut away automatically)\n'
    '  C : wall cutaway     U : upper floor on / off     R : roof on / off\n'
    '  Page Up / Page Down : upper / ground floor     1 - 5 : select room of this floor\n\n'
    'FURNITURE\n'
    '  Click an item, then DRAG it with the left mouse button (it stays inside its room).\n'
    '  I J K L : move     Q / E : rotate     RAISE / LOWER : height above floor\n'
    '  X or Delete : remove     Tab : next item     G : snap grid     DUPLICATE button\n\n'
    'SCENE\n'
    '  N : day / night     - / = : brightness     SUN - / SUN + : time of day     P : screenshot\n'
    '  F5 : save     F9 : load latest     H : this help     Esc : back / close / exit\n\n'
    'REAL-WORLD DESIGN STUDIO  (bottom bar)\n'
    '  Opens a separate workspace for room photo editing and approximate 3D room reconstruction.',
    -0.43, 0.35, 0.74, UI_TEXT, parent=help_panel)
make_button('CLOSE', 0, -0.40, lambda: toggle_help(), w=0.2, parent=help_panel)


def toggle_help():
    state['help'] = not state['help']
    help_panel.enabled = state['help']


def refresh_photo_ui():
    if 'photo_info' not in globals():
        return
    if PHOTO['img'] is None:
        photo_info.text = 'No photo yet.\nUse LOAD / CHANGE PHOTO.'
    else:
        photo_info.text = (f'FILE   : {PHOTO["name"][:26]}\n'
                           f'SIZE   : {PHOTO["w"]:.0f} x {PHOTO["h"]:.0f} x {PHOTO["d"]:.0f} m\n'
                           f'ROOF   : {PHOTO["roof"].title()}')
    for i, b in photo_found.items():
        cols = PHOTO['colors']
        b.color = rgba(cols[i] if i < len(cols) else (60, 60, 60))
        b.highlight_color = b.color
    for k, b in photo_tints.items():
        b.scale = (0.038, 0.038) if k == PHOTO['tint'] else (0.030, 0.030)
    for s, b in roof_style_btns.items():
        b.color = rgba(UI_ACTIVE if s == PHOTO['roof'] else UI_BTN)
    for i, b in photo_roofs.items():
        b.scale = (0.038, 0.038) if ROOF_COLS[i][1] == PHOTO['roof_col'] else (0.030, 0.030)
    garden_btn.text = 'GARDEN: ON' if PHOTO['garden'] else 'GARDEN: OFF'
    pool_btn.text = 'POOL: ON' if PHOTO['pool'] else 'POOL: OFF'


def refresh_ui():
    rk = state['room']
    rt = room_rt[rk]
    it = state['item']
    lvl = state['level']
    info_text.text = (f'ROOM   : {ROOMS[rk]["label"]}\n'
                      f'LEVEL  : {"Upper floor" if ROOMS[rk]["level"] else "Ground floor"}\n'
                      f'WALLS  : {PALETTE[rt["wall_color"]][0]}\n'
                      f'FLOOR  : {PALETTE[rt["floor_color"]][0]}\n'
                      f'ITEM   : {LABEL[it.kind] if it else "none"}')
    for i, b in enumerate(level_btns):
        b.color = rgba(UI_ACTIVE if i == lvl else UI_BTN)
    for b, k in zip(room_btns, LEVEL_ROOMS[lvl]):
        b.text = ROOMS[k]['label'].upper()
        b.color = rgba(UI_ACTIVE if k == rk else UI_BTN)
    view_btn.text = 'BACK TO EXTERIOR' if state['view'] == 'room' else 'ENTER ROOM VIEW'
    for ck, b in wall_swatches.items():
        b.scale = (0.038, 0.038) if ck == rt['wall_color'] else (0.030, 0.030)
    for ck, b in floor_swatches.items():
        b.scale = (0.038, 0.038) if ck == rt['floor_color'] else (0.030, 0.030)
    mode_btn.text = 'MODE: NIGHT (click for day)' if state['night'] else 'MODE: DAY (click for night)'
    roof_btn.text = 'ROOF: VISIBLE' if state['roof'] else 'ROOF: HIDDEN'
    upper_btn.text = 'UPPER FLOOR: SHOWN' if state['upper'] else 'UPPER FLOOR: HIDDEN'
    cut_btn.text = 'WALL CUTAWAY: ON' if state['cut'] else 'WALL CUTAWAY: OFF'
    snap_btn.text = 'SNAP GRID: ON' if state['snap'] else 'SNAP GRID: OFF'
    bright_text.text = f'BRIGHTNESS {int(state["brightness"] * 100)}%'
    top_mode.text = (f'{"NIGHT" if state["night"] else "DAY"}  |  '
                     f'{"PHOTO STUDIO" if state["photo"] else "ROOM VIEW" if state["view"] == "room" else "EXTERIOR"}')
    refresh_photo_ui()


select_room('living_room', announce=False)
refresh_ui()
sync_panels()


# =====================================================================
# 13.5. MAIN MENU  (shown on startup, reachable any time from the FILE bar)
# =====================================================================
MENU_STATE = dict(active=True)

main_menu = Entity(parent=camera.ui, enabled=True)
Entity(parent=main_menu, model='quad', scale=(4, 4), position=(0, 0, 0.9), color=rgba((10, 14, 22, 250)))
Text('ARCHIVISION 3D', parent=main_menu, position=(0, 0.27), origin=(0, 0),
     scale=2.4, color=rgba(UI_TEXT))
Text('REAL-WORLD ARCHITECTURAL STUDIO', parent=main_menu, position=(0, 0.195), origin=(0, 0),
     scale=1.0, color=rgba(UI_ACCENT))
menu_hint = Text('', parent=main_menu, position=(0, -0.335), origin=(0, 0), scale=0.7, color=rgba(UI_TEXT))


def _menu_hide():
    MENU_STATE['active'] = False
    main_menu.enabled = False


def menu_new_project():
    _menu_hide()
    reset_scene()
    set_status('New project started')


def menu_continue_project():
    _menu_hide()
    files = saved_files()
    if files:
        load_design(files[0])
        set_status(f'Continuing: {files[0].name}')
    else:
        set_status('No saved design found - starting with a fresh villa')


def menu_load_project():
    _menu_hide()
    open_load_menu()


def menu_interior_studio():
    _menu_hide()
    open_real_world_workspace()


def menu_exit():
    application.quit()


def open_main_menu():
    files = saved_files()
    menu_hint.text = (f'Last save: {files[0].name}' if files else 'No saved designs yet')
    MENU_STATE['active'] = True
    main_menu.enabled = True


make_button('NEW PROJECT', 0, 0.075, menu_new_project, w=0.34, h=0.05, parent=main_menu)
make_button('CONTINUE LAST PROJECT', 0, 0.01, menu_continue_project, w=0.34, h=0.05, parent=main_menu)
make_button('LOAD A SAVED DESIGN', 0, -0.055, menu_load_project, w=0.34, h=0.05, parent=main_menu)
make_button('INTERIOR DESIGN STUDIO', 0, -0.12, menu_interior_studio, w=0.34, h=0.05, parent=main_menu,
            col=(30, 90, 70))
make_button('EXIT', 0, -0.185, menu_exit, w=0.34, h=0.05, parent=main_menu, col=(110, 40, 48))
open_main_menu()


# =====================================================================
# 14. INPUT AND MAIN LOOP
# =====================================================================
HOUSE_KEYS = ('f', 'u', 'c', 'g', 'page up', 'page down', 'x', 'delete', 'tab', 'r',
              '1', '2', '3', '4', '5')


def in_viewport():
    half = window.aspect_ratio / 2
    lo = -half + (0.345 if ui_open['left'] else 0.06)
    hi = half - (0.345 if ui_open['right'] else 0.06)
    low_y = -0.41 if ui_open['bottom'] else -0.46
    return lo < mouse.x < hi and low_y < mouse.y < 0.5


def handle_click():
    if state['popup'] is not None or state['help'] or state['photo'] or not in_viewport():
        return
    ent = mouse.hovered_entity
    if ent is None:
        select_item(None, announce=False)
        return
    item = getattr(ent, 'ab_item', None)
    if item is not None:
        select_item(item)
        start_drag(item)
        return
    room = getattr(ent, 'ab_room', None)
    if room:
        select_item(None, announce=False)
        select_room(room)


def cycle_item():
    items = [i for i in ITEMS if i.level == state['level']]
    if not items:
        return
    cur = state['item']
    idx = (items.index(cur) + 1) % len(items) if cur in items else 0
    select_item(items[idx])


def input(key):
    if REAL_ROOM.get('active'):
        if key == 'escape':
            exit_real_room_mode()
        elif key in ('+', '='):
            adjust_real_room('width', 0.5)
        elif key in ('-', '_'):
            adjust_real_room('width', -0.5)
        elif key == ']':
            adjust_real_room('depth', 0.5)
        elif key == '[':
            adjust_real_room('depth', -0.5)
        elif key == 'page up':
            adjust_real_room('height', 0.2)
        elif key == 'page down':
            adjust_real_room('height', -0.2)
        elif key == 's':
            data = {'width': REAL_ROOM['width'], 'depth': REAL_ROOM['depth'], 'height': REAL_ROOM['height'], 'photo': REAL_ROOM['photo_path']}
            out = SAVE_DIR / f'real_room_{datetime.now():%Y%m%d_%H%M%S}.json'
            out.write_text(json.dumps(data, indent=2), encoding='utf-8')
            set_status(f'3D room dimensions saved: {out.name}')
        elif key in ('1', '2', '3', '4', '5', '6'):
            REAL_ROOM['wall_color'] = REAL_STUDIO_COLORS[int(key) - 1][1]
            build_real_room()
            real_room_root.enabled = True
            set_status(f'3D room wall finish: {REAL_STUDIO_COLORS[int(key) - 1][0]}')
        elif key == '7':
            floors = [(190, 185, 174), (150, 135, 116), (215, 211, 201), (95, 99, 105)]
            current = REAL_ROOM.get('floor_color', floors[0])
            REAL_ROOM['floor_color'] = floors[(floors.index(current) + 1) % len(floors)] if current in floors else floors[0]
            build_real_room()
            real_room_root.enabled = True
            set_status('3D room floor finish changed.')
        elif key == 't':
            REAL_ROOM['kind'] = 'living' if REAL_ROOM.get('kind') == 'classroom' else 'classroom'
            build_real_room()
            real_room_root.enabled = True
            set_status('3D room type: ' + REAL_ROOM['kind'])
        elif key == 'scroll up':
            cam['dist_t'] = max(5.0, cam['dist_t'] - 1.0)
        elif key == 'scroll down':
            cam['dist_t'] = min(35.0, cam['dist_t'] + 1.0)
        elif key == 'left mouse down':
            pass
        return
    if state['photo'] and key in HOUSE_KEYS:
        return
    if key == 'left mouse down':
        handle_click()
    elif key == 'left mouse up':
        end_drag()
    elif key == 'scroll up':
        if in_viewport():
            cam['dist_t'] -= 2.0 if state['view'] == 'exterior' else 0.8
    elif key == 'scroll down':
        if in_viewport():
            cam['dist_t'] += 2.0 if state['view'] == 'exterior' else 0.8
    elif key == ',':
        cam['dist_t'] -= 2.0
    elif key == '.':
        cam['dist_t'] += 2.0
    elif key == 'n':
        set_night(not state['night'])
    elif key == 'r':
        set_roof(not state['roof'])
    elif key == 'u':
        toggle_upper()
    elif key == 'c':
        toggle_cut()
    elif key == 'g':
        toggle_snap()
    elif key == 'f':
        toggle_view()
    elif key == 'page up':
        set_level(1)
    elif key == 'page down':
        set_level(0)
    elif key == 'v':
        reset_view()
    elif key == 'h':
        toggle_help()
    elif key == 'p':
        take_screenshot()
    elif key == 'f1':
        toggle_panel('left')
    elif key == 'f2':
        toggle_panel('right')
    elif key == 'f3':
        toggle_panel('bottom')
    elif key in ('x', 'delete'):
        remove_selected()
    elif key == 'tab':
        cycle_item()
    elif key in ('1', '2', '3', '4', '5'):
        select_item(None, announce=False)
        select_room(LEVEL_ROOMS[state['level']][int(key) - 1])
    elif key == '-':
        set_brightness(state['brightness'] - 0.1)
    elif key == '=':
        set_brightness(state['brightness'] + 0.1)
    elif key == 'f5':
        save_design()
    elif key == 'f9':
        files = saved_files()
        if files:
            load_design(files[0])
        else:
            set_status('No saved designs found')
    elif key == 'escape':
        if state['popup'] is not None:
            close_popup()
        elif state['help']:
            toggle_help()
        elif state['photo']:
            exit_photo_mode()
        elif any(ui_open.values()):
            close_panels()
        elif state['view'] == 'room':
            toggle_view()
        else:
            open_main_menu()


def update():
    dt = time.dt
    room_view = state['view'] == 'room'

    # --- camera: arrows pan, A D orbit, W S tilt, shift+up/down height, mouse buttons ---
    px = held_keys['right arrow'] - held_keys['left arrow']
    pz = held_keys['up arrow'] - held_keys['down arrow']
    s = cam['dist'] * 0.9 * dt
    if held_keys['shift']:
        pan_camera(px * s, 0.0, pz * 6 * dt)
    elif px or pz:
        pan_camera(px * s, pz * s)
    if held_keys['a']:
        cam['yaw_t'] -= 60 * dt
    if held_keys['d']:
        cam['yaw_t'] += 60 * dt
    if held_keys['w']:
        cam['pitch_t'] += 35 * dt
    if held_keys['s']:
        cam['pitch_t'] -= 35 * dt
    if mouse.left:
        for b, fn in PAD:
            if b.hovered:
                fn(dt)
    if REAL_ROOM.get('active') or in_viewport():
        if mouse.right:
            cam['yaw_t'] -= mouse.velocity[0] * 220
            cam['pitch_t'] -= mouse.velocity[1] * 140
        if getattr(mouse, 'middle', False):
            pan_camera(-mouse.velocity[0] * cam['dist'] * 1.3, -mouse.velocity[1] * cam['dist'] * 1.3)
    if room_view:
        cam['pitch_t'] = max(12, min(85, cam['pitch_t']))
        cam['dist_t'] = max(4, min(28, cam['dist_t']))
    else:
        cam['pitch_t'] = max(6, min(80, cam['pitch_t']))
        cam['dist_t'] = max(10, min(80, cam['dist_t']))
    k = min(1.0, dt * 7)
    for name in ('yaw', 'pitch', 'dist', 'tx', 'ty', 'tz'):
        cam[name] += (cam[name + '_t'] - cam[name]) * k
    apply_camera()
    update_cutaway()

    # --- furniture: mouse drag ---
    d = state['drag']
    if d is not None:
        if not mouse.left:
            end_drag()
        else:
            wp = getattr(mouse, 'world_point', None)
            if wp is not None and in_viewport():
                x, z = wp.x + drag_off[0], wp.z + drag_off[1]
                if state['snap']:
                    x, z = round(x * 4) / 4, round(z * 4) / 4
                set_target(d, x, z)

    # --- furniture: keys I J K L move, Q E rotate ---
    it = state['item']
    if it is not None and state['popup'] is None and state['drag'] is None and not state['photo']:
        mx = held_keys['l'] - held_keys['j']
        mz = held_keys['i'] - held_keys['k']
        if mx or mz:
            yaw = math.radians(cam['yaw'])
            fx, fz = -math.sin(yaw), math.cos(yaw)
            rx, rz = math.cos(yaw), math.sin(yaw)
            step = 3.0 * dt
            set_target(it, it.tx + (rx * mx + fx * mz) * step, it.tz + (rz * mx + fz * mz) * step)
        spin = held_keys['e'] - held_keys['q']
        if spin:
            rotate_item(spin * 90 * dt)

    # --- smooth movement of every item towards its target (position, height, rotation) ---
    k2 = min(1.0, dt * 16)
    for o in ITEMS:
        r = o.root
        r.x += (o.tx - r.x) * k2
        r.z += (o.tz - r.z) * k2
        r.y += (floor_y(o.level) + o.elev - r.y) * k2
        diff = ((o.trot - r.rotation_y + 180) % 360) - 180
        r.rotation_y = r.rotation_y + diff * k2

    # --- pool water shimmer ---
    if TEX.get('water') is not None:
        water_t[0] += dt
        off = (water_t[0] * 0.03, water_t[0] * 0.02)
        for w in (PHOTO_WATERS if state['photo'] else WATERS):
            w.texture_offset = off




# =====================================================================
# 14.5. DEDICATED REAL-WORLD DESIGN WORKSPACE
# =====================================================================
# This workspace is a separate application page. It never places the
# selected room photograph on the villa facade. The image remains in a
# 2D design canvas until the user explicitly chooses BUILD 3D ROOM.

REAL_STUDIO = {
    'active': False,
    'image': None,
    'image_path': None,
    'display_texture': None,
    'camera': None,
    'camera_texture': None,
    'camera_size': None,
    'last_frame': None,
    'points': [],
    'regions': [],
    'target': 'WALL',
    'palette_index': 0,
    'status': 'Choose a room photo to get started.',
    'image_rect': (0.0, 0.0, 1.0, 1.0),
}

REAL_STUDIO_COLORS = [
    ('Warm white', (242, 235, 220)),
    ('Sage green', (151, 171, 139)),
    ('Soft blue', (145, 177, 205)),
    ('Charcoal', (75, 79, 86)),
    ('Sand beige', (205, 183, 150)),
    ('Terracotta', (185, 112, 82)),
]

# Dedicated, uncluttered interior-design workspace.
workspace_ui = Entity(parent=camera.ui, enabled=False)
ws_background = Entity(parent=workspace_ui, model='quad', position=(0, 0, 2),
                       scale=(2 * window.aspect_ratio + 0.2, 2.2),
                       color=rgba((12, 17, 27)))
ws_left_panel = Entity(parent=workspace_ui, model='quad',
                       position=(TL.x + 0.205, 0, 1),
                       scale=(0.41, 1.78), color=rgba((23, 31, 45, 250)))
ws_right_panel = Entity(parent=workspace_ui, model='quad',
                        position=(TR.x - 0.205, 0, 1),
                        scale=(0.41, 1.78), color=rgba((23, 31, 45, 250)))
ws_title = Text('ARCHIVISION 3D',
                parent=workspace_ui, position=(TL.x + 0.10, 0.465),
                origin=(-.5, .5), scale=0.72, color=rgba((220, 232, 244)))
ws_subtitle = Text('INTERIOR DESIGN STUDIO',
                   parent=workspace_ui, position=(TL.x + 0.10, 0.430),
                   origin=(-.5, .5), scale=0.43, color=rgba((107, 190, 177)))
ws_image = Entity(parent=workspace_ui, model='quad', position=(0, -0.015, 0.35),
                  scale=(1.25, 0.82), color=color.white)
ws_placeholder = Text('YOUR ROOM WILL APPEAR HERE\n\nBrowse a room photo to get started',
                      parent=workspace_ui, position=(0, 0), origin=(0, 0),
                      scale=0.72, color=rgba((183, 196, 210)))
ws_status = Text(REAL_STUDIO['status'], parent=workspace_ui,
                 position=(0, -0.465), origin=(0, 0), scale=0.43,
                 color=rgba((130, 205, 190)))


def ws_label(text_value, x, y, scale=0.52, col=(205, 218, 230)):
    return Text(text_value, parent=workspace_ui, position=(x, y * 0.5), origin=(0, 0),
                scale=scale, color=rgba(col))


def ws_button(text_value, x, y, callback, width=0.32, height=0.060, col=(43, 57, 75)):
    b = Button(parent=workspace_ui, text=text_value, position=(x, y * 0.5, 0),
               scale=(width, height * 0.5), color=rgba(col),
               highlight_color=rgba((68, 105, 125)),
               pressed_color=rgba((42, 126, 112)), on_click=callback)
    b.text_size = 0.56
    return b


ws_lx = TL.x + 0.205
ws_rx = TR.x - 0.205
ws_label('ROOM PHOTO', ws_lx, 0.72, 0.56, (112, 197, 183))
ws_button('BROWSE COMPUTER', ws_lx, 0.61, lambda: ws_browse_image(), col=(48, 76, 105))
ws_button('CLOSE PHOTO', ws_lx, 0.51, lambda: ws_close_photo(), col=(91, 55, 60))
ws_label('WALL / FLOOR COLOUR', ws_lx, 0.17, 0.50, (112, 197, 183))
ws_wall_btn = ws_button('WALL', ws_lx - 0.082, 0.075,
                        lambda: ws_set_target('WALL'), width=0.145, height=0.055)
ws_floor_btn = ws_button('FLOOR', ws_lx + 0.082, 0.075,
                         lambda: ws_set_target('FLOOR'), width=0.145, height=0.055)
ws_button('APPLY COLOUR AREA', ws_lx, -0.025,
          lambda: ws_apply_polygon(), col=(42, 91, 83))
ws_button('UNDO / CLEAR', ws_lx, -0.125,
          lambda: ws_undo_region(), col=(43, 57, 75))
ws_button('RESET PHOTO DESIGN', ws_lx, -0.225,
          lambda: ws_reset_design(), col=(43, 57, 75))
ws_button('AUTO-GUESS WALL + FLOOR', ws_lx, -0.325,
          lambda: ws_auto_surfaces(), col=(42, 91, 83))

ws_label('INTERIOR FINISHES', ws_rx, 0.72, 0.56, (112, 197, 183))
ws_palette_buttons = []
for _i, (_name, _rgb) in enumerate(REAL_STUDIO_COLORS):
    _col = _i % 2
    _row = _i // 2
    _x = ws_rx + (-0.080 if _col == 0 else 0.080)
    _y = 0.59 - _row * 0.105
    _b = ws_button(_name.upper(), _x, _y,
                   lambda i=_i: ws_select_color(i),
                   width=0.145, height=0.070, col=_rgb)
    _b.text_color = rgba((25, 30, 38))
    ws_palette_buttons.append(_b)
ws_color_name = ws_label('Warm white selected', ws_rx, 0.235, 0.43)
ws_label('AUTO INTERIOR DESIGN', ws_rx, 0.145, 0.50, (112, 197, 183))
ws_button('BUILD FURNISHED 3D ROOM', ws_rx, 0.045,
          lambda: ws_build_3d_room(), width=0.34, col=(35, 105, 91))
ws_button('SAVE DESIGNED PHOTO', ws_rx, -0.055,
          lambda: ws_save_design(), width=0.34, col=(42, 91, 83))
ws_kind_btn = ws_button('ROOM TYPE: CLASSROOM', ws_rx, -0.155,
          lambda: ws_toggle_kind(), width=0.34, col=(43, 57, 75))
ws_button('BACK TO VILLA STUDIO', ws_rx, -0.69,
          lambda: close_real_world_workspace(), width=0.34, col=(75, 62, 75))
ws_help = ws_label('Click around a wall or floor to outline it.\nPress ENTER to apply • U to undo • ESC to return',
                   0, -0.435, 0.43, (156, 171, 188))



def ws_set_status(message):
    REAL_STUDIO['status'] = str(message)
    ws_status.text = REAL_STUDIO['status']


def ws_close_camera():
    cap = REAL_STUDIO.get('camera')
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass
    REAL_STUDIO['camera'] = None
    REAL_STUDIO['camera_texture'] = None
    REAL_STUDIO['camera_size'] = None
    REAL_STUDIO['last_frame'] = None


def ws_fit_image(width, height):
    aspect = max(0.6, float(width) / max(1, height))
    # Leave the two side control panels clear; keep the photo fully visible.
    max_width = max(0.5, window.aspect_ratio - 0.90)
    max_height = 0.80
    if aspect >= max_width / max_height:
        dw, dh = max_width, max_width / aspect
    else:
        dh, dw = max_height, max_height * aspect
    ws_image.scale = (dw, dh)
    ws_image.position = (0, -0.015, 0.35)
    REAL_STUDIO['image_rect'] = (ws_image.x - dw / 2, ws_image.y - dh / 2, dw, dh)


def ws_shade_regions(img, regions):
    """Recolour traced regions but keep the photo's own light, shadow and texture."""
    from PIL import ImageChops, ImageStat
    base = img.convert('RGB')
    gray = base.convert('L')
    gray_rgb = gray.convert('RGB')
    for polygon, rgb, target in regions:
        if len(polygon) < 3:
            continue
        mask = PILImage.new('L', base.size, 0)
        ImageDraw.Draw(mask).polygon([tuple(p) for p in polygon], fill=255)
        mean = max(20.0, ImageStat.Stat(gray, mask).mean[0])
        gain = 255.0 / mean
        tint = PILImage.new('RGB', base.size, tuple(rgb))
        shaded = ImageChops.multiply(tint, gray_rgb).point(lambda v, g=gain: min(255, int(v * g)))
        mask = mask.filter(ImageFilter.GaussianBlur(1.2))
        base = PILImage.composite(shaded, base, mask)
    return base


def ws_composed():
    """Photo with all applied colour regions (cached until the regions change)."""
    img = REAL_STUDIO.get('image')
    if img is None:
        return None
    key = (id(img), str(REAL_STUDIO['regions']))
    cache = REAL_STUDIO.get('_cache')
    if cache is None or cache[0] != key:
        cache = (key, ws_shade_regions(img, REAL_STUDIO['regions']))
        REAL_STUDIO['_cache'] = cache
    return cache[1]


def ws_render_image():
    img = REAL_STUDIO.get('image')
    if img is None:
        ws_image.enabled = False
        ws_placeholder.enabled = True
        return
    canvas = ws_composed().convert('RGBA')
    overlay = PILImage.new('RGBA', canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, 'RGBA')
    lw = max(2, int(min(canvas.size) * 0.002))
    for polygon, rgb, target in REAL_STUDIO['regions']:
        if len(polygon) >= 3:
            draw.line([tuple(p) for p in polygon] + [tuple(polygon[0])], fill=(255, 255, 255, 120), width=1)
    pts = REAL_STUDIO['points']
    if len(pts) >= 2:
        draw.line([tuple(p) for p in pts], fill=(50, 230, 195, 255), width=lw)
    for pt in pts:
        r = max(4, int(min(canvas.size) * 0.004))
        draw.ellipse((pt[0]-r, pt[1]-r, pt[0]+r, pt[1]+r), fill=(50, 230, 195, 255))
    canvas = PILImage.alpha_composite(canvas, overlay).convert('RGB')
    ws_image.texture = Texture(canvas)
    ws_image.enabled = True
    ws_placeholder.enabled = False
    ws_fit_image(canvas.width, canvas.height)


def ws_set_image(img, path=None):
    ws_close_camera()
    img = img.convert('RGB')
    img.thumbnail((2200, 1600), PILImage.Resampling.LANCZOS)
    REAL_STUDIO['image'] = img.copy()
    REAL_STUDIO['image_path'] = str(path) if path else None
    REAL_STUDIO['points'] = []
    REAL_STUDIO['regions'] = []
    ws_render_image()
    ws_set_status(f'Loaded {Path(path).name if path else "captured room image"}. Select a surface and trace its boundary.')


def ws_browse_image():
    """Open a native Windows file picker for common interior-photo formats."""
    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
            root.update()
        except Exception:
            pass
        path = filedialog.askopenfilename(
            parent=root,
            title='Choose a bedroom, living room or other interior photo',
            initialdir=str(Path.home() / 'Pictures'),
            filetypes=[
                ('Interior photographs', '*.jpg *.jpeg *.png *.webp *.bmp'),
                ('All image files', '*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff'),
                ('All files', '*.*')
            ])
        if path:
            with PILImage.open(path) as selected:
                selected.load()
                ws_set_image(selected.copy(), path)
        else:
            ws_set_status('No photo selected. Choose BROWSE COMPUTER to try again.')
    except Exception as exc:
        ws_set_status(f'Photo browser could not open: {exc}')
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass



def ws_close_photo():
    """Close/clear the currently loaded workspace photo without picking a new one."""
    ws_close_camera()
    REAL_STUDIO['image'] = None
    REAL_STUDIO['image_path'] = None
    REAL_STUDIO['points'] = []
    REAL_STUDIO['regions'] = []
    REAL_STUDIO['_cache'] = None
    ws_image.enabled = False
    ws_placeholder.enabled = True
    ws_set_status('Photo closed. Choose BROWSE COMPUTER to open another.')


def ws_set_target(target):
    REAL_STUDIO['target'] = target
    ws_wall_btn.color = rgba(UI_ACTIVE if target == 'WALL' else UI_BTN)
    ws_floor_btn.color = rgba(UI_ACTIVE if target == 'FLOOR' else UI_BTN)
    ws_set_status(f'{target} selected. Click points around that surface, then apply the polygon.')


def ws_select_color(index):
    REAL_STUDIO['palette_index'] = index
    ws_color_name.text = REAL_STUDIO_COLORS[index][0]
    for i, button in enumerate(ws_palette_buttons):
        button.scale = (0.152, 0.040) if i == index else (0.145, 0.035)
    ws_set_status(f'Design colour: {REAL_STUDIO_COLORS[index][0]}')


def ws_apply_polygon():
    pts = REAL_STUDIO['points']
    if len(pts) < 3:
        ws_set_status('A surface region needs at least three points.')
        return
    rgb = REAL_STUDIO_COLORS[REAL_STUDIO['palette_index']][1]
    REAL_STUDIO['regions'].append((pts.copy(), rgb, REAL_STUDIO['target']))
    REAL_STUDIO['points'] = []
    ws_render_image()
    ws_set_status(f'{REAL_STUDIO["target"]} colour applied. Add another region or save the design.')


def ws_undo_region():
    if REAL_STUDIO['points']:
        REAL_STUDIO['points'].pop()
    elif REAL_STUDIO['regions']:
        REAL_STUDIO['regions'].pop()
    ws_render_image()
    ws_set_status('Last point or applied region undone.')


def ws_clear_points():
    REAL_STUDIO['points'] = []
    ws_render_image()
    ws_set_status('Pending polygon points cleared.')


def ws_reset_design():
    REAL_STUDIO['points'] = []
    REAL_STUDIO['regions'] = []
    ws_render_image()
    ws_set_status('Photo design reset to the original image.')


def ws_save_design():
    img = REAL_STUDIO.get('image')
    if img is None:
        ws_set_status('Open a room photo first.')
        return
    result = ws_composed().convert('RGB')
    out = PHOTO_DIR / f'archivision_room_design_{datetime.now():%Y%m%d_%H%M%S}.jpg'
    result.save(out, quality=96)
    ws_set_status(f'Design saved: {out.name}')


def ws_build_3d_room():
    img = REAL_STUDIO.get('image')
    if img is None:
        ws_set_status('Open a room photo or capture one before building the 3D room.')
        return
    # Keep the image in the room-design workflow; do NOT call load_photo(),
    # because that old function attaches the picture to the villa facade.
    PHOTO['img'] = img.copy()
    PHOTO['name'] = Path(REAL_STUDIO['image_path']).name if REAL_STUDIO.get('image_path') else 'Captured room'
    PHOTO['source_path'] = REAL_STUDIO.get('image_path')
    PHOTO['tex'] = Texture(img.convert('RGBA'))
    REAL_ROOM['photo_path'] = REAL_STUDIO.get('image_path')
    REAL_ROOM['photo_texture'] = Texture(ws_composed().convert('RGBA'))
    REAL_ROOM['active'] = False
    REAL_ROOM['width'], REAL_ROOM['depth'], REAL_ROOM['height'] = 8.0, 7.0, 3.2
    REAL_ROOM['wall_color'] = (232, 229, 220)
    REAL_ROOM['floor_color'] = (190, 185, 174)
    for _poly, _rgb, _target in REAL_STUDIO['regions']:      # the colours you chose carry into 3D
        REAL_ROOM['wall_color' if _target == 'WALL' else 'floor_color'] = tuple(_rgb)
    analyse_photo()
    close_real_world_workspace()
    enter_real_room_mode()
    set_status('Approximate editable 3D room created from the selected reference photo.')


def ws_auto_surfaces():
    """Rough one-point-perspective guess: back wall, two side walls and floor. Edit/undo as needed."""
    img = REAL_STUDIO.get('image')
    if img is None:
        ws_set_status('Open a room photo or capture one first.')
        return
    w, h = img.size
    wall_rgb = REAL_STUDIO_COLORS[REAL_STUDIO['palette_index']][1]
    floor_rgb = REAL_STUDIO_COLORS[4][1]
    L, R, T, B = 0.15 * w, 0.85 * w, 0.14 * h, 0.62 * h
    REAL_STUDIO['regions'] += [
        ([(L, T), (R, T), (R, B), (L, B)], wall_rgb, 'WALL'),
        ([(0, 0), (L, T), (L, B), (0, h)], wall_rgb, 'WALL'),
        ([(R, T), (w, 0), (w, h), (R, B)], wall_rgb, 'WALL'),
        ([(0, h), (L, B), (R, B), (w, h)], floor_rgb, 'FLOOR'),
    ]
    ws_render_image()
    ws_set_status('Auto-guess applied (rough). Press U to undo, or trace the real wall/floor edges yourself.')


def ws_toggle_kind():
    REAL_ROOM['kind'] = 'living' if REAL_ROOM.get('kind', 'classroom') == 'classroom' else 'classroom'
    ws_kind_btn.text = 'ROOM TYPE: ' + REAL_ROOM['kind'].upper()
    ws_set_status(f'3D room will be furnished as: {REAL_ROOM["kind"]}')


def open_real_world_workspace():
    ws_close_camera()
    REAL_STUDIO['active'] = True
    world.enabled = False
    photo_root.enabled = False
    real_room_root.enabled = False
    left_ui.enabled = False
    right_ui.enabled = False
    bottom_ui.enabled = False
    photo_ui.enabled = False
    left_tab.enabled = False
    right_tab.enabled = False
    bottom_tab.enabled = False
    status_text.enabled = False
    help_panel.enabled = False
    workspace_ui.enabled = True
    ws_background.scale = (2 * window.aspect_ratio + 0.2, 2.2)
    ws_render_image()
    ws_set_status('Interior studio ready. Browse a room photo to get started.')


def close_real_world_workspace():
    ws_close_camera()
    REAL_STUDIO['active'] = False
    workspace_ui.enabled = False
    world.enabled = True
    photo_root.enabled = False
    real_room_root.enabled = False
    state['photo'] = False
    REAL_ROOM['active'] = False
    sync_panels()
    refresh_ui()
    set_status('Returned to the ArchiVision villa studio.')


def workspace_tick():
    # Live camera preview removed - nothing to drive here per-frame any more.
    return



def workspace_input(key):
    if key == 'escape':
        close_real_world_workspace()
        return
    if key in ('enter', 'return'):
        ws_apply_polygon()
    elif key in ('u', 'backspace'):
        ws_undo_region()
    elif key == 'c':
        ws_clear_points()
    elif key in ('1', '2', '3', '4', '5', '6'):
        ws_select_color(int(key) - 1)
    elif key == 'w':
        ws_set_target('WALL')
    elif key == 'f':
        ws_set_target('FLOOR')
    elif key == 's':
        ws_save_design()
    elif key == 'left mouse down' and REAL_STUDIO.get('image') is not None:
        x0, y0, dw, dh = REAL_STUDIO['image_rect']
        mx, my = mouse.x, mouse.y
        if x0 <= mx <= x0 + dw and y0 <= my <= y0 + dh:
            img = REAL_STUDIO['image']
            px = int((mx - x0) / dw * img.width)
            py = int((1 - (my - y0) / dh) * img.height)
            REAL_STUDIO['points'].append((max(0, min(img.width - 1, px)),
                                          max(0, min(img.height - 1, py))))
            ws_render_image()


# Make the older LOAD / CHANGE PHOTO action open the new dedicated page too.
def open_photo_menu():
    open_real_world_workspace()


# Replace the original application event handlers while the dedicated page is open.
_archivision_original_input = input
_archivision_original_update = update

def input(key):
    if MENU_STATE['active']:
        if key == 'escape':
            _menu_hide()
        return
    if REAL_STUDIO['active']:
        workspace_input(key)
        return
    _archivision_original_input(key)


def update():
    if MENU_STATE['active']:
        return
    if REAL_STUDIO['active']:
        workspace_tick()
        return
    _archivision_original_update()


# =====================================================================
# 15. RUN
# =====================================================================
print('ArchiVision 3D started. Photo editor: trace wall/floor polygons.')
app.run()
