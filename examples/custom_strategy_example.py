# Copyright (c) 2024
# Licensed under the MIT License.

"""
自定义策略示例

展示如何创建自定义策略并集成到 OnlineManager 中。

适用场景：
1. 不使用滚动训练（例如，使用固定窗口）
2. 自定义模型切换逻辑
3. 需要特殊的任务生成逻辑
4. 多阶段训练流程
"""

from typing import List, Dict
from qlib.workflow.online.strategy import OnlineStrategy
from qlib.workflow.online.utils import OnlineToolR
from qlib.workflow.task.gen import task_generator
import pandas as pd


class FixedWindowStrategy(OnlineStrategy):
    """
    固定窗口策略示例

    与 RollingStrategy 不同，这个策略使用固定的训练窗口，
    而不是滚动更新。
    """

    def __init__(self, name_id: str, task_template: Dict,
                 retrain_interval: int = 90):
        """
        Args:
            name_id: 策略名称
            task_template: 任务模板（包含模型和dataset配置）
            retrain_interval: 重新训练间隔（天）
        """
        super().__init__(name_id=name_id)
        self.task_template = task_template
        self.retrain_interval = retrain_interval
        self.tool = OnlineToolR(self.name_id)
        self.last_train_date = None

    def first_tasks(self) -> List[dict]:
        """
        生成初始任务
        """
        # 返回单个任务（使用配置中的固定窗口）
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs) -> List[dict]:
        """
        检查是否需要重新训练

        Args:
            cur_time: 当前时间
        """
        cur_time = pd.Timestamp(cur_time)

        # 如果从未训练过，或者距离上次训练超过间隔时间
        if self.last_train_date is None:
            self.last_train_date = cur_time
            return [self.task_template.copy()]

        days_since_last = (cur_time - self.last_train_date).days

        if days_since_last >= self.retrain_interval:
            self.last_train_date = cur_time
            return [self.task_template.copy()]

        # 不需要重新训练
        return []

    def get_collector(self, process_list=[], **kwargs):
        """
        获取结果收集器
        """
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        def rec_key(recorder):
            # 使用 recorder ID 作为 key
            return recorder.info['id']

        return RecorderCollector(
            experiment=self.name_id,
            process_list=process_list or [RollingGroup()],
            rec_key_func=rec_key,
        )


class EnsembleStrategy(OnlineStrategy):
    """
    集成策略示例

    同时维护多个模型，并使用集成方法生成信号。
    适用于需要同时保留多个模型的场景。
    """

    def __init__(self, name_id: str, task_templates: List[Dict],
                 keep_n_models: int = 3):
        """
        Args:
            name_id: 策略名称
            task_templates: 任务模板列表（每个模板对应一个模型）
            keep_n_models: 保留最近训练的 N 个模型
        """
        super().__init__(name_id=name_id)
        self.task_templates = task_templates
        self.keep_n_models = keep_n_models
        self.tool = OnlineToolR(self.name_id)
        self.model_history = []  # 记录训练历史

    def first_tasks(self) -> List[dict]:
        """生成初始任务"""
        return [tmpl.copy() for tmpl in self.task_templates]

    def prepare_tasks(self, cur_time, **kwargs) -> List[dict]:
        """
        每次重新训练所有模型
        """
        return [tmpl.copy() for tmpl in self.task_templates]

    def prepare_online_models(self, trained_models, cur_time=None) -> List:
        """
        只保留最近训练的 N 个模型作为在线模型
        """
        if not trained_models:
            return self.tool.online_models()

        # 添加到历史记录
        self.model_history.extend(trained_models)

        # 只保留最近的 N 个
        if len(self.model_history) > self.keep_n_models:
            online_models = self.model_history[-self.keep_n_models:]
        else:
            online_models = self.model_history

        # 更新 online 标签
        self.tool.reset_online_tag(online_models)
        return online_models

    def get_collector(self, process_list=[], **kwargs):
        """获取结果收集器"""
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        def rec_key(recorder):
            return recorder.info['id']

        return RecorderCollector(
            experiment=self.name_id,
            process_list=process_list or [RollingGroup()],
            rec_key_func=rec_key,
        )


