# -*- coding: utf-8 -*-
"""
Module: context.py
Author: Takeshi
Date: 2025-12-06

Description:
    各类功能模块的全局对象集合
"""


from typing import Optional

from .user_manager import UserManager
from .health_checker import HealthChecker
from .security_manager import SecurityManager
from .ip_geo_manager import IPGeoManager
from .stats_manager import StatsManager

from .signals import LogSignals, StatusSignals


class ManagerContext:
    def __init__(self):
        self.user_manager: Optional[UserManager] = None
        self.security_manager: Optional[SecurityManager] = None
        self.health_checker: Optional[HealthChecker] = None
        self.stats_manager: Optional[StatsManager] = None
        self.ip_geo_manager: Optional[IPGeoManager] = None
        self.log_singals: Optional[LogSignals] = None
        self.status_singals: Optional[StatusSignals] = None

    def initialize(self,
                   user_manager: UserManager,
                   security_manager: SecurityManager,
                   health_checker: HealthChecker,
                   stats_manager: StatsManager,
                   ip_geo_manager: IPGeoManager,

                   log_signals: LogSignals,
                   status_signals: StatusSignals,
                   ):
        self.user_manager = user_manager
        self.security_manager = security_manager
        self.health_checker = health_checker
        self.stats_manager = stats_manager
        self.ip_geo_manager = ip_geo_manager

        self.log_signals = log_signals
        self.status_signals = status_signals
