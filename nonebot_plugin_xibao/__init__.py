from nonebot import on_command
from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_saa")

from nonebot.adapters import Message
from nonebot.params import CommandArg
import nonebot_plugin_saa as saa

import skia

from pathlib import Path

__plugin_meta__ = PluginMetadata(
    name="喜（悲）报生成器",
    description="生成喜报（或是悲报，管他呢）",
    usage="/喜报 [文字] 生成喜报\n/悲报 [文字] 生成悲报",
    type="application",
    homepage="https://github.com/sp2dev/nonebot-plugin-xibao",
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_saa"
    )
)

font_path = Path(__file__).parent / "SourceHanSansSC-Regular.otf"


def _make_font(typeface: skia.Typeface, size: int) -> skia.Font:
    """
    创建配置完善的 skia.Font。
    """
    font = skia.Font(typeface, size)
    font.setSubpixel(True)
    font.setEdging(skia.Font.Edging.kAntiAlias)
    font.setHinting(skia.FontHinting.kNormal)
    font.setEmbolden(False)
    return font


def _get_fontmgr() -> skia.FontMgr:
    """获取默认 FontMgr，兼容不同 skia-python 版本。"""
    if hasattr(skia.FontMgr, "RefDefault"):
        return skia.FontMgr.RefDefault()
    if hasattr(skia.FontMgr, "Default"):
        return skia.FontMgr.Default()
    if hasattr(skia.FontMgr, "MakeDefault"):
        return skia.FontMgr.MakeDefault()
    # 最后兜底尝试 RefDefault（若不存在将触发 AttributeError，便于快速暴露环境问题）
    return skia.FontMgr.RefDefault()


def _fontstyle_normal() -> skia.FontStyle:
    """获取 Normal 字重/宽度/倾斜的 FontStyle。"""
    try:
        return skia.FontStyle.Normal()
    except Exception:
        return skia.FontStyle()


def _get_default_typeface() -> skia.Typeface | None:
    """获取系统默认的 Typeface，尽量跨版本兼容。"""
    tf = getattr(skia.Typeface, "MakeDefault", lambda: None)()
    if tf:
        return tf
    fm = _get_fontmgr()
    style = _fontstyle_normal()
    # 通过匹配常见字符获得默认字体
    for ch in ("A", " ", "汉"):
        tf = getattr(fm, "matchFamilyStyleCharacter")("", style, ["und"], ord(ch))
        if tf:
            return tf
    # 备用：尝试 matchFamilyStyle（若绑定提供）
    try:
        tf = fm.matchFamilyStyle(None, style)  # type: ignore[attr-defined]
        if tf:
            return tf
    except Exception:
        pass
    return None


def _split_runs(line: str, base_typeface: skia.Typeface, size: int) -> list[tuple[str, skia.Font]]:
    """
    将一行文本按字体可渲染能力拆分为多个连续段，每段使用对应的字体。
    优先使用 `base_typeface`，对不可渲染的字符调用 FontMgr 进行字体回退。
    """
    base_font = _make_font(base_typeface, size)
    fm = _get_fontmgr()
    style = _fontstyle_normal()
    bcp47 = ["zh-Hans", "en", "und"]

    # 缓存：同一字符的回退字体在同字号下复用
    cache: dict[int, skia.Font] = {}

    runs: list[tuple[str, skia.Font]] = []
    current_font = base_font
    buf: list[str] = []

    # 获取基础字体族名（用于优先匹配同族的回退）
    try:
        base_family = base_typeface.familyName()
    except Exception:
        base_family = ""

    for ch in line:
        uni = ord(ch)
        # 先用当前字体检测是否可渲染
        if current_font.unicharToGlyph(uni) != 0:
            target_font = current_font
        else:
            # 查缓存或通过 FontMgr 查找可用字体
            target_font = cache.get(uni)
            if not target_font:
                tf = fm.matchFamilyStyleCharacter(base_family if base_family else "", style, bcp47, uni)
                if not tf:
                    tf = fm.matchFamilyStyleCharacter("", style, bcp47, uni)
                target_font = _make_font(tf if tf else base_typeface, size)
                cache[uni] = target_font

        if target_font is current_font:
            buf.append(ch)
        else:
            if buf:
                runs.append(("".join(buf), current_font))
                buf = []
            current_font = target_font
            buf.append(ch)

    if buf:
        runs.append(("".join(buf), current_font))

    return runs


def _measure_line_with_fallback(line: str, base_typeface: skia.Typeface, size: int) -> tuple[float, list[tuple[str, skia.Font]]]:
    """
    使用字体回退逻辑测量一行的宽度，并返回对应的分段运行。
    """
    runs = _split_runs(line, base_typeface, size)
    width = 0.0
    for seg, font in runs:
        width += font.measureText(seg)
    return width, runs

def _wrap_text(text: str, chars_per_line: int = 10) -> list[str]:
    """
    将文本按指定字符数换行
    """
    if len(text) <= chars_per_line:
        return [text]
    
    lines = []
    for i in range(0, len(text), chars_per_line):
        lines.append(text[i:i + chars_per_line])
    return lines


