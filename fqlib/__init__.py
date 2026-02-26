# Copyright (c) 2024
# Licensed under the MIT License.

"""
fin-qlib: Qlib Online Manager Best Practices

A production-ready framework for managing online quant trading models with Qlib.
"""

__version__ = "1.0.0"

from .managed_manager import ManagedOnlineManager
from .ensemble import (
    WeightedEnsemble,
    BestModelEnsemble,
    DynamicWeightEnsemble,
    VotingEnsemble,
    SignalEvaluator
)
from .prediction_service import PredictionService

# Define __all__ first
__all__ = [
    "ManagedOnlineManager",
    "WeightedEnsemble",
    "BestModelEnsemble",
    "DynamicWeightEnsemble",
    "VotingEnsemble",
    "SignalEvaluator",
    "PredictionService",
]

# API server (optional - requires fastapi)
try:
    from .api_server import app
    __all__.append("app")
except ImportError:
    pass  # FastAPI is optional

# MLflow integration (optional - requires mlflow)
try:
    from .mlflow_integration import (
        MLflowLogger,
        QlibMetricsLogger,
        QlibBacktestAnalyzer,
        MLflowEnabledStrategy,
    )
    __all__.extend([
        "MLflowLogger",
        "QlibMetricsLogger",
        "QlibBacktestAnalyzer",
        "MLflowEnabledStrategy",
    ])
except ImportError:
    pass  # MLflow is optional
