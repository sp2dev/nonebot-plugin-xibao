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


async def _generate_image(bg_file: str, text = "", font_size = 250, text_color = "black", stroke="") -> bytes:

    img_path = Path(__file__).parent / bg_file
    img = Image.open(img_path)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    image_width, image_height = img.size

    x = (image_width - text_width) / 2
    y = (image_height - text_height) / 2 - font_size / 4

    draw.text((x, y), text, fill=text_color, font=font, stroke_fill=stroke, stroke_width=10)
    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()


async def gen_xibao(font_size: int = 250, text: str = "") -> bytes:
    return await _generate_image("xibao_bg.png", text, font_size, "red", stroke="yellow")

async def gen_beibao(font_size: int = 250, text: str = "") -> bytes:
    return await _generate_image("beibao_bg.png", text, font_size, "black", stroke="white")


genxibao = on_command("喜报", aliases={"喜报：", "喜报:"} )
@genxibao.handle()
async def xibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 20:
        await genbeibao.finish("字数太多啦！长度应在 20 个字符以内。")
    elif len(textinput) < 10:
        size = 250 - len(textinput) * 8
    elif 15 < len(textinput) < 20:
        size = 250 - len(textinput) * 9
    else:
        size = 250 - len(textinput) * 10
    picdata = await gen_xibao(text = textinput, font_size=size)
    await saa.Image(picdata).send()


genbeibao = on_command("悲报", aliases={"悲报：", "悲报:"} )
@genbeibao.handle()
async def beibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    if len(textinput) >= 20:
        await genbeibao.finish("字数太多啦！长度应在 20 个字符以内。")
    elif len(textinput) < 10:
        size = 250 - len(textinput) * 8
    elif 15 < len(textinput) < 20:
        size = 250 - len(textinput) * 9
    else:
        size = 250 - len(textinput) * 10
    picdata = await gen_beibao(text = textinput, font_size=size)
    await saa.Image(picdata).send()
