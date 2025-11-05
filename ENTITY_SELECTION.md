# Entity Selection and Filtering Guide

This guide explains the comprehensive entity selection, filtering, and classification system in the Clarify Data Bridge integration.

## Overview

The Clarify Data Bridge now features an intelligent entity discovery system that automatically:
- **Discovers** all available Home Assistant entities
- **Classifies** entities by domain, device class, and data type
- **Prioritizes** entities based on data value for time-series analytics
- **Extracts** comprehensive metadata including device info and location
- **Filters** entities using flexible criteria
- **Converts** binary sensors to numeric values (0/1)

## Entity Classification

### Priority Levels

Entities are automatically assigned priority levels based on their value for time-series data collection:

#### HIGH Priority
Critical time-series data, automatically tracked by default:
- **Energy & Power**: energy, power, voltage, current, power_factor, apparent_power, reactive_power
- **Environmental**: temperature, humidity, pressure, CO2, air quality (PM2.5, PM10, AQI)
- **Gases**: carbon_monoxide, nitrogen_dioxide, ozone, volatile_organic_compounds
- **Resource Monitoring**: battery, data_rate, frequency, weight

#### MEDIUM Priority
Useful metrics:
- **Light & Sound**: illuminance, brightness, sound_pressure
- **Motion**: distance, speed, signal_strength
- **Time**: duration, timestamp

#### LOW Priority
Less critical but still trackable:
- **Binary Sensors**: door, window, motion, occupancy (converted to 0/1)
- **Control Devices**: switches, lights with state data
- **Other**: miscellaneous sensors

### Entity Categories

Entities are classified into categories for better organization:

| Category | Description | Examples |
|----------|-------------|----------|
| `numeric_sensor` | Pure numeric sensors | Temperature, humidity, power |
| `binary_sensor` | Binary on/off sensors (→ 0/1) | Motion, door, window |
| `multi_value_sensor` | Sensors with multiple numeric attributes | Climate entities with temp + humidity |
| `control_device` | Switches, lights with state + attributes | Lights with brightness |
| `climate_device` | Climate control systems | Thermostats, HVAC |
| `power_device` | Power monitoring devices | Smart plugs, energy meters |
| `environmental` | Weather and air quality | Weather stations, air quality sensors |

## Configuration Options

### Basic Configuration

Configure entity selection in your `configuration.yaml` or via the integration config:

```yaml
# Example configuration (via config flow or YAML)
clarify_data_bridge:
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  integration_id: "your-integration-id"

  # Entity filtering options
  include_domains:
    - sensor
    - binary_sensor
    - climate

  exclude_entities:
    - sensor.excluded_sensor_1
    - sensor.excluded_sensor_2

  # Advanced filtering
  include_device_classes:
    - temperature
    - humidity
    - power
    - energy

  exclude_device_classes:
    - timestamp

  min_priority: "MEDIUM"  # HIGH, MEDIUM, or LOW

  # Pattern-based filtering (regex)
  include_patterns:
    - "sensor\\..*_temperature"
    - "sensor\\..*_power"

  exclude_patterns:
    - "sensor\\.test_.*"
```

### Filtering Options Explained

#### Domain Filtering

**`include_domains`** - Only track entities from these domains:
```yaml
include_domains:
  - sensor
  - binary_sensor
  - climate
```

**`exclude_domains`** - Exclude specific domains entirely:
```yaml
exclude_domains:
  - media_player
  - weather
```

#### Entity Filtering

**`exclude_entities`** - Exclude specific entities by ID:
```yaml
exclude_entities:
  - sensor.noisy_sensor
  - binary_sensor.unused_motion
```

**`include_entity_ids`** - Only track these specific entities (exclusive mode):
```yaml
include_entity_ids:
  - sensor.living_room_temperature
  - sensor.kitchen_humidity
  - sensor.total_power_consumption
```

#### Device Class Filtering

