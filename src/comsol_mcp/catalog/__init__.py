"""Offline static COMSOL API catalog and local installation XML extractor."""

from .store import CatalogStore, build_catalog_from_install

__all__ = ["CatalogStore", "build_catalog_from_install"]
