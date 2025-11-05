# Clarify Data Bridge for Home Assistant

A powerful Home Assistant integration that intelligently collects and streams sensor data from your smart home to Clarify.io for advanced time-series visualization, analytics, and collaboration.

## What it does

This integration provides **intelligent, automated data streaming** from Home Assistant to Clarify.io:

- **Automatic Entity Discovery**: Finds all numeric sensors and devices in your home
- **Smart Classification**: Prioritizes entities by data value (energy, temperature, etc.)
- **Intelligent Filtering**: Advanced filtering by domain, device class, priority, and patterns
- **Auto-Publishing**: Automatically publishes signals as Clarify items using flexible strategies
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

## Configuration

### Intuitive UI Setup

The integration features a **user-friendly multi-step configuration flow** - no YAML required!

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Clarify Data Bridge"**
4. Follow the guided setup:

#### Step 1: Credentials
Enter your Clarify OAuth 2.0 credentials

#### Step 2: Choose Selection Method
Pick how you want to select entities:
- 🚀 **Quick Setup** (Recommended) - Select by priority level
- 📊 **By Priority** - High/Medium/Low with domain filtering
- 📁 **By Domain** - Sensors, climate, binary sensors, etc.
- 🏷️ **By Device Class** - Temperature, power, energy, etc.
- ✅ **Manual Selection** - Pick specific entities
- ⚙️ **Advanced Filters** - Regex patterns and rules

#### Step 3: Entity Selection
Configure your chosen method with real-time entity counts

#### Step 4: Preview & Confirm
Review your selection summary:
- Total entities
- Priority breakdown
- Domain distribution
- Sample entities

**Result**: Automatic entity discovery with rich metadata!

### After Setup

Access **integration options** anytime:
- **Batch Settings** - Adjust transmission intervals
- **Entity Filters** - Change priority/domains/device classes
- **Advanced Filters** - Add regex patterns and exclusions

**See [CONFIG_UI.md](./CONFIG_UI.md) for detailed UI guide with examples.**

### YAML Configuration (Optional)

Advanced users can still use YAML:

