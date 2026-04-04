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

# 插件内置字体文件路径。
# 使用固定字体可以减少不同系统下渲染结果差异（尤其是中文字符宽度差异）。
font_path = Path(__file__).parent / "SourceHanSansSC-Regular.otf"


# 安全边距（按底图宽高比例计算）：
# 1. 限制文本绘制区域，避免贴边。
# 2. 避开模板背景中的主要视觉元素（例如边框、装饰图形、角色等）。
# 3. 不同分辨率下保持相对一致的视觉留白。
SAFE_MARGIN_TOP = 0.18
SAFE_MARGIN_BOTTOM = 0.08
SAFE_MARGIN_LEFT = 0.10
SAFE_MARGIN_RIGHT = 0.07

# 手动上下偏移（像素）：
# 在自动垂直居中的基础上再做一次整体偏移。
# 正数整体下移，负数整体上移，可用于快速微调视觉中心。
TEXT_VERTICAL_OFFSET_PX = -60

# 字号与排版参数。
# MIN/MAX_FONT_SIZE：自动计算时允许的字号区间。
# LINE_HEIGHT_FACTOR：行高 = 字号 * 因子，值越大行距越宽。
# STROKE_WIDTH：描边宽度，参与文本测量与实际绘制，确保“测量尺寸”和“渲染尺寸”一致。
MIN_FONT_SIZE = 30
MAX_FONT_SIZE = 180
LINE_HEIGHT_FACTOR = 1.3
STROKE_WIDTH = 10


def _get_safe_rect(image_width: int, image_height: int) -> tuple[int, int, int, int]:
    """根据图片尺寸计算文本可用安全区域。

    返回值是 (left, top, right, bottom)，用于后续统一的排版与居中计算。
    """
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
    """测量单行文本宽高，优先使用 Pilmoji 以兼容 emoji。

    说明：
    - Pilmoji 负责将 emoji 按图片方式渲染，普通 PIL 测量在某些情况下会低估尺寸。
    - 若 Pilmoji 不支持 getsize（或调用失败），回退到 ImageDraw.textbbox。
    - 返回结果会把描边厚度纳入尺寸，避免居中计算时出现“看起来偏移”。
    """
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
    """按最大宽度逐字换行，保留原始段落换行。
    """
    if not text:
        return []

    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph:
            lines.append("")
            continue
        # 逐段处理：用户手动输入的换行会被保留为段落边界。
        current = ""
        for char in paragraph:
            candidate = current + char
            candidate_width, _ = _measure_text(
                candidate, draw, pilmoji, font, STROKE_WIDTH
            )
            if candidate_width <= max_width or not current:
                current = candidate
            else:
                # 超出宽度后，将上一段落行落地，再从当前字符重新开始。
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
    """在安全区域内通过二分搜索寻找可容纳文本的最大字号。

    返回 (font_size, wrapped_lines)：
    - font_size：最终可用字号（尽可能大）。
    - wrapped_lines：在该字号下按宽度换行后的文本行。
    """
    if not text:
        return max_font_size, []

    left, top, right, bottom = _get_safe_rect(image_width, image_height)
    available_width = max(1, right - left)
    available_height = max(1, bottom - top)

    # 测量专用画布：只用于计算尺寸，不参与最终输出。
    measure_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(measure_img)
    with Pilmoji(measure_img) as pilmoji:
        low, high = min_font_size, max_font_size
        best_size = min_font_size
        best_lines: list[str] = []

        while low <= high:
            # 二分查找：尝试中间字号，能放下则继续放大，放不下则缩小。
            mid = (low + high) // 2
            font = ImageFont.truetype(font_path, mid)
            lines = _wrap_text_by_width(
                text, draw, pilmoji, font, available_width
            )
            line_height = max(1, int(mid * LINE_HEIGHT_FACTOR))
            total_height = line_height * max(1, len(lines))

            if total_height <= available_height:
                # 当前字号可用，记录为最优候选并尝试更大字号。
                best_size = mid
                best_lines = lines
                low = mid + 1
            else:
                # 当前字号过大，缩小搜索区间。
                high = mid - 1

        if not best_lines:
            # 理论上极端情况下可能没有可用解，降级到最小字号兜底。
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
    """通用图片生成流程：加载底图、排版文本、绘制并导出 JPEG。

    参数：
    - bg_file: 背景图文件名（位于插件目录）。
    - text: 要绘制的文本；为空时仅输出底图。
    - font_size: 可选的字号上限，不传时使用全局最大字号。
    - text_color/stroke: 文本颜色和描边颜色。
    """
    img_path = Path(__file__).parent / bg_file
    img = Image.open(img_path)
    image_width, image_height = img.size

    if not text.strip():
        # 无文本时直接返回底图，避免不必要的测量与绘制开销。
        output = io.BytesIO()
        img.save(output, format="JPEG")
        return output.getvalue()

    left, top, right, bottom = _get_safe_rect(image_width, image_height)
    available_width = max(1, right - left)
    available_height = max(1, bottom - top)

    # font_size 被视为“上限”而非固定值，最终仍会自动收缩以适应可用区域。
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
    # 这样默认居中效果稳定，且保留可配置“视觉微调旋钮”。
    start_y = top + (available_height - total_height) / 2 + TEXT_VERTICAL_OFFSET_PX

    with Pilmoji(img) as pilmoji:
        for i, line in enumerate(lines):
            line_width, _ = _measure_text(line, draw, pilmoji, font, STROKE_WIDTH)
            # 每行单独水平居中，确保长短行混排时版心一致。
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
    return await _generate_image(
        "xibao_bg.jpg", text, font_size, "red", stroke="yellow"
    )


async def gen_beibao(text: str = "", font_size: int | None = None) -> bytes:
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
    textinput = args.extract_plain_text()
    picdata = await gen_beibao(text=textinput)
    await saa.Image(picdata).send()