**`include_device_classes`** - Only track entities with these device classes:
```yaml
include_device_classes:
  - temperature
  - humidity
  - power
  - energy
  - carbon_dioxide
```

**`exclude_device_classes`** - Exclude entities with these device classes:
```yaml
exclude_device_classes:
  - timestamp
  - date
```

#### Priority Filtering

**`min_priority`** - Set minimum priority level (HIGH, MEDIUM, or LOW):
```yaml
min_priority: "HIGH"  # Only track HIGH priority entities
```

Options:
- `"HIGH"` - Only energy, power, temperature, CO2, and other critical sensors
- `"MEDIUM"` - HIGH + illuminance, distance, speed, etc.
- `"LOW"` - All trackable entities (default)

#### Pattern-Based Filtering (Advanced)

**`include_patterns`** - Regular expressions for entity IDs to include:
```yaml
include_patterns:
  - "sensor\\..*_temperature"     # All temperature sensors
  - "sensor\\.(kitchen|bedroom)_.*"  # Sensors in specific rooms
  - "sensor\\..*_(power|energy)"  # All power and energy sensors
```

**`exclude_patterns`** - Regular expressions for entity IDs to exclude:
```yaml
exclude_patterns:
  - "sensor\\.test_.*"            # Exclude all test sensors
  - "sensor\\..*_unavailable"     # Exclude unavailable sensors
```

## Metadata Extraction

The system automatically extracts comprehensive metadata for each entity:

### Basic Metadata
- **Entity ID**: `sensor.living_room_temperature`
- **Friendly Name**: "Living Room Temperature"
- **Domain**: `sensor`
- **Device Class**: `temperature`
- **Unit**: `°C`
- **State Class**: `measurement`

### Device Information
- **Device Name**: "Living Room Climate Sensor"
- **Manufacturer**: "Xiaomi"
- **Model**: "WSDCGQ11LM"

### Location
- **Area Name**: "Living Room"
- **Area ID**: `living_room`

### Classification
- **Category**: `environmental`
- **Priority**: `HIGH`

### Data Characteristics
- **Has Numeric State**: `true`
- **Numeric Attributes**: `["temperature", "humidity", "battery"]`

## Clarify Signal Labels

All extracted metadata is converted to Clarify labels for easy filtering and organization:

```python
{
  "source": ["Home Assistant"],
  "domain": ["sensor"],
  "entity_id": ["sensor.living_room_temperature"],
  "device_class": ["temperature"],
  "unit": ["°C"],
  "state_class": ["measurement"],
  "area": ["Living Room"],
  "device": ["Living Room Climate Sensor"],
  "manufacturer": ["Xiaomi"],
  "model": ["WSDCGQ11LM"],
  "category": ["environmental"],
  "priority": ["high"],
  "integration": ["my_integration_id"]
}
```

## Use Cases and Examples

### Example 1: Energy Monitoring Only

Track only energy-related sensors:

```yaml
clarify_data_bridge:
  include_device_classes:
    - energy
    - power
    - voltage
    - current
  min_priority: "HIGH"
```

### Example 2: Climate Monitoring

Track temperature, humidity, and CO2 in specific rooms:

```yaml
clarify_data_bridge:
  include_device_classes:
    - temperature
    - humidity
    - carbon_dioxide
    - pressure
  include_patterns:
    - "sensor\\.(living_room|bedroom|kitchen)_.*"
  min_priority: "HIGH"
```

### Example 3: Comprehensive Home Monitoring

Track all high and medium priority sensors:

```yaml
clarify_data_bridge:
  include_domains:
    - sensor
    - binary_sensor
    - climate
  min_priority: "MEDIUM"
  exclude_patterns:
    - "sensor\\.sun_.*"        # Exclude sun sensors
    - "sensor\\.moon_.*"       # Exclude moon sensors
```

### Example 4: Specific Entities Only

Track only specific critical sensors:

