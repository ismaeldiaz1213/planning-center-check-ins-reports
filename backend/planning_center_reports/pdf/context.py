# planning_center_reports/pdf/context.py
#
# What a PDF function needs besides its data: the church's words, its colours
# and its branding. One RenderContext is passed to every drawing function, so
# two churches can be rendered in the same process without sharing anything.
# (It replaces the old config._theme global and config.T().)

from __future__ import annotations

from dataclasses import dataclass, replace

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.config import THEMES
from planning_center_reports.i18n import Catalog


@dataclass(frozen=True)
class RenderContext:
    texts:     Catalog
    branding:  Branding
    theme_key: str | None = None      # None = the default navy/blue look

    @classmethod
    def for_church(cls, church: ChurchConfig, theme: str | None = None) -> RenderContext:
        return cls(texts=church.texts, branding=church.branding, theme_key=theme or church.theme)

    @property
    def theme(self) -> dict:
        return THEMES[self.theme_key]

    def T(self, key: str):
        """A colour or asset name from the active theme."""
        return self.theme[key]

    @property
    def campaign(self) -> str | None:
        """The campaign label printed in the page header, if a theme is active."""
        return self.texts.t(f"campaign.{self.theme_key}") if self.theme_key else None

    def with_theme(self, theme: str | None) -> RenderContext:
        return replace(self, theme_key=theme)
