"""Camada modular de ingestão e features para demanda automotiva."""

from .contracts import FeatureBuildResult, NewsQuery, SourceName, SourceRunStatus, SourceState, TimeWindow
from .feature_builder import FeatureBuilder
from .settings import FeatureSettings, FeatureSourceConfig, load_feature_source_config

__all__ = [
    "FeatureBuilder",
    "FeatureBuildResult",
    "FeatureSettings",
    "FeatureSourceConfig",
    "NewsQuery",
    "SourceName",
    "SourceRunStatus",
    "SourceState",
    "TimeWindow",
    "load_feature_source_config",
]