```yaml
clarify_data_bridge:
  include_entity_ids:
    - sensor.total_energy_consumption
    - sensor.solar_production
    - sensor.grid_import
    - sensor.grid_export
    - sensor.battery_level
```

### Example 5: Advanced Pattern Matching

Track sensors by naming convention:

```yaml
clarify_data_bridge:
  include_patterns:
    - "sensor\\..*_(temperature|humidity|pressure)"
    - "sensor\\..*_energy_.*"
    - "sensor\\..*_power_.*"
  exclude_patterns:
    - "sensor\\..*_forecast_.*"
    - "sensor\\..*_yesterday_.*"
  min_priority: "MEDIUM"
```

## Binary Sensor Handling

Binary sensors are automatically converted to numeric values for time-series compatibility:

- **State `on`** → `1.0`
- **State `off`** → `0.0`

Example:
```
binary_sensor.motion_living_room
  State: on → Clarify receives: 1.0
  State: off → Clarify receives: 0.0
```

This allows you to:
- Track motion frequency over time
- Analyze door/window open duration
- Monitor occupancy patterns
- Detect anomalies in binary state changes

## Multi-Attribute Entities

Entities with multiple numeric attributes create separate signals in Clarify:

Example: Climate entity with temperature and humidity
```
climate.living_room_thermostat
  ├─ climate.living_room_thermostat (main state)
  ├─ climate.living_room_thermostat_temperature
  ├─ climate.living_room_thermostat_humidity
  └─ climate.living_room_thermostat_target_temperature
```

Each attribute gets its own signal with proper metadata and labels.

## Performance Considerations

### Entity Discovery
- Discovery runs once at startup
- Cached metadata for fast access
- Minimal overhead on state changes

### Filtering Priority
1. **Domain filtering** (fastest)
2. **Device class filtering**
3. **Entity ID filtering**
4. **Pattern matching** (regex)
5. **Priority filtering**

### Recommendations
- Use domain filtering when possible (most efficient)
- Device class filtering is highly efficient
- Pattern matching is powerful but slightly slower
- Start with `min_priority: "HIGH"` and expand as needed

## Monitoring Entity Discovery

Check Home Assistant logs to see discovered entities:

```
INFO (MainThread) [custom_components.clarify_data_bridge.entity_listener] Advanced discovery found 45 entities (priority >= HIGH)
INFO (MainThread) [custom_components.clarify_data_bridge.entity_listener] Entity discovery summary:
INFO (MainThread) [custom_components.clarify_data_bridge.entity_listener]   By priority: {'HIGH': 30, 'MEDIUM': 15}
INFO (MainThread) [custom_components.clarify_data_bridge.entity_listener]   By category: {'environmental': 20, 'power_device': 10, 'numeric_sensor': 15}
INFO (MainThread) [custom_components.clarify_data_bridge.entity_listener]   High priority entities (30): ['sensor.living_room_temperature', ...]
```

## Troubleshooting

### No Entities Discovered

Check:
1. Domain filtering is not too restrictive
2. Priority level is not too high
3. Device class filters are not excluding everything
4. Patterns are correct (test regex separately)

### Too Many Entities

Solutions:
1. Increase `min_priority` to `"MEDIUM"` or `"HIGH"`
2. Add `exclude_patterns` for unwanted entities
3. Use `include_device_classes` instead of domains
4. Add specific entities to `exclude_entities`

### Missing Expected Entity

Causes:
1. Entity has no numeric state or attributes
2. Entity is in excluded domain
3. Entity matches exclude pattern
4. Entity is below min_priority threshold
5. Entity has unsupported device class

Check entity in Home Assistant Developer Tools → States to verify it has numeric data.

## API Reference

### DataPriority Enum

```python
from custom_components.clarify_data_bridge.entity_selector import DataPriority

DataPriority.HIGH     # Critical time-series data
DataPriority.MEDIUM   # Useful metrics
DataPriority.LOW      # Less critical data
DataPriority.EXCLUDED # Not suitable for collection
```

