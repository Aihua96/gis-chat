# 测绘报告 AI 演示 MVP

面向工程测量（道路/场坪竣工测量）的本地演示应用。它以模拟项目数据展示从 GIS 矢量成果到指标、质检、示意图和 Word 技术总结初稿的闭环。

## 快速启动

需要 Python 3.10+。GIS 解析、统计与 Web 服务全部使用标准库，只有 Word 导出依赖 `python-docx`：

```bash
pip install -r requirements.txt
python3 app.py
```

浏览器打开 <http://127.0.0.1:8080>。未安装 `python-docx` 时应用仍可启动并完成导入与统计，仅报告导出不可用。

## 目录结构

```
app.py                  HTTP 路由与请求校验
src/config.py           演示项目元数据、路径与报告字体常量
src/gis_service.py      Shapefile/GeoJSON 导入、确定性统计、SVG 示意图
src/llm.py              叙述章节生成（OpenAI 兼容接口 + 受控模板回退）
src/documents.py        上传资料文本提取与 Word 报告排版
web/index.html          单页前端
scripts/create_demo_shp.py  由演示 GeoJSON 生成示例 Shapefile ZIP
```

## 演示范围

- 内置“新城产业园西侧配套道路竣工测量”模拟项目；
- 支持导入 GeoJSON，以及包含 `.shp + .dbf + .shx + .prj` 的 Shapefile ZIP（Polygon / PolyLine / Point）；
- 自动统计面积、长度、要素数、图层及坐标参考；
- 执行属性完整性、重复编号、面要素重叠等基础检查；
- 生成可下载的 DOCX《工程测量技术总结报告》；
- 生成 SVG 测区示意图与可追溯的指标口径；
- 用四步界面演示“项目创建 → 成果导入 → 统计质检 → Word 审核导出”。
- 支持上传 TXT/MD/CSV/DOCX 项目资料、填写用户需求、选择报告模板；
- 支持配置本地或公网的 OpenAI 兼容 `chat/completions` API（Base URL、模型、API Key）。

这是演示型 MVP：GIS 数值由确定性程序计算，模型生成的分析性段落（项目概况、技术路线、质量评价、结论建议）由配置的大模型生成，避免把关键数值交给大模型。未配置模型时系统会以受控模板模式生成，便于无模型环境演示。

## 配置大模型

在页面的“2. 大模型配置”中填写：

- 内网模型：例如 `http://模型服务器:8000/v1`，模型名为服务实际暴露的名称；
- 公网服务：填写该服务提供的 OpenAI 兼容 Base URL、模型名和 API Key；
- API Key 只随本次“生成报告”请求发送，不写入服务器文件。

模型只能接收项目描述、上传资料摘录和 GIS 引擎生成的结构化证据。提示词明确禁止模型自行生成面积、长度、坐标、精度等数据；这些数值始终由 GIS 计算模块提供。

演示用 Shapefile ZIP 位于 `data/demo_engineering_survey_shp.zip`。SHP 是单一几何类型/图层格式，示例 ZIP 内含四组图层文件，用于模拟工程测量成果包。

## 已知限制（生产化前需处理）

- **面重叠检查为包络盒近似**，只能作为人工复核提示，不能替代严格拓扑验证；
- **Shapefile 解析器为手写实现**，仅支持 Point / PolyLine / Polygon，对畸形文件容错有限，生产版建议改用 pyshp / fiona；
- **面积长度按投影平面坐标计算**，输入若为经纬度坐标则结果无物理意义，导入前需确认坐标系；
- **服务无鉴权且仅监听 127.0.0.1**，仅供本地演示；模型 Base URL 由前端传入并由服务端发起请求，若对外暴露需增加认证与出站地址白名单；
- **项目信息硬编码在 `src/config.py`**，尚无多项目管理与持久化；
- 报告正文字体默认 `Heiti SC`（macOS），其他系统需在 `src/config.py` 中改为本地已授权的中文字体。
