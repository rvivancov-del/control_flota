"""Modelos ORM del esquema fleet."""
from app.models.vehicle import Vehicle
from app.models.driver import Driver
from app.models.trip import Trip
from app.models.expense import Expense
from app.models.maintenance import MaintenanceRecord
from app.models.costs import FixedCost, PersonnelCost

__all__ = ["Vehicle", "Driver", "Trip", "Expense", "MaintenanceRecord", "FixedCost", "PersonnelCost"]
