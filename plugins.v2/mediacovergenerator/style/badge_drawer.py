# plugins.v2/mediacovergenerator/style/badge_drawer.py
# 角标绘制模块：圆角灰 / 平缎带 / 勋章红 / 勋章金

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import logging
import os
import sys
from pathlib import Path

_badge_logger = logging.getLogger(__name__)

_badge_img_cache = None
_badge_img_resolved_path = None  # 诊断用：记录实际找到的路径


def _find_badge_image():
    """多路径回退查找徽章图片，返回 (Image, path) 或 (None, error_msg)"""
    global _badge_img_cache, _badge_img_resolved_path

    if _badge_img_cache is not None:
        return _badge_img_cache, _badge_img_resolved_path

    candidates = []

    # 策略1: __file__ 所在目录
    try:
        d = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(d, "badge_image_original.png"))
    except Exception:
        pass

    # 策略2: 相对于当前工作目录
    candidates.append(os.path.join(os.getcwd(), "plugins.v2", "mediacovergenerator", "style", "badge_image_original.png"))
    candidates.append(os.path.join(os.getcwd(), "style", "badge_image_original.png"))
    candidates.append(os.path.join(os.getcwd(), "badge_image_original.png"))

    # 策略3: 从 sys.path 中的插件路径搜索
    for sp in sys.path:
        if "mediacovergenerator" in sp or "plugins" in sp:
            for sub in ["", "style"]:
                p = os.path.join(sp, sub, "badge_image_original.png")
                if os.path.exists(p) and p not in candidates:
                    candidates.append(p)

    # 策略4: 环境变量 PLUGIN_DIR
    plugin_dir = os.environ.get("PLUGIN_DIR", "") or os.environ.get("MOVIEPILOT_PLUGIN_DIR", "")
    if plugin_dir:
        for sub in ["", "style"]:
            candidates.append(os.path.join(plugin_dir, "mediacovergenerator", sub, "badge_image_original.png"))

    # 策略5: 常见 MoviePilot 插件目录
    common_dirs = [
        "/app/plugins/mediacovergenerator",
        "/config/plugins/mediacovergenerator",
        os.path.expanduser("~/plugins/mediacovergenerator"),
    ]
    for cd in common_dirs:
        for sub in ["", "style"]:
            p = os.path.join(cd, sub, "badge_image_original.png")
            if os.path.exists(p) and p not in candidates:
                candidates.append(p)

    _badge_logger.info(f"🔍 徽章图片搜索 - __file__={__file__}, cwd={os.getcwd()}, 候选路径数={len(candidates)}")

    for i, path in enumerate(candidates):
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        _badge_logger.info(f"  候选[{i}]: {path} exists={exists} size={size}")
        if exists and size > 1000:
            try:
                _badge_img_cache = Image.open(path).convert("RGBA")
                _badge_img_resolved_path = path
                _badge_logger.info(f"✅ 徽章图片加载成功: {path} ({_badge_img_cache.size})")
                return _badge_img_cache, path
            except Exception as e:
                _badge_logger.warning(f"  ⚠️ 打开失败: {e}")

    _badge_logger.error(f"❌ 徽章图片未找到！搜索了 {len(candidates)} 个路径均无效")
    return None, "ALL_PATHS_FAILED"


def _load_badge_image(target_height):
    """加载并缩放原版徽章图片（带缓存和多路径回退）"""
    badge_img, path = _find_badge_image()
    if badge_img is None:
        return None
    orig_w, orig_h = badge_img.size
    new_w = int(target_height * orig_w / orig_h)
    return badge_img.resize((new_w, target_height), Image.Resampling.LANCZOS)


def _get_badge_radius(badge_img):
    """从 alpha 通道检测徽章外圆半径"""
    alpha = badge_img.split()[3]
    w, h = badge_img.size
    cx, cy = w / 2, h / 2
    max_r = 0
    pixels = alpha.load()
    for y in range(h):
        for x in range(w):
            if pixels[x, y] > 128:
                dx, dy = x - cx, y - cy
                r = math.sqrt(dx * dx + dy * dy)
                if r > max_r:
                    max_r = r
    return int(max_r * 0.88)


