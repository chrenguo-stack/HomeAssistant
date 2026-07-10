# LCD12864 像素字体依赖

F1.0-RC2 的 ST7920 LCD12864 使用固定像素 BDF 字体，不使用 Roboto Mono 等矢量字体。

## 所需文件

请将以下文件放在本目录：

```text
fusion-pixel-10px-monospaced-zh_hans.bdf
fusion-pixel-12px-monospaced-zh_hans.bdf
ark-pixel-16px-monospaced-zh_cn.bdf
```

## 选择原因

- 10px、12px：延续 14.8 的 Fusion Pixel Font，适合小字号中英文混排；
- 16px：使用 Ark Pixel Font，仅加载数字、小数点和负号，用于电压等醒目数值；
- 全部使用 `bpp: 1`，与 128×64 单色点阵屏匹配；
- 等宽字形便于表格化数据对齐，并避免矢量字体在低分辨率下的笔画模糊。

## 上游项目

- Fusion Pixel Font：https://github.com/TakWolf/fusion-pixel-font
- Ark Pixel Font：https://github.com/TakWolf/ark-pixel-font

字体由上游项目按 SIL Open Font License 1.1 授权。仓库不重复提交字体文件；开发环境应从上游正式 Release 获取并保留版本记录。

当前建议固定 Release：`2026.07.01`。
