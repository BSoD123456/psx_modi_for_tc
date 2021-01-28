# PSX rom modifier for Tail Concerto
PS游戏Tail Concerto汉化工具集。
## 使用
- 安装 Ptyhon 3
- 直接运行 main.py
- 如果报错，则依照使用情况修改 config.txt。
- 第一次运行会花较长时间解包。完成后全文本文件texts.json会被保存在sav文件夹（默认table/sav)下。
- 为了可读性，可以使用JS格式美化工具处理texts.json（比如notepad++的JSTool插件）。
- 翻译文本直接填入texts.json每一条目中的trans项内。
- - 翻译文本只能使用GB2312编码允许的全角字符（控制符号@除外）。
- - info项内的第3个数字代表空余长度，翻译文本长度必须小于（原始文本长度+空余长度）。全角字符长度算2，@符长度算1。
- - 如果原文本以@符结尾，翻译文本也必须以@符结尾。
- 如果要使用tim图片相关功能，将config.txt中TIM页下的enable项设置为on（默认为off）。
- - 之后运行 main.py 即可导出tim文件至ext路径下的tim文件夹内。
- - 将修改过的tim文件放入sav路径下的tim文件夹内，再次运行 main.py 即可导回tim文件。
- 再次运行 main.py 即可导回文本。输出文件会被保存在out文件夹（默认table/out）下，包括修改后的rom和修改后的BIOS文件。
- 使用修改版的rom时，必须要搭配修改版的BIOS文件一起使用，否则会显示乱码。
## 声明
如无法同意下述声明，请勿使用本工具：
- 本工具中使用的所有其他工具（tools文件夹中）和资源（assets文件夹中）的所有版权归其原作者。
- 本工具中其他代码可以任意使用和修改。
- 本工具作者不承担任何使用本工具造成的结果。
