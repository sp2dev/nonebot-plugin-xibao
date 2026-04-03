from nonebot import on_command, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_saa")

import io
from pathlib import Path

import nonebot_plugin_saa as saa
from nonebot.adapters import Message
from nonebot.params import CommandArg
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

__plugin_meta__ = PluginMetadata(
    name="喜（悲）报生成器",
    description="生成喜报（或是悲报，管他呢）",
    usage="/喜报 [文字] 生成喜报\n/悲报 [文字] 生成悲报",
    type="application",
    homepage="https://github.com/sp2dev/nonebot-plugin-xibao",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_saa"),
)

font_path = Path(__file__).parent / "SourceHanSansSC-Regular.otf"


# 安全边距：限制文本绘制区域，避免贴边或压到背景关键元素。
SAFE_MARGIN_TOP = 0.18
SAFE_MARGIN_BOTTOM = 0.08
SAFE_MARGIN_LEFT = 0.10
SAFE_MARGIN_RIGHT = 0.07

# 手动上下偏移（像素）：
# 正数整体下移，负数整体上移。你可以直接改这个值来微调文字位置。
TEXT_VERTICAL_OFFSET_PX = -50

# 字号与排版参数。
MIN_FONT_SIZE = 30
MAX_FONT_SIZE = 180
LINE_HEIGHT_FACTOR = 1.3
STROKE_WIDTH = 10


def _get_safe_rect(image_width: int, image_height: int) -> tuple[int, int, int, int]:
    """根据图片尺寸计算文本可用安全区域。"""
    left = int(image_width * SAFE_MARGIN_LEFT)
    right = int(image_width * (1 - SAFE_MARGIN_RIGHT))
    top = int(image_height * SAFE_MARGIN_TOP)
    bottom = int(image_height * (1 - SAFE_MARGIN_BOTTOM))
    return left, top, right, bottom


def _measure_text(
    text: str,
    draw: ImageDraw.ImageDraw,
    pilmoji: Pilmoji,
    font: ImageFont.FreeTypeFont,
    stroke_width: int,
) -> tuple[int, int]:
    """测量单行文本宽高，优先使用 Pilmoji 以兼容 emoji。"""
    if not text:
        return 0, int(font.size * LINE_HEIGHT_FACTOR)

    try:
        if hasattr(pilmoji, "getsize"):
            width, height = pilmoji.getsize(text, font=font)
            return int(width) + stroke_width * 2, int(height) + stroke_width * 2
    except (AttributeError, TypeError, ValueError):
        pass

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def _wrap_text_by_width(
    text: str,
    draw: ImageDraw.ImageDraw,
    pilmoji: Pilmoji,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """按最大宽度逐字换行，保留原始段落换行。"""
    if not text:
        return []

    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph:
            lines.append("")
            continue

        current = ""
        for char in paragraph:
            candidate = current + char
            candidate_width, _ = _measure_text(
                candidate, draw, pilmoji, font, STROKE_WIDTH
            )
            if candidate_width <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char

        if current:
            lines.append(current)

    return lines


def _calculate_font_size(
    text: str,
    image_width: int,
    image_height: int,
    max_font_size: int = MAX_FONT_SIZE,
    min_font_size: int = MIN_FONT_SIZE,
) -> tuple[int, list[str]]:
    """在安全区域内通过二分搜索寻找可容纳文本的最大字号。"""
    if not text:
        return max_font_size, []

    left, top, right, bottom = _get_safe_rect(image_width, image_height)
    available_width = max(1, right - left)
    available_height = max(1, bottom - top)

    measure_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(measure_img)
    with Pilmoji(measure_img) as pilmoji:
        low, high = min_font_size, max_font_size
        best_size = min_font_size
        best_lines: list[str] = []

        while low <= high:
            mid = (low + high) // 2
            font = ImageFont.truetype(font_path, mid)
            lines = _wrap_text_by_width(
                text, draw, pilmoji, font, available_width
            )
            line_height = max(1, int(mid * LINE_HEIGHT_FACTOR))
            total_height = line_height * max(1, len(lines))

            if total_height <= available_height:
                best_size = mid
                best_lines = lines
                low = mid + 1
            else:
                high = mid - 1

        if not best_lines:
            fallback_font = ImageFont.truetype(font_path, min_font_size)
            best_lines = _wrap_text_by_width(
                text, draw, pilmoji, fallback_font, available_width
            )

    return best_size, best_lines


async def _generate_image(
    bg_file: str,
    text: str = "",
    font_size: int | None = None,
    text_color: str = "black",
    stroke: str = "",
) -> bytes:
    """通用图片生成流程：加载底图、排版文本、绘制并导出 JPEG。"""
    img_path = Path(__file__).parent / bg_file
    img = Image.open(img_path)
    image_width, image_height = img.size

    if not text.strip():
        output = io.BytesIO()
        img.save(output, format="JPEG")
        return output.getvalue()

    left, top, right, bottom = _get_safe_rect(image_width, image_height)
    available_width = max(1, right - left)
    available_height = max(1, bottom - top)

    auto_max_font = font_size if font_size is not None else MAX_FONT_SIZE
    resolved_font_size, lines = _calculate_font_size(
        text,
        image_width,
        image_height,
        max_font_size=max(MIN_FONT_SIZE, auto_max_font),
        min_font_size=MIN_FONT_SIZE,
    )

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, resolved_font_size)
    line_height = max(1, int(resolved_font_size * LINE_HEIGHT_FACTOR))
    total_height = line_height * max(1, len(lines))
    # 文字先在安全区域内垂直居中，再叠加手动上下偏移。
    start_y = top + (available_height - total_height) / 2 + TEXT_VERTICAL_OFFSET_PX

    with Pilmoji(img) as pilmoji:
        for i, line in enumerate(lines):
            line_width, _ = _measure_text(line, draw, pilmoji, font, STROKE_WIDTH)
            x = left + (available_width - line_width) / 2
            y = start_y + i * line_height
            pilmoji.text(
                (int(x), int(y)),
                line,
                fill=text_color,
                font=font,
                stroke_fill=stroke,
                stroke_width=STROKE_WIDTH,
            )

    output = io.BytesIO()
    img.save(output, format="JPEG")
    return output.getvalue()


async def gen_xibao(text: str = "", font_size: int | None = None) -> bytes:
    """生成喜报图片（红字黄描边）。"""
    return await _generate_image(
        "xibao_bg.jpg", text, font_size, "red", stroke="yellow"
    )


async def gen_beibao(text: str = "", font_size: int | None = None) -> bytes:
    """生成悲报图片（黑字白描边）。"""
    return await _generate_image(
        "beibao_bg.jpg", text, font_size, "black", stroke="white"
    )


genxibao = on_command(
    "喜报",
    aliases={
        "喜报：",
        "喜报:",
    },
)


@genxibao.handle()
async def xibaohandle(args: Message = CommandArg()) -> None:
    """处理“喜报”命令：读取参数并发送生成图片。"""
    textinput = args.extract_plain_text()
    picdata = await gen_xibao(text=textinput)
    await saa.Image(picdata).send()


genbeibao = on_command(
    "悲报",
    aliases={
        "悲报：",
        "悲报:",
    },
)


@genbeibao.handle()
async def beibaohandle(args: Message = CommandArg()) -> None:
    """处理“悲报”命令：读取参数并发送生成图片。"""
    textinput = args.extract_plain_text()
    picdata = await gen_beibao(text=textinput)
    await saa.Image(picdata).send()
