from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from django.conf import settings

def user_listing_path(instance, filename):
    product = instance.product
    # Check if product has an ID (it may not during first save)
    if not product.id:
        # This is a temporary path that will be corrected later
        return f'product_images/temp/{filename}'
    return f'product_images/{product.seller.user.username}/{product.id}/{filename}'


def category_image_path(instance, filename):
    return f'categories/{instance.name}/{filename}'


# Tuneable constants — adjust these to match your brand
_WM_LOGO_MAX_WIDTH  = 28       # logo icon size inside the pill
_WM_PADDING         = 16       # outer margin from image edge
_WM_PILL_PADDING_X  = 14       # horizontal inner padding inside pill
_WM_PILL_PADDING_Y  = 8        # vertical inner padding inside pill
_WM_PILL_GAP        = 8        # gap between elements inside pill
_WM_PILL_COLOR      = (0, 0, 0, 140)        # frosted dark pill background
_WM_DIVIDER_COLOR   = (255, 255, 255, 60)   # subtle vertical divider between brand and username
_WM_BRAND_COLOR     = (255, 255, 255, 255)  # solid white — brand name
_WM_TEXT_COLOR      = (200, 200, 200, 255)  # slightly dimmed white — username
_WM_BRAND_NAME      = 'opensell.ng'         # brand label shown beside the logo
_WM_CORNER          = 'bottom-center'       # 'bottom-right' | 'bottom-left' | 'bottom-center'

_WM_LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'images', 'logoshort.png')
_WM_FONT_PATH = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Poppins-Regular.ttf')


def _wm_load_logo(target_width):
    logo = Image.open(_WM_LOGO_PATH).convert('RGBA')
    ratio = target_width / logo.width
    new_size = (target_width, max(1, int(logo.height * ratio)))
    return logo.resize(new_size, Image.LANCZOS)


def _wm_load_font(size):
    try:
        return ImageFont.truetype(_WM_FONT_PATH, size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _draw_rounded_rect(draw, xy, radius, fill):
    """Draw a filled rounded rectangle onto `draw`."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def apply_watermark(image_file, profile):
    """
    Composite an advanced pill-badge watermark onto image_file.

    Layout (single pill, bottom-center):
      [ logo  |  opensell.ng  ·  <display name> ]

    The display name shown on the watermark resolves as follows:
      - Verified business  →  profile.business_name  (e.g. "Acme Ltd")
      - Everyone else      →  profile.user.username

    `profile` must be a User.models.Profile instance; the property
    `business_display_name` already encapsulates this logic.

    - No shadows anywhere
    - Frosted semi-transparent pill background for legibility on any image
    - Subtle vertical divider separates brand from display name
    - Rounded pill shape for a modern, premium feel

    Returns a BytesIO of the watermarked JPEG, ready to pass to ContentFile.
    Called from Product_Image.save() and Product_Receipt.save() in models.py.
    """
    # Verified businesses show their business name; everyone else shows username.
    display_name = profile.business_display_name

    img = Image.open(image_file).convert('RGBA')
    img_w, img_h = img.size

    # --- logo -----------------------------------------------------------
    logo = _wm_load_logo(_WM_LOGO_MAX_WIDTH)
    logo_w, logo_h = logo.size

    # --- fonts (scale with image so it looks right on any resolution) ---
    base_size   = max(13, img_w // 55)
    brand_font  = _wm_load_font(base_size + 1)   # opensell.ng — slightly bolder
    uname_font  = _wm_load_font(base_size)        # username — one step smaller

    # --- measure text ---------------------------------------------------
    dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))

    bb = dummy.textbbox((0, 0), _WM_BRAND_NAME, font=brand_font)
    brand_w, brand_h = bb[2] - bb[0], bb[3] - bb[1]

    bb = dummy.textbbox((0, 0), display_name, font=uname_font)
    uname_w, uname_h = bb[2] - bb[0], bb[3] - bb[1]

    # --- pill geometry --------------------------------------------------
    divider_w   = 1
    inner_h     = max(logo_h, brand_h, uname_h)
    pill_inner_w = (
        logo_w
        + _WM_PILL_GAP
        + brand_w
        + _WM_PILL_GAP * 2
        + divider_w
        + _WM_PILL_GAP * 2
        + uname_w
    )
    pill_w = pill_inner_w + _WM_PILL_PADDING_X * 2
    pill_h = inner_h + _WM_PILL_PADDING_Y * 2
    radius = pill_h // 2   # full capsule shape

    # --- position pill --------------------------------------------------
    if _WM_CORNER == 'bottom-right':
        pill_x = img_w - pill_w - _WM_PADDING
    elif _WM_CORNER == 'bottom-left':
        pill_x = _WM_PADDING
    else:  # bottom-center
        pill_x = (img_w - pill_w) // 2
    pill_y = (img_h - pill_h) // 2

    # --- draw overlay ---------------------------------------------------
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # Pill background
    _draw_rounded_rect(
        draw,
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius,
        _WM_PILL_COLOR,
    )

    # Starting x cursor (left inner edge of pill)
    cx = pill_x + _WM_PILL_PADDING_X

    # Logo — vertically centred inside pill
    logo_y = pill_y + (pill_h - logo_h) // 2
    overlay.paste(logo, (cx, logo_y), logo)
    cx += logo_w + _WM_PILL_GAP

    # Brand name — vertically centred
    brand_y = pill_y + (pill_h - brand_h) // 2
    draw.text((cx, brand_y), _WM_BRAND_NAME, font=brand_font, fill=_WM_BRAND_COLOR)
    cx += brand_w + _WM_PILL_GAP * 2

    # Vertical divider
    div_top    = pill_y + pill_h * 20 // 100
    div_bottom = pill_y + pill_h * 80 // 100
    draw.line([(cx, div_top), (cx, div_bottom)], fill=_WM_DIVIDER_COLOR, width=divider_w)
    cx += divider_w + _WM_PILL_GAP * 2

    # Display name — vertically centred, no @ prefix
    uname_y = pill_y + (pill_h - uname_h) // 2
    draw.text((cx, uname_y), display_name, font=uname_font, fill=_WM_TEXT_COLOR)

    # --- composite & export --------------------------------------------
    watermarked = Image.alpha_composite(img, overlay)

    output = BytesIO()
    watermarked.convert('RGB').save(output, format='JPEG', quality=92, optimize=True)
    output.seek(0)
    return output