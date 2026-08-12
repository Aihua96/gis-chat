#!/usr/bin/env python3
"""启动入口（composition root）：在这里装配依赖，其余模块之间互不知晓具体实现。

    HTTP(src/http_api) → 服务(src/services) → 仓储(src/storage)
                                            → GIS 引擎(src/gis)
                                            → 模型接入(src/ai)
                                            → 报告产出(src/reporting)
"""
from src import config
from src.ai import NarrativeGenerator
from src.http_api import Api, serve
from src.services import DatasetService, ProjectService, ReportService
from src.storage import ProjectDataStore, ProjectRepository, ReportRepository, SettingsStore

def build_api() -> Api:
    config.RUNTIME.mkdir(parents=True, exist_ok=True)
    config.OUTPUT.mkdir(parents=True, exist_ok=True)

    project_repo = ProjectRepository(config.RUNTIME)
    report_repo = ReportRepository(config.RUNTIME)
    data_store = ProjectDataStore(config.RUNTIME)
    settings = SettingsStore(config.RUNTIME)

    datasets = DatasetService(project_repo, data_store, config.DEFAULT_CRS)
    projects = ProjectService(project_repo, data_store, report_repo, datasets,
                              config.DEMO_PROJECT, config.DATA / 'demo_project.geojson')
    reports = ReportService(project_repo, datasets, report_repo, config.OUTPUT, NarrativeGenerator())

    return Api(projects, datasets, reports, settings,
               web_dir=config.WEB, data_dir=config.DATA, output_dir=config.OUTPUT)

def main():
    print(f'测绘报告 AI v{config.VERSION} → http://{config.HOST}:{config.PORT}')
    serve(build_api(), config.HOST, config.PORT, config.MAX_BODY)

if __name__ == '__main__':
    main()
