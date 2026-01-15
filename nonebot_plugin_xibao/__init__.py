from nonebot import on_command
from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_saa")

from nonebot.adapters import Message
from nonebot.params import CommandArg
import nonebot_plugin_saa as saa

from PIL import Image, ImageDraw, ImageFont

from pathlib import Path
import io

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

font_path = Path(__file__).parent / "SourceHanSans.otf"


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
    
    # 二分查找最适合的字体大小
    low, high = min_font_size, max_font_size
    best_size = min_font_size
    
    while low <= high:
        mid = (low + high) // 2
        font = ImageFont.truetype(font_path, mid)
        
        # 检查最长一行的宽度
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), longest_line, font=font)
        text_width = bbox[2] - bbox[0]
        
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
    img = Image.open(img_path)
    image_width, image_height = img.size
    
    # 如果没有指定字体大小，自动计算
    if font_size is None:
        font_size = _calculate_font_size(text, image_width, image_height, font_path)
    
    # 换行处理
    lines = _wrap_text(text)
    
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    
    # 计算总的文本高度和宽度
    line_height = font_size * 1.3  # 行高为字体大小的1.3倍
    total_height = line_height * len(lines)
    
    # 计算每一行的最大宽度
    max_width = 0
    bboxes = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        bboxes.append(bbox)
        line_width = bbox[2] - bbox[0]
        max_width = max(max_width, line_width)
    
    # 计算起始位置（居中）
    start_x = (image_width - max_width) / 2
    start_y = (image_height - total_height) / 2 + 40
    
    # 绘制每一行文本
    for i, (line, bbox) in enumerate(zip(lines, bboxes)):
        x = (image_width - (bbox[2] - bbox[0])) / 2  # 每行单独水平居中
        y = start_y + i * line_height - bbox[1]
        draw.text((x, y), line, fill=text_color, font=font, stroke_fill=stroke, stroke_width=10)
    
    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()


async def gen_xibao(text: str = "", font_size: int | None = None) -> bytes:
    return await _generate_image("xibao_bg.png", text, font_size, "red", stroke="yellow")

async def gen_beibao(text: str = "", font_size: int | None = None) -> bytes:
    return await _generate_image("beibao_bg.png", text, font_size, "black", stroke="white")


genxibao = on_command("喜报", aliases={"喜报：", "喜报:", "喜报。", "喜报.", "喜报，", "喜报,", 
    "喜报！", "喜报!", "喜报？", "喜报?", "喜报；", "喜报;",
    "喜报、", "喜报-", "喜报_", "喜报|", "喜报~", "喜报@"} )
@genxibao.handle()
async def xibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 30:
        await genxibao.finish("字数太多啦！长度应在 30 个字符以内。")
    picdata = await gen_xibao(text = textinput)
    await saa.Image(picdata).send()


genbeibao = on_command("悲报", aliases={"悲报：", "悲报:", "悲报。", "悲报.", "悲报，", "悲报,", 
    "悲报！", "悲报!", "悲报？", "悲报?", "悲报；", "悲报;",
    "悲报、", "悲报-", "悲报_", "悲报|", "悲报~", "悲报@"} )
@genbeibao.handle()
async def beibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 30:
        await genbeibao.finish("字数太多啦！长度应在 30 个字符以内。")
    picdata = await gen_beibao(text = textinput)
    await saa.Image(picdata).send() 