class AdaptiveRetrainStrategy(OnlineStrategy):
    """
    自适应重训练策略

    根据模型性能动态决定是否重新训练：
- 如果性能下降超过阈值，立即重训练
- 否则按固定周期重训练
    """

    def __init__(self, name_id: str, task_template: Dict,
                 retrain_interval: int = 30,
                 performance_threshold: float = 0.02,
                 metric: str = 'ic'):
        """
        Args:
            name_id: 策略名称
            task_template: 任务模板
            retrain_interval: 正常重训练间隔（天）
            performance_threshold: 性能下降阈值（触发立即重训练）
            metric: 监控的指标
        """
        super().__init__(name_id=name_id)
        self.task_template = task_template
        self.retrain_interval = retrain_interval
        self.performance_threshold = performance_threshold
        self.metric = metric
        self.tool = OnlineToolR(self.name_id)
        self.last_train_date = None
        self.last_performance = None

    def first_tasks(self) -> List[dict]:
        self.last_train_date = pd.Timestamp.now()
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs) -> List[dict]:
        cur_time = pd.Timestamp(cur_time)

        # 检查性能
        current_performance = self._get_current_performance()

        need_retrain = False

        # 情况1: 超过重训练间隔
        if self.last_train_date is not None:
            days_since_last = (cur_time - self.last_train_date).days
            if days_since_last >= self.retrain_interval:
                need_retrain = True

        # 情况2: 性能下降
        if (self.last_performance is not None and
            current_performance is not None):
            performance_drop = self.last_performance - current_performance
            if performance_drop > self.performance_threshold:
                print(f"Performance dropped from {self.last_performance:.4f} "
                      f"to {current_performance:.4f}, triggering retrain")
                need_retrain = True

        if need_retrain:
            self.last_train_date = cur_time
            self.last_performance = current_performance
            return [self.task_template.copy()]

        return []

    def _get_current_performance(self) -> float:
        """
        获取当前模型性能

        NOTE: 这是简化实现，生产环境应该从 Recorder 或数据库查询
        """
        # TODO: 实现实际的性能查询
        # 可以从 Recorder 的 artifacts 中加载 IC 等指标
        return 0.05  # Mock IC

    def get_collector(self, process_list=[], **kwargs):
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        def rec_key(recorder):
            return recorder.info['id']

        return RecorderCollector(
            experiment=self.name_id,
            process_list=process_list or [RollingGroup()],
            rec_key_func=rec_key,
        )


# 使用示例
if __name__ == "__main__":
    # 示例1: 固定窗口策略
    fixed_window_strat = FixedWindowStrategy(
        name_id="FixedWindow_LGB",
        task_template={
            "model": {
                "class": "LGBModel",
                "module_path": "qlib.contrib.model.gbdt",
            },
            "dataset": {
                "class": "DatasetH",
                "module_path": "qlib.data.dataset",
                "kwargs": {
                    "handler": {
                        "class": "Alpha158",
                        "module_path": "qlib.contrib.data.handler",
                    },
                    "segments": {
                        "train": ("2020-01-01", "2023-01-01"),  # 固定3年窗口
                        "valid": ("2023-01-01", "2023-07-01"),
                        "test": ("2023-07-01", "2024-01-01"),
                    }
                }
            }
        },
        retrain_interval=90  # 每90天重训练
    )

    # 示例2: 集成策略
    ensemble_strat = EnsembleStrategy(
        name_id="Ensemble_LGB_XGB",
        task_templates=[
            {  # LGB 模型
                "model": {"class": "LGBModel", "module_path": "qlib.contrib.model.gbdt"},
                "dataset": {...}
            },
            {  # XGB 模型
                "model": {"class": "XGBoostModel", "module_path": "qlib.contrib.model.xgboost"},
                "dataset": {...}
            },
        ],
        keep_n_models=3  # 保留最近的3个模型
    )

    # 示例3: 自适应重训练策略
    adaptive_strat = AdaptiveRetrainStrategy(
        name_id="Adaptive_LGB",
        task_template={...},
        retrain_interval=30,
        performance_threshold=0.02  # IC下降0.02时触发重训练
    )
