# Clarify Data Bridge for Home Assistant

A powerful Home Assistant integration that intelligently collects and streams sensor data from your smart home to Clarify.io for advanced time-series visualization, analytics, and collaboration.

## What it does

This integration provides **intelligent, automated data streaming** from Home Assistant to Clarify.io:

- **Automatic Entity Discovery**: Finds all numeric sensors and devices in your home
- **Smart Classification**: Prioritizes entities by data value (energy, temperature, etc.)
- **Intelligent Filtering**: Advanced filtering by domain, device class, priority, and patterns
- **Rich Metadata**: Extracts device info, locations (areas), and comprehensive labels
- **Efficient Batching**: Optimized data transmission with configurable batch sizes
- **Multi-Attribute Support**: Tracks multiple values from single entities (e.g., temp + humidity)
- **Binary Sensor Conversion**: Automatically converts on/off sensors to 0/1 for time-series

Unlike basic Home Assistant dashboards, Clarify.io provides industrial-grade time-series analytics, mobile access, and team collaboration features - perfect for analyzing your home's energy usage, climate patterns, and IoT device performance over time.

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "Clarify Data Bridge" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/clarify_data_bridge` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Quick Start Configuration

### Basic Setup

1. Go to Settings -> Devices & Services
2. Click "+ Add Integration"
3. Search for "Clarify Data Bridge"
4. Enter your Clarify OAuth 2.0 credentials:
   - **Client ID**: Your OAuth client ID from Clarify
   - **Client Secret**: Your OAuth client secret
   - **Integration ID**: Your Clarify integration ID

### Advanced Configuration (Optional)

Configure entity selection and filtering through the integration options or `configuration.yaml`:

```yaml
# Example: Energy monitoring focus
clarify_data_bridge:
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  integration_id: "your-integration-id"

  # Filter by priority (HIGH, MEDIUM, LOW)
  min_priority: "HIGH"  # Only energy, temperature, CO2, etc.

  # Filter by device class
  include_device_classes:
    - energy
    - power
    - temperature
    - humidity

  # Exclude specific entities
  exclude_entities:
    - sensor.sun_elevation
    - sensor.time_date
```

**See [ENTITY_SELECTION.md](./ENTITY_SELECTION.md) for comprehensive filtering options and examples.**

## Getting Clarify Credentials

1. Sign up for an account at [clarify.io](https://clarify.io)
2. Create a new integration in your Clarify dashboard
3. Generate OAuth 2.0 credentials (Client ID and Client Secret)
4. Copy the credentials and Integration ID

## Key Features

### 🎯 Intelligent Entity Discovery
- **Automatic detection** of all Home Assistant entities with numeric data
- **Priority-based classification**: HIGH (energy, temp, CO2), MEDIUM (light, speed), LOW (binary sensors)
- **Smart categorization**: Environmental, power, climate, binary sensors, control devices
- **Device class analysis**: Identifies valuable time-series data automatically

### 🔍 Powerful Filtering
- **Domain filtering**: Select specific domains (sensor, climate, etc.)
- **Device class filtering**: Target specific types (temperature, power, energy)
- **Priority filtering**: Focus on HIGH/MEDIUM/LOW priority entities
- **Pattern matching**: Use regex to include/exclude entities by name
- **Entity lists**: Explicitly include or exclude specific entities

### 📊 Rich Metadata Extraction
- **Device information**: Manufacturer, model, device name
- **Location data**: Automatically includes area/room assignments
- **Comprehensive labels**: All metadata as Clarify labels for easy filtering
- **Multi-attribute tracking**: Separate signals for entity attributes (temp, humidity, etc.)
- **Binary sensor conversion**: On/off → 1/0 for time-series compatibility

### ⚡ Efficient Data Handling
- **Batch processing**: Configurable batch intervals (60-3600s)
- **Automatic retry**: Failed data batches are retried
- **Overflow protection**: Automatic send when buffer is full
- **OAuth 2.0 authentication**: Secure credentials management
- **Connection monitoring**: Automatic reconnection on failures

### 🔧 Services for Manual Control
- `publish_entity`: Publish single entity as Clarify item
- `publish_entities`: Publish multiple entities
- `publish_all_tracked`: Publish all tracked entities
- `publish_domain`: Publish all entities in a domain
- `update_item_visibility`: Toggle item visibility in Clarify

### 📈 Data Retrieval
- Fetch data back from Clarify
- Statistics sensors (latest, average, min, max)
- Configurable lookback periods

## Requirements

- Home Assistant 2024.1.0 or newer
- Clarify.io account (free tier available)
- Python 3.11 or newer

## Documentation

- **[Entity Selection Guide](./ENTITY_SELECTION.md)**: Comprehensive guide to entity filtering, classification, and configuration
- **Configuration Examples**: See ENTITY_SELECTION.md for detailed use cases
- **API Reference**: Entity metadata structure and priority levels

## Use Cases

### 🏡 Home Energy Monitoring
Track energy consumption, solar production, and power usage across your home:
```yaml
include_device_classes: [energy, power, voltage, current]
min_priority: "HIGH"
```

### 🌡️ Climate Monitoring
Monitor temperature, humidity, and air quality:
```yaml
include_device_classes: [temperature, humidity, carbon_dioxide, pm25]
min_priority: "HIGH"
```

### 🏢 Comprehensive Home Analytics
Track all valuable sensor data:
```yaml
min_priority: "MEDIUM"
exclude_patterns: ["sensor\\.sun_.*", "sensor\\.moon_.*"]
```

## Examples

### Discovered Entities Summary
When the integration starts, it logs discovered entities:
```
INFO: Advanced discovery found 45 entities (priority >= HIGH)
INFO: Entity discovery summary:
  By priority: {'HIGH': 30, 'MEDIUM': 15}
  By category: {'environmental': 20, 'power_device': 10, 'numeric_sensor': 15}
  High priority entities: ['sensor.living_room_temperature', ...]
```

### Clarify Signal Labels
Each entity in Clarify includes rich metadata labels:
```json
{
  "source": ["Home Assistant"],
  "domain": ["sensor"],
  "device_class": ["temperature"],
  "unit": ["°C"],
  "area": ["Living Room"],
  "device": ["Climate Sensor"],
  "manufacturer": ["Xiaomi"],
  "category": ["environmental"],
  "priority": ["high"]
}
```

## Troubleshooting

### No entities discovered
- Check `min_priority` is not too restrictive (try "LOW")
- Verify entities have numeric states or attributes
- Check domain and device class filters

### Too many entities
- Increase `min_priority` to "MEDIUM" or "HIGH"
- Use `include_device_classes` for specific types
- Add `exclude_patterns` for unwanted entities

### Missing expected entity
- Verify entity has numeric data in Developer Tools → States
- Check entity is not in `exclude_entities` or matching `exclude_patterns`
- Verify entity domain is in `include_domains`

See [ENTITY_SELECTION.md](./ENTITY_SELECTION.md) for detailed troubleshooting.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/NickKibish/Clarify-Data-Bridge/issues).

## License

MIT License - See LICENSE file for details