def _calculate_font_size(text: str, image_width: int, image_height: int, font_path: Path, 
                        max_font_size: int = 250, min_font_size: int = 50) -> int:
    """
    根据文本长度和图片尺寸动态计算字体大小
    确保文本能完整显示在图片中
    """
    if not text:
        return max_font_size
    
    # 换行处理
    lines = _wrap_text(text)
    num_lines = len(lines)
    longest_line = max(lines, key=len)
    
    # 创建字体，失败则使用默认字体兜底
    typeface = skia.Typeface.MakeFromFile(str(font_path)) or _get_default_typeface()
    if not typeface:
        # 实在获取不到，保持可继续运行但字号退回最小
        return min_font_size
    
    # 二分查找最适合的字体大小
    low, high = min_font_size, max_font_size
    best_size = min_font_size
    
    while low <= high:
        mid = (low + high) // 2
        # 使用回退测量最长行宽度
        text_width, _ = _measure_line_with_fallback(longest_line, typeface, mid)
        
        # 估算总高度（每行高度约为字体大小的1.3倍）
        line_height = mid * 1.3
        total_height = line_height * num_lines
        
        # 预留边距（宽度边距15%，高度边距15%）
        margin_width = image_width * 0.15
        margin_height = image_height * 0.15
        
        # 检查是否能放下
        if text_width + margin_width < image_width and total_height + margin_height < image_height:
            best_size = mid
            low = mid + 1
        else:
            high = mid - 1
    
    return best_size


async def _generate_image(bg_file: str, text = "", font_size: int | None = None, text_color = "black", stroke="") -> bytes:
    """
    生成图片，自动计算字体大小和居中位置，支持多行文本
    """
    img_path = Path(__file__).parent / bg_file
    
    # 读取背景图片（使用编码数据以提高兼容性）
    data = skia.Data.MakeFromFileName(str(img_path))
    if not data:
        raise FileNotFoundError(f"背景图片不存在: {img_path}")
    bg_image = skia.Image.MakeFromEncoded(data)
    if not bg_image:
        raise RuntimeError("无法解码背景图片")
    image_width = bg_image.width()
    image_height = bg_image.height()
    
    # 如果没有指定字体大小，自动计算
    if font_size is None:
        font_size = _calculate_font_size(text, image_width, image_height, font_path)
    
    # 换行处理
    lines = _wrap_text(text)
    
    # 创建画布
    surface = skia.Surface(image_width, image_height)
    canvas = surface.getCanvas()
    
    # 绘制背景图片
    canvas.drawImage(bg_image, 0, 0)
    
    # 基础字体（简体中文优先），加载失败则回退到默认字体
    typeface = skia.Typeface.MakeFromFile(str(font_path)) or _get_default_typeface()
    if not typeface:
        raise RuntimeError("无法加载任何可用字体，请检查字体文件与系统字体")
    font = _make_font(typeface, font_size)
    
    # 计算总的文本高度和宽度
    line_height = font_size * 1.3
    total_height = line_height * len(lines)
    
    # 计算每一行的宽度（含回退），并保留绘制所需的分段
    line_runs: list[list[tuple[str, skia.Font]]] = []
    line_widths: list[float] = []
    for line in lines:
        w, runs = _measure_line_with_fallback(line, typeface, font_size)
        line_widths.append(w)
        line_runs.append(runs)
    max_width = max(line_widths) if line_widths else 0
    
    # 计算起始位置（居中）
    start_y = (image_height - total_height) / 2 + 40
    
    # 颜色映射（使用通用构造，跨版本更稳健）
    color_map = {
        "red": skia.Color(255, 0, 0),
        "black": skia.Color(0, 0, 0),
        "yellow": skia.Color(255, 255, 0),
        "white": skia.Color(255, 255, 255),
    }
    fill_color = color_map.get(text_color, skia.Color(0, 0, 0))
    stroke_color = color_map.get(stroke, skia.Color(255, 255, 255))
    
    # 创建 Paint 对象（复用以提高性能）
    stroke_paint = skia.Paint(
        Color=stroke_color,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=10,
        AntiAlias=True,
        StrokeJoin=skia.Paint.kRound_Join,
        StrokeCap=skia.Paint.kRound_Cap
    )
    
    fill_paint = skia.Paint(
        Color=fill_color,
        Style=skia.Paint.kFill_Style,
        AntiAlias=True
    )
    
    # 绘制每一行文本（按分段运行逐段绘制）
    for i, (runs, line_width) in enumerate(zip(line_runs, line_widths)):
        x = (image_width - line_width) / 2
        y = start_y + i * line_height + font_size * 0.8
        for seg, seg_font in runs:
            if stroke:
                canvas.drawString(seg, x, y, seg_font, stroke_paint)
            canvas.drawString(seg, x, y, seg_font, fill_paint)
            x += seg_font.measureText(seg)
    
    # 导出为 PNG（高质量编码）
    image = surface.makeImageSnapshot()
    encode_options = skia.EncodedImageFormat.kPNG
    data = image.encodeToData(encode_options, 100)  # 质量参数 100（最高）
    return data.bytes()


async def gen_xibao(text: str = "", font_size: int | None = None) -> bytes:
    return await _generate_image("xibao_bg.png", text, font_size, "red", stroke="yellow")

async def gen_beibao(text: str = "", font_size: int | None = None) -> bytes:
    return await _generate_image("beibao_bg.png", text, font_size, "black", stroke="white")


genxibao = on_command("喜报", aliases={"xibao","喜报：", "喜报:", "喜报！", "喜报!"} )
@genxibao.handle()
async def xibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 30:
        await genxibao.finish("字数太多啦！长度应在 30 个字符以内。")
    picdata = await gen_xibao(text = textinput)
    await saa.Image(picdata).send()


genbeibao = on_command("悲报", aliases={"beibao","悲报：", "悲报:", "悲报！", "悲报!"} )
@genbeibao.handle()
async def beibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 30:
        await genbeibao.finish("字数太多啦！长度应在 30 个字符以内。")
    picdata = await gen_beibao(text = textinput)
    await saa.Image(picdata).send() 
