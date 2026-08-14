"""Clientes de fontes externas usados pelo feature builder."""

from .eia import EIAClient
from .epa import EPAClient
from .fred import FREDClient
from .news import NewsAPIClient
from .nhtsa import NHTSAClient

__all__ = ["EIAClient", "EPAClient", "FREDClient", "NewsAPIClient", "NHTSAClient"]
