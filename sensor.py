"""Support for IoTaWatt Energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from iotawattpy.sensor import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt

from .const import DOMAIN, VOLT_AMPERE_REACTIVE, VOLT_AMPERE_REACTIVE_HOURS
from .coordinator import IotawattUpdater

_LOGGER = logging.getLogger(__name__)


@dataclass
class IotaWattSensorEntityDescription(SensorEntityDescription):
    """Class describing IotaWatt sensor entities."""

    value: Callable | None = None
    min_value: float | None = None
    max_value: float | None = None


ENTITY_DESCRIPTION_KEY_MAP: dict[str, IotaWattSensorEntityDescription] = {
    "Amps": IotaWattSensorEntityDescription(
        "Amps",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        min_value=-1000.0,
        max_value=1000.0,
    ),
    "Hz": IotaWattSensorEntityDescription(
        "Hz",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
        min_value=0.0,
        max_value=1000.0,
    ),
    "PF": IotaWattSensorEntityDescription(
        "PF",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
        min_value=0.0,
        max_value=100.0,
    ),
    "Watts": IotaWattSensorEntityDescription(
        "Watts",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        min_value=-100000.0,
        max_value=100000.0,
    ),
    "WattHours": IotaWattSensorEntityDescription(
        "WattHours",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        min_value=-1000000.0,
        max_value=1000000.0,
    ),
    "VA": IotaWattSensorEntityDescription(
        "VA",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_registry_enabled_default=False,
        min_value=-100000.0,
        max_value=100000.0,
    ),
    "VAR": IotaWattSensorEntityDescription(
        "VAR",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
        min_value=-100000.0,
        max_value=100000.0,
    ),
    "VARh": IotaWattSensorEntityDescription(
        "VARh",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE_HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
        min_value=-1000000.0,
        max_value=1000000.0,
    ),
    "Volts": IotaWattSensorEntityDescription(
        "Volts",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        min_value=0.0,
        max_value=1000.0,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: IotawattUpdater = hass.data[DOMAIN][config_entry.entry_id]
    created = set()

    @callback
    def _create_entity(key: str) -> IotaWattSensor:
        """Create a sensor entity."""
        created.add(key)
        data = coordinator.data["sensors"][key]
        description = ENTITY_DESCRIPTION_KEY_MAP.get(
            data.getUnit(), IotaWattSensorEntityDescription("base_sensor")
        )

        return IotaWattSensor(
            coordinator=coordinator,
            key=key,
            entity_description=description,
        )

    async_add_entities(_create_entity(key) for key in coordinator.data["sensors"])

    @callback
    def new_data_received():
        """Check for new sensors."""
        entities = [
            _create_entity(key)
            for key in coordinator.data["sensors"]
            if key not in created
        ]
        async_add_entities(entities)

    coordinator.async_add_listener(new_data_received)


class IotaWattSensor(CoordinatorEntity[IotawattUpdater], SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    entity_description: IotaWattSensorEntityDescription

    def __init__(
        self,
        coordinator: IotawattUpdater,
        key: str,
        entity_description: IotaWattSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self._key = key
        self._attr_unique_id = self._sensor_data.getSensorID()
        self.entity_description = entity_description

    @property
    def _sensor_data(self) -> Sensor:
        """Return sensor data."""
        return self.coordinator.data["sensors"][self._key]

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return self._sensor_data.getName()

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return device info."""
        return entity.DeviceInfo(
            connections={
                (dr.CONNECTION_NETWORK_MAC, self._sensor_data.hub_mac_address)
            },
            manufacturer="IoTaWatt",
            model="IoTaWatt",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._key not in self.coordinator.data["sensors"]:
            if self._attr_unique_id:
                er.async_get(self.hass).async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove())
            return

        if (begin := self._sensor_data.getBegin()) and (
            last_reset := dt.parse_datetime(begin)
        ):
            if last_reset.timestamp() > 86400:
                self._attr_last_reset = last_reset
            else:
                self._attr_last_reset = None

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the extra state attributes of the entity."""
        data = self._sensor_data
        attrs = {"type": data.getType()}
        if attrs["type"] == "Input":
            attrs["channel"] = data.getChannel()

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = self._sensor_data.getValue()
        if func := self.entity_description.value:
            value = func(value)

        # Apply limits
        if self.entity_description.min_value is not None and value < self.entity_description.min_value:
            _LOGGER.warning(f"Value {value} for {self.name} is below the minimum limit. Marking as unavailable.")
            return None
        if self.entity_description.max_value is not None and value > self.entity_description.max_value:
            _LOGGER.warning(f"Value {value} for {self.name} is above the maximum limit. Marking as unavailable.")
            return None

        return value