def _fit_text_size(count_text, font_path, badge_radius, max_base_ratio=0.45):
    """自适应字号，确保文字对角线不超出徽章内圆"""
    bh = int(badge_radius / 0.88 * 2)
    font_size = int(bh * max_base_ratio)
    try:
        f = ImageFont.truetype(font_path, size=font_size)
    except Exception:
        f = ImageFont.load_default()
    td = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bb = td.textbbox((0, 0), count_text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    diag = math.sqrt(tw * tw + th * th)
    if diag > badge_radius * 2:
        scale = (badge_radius * 2) / diag * 0.95
        font_size = max(14, int(font_size * scale))
    return font_size


def _build_metallic_text_layer(count_text, font, text_colors):
    """多层描边 + 渐变金属文字图层"""
    tmp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bb = tmp_draw.textbbox((0, 0), count_text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cs = int(max(tw, th) * 3.5)
    cx, cy = cs / 2, cs / 2

    fill = text_colors.get('fill')
    highlight = text_colors.get('highlight')
    dark = text_colors.get('dark')
    inner_stroke = text_colors.get('inner_stroke', (85, 85, 85, 255))
    outer_stroke = text_colors.get('outer_stroke', (184, 134, 11, 250))
    shadow_color = text_colors.get('shadow', (0, 0, 0, 90))

    mask = Image.new('L', (cs, cs), 0)
    md = ImageDraw.Draw(mask)
    md.text((cx, cy), count_text, font=font, fill=255, anchor="mm")

    result = Image.new('RGBA', (cs, cs), (0, 0, 0, 0))

    # Layer 1: 投影 (offset 2,2)
    sh_cvs = Image.new('RGBA', (cs, cs), (0, 0, 0, 0))
    sh_d = ImageDraw.Draw(sh_cvs)
    sh_d.text((cx + 2, cy + 2), count_text, font=font, fill=shadow_color, anchor="mm")
    result.paste(sh_cvs, (0, 0), sh_cvs)

    # Layer 2: 外描边 (暗金 2px，8方向)
    outer_cvs = Image.new('RGBA', (cs, cs), (0, 0, 0, 0))
    od = ImageDraw.Draw(outer_cvs)
    for dx, dy in [(dx, dy) for dx in [-2, 0, 2] for dy in [-2, 0, 2] if not (dx == 0 and dy == 0)]:
        od.text((cx + dx, cy + dy), count_text, font=font, fill=outer_stroke, anchor="mm")
    result.paste(outer_cvs, (0, 0), outer_cvs)

    # Layer 3: 内描边 (深灰 1px，8方向)
    inner_cvs = Image.new('RGBA', (cs, cs), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(inner_cvs)
    for dx, dy in [(dx, dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1] if not (dx == 0 and dy == 0)]:
        idraw.text((cx + dx, cy + dy), count_text, font=font, fill=inner_stroke, anchor="mm")
    result.paste(inner_cvs, (0, 0), inner_cvs)

    # Layer 4: 渐变主体
    body = Image.new('RGBA', (cs, cs), (0, 0, 0, 0))
    lx = int(cx - tw / 2)
    ly = int(cy - th / 2)
    if highlight and dark:
        for sy in range(ly, ly + th):
            t = (sy - ly) / th
            if t < 0.30:
                ratio = t / 0.30
                r = int(highlight[0] + (fill[0] - highlight[0]) * ratio)
                g = int(highlight[1] + (fill[1] - highlight[1]) * ratio)
                b = int(highlight[2] + (fill[2] - highlight[2]) * ratio)
            elif t < 0.65:
                r, g, b = fill[0], fill[1], fill[2]
            else:
                ratio = (t - 0.65) / 0.35
                r = int(fill[0] + (dark[0] - fill[0]) * ratio)
                g = int(fill[1] + (dark[1] - fill[1]) * ratio)
                b = int(fill[2] + (dark[2] - fill[2]) * ratio)
            a = fill[3] if len(fill) > 3 else 250
            for x in range(lx, lx + tw):
                if mask.getpixel((x, sy)) > 128:
                    body.putpixel((x, sy), (r, g, b, a))
    else:
        bd = ImageDraw.Draw(body)
        bd.text((cx, cy), count_text, font=font, fill=fill, anchor="mm")
    result.paste(body, (0, 0), body)
    return result


def _draw_style_badge(image, item_count, font_path, size_ratio, base_color):
    """圆角灰 - 原版灰底圆角矩形 + 白字"""
    canvas_width, canvas_height = image.size
    count_text = str(item_count)

    badge_font_size = int(canvas_height * size_ratio)
    margin = int(canvas_height * 0.04)
    try:
        badge_font = ImageFont.truetype(font_path, size=badge_font_size)
    except Exception:
        badge_font = ImageFont.load_default()

    temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = temp_draw.textbbox((0, 0), count_text, font=badge_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    badge_padding_h = int(badge_font_size * 0.4)
    badge_padding_v = int(badge_font_size * 0.2)
    badge_width = int(text_width + badge_padding_h * 2)
    badge_height = int(text_height + badge_padding_v * 2)
    badge_pos = (margin, margin)
    badge_rect = (badge_pos[0], badge_pos[1], badge_pos[0] + badge_width, badge_pos[1] + badge_height)

    if base_color:
        badge_fill = (int(base_color[0] * 0.3), int(base_color[1] * 0.3), int(base_color[2] * 0.3), 190)
    else:
        badge_fill = (40, 40, 40, 180)

    badge_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge_layer)
    badge_draw.rounded_rectangle(badge_rect, radius=int(badge_height * 0.3), fill=badge_fill)
    image = Image.alpha_composite(image, badge_layer)

    draw = ImageDraw.Draw(image)
    cx_b = badge_pos[0] + badge_width / 2
    cy_b = badge_pos[1] + badge_height / 2
    draw.text((cx_b + 2, cy_b + 2), count_text, font=badge_font, fill=(0, 0, 0, 100), anchor="mm")
    draw.text((cx_b, cy_b), count_text, font=badge_font, fill=(255, 255, 255, 240), anchor="mm")
    return image


def _draw_style_ribbon(image, item_count, font_path, size_ratio, base_color):
    """平缎带 - 金色三角缎带 + 棕字旋转"""
    canvas_width, canvas_height = image.size
    count_text = str(item_count)

    badge_font_size = int(canvas_height * size_ratio)
    try:
        badge_font = ImageFont.truetype(font_path, size=badge_font_size)
    except Exception:
        badge_font = ImageFont.load_default()

    ribbon_width = int(badge_font_size * 3.0)
    fold_size = int(ribbon_width * 0.5)

    ribbon_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    ribbon_draw = ImageDraw.Draw(ribbon_layer)
    ribbon_draw.polygon([(0, 0), (ribbon_width, 0), (0, ribbon_width)], fill=(250, 222, 135, 250))
    ribbon_draw.polygon([(0, 0), (fold_size, 0), (0, fold_size)], fill=(0, 0, 0, 0))
    image = Image.alpha_composite(image, ribbon_layer)

    temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = temp_draw.textbbox((0, 0), count_text, font=badge_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    text_canvas_size = int(math.sqrt(text_width ** 2 + text_height ** 2) * 1.5)
    text_canvas = Image.new('RGBA', (text_canvas_size, text_canvas_size), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_canvas)
    cx_c, cy_c = text_canvas_size / 2, text_canvas_size / 2
    text_draw.text((cx_c + 2, cy_c + 2), count_text, font=badge_font, fill=(0, 0, 0, 80), anchor="mm")
    text_draw.text((cx_c, cy_c), count_text, font=badge_font, fill=(89, 52, 2, 245), anchor="mm")

    rotated_text = text_canvas.rotate(45, resample=Image.BICUBIC, expand=True)
    position_factor = 0.38
    paste_x = int(ribbon_width * position_factor) - rotated_text.width // 2
    paste_y = int(ribbon_width * position_factor) - rotated_text.height // 2

    text_final_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    text_final_layer.paste(rotated_text, (paste_x, paste_y))
    image = Image.alpha_composite(image, text_final_layer)
    return image


def _draw_style_medal(image, item_count, font_path, size_ratio, text_colors):
    """勋章红 / 勋章金：RWB 缎带 + 原版徽章 + 旋转金属渐变字"""
    w, h = image.size
    raw_count = item_count
    count_text = f"{raw_count:02d}" if raw_count < 10 else str(raw_count)

    # 加载徽章
    badge_h = int(h * size_ratio * 2.2)
    badge_img = _load_badge_image(badge_h)
    if badge_img is None:
        return image
    bw, bh = badge_img.size
    margin = int(h * 0.018)
    badge_x, badge_y = margin, margin
    badge_cx, badge_cy = badge_x + bw // 2, badge_y + bh // 2
    badge_radius = _get_badge_radius(badge_img)

    # ===== RWB 缎带 =====
    band_w = int(bh * 0.26)
    tail_len = int(w * 0.55)
    fold_len = int(w * 0.65)
    total_w = fold_len + tail_len + int(band_w * 1.5)
    total_h = band_w * 3 + 6
    pivot_x = fold_len
    pivot_y = total_h // 2

    ribbon_canvas = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon_canvas)

    for band_dy, name, rgb in [
        (-band_w, "红", (195, 28, 28)),
        (0, "白", (248, 248, 248)),
        (band_w, "蓝", (28, 55, 185)),
    ]:
        top, btm = pivot_y + band_dy, pivot_y + band_dy + band_w
        rd.rectangle([(0, top), (total_w, btm)], fill=rgb + (235,))
        for sy in range(int(top), int(btm), 2):
            t = (sy - top) / band_w
            shade = 0.78 + t * 0.44
            rd.line([(0, sy), (total_w, sy)],
                    fill=(min(255, int(rgb[0] * shade)),
                          min(255, int(rgb[1] * shade)),
                          min(255, int(rgb[2] * shade)), 120), width=1)
        rd.line([(0, top), (total_w, top)], fill=(255, 255, 255, 90), width=2)
        rd.line([(0, btm - 1), (total_w, btm - 1)], fill=(0, 0, 0, 50), width=1)
        # 尾部三角
        td = int(band_w * 1.1)
        tmid = top + band_w // 2
        rd.polygon([(total_w, top), (total_w + td, tmid), (total_w, btm)],
                   fill=(int(rgb[0] * 0.65), int(rgb[1] * 0.65), int(rgb[2] * 0.65), 220))
        rd.line([(total_w, top), (total_w + td, tmid)], fill=(255, 255, 255, 55), width=1)
        # 折角
        ld = int(band_w * 0.9)
        rd.polygon([(0, top), (-ld, tmid), (0, btm)],
                   fill=(int(rgb[0] * 0.55), int(rgb[1] * 0.55), int(rgb[2] * 0.55), 200))
        rd.line([(pivot_x, top), (pivot_x, btm)], fill=(255, 255, 255, 25), width=2)

    for i in range(2):
        sy = pivot_y + (i - 0.5) * band_w
        rd.line([(0, sy), (total_w + int(band_w * 0.5), sy)], fill=(0, 0, 0, 45), width=1)

    # 旋转缎带
    sq = max(total_w + int(band_w * 1.5), total_h) * 2
    big = Image.new('RGBA', (sq, sq), (0, 0, 0, 0))
    big.paste(ribbon_canvas, (sq // 2 - pivot_x, sq // 2 - pivot_y))
    rotated = big.rotate(45, resample=Image.BICUBIC, expand=False)
    paste_rx = badge_cx - sq // 2
    paste_ry = badge_cy - sq // 2

    # 缎带投影
    alpha = rotated.split()[3]
    shadow_alpha = alpha.point(lambda x: x // 3)
    shadow_rgba = Image.merge('RGBA', (
        Image.new('L', (sq, sq), 0), Image.new('L', (sq, sq), 0),
        Image.new('L', (sq, sq), 0), shadow_alpha
    ))
    shadow_lyr = Image.new('RGBA', image.size, (0, 0, 0, 0))
    shadow_lyr.paste(shadow_rgba, (paste_rx + 7, paste_ry + 9))
    shadow_lyr = shadow_lyr.filter(ImageFilter.GaussianBlur(radius=6))
    image = Image.alpha_composite(image, shadow_lyr)

    # 缎带
    ribbon_lyr = Image.new('RGBA', image.size, (0, 0, 0, 0))
    ribbon_lyr.paste(rotated, (paste_rx, paste_ry))
    image = Image.alpha_composite(image, ribbon_lyr)

    # 徽章
    image.paste(badge_img, (badge_x, badge_y), badge_img)

    # 数字
    num_font_size = _fit_text_size(count_text, font_path, badge_radius)
    try:
        num_font = ImageFont.truetype(font_path, size=num_font_size)
    except Exception:
        num_font = ImageFont.load_default()

    text_canvas = _build_metallic_text_layer(count_text, num_font, text_colors)
    rotated_text = text_canvas.rotate(45, resample=Image.BICUBIC, expand=True)

    paste_tx = badge_cx - rotated_text.width // 2
    paste_ty = badge_cy - rotated_text.height // 2

    # Alpha mask 裁剪
    badge_alpha = badge_img.split()[3]
    text_mask = Image.new('L', image.size, 0)
    text_mask.paste(badge_alpha, (badge_x, badge_y))

    text_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    text_layer.paste(rotated_text, (paste_tx, paste_ty))
    text_layer.putalpha(Image.composite(
        text_layer.split()[3], Image.new('L', image.size, 0), text_mask
    ))
    image = Image.alpha_composite(image, text_layer)
    return image


# === 勋章红 / 勋章金 预设配色 ===
_MEDAL_RED_COLORS = {
    "fill": (139, 0, 42, 250),
    "highlight": (210, 80, 90, 250),
    "dark": (90, 0, 20, 250),
    "inner_stroke": (85, 85, 85, 255),
    "outer_stroke": (184, 134, 11, 250),
    "shadow": (0, 0, 0, 90),
}

_MEDAL_GOLD_COLORS = {
    "fill": (184, 115, 51, 250),
    "highlight": (230, 175, 100, 250),
    "dark": (120, 70, 25, 250),
    "inner_stroke": (85, 85, 85, 255),
    "outer_stroke": (184, 134, 11, 250),
    "shadow": (0, 0, 0, 90),
}


def draw_badge(image, item_count, font_path, style='badge', size_ratio=0.12, base_color=None):
    """
    在所有封面图片上绘制媒体数量角标的唯一函数。
    支持四种风格：
        'badge'     - 圆角灰 (原版灰底圆角矩形 + 白字)
        'ribbon'    - 平缎带 (金色三角缎带 + 棕字旋转)
        'medal_red' - 勋章红 (RWB缎带 + 徽章 + 勃艮第红金属渐变字)
        'medal_gold'- 勋章金 (RWB缎带 + 徽章 + 古铜金属渐变字)

    参数:
        image: PIL.Image 对象
        item_count: 要显示的媒体数量
        font_path: 字体文件路径
        style: 角标样式名称
        size_ratio: 角标大小相对于画布高度的比例（默认 0.12）
        base_color: 基础颜色 RGB 元组（badge/ribbon 使用）
    """
    if not item_count:
        return image

    canvas_width, canvas_height = image.size
    _badge_logger.info(f"draw_badge - item_count={item_count}, style={style}, "
                       f"image_size={canvas_width}x{canvas_height}, size_ratio={size_ratio}")
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # =================================================
    # 圆角灰
    # =================================================
    if style == 'badge':
        return _draw_style_badge(image, item_count, font_path, size_ratio, base_color)

    # =================================================
    # 平缎带
    # =================================================
    elif style == 'ribbon':
        return _draw_style_ribbon(image, item_count, font_path, size_ratio, base_color)

    # =================================================
    # 勋章红
    # =================================================
    elif style == 'medal_red':
        return _draw_style_medal(image, item_count, font_path, size_ratio, _MEDAL_RED_COLORS)

    # =================================================
    # 勋章金
    # =================================================
    elif style == 'medal_gold':
        return _draw_style_medal(image, item_count, font_path, size_ratio, _MEDAL_GOLD_COLORS)

    # 未知样式，返回原图
    else:
        _badge_logger.warning(f"未知角标样式: {style}，返回原图")
        return image


def preview_badge_styles(font_path, output_dir):
    """
    生成4种角标样式的预览图片，用于诊断和预览。
    
    参数:
        font_path: 字体文件路径
        output_dir: 输出目录路径
    
    返回:
        dict: {"success": bool, "files": [...], "errors": [...], "diagnostics": {...}}
    """
    import traceback
    result = {"success": True, "files": [], "errors": [], "diagnostics": {}}
    
    # 诊断信息
    result["diagnostics"]["__file__"] = __file__
    result["diagnostics"]["cwd"] = os.getcwd()
    result["diagnostics"]["python_version"] = sys.version
    
    # 测试徽章图片加载
    badge_img, badge_path = _find_badge_image()
    result["diagnostics"]["badge_image_found"] = badge_img is not None
    result["diagnostics"]["badge_image_path"] = badge_path
    
    # 测试字体
    result["diagnostics"]["font_path"] = font_path
    result["diagnostics"]["font_exists"] = os.path.exists(font_path) if font_path else False
    
    if not font_path or not os.path.exists(font_path):
        result["errors"].append(f"字体不存在: {font_path}")
        result["success"] = False
        return result
    
    os.makedirs(output_dir, exist_ok=True)
    
    w, h = 1200, 675
    bg = (30, 40, 60)
    styles = [
        ("badge", "圆角灰"),
        ("ribbon", "平缎带"),
        ("medal_red", "勋章红"),
        ("medal_gold", "勋章金"),
    ]
    test_nums = [5, 42, 123]
    
    for style_name, style_label in styles:
        for num in test_nums:
            try:
                img = Image.new('RGB', (w, h), bg)
                res = draw_badge(img, num, font_path, style=style_name, size_ratio=0.12, base_color=None)
                filename = f"preview_{style_name}_{num}.png"
                filepath = os.path.join(output_dir, filename)
                res.save(filepath)
                result["files"].append(filename)
                _badge_logger.info(f"预览生成: {filename}")
            except Exception as e:
                err_msg = f"{style_label} num={num}: {e}"
                result["errors"].append(err_msg)
                _badge_logger.error(f"预览失败: {err_msg}\n{traceback.format_exc()}")
                result["success"] = False
    
    return result
