# plugins.v2/mediacovergenerator/style/badge_drawer.py
# 从 emby-toolkit 移植的角标绘制模块
# 用于在封面生成图片上叠加媒体数量角标

from PIL import Image, ImageDraw, ImageFont
import math


def _darken_color(color, factor=0.7):
    """颜色加深辅助函数"""
    if not color or len(color) < 3:
        return (0, 0, 0)
    r, g, b = color[:3]
    return (int(r * factor), int(g * factor), int(b * factor))


def draw_badge(image, item_count, font_path, style='badge', size_ratio=0.12, base_color=None):
    """
    在所有封面图片上绘制媒体数量角标的唯一函数。
    支持两种风格：'badge'（徽章）和 'ribbon'（缎带）。

    参数:
        image: PIL.Image 对象
        item_count: 要显示的媒体数量
        font_path: 字体文件路径（用于数字渲染）
        style: 'badge' 或 'ribbon'
        size_ratio: 角标大小相对于画布高度的比例（默认 0.12）
        base_color: 基础颜色 RGB 元组，用作角标背景色

    返回:
        添加了角标的 PIL.Image 对象
    """
    if not item_count:
        return image

    canvas_width, canvas_height = image.size
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    draw = ImageDraw.Draw(image)

    # --- 动态计算所有尺寸 ---
    badge_font_size = int(canvas_height * size_ratio)
    margin = int(canvas_height * 0.04)
    count_text = str(item_count)

    try:
        badge_font = ImageFont.truetype(font_path, size=badge_font_size)
    except Exception:
        try:
            badge_font = ImageFont.load_default()
        except Exception:
            # 如果默认字体也加载失败，返回原图
            return image

    # =================================================
    # --- 风格一：徽章 (Badge Style) ---
    # =================================================
    if style == 'badge':
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        text_bbox = temp_draw.textbbox((0, 0), count_text, font=badge_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        badge_padding_h = int(badge_font_size * 0.4)
        badge_padding_v = int(badge_font_size * 0.2)
        badge_width = int(text_width + badge_padding_h * 2)
        badge_height = int(text_height + badge_padding_v * 2)
        badge_pos = (margin, margin)
        badge_rect = (
            badge_pos[0],
            badge_pos[1],
            badge_pos[0] + badge_width,
            badge_pos[1] + badge_height
        )

        # 动态生成徽章背景颜色
        if base_color:
            badge_fill = _darken_color(base_color, 0.3) + (190,)
        else:
            badge_fill = (40, 40, 40, 180)

        badge_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_layer)
        badge_draw.rounded_rectangle(
            badge_rect,
            radius=int(badge_height * 0.3),
            fill=badge_fill
        )
        image = Image.alpha_composite(image, badge_layer)

        # 绘制文字
        draw = ImageDraw.Draw(image)
        badge_center_x = badge_pos[0] + badge_width / 2
        badge_center_y = badge_pos[1] + badge_height / 2
        shadow_offset = 2
        draw.text(
            (badge_center_x + shadow_offset, badge_center_y + shadow_offset),
            count_text,
            font=badge_font,
            fill=(0, 0, 0, 100),
            anchor="mm"
        )
        draw.text(
            (badge_center_x, badge_center_y),
            count_text,
            font=badge_font,
            fill=(255, 255, 255, 240),
            anchor="mm"
        )

    # =================================================
    # --- 风格二：缎带 (Ribbon Style) ---
    # =================================================
    elif style == 'ribbon':
        ribbon_width = int(badge_font_size * 3.0)
        fold_size = int(ribbon_width * 0.5)

        # 金色调缎带
        ribbon_fill = (250, 222, 135, 250)

        ribbon_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        ribbon_draw = ImageDraw.Draw(ribbon_layer)
        ribbon_draw.polygon(
            [(0, 0), (ribbon_width, 0), (0, ribbon_width)],
            fill=ribbon_fill
        )
        # 透明缺口
        ribbon_draw.polygon(
            [(0, 0), (fold_size, 0), (0, fold_size)],
            fill=(0, 0, 0, 0)
        )
        image = Image.alpha_composite(image, ribbon_layer)

        # 创建并旋转数字
        text_fill_color = (89, 52, 2, 245)
        text_shadow_color = (0, 0, 0, 80)
        rotation_angle = 45

        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        text_bbox = temp_draw.textbbox((0, 0), count_text, font=badge_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        text_canvas_size = int(math.sqrt(text_width ** 2 + text_height ** 2) * 1.5)
        text_canvas = Image.new('RGBA', (text_canvas_size, text_canvas_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_canvas)

        canvas_center_x, canvas_center_y = text_canvas_size / 2, text_canvas_size / 2
        shadow_offset = 2
        text_draw.text(
            (canvas_center_x + shadow_offset, canvas_center_y + shadow_offset),
            count_text,
            font=badge_font,
            fill=text_shadow_color,
            anchor="mm"
        )
        text_draw.text(
            (canvas_center_x, canvas_center_y),
            count_text,
            font=badge_font,
            fill=text_fill_color,
            anchor="mm"
        )

        rotated_text = text_canvas.rotate(rotation_angle, resample=Image.BICUBIC, expand=True)

        position_factor = 0.38
        paste_center_x = int(ribbon_width * position_factor)
        paste_center_y = int(ribbon_width * position_factor)

        paste_x = paste_center_x - rotated_text.width // 2
        paste_y = paste_center_y - rotated_text.height // 2

        text_final_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        text_final_layer.paste(rotated_text, (paste_x, paste_y))
        image = Image.alpha_composite(image, text_final_layer)

    return image