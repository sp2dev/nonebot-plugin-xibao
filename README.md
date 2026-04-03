# 喜（悲）报生成器

## 提醒

~~字体渲染引擎现已迁移至 `skia-python`，带来了渲染 Unicode 级别的字形和 emoji 支持（人话：字体不支持一个字符时会自动回调至有这个字符的系统字体）~~（即将废弃）

由于 skia 无法完美支持所有 linux 系统，插件正在进行 `pillow` + `pilmoji` 的重构，
如果你在运行中发现 `ImportError: libEGL.so.1: cannot open shared object` 的问题，请执行以下命令

```bash
sudo apt install libglu1-mesa-dev libegl1-mesa
```

**作者产能不是很够，所以需要等待很长时间才能完成重构，如果有急用，请参阅 [#1](https://github.com/sp2dev/nonebot-plugin-xibao/issues/1)**

## 安装

```bash
nb plugin install nonebot-plugin-xibao
```

或者

```bash
pip install nonebot-plugin-xibao
```

之后在 `pyproject.toml` 中手动添加

## 使用

使用时记得加上前缀哦！

| 命令 | 功能 |
| --- | --- |
| `喜报` | 生成一张喜报 |
| `悲报` | 生成一张悲报 |

## 效果图

### 喜报

![Image_1750860971884](https://github.com/user-attachments/assets/19892b1a-3c49-4e34-9081-4a8dfe955442)

### 悲报

![Image_1750860974571](https://github.com/user-attachments/assets/ea14dc6b-30a3-4528-bce3-6573e22011fc)
