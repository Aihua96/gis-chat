# 测绘报告 AI

面向工程测量（道路/场坪竣工测量）的报告生成应用。用户按项目组织资料与 GIS 矢量成果，
系统用确定性程序计算指标与质检结论，再由大模型完成叙述性成文，输出可下载的 Word 技术报告。

**核心产品约束：面积、长度、要素数、坐标系等一切数值由 GIS 引擎计算，大模型只负责组织语言。**
提示词中明确禁止模型自行推算数值；未配置模型时退回受控模板，流程随时可跑通。

## 快速启动

需要 Python 3.10+。GIS 解析、统计与 Web 服务全部使用标准库，只有 Word 读写依赖 `python-docx`：

```bash
pip install -r requirements.txt
python3 app.py
```

浏览器打开 <http://127.0.0.1:8080>，点「创建示例项目并导入成果」可一键跑通全流程。

## 使用流程

1. **创建项目** —— 填写名称、类型、测区、周期、承担单位等，或一键创建示例项目；
2. **上传项目资料** —— TXT / MD / CSV / DOCX，提取为文本供模型参考；
3. **导入矢量成果** —— GeoJSON，或含 `.shp + .dbf + .shx + .prj` 的 Shapefile ZIP；
4. **查看统计与质检** —— 要素数、分图层面积长度、属性与重叠预警、测区示意图；
5. **配置大模型**（可选）—— 任意 OpenAI 兼容服务，地址与模型名保存在服务端，API Key 只随本次请求发送、不落盘；
6. **生成报告** —— 选择模板生成 Word 初稿，报告按项目留存历史，可反复下载。

项目、成果、资料与报告记录持久化在 `runtime/`，重启不丢失。

## 架构

分层依赖单向向下，每层只依赖下层的接口：

```
app.py            装配入口（composition root）：在这里注入具体实现
 └ src/http_api   HTTP 路由：只做协议转换与错误映射，不含业务规则
    └ src/services   应用服务：ProjectService / DatasetService / ReportService，编排完整用例
       ├ src/storage   仓储：JSON 文件实现，可替换为数据库
       ├ src/gis       GIS 引擎：导入(shapefile) / 统计(evidence) / 示意图(preview)
       ├ src/ai        模型接入：传输(client) 与 提示词及回退策略(narrative) 分离
       └ src/reporting 报告产出：资料提取(materials) / 模板注册(templates) / Word 排版(docx_writer)
          └ src/domain 领域模型与错误类型：纯数据结构，无任何 IO
```

替换点（都不需要改动其他层）：

| 想替换的东西 | 改哪里 |
| --- | --- |
| 换数据库存储 | 用同名方法实现 `src/storage.py` 中的四个仓储类，在 `app.py` 注入 |
| 换模型供应商 | 实现 `complete_json(system, user)`，注入 `NarrativeGenerator(client_factory=...)` |
| 换 Shapefile 解析库 | 只改 `src/gis/shapefile.py` 的 `read_shapefile_zip` |
| 加报告模板 | 在 `src/reporting/templates.py` 登记，前端选项由 `/api/meta` 自动下发 |
| 换 Web 框架 | 只重写 `src/http_api.py` |

## HTTP 接口

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/meta` | 模板列表、支持的文件类型、python-docx 可用性、已保存的模型配置 |
| `GET/PUT /api/settings` | 读取 / 保存模型地址与模型名（不含 API Key） |
| `GET/POST /api/projects` | 项目列表 / 创建项目 |
| `POST /api/projects/demo` | 创建示例项目并导入内置成果 |
| `GET/DELETE /api/projects/{id}` | 项目详情（含证据与报告历史）/ 删除项目 |
| `POST /api/projects/{id}/dataset` | 导入矢量成果，返回统计证据 |
| `GET /api/projects/{id}/preview.svg` | 测区成果示意图 |
| `POST /api/projects/{id}/materials` | 上传并提取项目资料 |
| `GET/POST /api/projects/{id}/reports` | 报告历史 / 生成报告 |
| `GET /output/{filename}` | 下载已生成的报告 |

## 已知限制（生产化前需处理）

- **面重叠检查为包络盒近似**，只能作为人工复核提示，不能替代严格拓扑验证；
- **Shapefile 解析器为手写实现**，仅支持 Point / PolyLine / Polygon，对畸形文件容错有限，生产版建议改用 pyshp / fiona；
- **面积长度按投影平面坐标计算**，输入若为经纬度坐标则结果无物理意义，导入前需确认坐标系；
- **无鉴权、无多用户隔离**，服务仅监听 127.0.0.1；模型 Base URL 由前端传入并由服务端发起请求，若对外暴露需增加认证与出站地址白名单；
- **报告生成为同步阻塞调用**，模型较慢时请求最长等待 90 秒，尚无异步任务与进度反馈；
- **仓储为单机 JSON 文件**，适合单人演示与试用，并发写入靠进程内锁保证，多实例部署需换数据库；
- 报告正文字体默认 `Heiti SC`（macOS），其他系统需在 `src/config.py` 中改为本地已授权的中文字体。