```yaml
# Example: Energy monitoring focus
clarify_data_bridge:
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  integration_id: "your-integration-id"

  # Filter by priority (HIGH, MEDIUM, LOW)
  min_priority: "HIGH"

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

**See [ENTITY_SELECTION.md](./ENTITY_SELECTION.md) for all filtering options.**

## Getting Clarify Credentials

1. Sign up for an account at [clarify.io](https://clarify.io)
2. Create a new integration in your Clarify dashboard
3. Generate OAuth 2.0 credentials (Client ID and Client Secret)
4. Copy the credentials and Integration ID

## Key Features

### 🖥️ Intuitive Configuration UI
- **Multi-step guided setup** - No technical knowledge required
- **6 selection methods** - From quick setup to advanced patterns
- **Real-time preview** - See exactly what will be tracked
- **Entity counts** - Know how many entities match your filters
- **Smart defaults** - Pre-selected high-value device classes
- **Options menu** - Adjust settings without recreating integration

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

### ⚡ Intelligent Data Collection & Validation
- **Event-driven monitoring**: Zero-poll state change capture
- **Data validation**: Robust validation with range checks and staleness detection
- **Boolean conversion**: Automatic on/off → 1/0 for binary sensors
- **Unit conversion**: Automatic temperature, power, energy, pressure conversions
- **Type safety**: NaN/Inf filtering and numeric range validation
- **Edge case handling**: Unavailable/unknown state filtering

### 🎯 Smart Buffering System
- **5 buffering strategies**: Time, size, priority, hybrid (recommended), adaptive
- **Priority-based flushing**: Immediate flush for critical sensors (energy, temp, CO2)
- **Adaptive rate adjustment**: Automatically adjusts to data volume
- **Configurable intervals**: 60s to 600s batch intervals
- **Size-based triggers**: Flush when buffer reaches limit (default: 100 points)
- **Comprehensive metrics**: Track flush triggers, buffer sizes, data rates

### 🚀 Intelligent Auto-Publishing
- **8 publishing strategies**: Manual, all, priority-based, category, device class, domain, and custom
- **Rule-based publishing**: Define custom rules for automatic item publishing
- **Visibility control**: Publish items as visible or hidden
- **Enhanced metadata**: Automatic device info, areas, and labels
- **Auto-publish tracking**: Know which items were automatically published
- **Flexible configuration**: Per-rule visibility and labeling

### 🔧 Services for Manual Control
- `publish_entity`: Publish single entity as Clarify item
- `publish_entities`: Publish multiple entities
- `publish_all_tracked`: Publish all tracked entities
- `publish_domain`: Publish all entities in a domain
- `publish_by_priority`: Publish entities by priority level
- `publish_by_device_class`: Publish entities by device class
- `update_item_visibility`: Toggle item visibility in Clarify

### ⚙️ Flexible Configuration & Templates
- **8 configuration templates**: Energy, environmental, HVAC, binary sensor, motion analytics, lighting, comprehensive, real-time
- **Per-entity customization**: Custom transmission intervals, aggregation methods, labels
- **Aggregation support**: None, average, min, max, sum, first, last
- **Priority override**: Per-entity priority configuration
- **YAML validation**: Voluptuous schema for configuration validation

### 🎛️ Performance Tuning
- **4 performance profiles**: Minimal, balanced, high performance, real-time
- **Resource monitoring**: Memory and CPU usage tracking
- **Dynamic optimization**: Automatic suggestions based on metrics
- **Configurable limits**: Buffer sizes, concurrent requests, memory limits
- **Profile comparison**: Easy switching between resource/latency trade-offs

### 🏥 Health Monitoring & Diagnostics
- **Health status tracking**: Excellent, good, fair, poor, critical ratings
- **API metrics**: Response times, success rates, error classification
- **Buffer monitoring**: Utilization, overflows, size tracking
- **Error analysis**: Frequency tracking and classification by type
- **Uptime tracking**: Comprehensive uptime and reliability metrics
- **Automated recommendations**: Context-aware optimization suggestions

### 📈 Data Retrieval
- Fetch data back from Clarify
- Statistics sensors (latest, average, min, max)
- Configurable lookback periods

## Requirements

- Home Assistant 2024.1.0 or newer
- Clarify.io account (free tier available)
- Python 3.11 or newer

## Documentation

- **[Configuration UI Guide](./CONFIG_UI.md)**: Complete guide to the configuration interface with screenshots and examples
- **[Entity Selection Guide](./ENTITY_SELECTION.md)**: Comprehensive guide to entity filtering, classification, and configuration
- **[Data Collection & Buffering](./DATA_COLLECTION.md)**: Guide to data validation, conversion, and intelligent buffering strategies
- **[Publishing Strategies](./PUBLISHING.md)**: Guide to automatic publishing of signals as Clarify.io items
- **Configuration Examples**: See CONFIG_UI.md for UI examples and ENTITY_SELECTION.md for YAML examples
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

### Configuration UI Flow

**Quick Setup Example**:
```
Step 1: Enter credentials → Validates immediately
Step 2: Choose "Quick Setup" → Select "High Priority"
Step 3: Preview shows:
  • 32 total entities
  • 32 high priority (energy, temp, CO2)
  • Domains: sensor(28), climate(4)
  • Sample: Living Room Temperature, Power Consumption, etc.
Step 4: Confirm → Done! ✅
```

**Device Class Example**:
```
Step 1: Enter credentials
Step 2: Choose "By Device Class"
Step 3: Select: temperature, humidity, power, energy
  → Shows: Temperature (12), Humidity (8), Power (5), Energy (5)
Step 4: Preview shows 30 entities
Step 5: Confirm → Done! ✅
```

**Advanced Pattern Example**:
```
Step 1: Enter credentials
Step 2: Choose "Advanced Filtering"
Step 3: Include pattern: sensor\.(kitchen|bedroom)_.*
         Exclude pattern: sensor\..*_forecast.*
Step 4: Preview shows 18 entities from those rooms
Step 5: Confirm → Done! ✅
```

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