### EntityCategory Enum

```python
from custom_components.clarify_data_bridge.entity_selector import EntityCategory

EntityCategory.NUMERIC_SENSOR      # Pure numeric sensors
EntityCategory.BINARY_SENSOR       # Binary on/off sensors
EntityCategory.MULTI_VALUE_SENSOR  # Multiple numeric attributes
EntityCategory.CONTROL_DEVICE      # Switches, lights with state
EntityCategory.CLIMATE_DEVICE      # Climate control systems
EntityCategory.POWER_DEVICE        # Power monitoring
EntityCategory.ENVIRONMENTAL       # Weather, air quality
EntityCategory.OTHER               # Other trackable entities
```

### EntityMetadata Class

Comprehensive metadata for each discovered entity:

```python
@dataclass
class EntityMetadata:
    # Core identity
    entity_id: str
    domain: str
    object_id: str

    # Display
    friendly_name: str
    description: str | None

    # Classification
    device_class: str | None
    category: EntityCategory
    priority: DataPriority

    # Measurement
    unit_of_measurement: str | None
    state_class: str | None

    # Device & location
    device_id: str | None
    device_name: str | None
    device_manufacturer: str | None
    device_model: str | None
    area_id: str | None
    area_name: str | None

    # Data characteristics
    has_numeric_state: bool
    numeric_attributes: list[str] | None
```

## Best Practices

### 1. Start Conservative
Begin with high-priority entities only:
```yaml
min_priority: "HIGH"
```

### 2. Gradually Expand
Add more entities as needed:
```yaml
min_priority: "MEDIUM"
include_device_classes:
  - temperature
  - humidity
  - power
  - energy
```

### 3. Use Device Classes
Device class filtering is efficient and semantic:
```yaml
include_device_classes:
  - temperature
  - humidity
  - power
```

### 4. Exclude Noisy Sensors
Remove sensors that change too frequently:
```yaml
exclude_entities:
  - sensor.sun_elevation
  - sensor.time_date
```

### 5. Pattern Match for Consistency
Use patterns for consistent naming schemes:
```yaml
include_patterns:
  - "sensor\\..*_(temperature|power|energy)"
```

### 6. Monitor Your Data
Check Clarify regularly to ensure:
- Data quality is good
- No unnecessary entities are tracked
- Signal names and labels are correct

### 7. Use Areas
Organize entities by area in Home Assistant for automatic location labeling in Clarify.

## Advanced Topics

### Custom Priority Rules

While priorities are automatic, you can influence them:
1. Use `include_device_classes` for specific high-value data
2. Use patterns to select specific entity types
3. Combine filters for precise control

### Dynamic Entity Selection

Entity discovery is dynamic - new entities are discovered at startup. To add new entities:
1. Add the entity to Home Assistant
2. Restart the integration (or reload)
3. New entity will be discovered automatically

### Integration with Clarify

All discovered entities:
1. Create signals in Clarify with rich metadata
2. Include comprehensive labels for filtering
3. Maintain proper units and descriptions
4. Support multi-attribute extraction

### Programmatic Access

Access discovered entities programmatically:

```python
# In a Home Assistant automation or script
listener = hass.data[DOMAIN][entry_id]["listener"]
entities = listener.discovered_entities

for entity_id, metadata in entities.items():
    print(f"{entity_id}: {metadata.category.value}, Priority: {metadata.priority.name}")
```

## Support and Feedback

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/NickKibish/Clarify-Data-Bridge/issues
- Documentation: Check the main README.md

## Version History

### Version 1.1.0
- Added comprehensive entity selection and classification system
- Implemented device class-based prioritization
- Added metadata extraction (device, area, manufacturer)
- Implemented pattern-based filtering
- Added priority-based filtering
- Enhanced binary sensor support (0/1 conversion)
- Improved multi-attribute handling

### Version 1.0.0
- Initial release with basic domain filtering
