# -*- coding=UTF-8 -*-

from abc import abstractmethod
import auto_derby
from auto_derby import single_mode


from typing import List, Text
import datetime

import logging
from auto_derby.single_mode.context import Context

from auto_derby.single_mode.race.race import Race
from auto_derby.single_mode.race import race_result

_LOGGER = logging.getLogger(__name__)


JST = datetime.timezone(datetime.timedelta(hours=9), name="JST")


class Campaign:
    def __init__(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        race_name: Text,
    ) -> None:
        self.start = start
        self.end = end
        self.race_name = race_name
        super().__init__()

    @abstractmethod
    def match(self, ctx: Context, race: Race) -> bool:
        if race.name != self.race_name:
            return False
        now = datetime.datetime.now(JST)
        if not (self.start <= now <= self.end):
            return False
        return True


class OncePerDayCampaign(Campaign):
    def __init__(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        race_name: Text,
        *,
        order_lte: int = 999,
    ) -> None:
        super().__init__(
            start,
            end,
            race_name,
        )
        self.order_lte = order_lte

    def match(self, ctx: Context, race: Race) -> bool:
        if not super().match(ctx, race):
            return False
        for r in race_result.iterate():
            if (
                r.race.name == race.name
                and r.order <= self.order_lte
                and r.time.astimezone(JST).date() == datetime.datetime.now(JST).date()
            ):
                return False

        return True


_CAMPAIGNS: List[Campaign] = []


def _add_compagin(
    c: Campaign,
) -> None:

    now = datetime.datetime.now(JST)
    # include tomorrow's campaign
    if not (c.start - datetime.timedelta(days=1) <= now <= c.end):
        return

    _CAMPAIGNS.append(c)


# https://dmg.umamusume.jp/news/detail/?id=470
_add_compagin(
    OncePerDayCampaign(
        datetime.datetime(2021, 12, 11, 5, 0, tzinfo=JST),
        datetime.datetime(2021, 12, 13, 4, 59, tzinfo=JST),
        "阪神ジュベナイルフィリーズ",
        order_lte=1,
    )
)

_add_compagin(
    OncePerDayCampaign(
        datetime.datetime(2021, 12, 18, 5, 0, tzinfo=JST),
        datetime.datetime(2021, 12, 20, 4, 59, tzinfo=JST),
        "朝日杯フューチュリティステークス",
        order_lte=1,
    ),
)

_add_compagin(
    OncePerDayCampaign(
        datetime.datetime(2021, 12, 25, 5, 0, tzinfo=JST),
        datetime.datetime(2021, 12, 27, 4, 59, tzinfo=JST),
        "有馬記念",
        order_lte=1,
    )
)

_add_compagin(
    OncePerDayCampaign(
        datetime.datetime(2021, 12, 27, 5, 0, tzinfo=JST),
        datetime.datetime(2021, 12, 29, 4, 59, tzinfo=JST),
        "ホープフルステークス",
        order_lte=1,
    ),
)


class Plugin(auto_derby.Plugin):
    """Pick race by compagin."""

    def install(self) -> None:
        if not _CAMPAIGNS:
            _LOGGER.info("no race campaign today")
            return

        for i in _CAMPAIGNS:
            _LOGGER.info("race campaign: %s~%s %s", i.start, i.end, i.race_name)

        class Race(auto_derby.config.single_mode_race_class):
            def score(self, ctx: single_mode.Context) -> float:
                ret = super().score(ctx)
                if ret < 0:
                    return ret 
                if any(i.match(ctx, self) for i in _CAMPAIGNS):
                    ret += 100
                return ret

        auto_derby.config.single_mode_race_class = Race


auto_derby.plugin.register(__name__, Plugin())
