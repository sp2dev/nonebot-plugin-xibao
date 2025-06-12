import nonebot
from nonebot import on_command
from nonebot import require

require("nonebot_plugin_saa")

from nonebot.adapters import Message
from nonebot.params import CommandArg
import nonebot_plugin_saa as saa

from PIL import Image, ImageDraw, ImageFont

from pathlib import Path
import io

font_path = Path(__file__).parent / "SourceHanSans.otf"


async def gen_xibao(font_size=250, text=""):
    xibao_path = Path(__file__).parent / "xibao_bg.png"
    xibao = Image.open(xibao_path)
    draw = ImageDraw.Draw(xibao)
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    image_width, image_height = xibao.size
    x = (image_width - text_width) / 2 + font_size / 4
    y = (image_height - text_height) / 2 - font_size / 4
    draw.text((x, y), text, fill="red", font=font)
    xibao_bytes = io.BytesIO()
    xibao.save(xibao_bytes,format='PNG')
    return xibao_bytes.getvalue()


async def gen_beibao(font_size=250, text=""):
    beibao_path = Path(__file__).parent / "beibao_bg.png"
    beibao = Image.open(beibao_path)
    draw = ImageDraw.Draw(beibao)
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    image_width, image_height = beibao.size
    x = (image_width - text_width) / 2 + font_size / 4
    y = (image_height - text_height) / 2 - font_size / 4
    draw.text((x, y), text, fill="black", font=font)
    beibao_bytes = io.BytesIO()
    beibao.save(beibao_bytes,format='PNG')
    return beibao_bytes.getvalue()


genxibao = on_command("喜报")
@genxibao.handle()
async def xibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    size = int(250 - round(len(textinput)) * 10)
    picdata = await gen_xibao(text = textinput, font_size=size)
    await saa.Image(picdata).send()


genbeibao = on_command("悲报")
@genbeibao.handle()
async def beibaohandle(args:Message = CommandArg()):
    textinput = args.extract_plain_text()
    size = int(250 - round(len(textinput)) * 10)
    picdata = await gen_beibao(text = textinput, font_size=size)
    await saa.Image(picdata).send()
