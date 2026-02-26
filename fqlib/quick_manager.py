import qlib
from qlib.workflow.online.manager import OnlineManager
from qlib.workflow.online.strategy import RollingStrategy
from qlib.workflow.task.gen import RollingGen
from qlib.model.trainer import TrainerR
import pandas as pd

# 1. 初始化 Qlib
qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

# 2. 定义任务配置
task_config = {
    "model": {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt"
    },
    "dataset": {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {"class": "Alpha158", "module_path": "qlib.contrib.data.handler"},
            "segments": {
                "train": ("2018-01-01", "2019-12-31"),
                "valid": ("2020-01-01", "2020-06-30"),
                "test":  ("2020-07-01", "2020-12-31")
            }
        }
    }
}

# 3. 创建策略
strategy = RollingStrategy(
    name_id="my_strategy",
    task_template=task_config,
    rolling_gen=RollingGen(step=250, rtype=RollingGen.ROLL_SD)
)

# 4. 创建 OnlineManager
manager = OnlineManager(
    strategies=strategy,
    trainer=TrainerR(),  # 简单场景用 TrainerR
    begin_time="2020-07-01"
)

# 5. 运行回测（一步到位！）
signals = manager.simulate(end_time="2020-12-31", frequency="day")

# 6. 获取结果
print(f"信号数量: {len(signals)}")
print(f"时间范围: {signals.index.get_level_values('datetime').min()} ~ {signals.index.get_level_values('datetime').max()}")
print(signals.head())
