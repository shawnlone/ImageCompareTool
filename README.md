# 图片对比工具

一个简单的桌面图片对比工具。  
平时改 UI、看截图、核对设计稿的时候，经常需要把两张图放在一起看差异，所以做了这个工具。

支持左右滑动对比，也可以拖拽、粘贴图片，适合快速看「改前 / 改后」。

## 功能

- 拖入两张图片开始对比
- 支持粘贴剪贴板里的图片
- 鼠标滚轮缩放，右键拖动画面
- `1` / `2` 快速只看 A 或 B，`3` 横向排列 A / B
- `Space` 切换彩色 / 黑白
- `Tab` 交换 A / B
- 多标签页
- 保存和打开 `.icp` 工程文件
- 可调整对比标题样式

## 运行

如果只是使用，建议直接下载 Release 里的 exe。

如果要从源码运行：

```bash
pip install PySide6 Pillow
python image_compare_tool.py
```

也可以这样运行：

```bash
python -m image_compare_tool.app
```

## 打包

项目里带了一个简单的打包脚本：

```powershell
.\build.ps1
```

打包后文件会生成在：

```text
dist/ImageCompareTool.exe
```

单文件 exe 第一次启动会慢一点，这是 PyInstaller 单文件模式的正常现象。  
如果比较在意启动速度，可以改用 `onedir` 模式打包。

## 快捷键

- `Ctrl + T`：新建标签页
- `Ctrl + W`：关闭当前标签页
- `Ctrl + C`：复制对比图
- `Ctrl + S`：保存工程
- `F`：标题设置
- `T`：窗口置顶

## 反馈

如果遇到问题，或者有功能建议，除了 GitHub Issues 之外，也可以通过下面的表单快速反馈：

https://my.feishu.cn/share/base/form/shrcnu1BRg8IsfimXzWCCFhbSXd


## License

见 [LICENSE](LICENSE)。
