# Clarify.io Publishing Strategies

Guide to automatic publishing of Home Assistant entities as Clarify.io items.

## Overview

The Clarify Data Bridge uses a two-stage data flow:

1. **Signals** (Private): All tracked entities create signals - these are your private data streams
2. **Items** (Published): Signals you publish as items become visible to your entire organization

Publishing strategies control which signals are automatically published as items.

## Publishing Strategies

### Manual (Default)

**Strategy**: `manual`

No automatic publishing. You control exactly which entities become items using services.

**Use when**:
- You want complete control over what's visible
- Testing new entity tracking
- Sensitive data that requires approval

**Configuration**:
```yaml
auto_publish: false
publishing_strategy: manual
```

---

### Publish All

**Strategy**: `all`

Automatically publishes all tracked entities as items.

**Use when**:
- Small deployments with few entities
- All data is safe to share with organization
- Quick setup for testing

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: all
default_visible: true
```

**Warning**: This publishes everything, including binary sensors and state changes.

---

### High Priority Only

**Strategy**: `high_priority`

Publishes only high-priority entities (energy, temperature, CO2, power, air quality).

**Use when**:
- You want critical metrics visible
- Focus on most valuable time-series data
- Typical production deployment

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: high_priority
default_visible: true
```

**Typical Count**: 20-40 published items

---

### Medium Priority and Above

**Strategy**: `medium_plus`

Publishes medium and high priority entities.

**Use when**:
- You want more comprehensive coverage
- Include light levels, motion detection, etc.
- Balanced visibility and data volume

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: medium_plus
default_visible: true
```

**Typical Count**: 40-80 published items

---

### By Category

**Strategy**: `by_category`

Publishes based on entity categories.

**Available Categories**:
- `numeric_sensor`: Traditional sensors with numeric values
- `power_device`: Energy and power monitoring
- `environmental`: Temperature, humidity, air quality
- `binary_sensor`: Motion, door, window sensors (as 0/1)
- `light_device`: Smart lights (brightness tracking)
- `climate_device`: HVAC and thermostats
- `media_device`: Media players (volume, position)
- `other_numeric`: Other devices with numeric attributes

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: by_category
publish_categories:
  - environmental
  - power_device
  - climate_device
```

**Use when**: You want specific types of entities published regardless of priority

---

### By Device Class

**Strategy**: `by_device_class`

Publishes based on specific device classes.

**Common Device Classes**:
- Energy: `energy`, `power`, `voltage`, `current`
- Environmental: `temperature`, `humidity`, `pressure`, `carbon_dioxide`
- Air Quality: `pm25`, `pm10`, `aqi`, `volatile_organic_compounds`
- Other: `illuminance`, `battery`, `signal_strength`

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: by_device_class
publish_device_classes:
  - temperature
  - humidity
  - power
  - energy
```

**Use when**: You want precise control over specific sensor types

---

### By Domain

**Strategy**: `by_domain`

Publishes all entities from specific domains.

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: by_domain
include_domains:
  - sensor
  - climate
```

**Use when**: You want all entities of certain types published

---

### Custom Rules

**Strategy**: `custom`

Define your own publishing rules with complete control.

**Configuration**:
```yaml
auto_publish: true
publishing_strategy: custom
publishing_rules:
  - name: "Critical Power Monitoring"
    min_priority: high
    device_classes:
      - energy
      - power
    visible: true
    additional_labels:
      category: ["critical"]

  - name: "Environmental Sensors"
    categories:
      - environmental
    visible: true
    additional_labels:
      monitored: ["yes"]
```

**Use when**: Pre-defined strategies don't meet your needs

---

## Visibility Control

Items can be published with different visibility settings:

- **`visible: true`**: Item appears in Clarify.io organization data catalog
- **`visible: false`**: Item exists but is hidden from general catalog (still accessible via API)

**Configuration**:
```yaml
default_visible: true  # Default visibility for auto-published items
```

---

## Publishing Services

Even with manual publishing strategy, you can publish entities using services:

### Publish Single Entity

```yaml
service: clarify_data_bridge.publish_entity
data:
  entity_id: sensor.living_room_temperature
  visible: true
  labels:
    room: ["living_room"]
    critical: ["yes"]
```

### Publish Multiple Entities

```yaml
service: clarify_data_bridge.publish_entities
data:
  entity_ids:
    - sensor.living_room_temperature
    - sensor.kitchen_temperature
    - sensor.bedroom_temperature
  visible: true
```

### Publish All Tracked

```yaml
service: clarify_data_bridge.publish_all_tracked
data:
  visible: true
```

### Publish by Domain

```yaml
service: clarify_data_bridge.publish_domain
data:
  domain: climate
  visible: true
```

### Publish by Priority

```yaml
service: clarify_data_bridge.publish_by_priority
data:
  priority: high
  visible: true
```

### Publish by Device Class

```yaml
service: clarify_data_bridge.publish_by_device_class
data:
  device_classes:
    - temperature
    - humidity
  visible: true
```

### Update Item Visibility

```yaml
service: clarify_data_bridge.update_item_visibility
data:
  entity_id: sensor.living_room_temperature
  visible: false
```

---

## Metadata Mapping

When entities are published as items, rich metadata is automatically included:

### Signal Labels (Always Included)

```json
{
  "source": ["Home Assistant"],
  "integration": ["your-integration-id"],
  "domain": ["sensor"],
  "entity_id": ["sensor.living_room_temperature"],
  "priority": ["high"],
  "category": ["environmental"]
}
```

### Entity Metadata (When Available)

```json
{
  "friendly_name": ["Living Room Temperature"],
  "device_class": ["temperature"],
  "unit_of_measurement": ["°C"],
  "state_class": ["measurement"],
  "area": ["Living Room"],
  "device_name": ["Living Room Sensor"],
  "device_manufacturer": ["Xiaomi"],
  "device_model": ["WSDCGQ11LM"]
}
```

### Custom Labels (Optional)

Add additional labels via configuration or service calls:

```yaml
additional_labels:
  monitoring_level: ["critical"]
  team: ["facilities"]
  cost_center: ["building-operations"]
```

---

## Best Practices

### Start Conservative

1. Begin with `manual` or `high_priority` strategy
2. Monitor what gets published
3. Expand gradually as needed

### Monitor Published Count

Check integration statistics:
```yaml
- platform: template
  sensors:
    clarify_published_count:
      value_template: "{{ state_attr('sensor.clarify_status', 'published_items') }}"
```

### Use Categories for Organization

Group related items using additional labels:

```yaml
publishing_rules:
  - name: "HVAC Monitoring"
    categories:
      - climate_device
      - environmental
    additional_labels:
      system: ["hvac"]
      building: ["main"]
```

### Review Quarterly

1. Check published items in Clarify.io
2. Remove unnecessary items
3. Add missing critical data
4. Update strategies as needs change

---

## Configuration Examples

### Example 1: Energy Monitoring Deployment

**Goal**: Publish only energy and power metrics

```yaml
auto_publish: true
publishing_strategy: by_device_class
default_visible: true
publish_device_classes:
  - energy
  - power
  - voltage
  - current
  - power_factor
```

**Result**: 10-20 published items, all power-related

---

### Example 2: Building Management System

**Goal**: Comprehensive environmental and HVAC monitoring

```yaml
auto_publish: true
publishing_strategy: by_category
default_visible: true
publish_categories:
  - environmental
  - climate_device
  - power_device
```

**Result**: 50-100 published items covering temperature, humidity, HVAC, and power

---

### Example 3: Selective High-Value Data

**Goal**: Only critical, high-value metrics visible

```yaml
auto_publish: true
publishing_strategy: custom
default_visible: true
publishing_rules:
  - name: "Critical Energy"
    min_priority: high
    device_classes:
      - energy
      - power
    additional_labels:
      critical: ["yes"]

  - name: "Environmental Compliance"
    device_classes:
      - temperature
      - humidity
      - carbon_dioxide
      - pm25
    additional_labels:
      compliance: ["yes"]
```

**Result**: 20-40 carefully selected items with enhanced labeling

---

### Example 4: Phased Rollout

**Goal**: Manual control with targeted auto-publishing

```yaml
# Initial setup: Manual only
auto_publish: false
publishing_strategy: manual

# After testing: Auto-publish high priority
auto_publish: true
publishing_strategy: high_priority
default_visible: true

# Production: Custom rules
auto_publish: true
publishing_strategy: custom
publishing_rules:
  - name: "Production Metrics"
    min_priority: medium
    visible: true
  - name: "Test Metrics"
    categories:
      - other_numeric
    visible: false  # Hidden items for testing
```

---

## Troubleshooting

### Problem: Too Many Items Published

**Solutions**:
1. Switch to `high_priority` or `manual` strategy
2. Use `by_device_class` for precise control
3. Add exclude patterns in entity filtering
4. Set `default_visible: false` and manually show important items

### Problem: Missing Expected Items

**Check**:
1. Is entity tracked? (Check entity filtering)
2. Does entity match publishing rules?
3. Is `auto_publish` enabled?
4. Check logs for publishing errors

**Debug**:
```yaml
# Enable debug logging
logger:
  default: info
  logs:
    custom_components.clarify_data_bridge.item_manager: debug
    custom_components.clarify_data_bridge.publishing_strategy: debug
```

### Problem: Items Have Wrong Visibility

**Solutions**:
1. Check `default_visible` setting
2. Use `update_item_visibility` service to fix
3. Republish with correct visibility

### Problem: Missing Metadata Labels

**Check**:
1. Device registry integration (requires device_id)
2. Area assignments in Home Assistant
3. Entity registry attributes

**Enhance**:
- Assign entities to areas
- Register devices properly
- Add entity attributes

---

## Advanced Topics

### Dynamic Publishing

Publishing rules are evaluated at startup and when configuration changes. To dynamically adjust:

1. Update configuration
2. Reload integration (not Home Assistant)
3. New entities matching rules are auto-published

### Publishing State

Track published items programmatically:

```python
from homeassistant.helpers import device_registry as dr

# Check if entity is published
item_manager.is_published("sensor.living_room_temperature")

# Check if auto-published
item_manager.is_auto_published("sensor.living_room_temperature")

# Get item ID
item_id = item_manager.get_item_id("sensor.living_room_temperature")

# Statistics
published_count = item_manager.published_count
auto_published_count = item_manager.auto_published_count
```

### Custom Publishing Logic

For complex scenarios, create custom rules:

```yaml
publishing_rules:
  - name: "Critical Infrastructure"
    min_priority: high
    visible: true
    additional_labels:
      infrastructure: ["critical"]
      alerting: ["enabled"]

  - name: "Development Testing"
    categories:
      - other_numeric
    visible: false
    additional_labels:
      environment: ["development"]

  - name: "Compliance Required"
    device_classes:
      - temperature
      - humidity
      - carbon_dioxide
    visible: true
    additional_labels:
      compliance_standard: ["ISO-50001"]
      audit_required: ["yes"]
```

---

## Performance Considerations

### Publishing Impact

- **Initial publish**: One API call per entity (can take 5-10 seconds for 50 entities)
- **Updates**: No additional overhead (same data stream)
- **Visibility changes**: One API call per entity

### Large Deployments

For >200 entities:
1. Use specific strategies (not `all`)
2. Consider `visible: false` for testing
3. Batch manual publishing via services
4. Monitor Clarify.io API rate limits

### Cost Optimization

Clarify.io costs scale with item count. Optimize:
1. Only publish actionable data
2. Use `high_priority` strategy
3. Regularly review and unpublish unused items
4. Consider aggregation for similar sensors

---

## Migration Guide

### From Manual to Auto-Publishing

1. Document currently published items
2. Configure strategy matching current selection
3. Enable `auto_publish: true`
4. Reload integration
5. Verify published count matches

### From Auto to Manual

1. Note current auto-published items
2. Set `auto_publish: false`
3. Reload integration
4. Items remain published (not automatic unpublish)
5. Manually publish/unpublish as needed

---

## Summary

- **Manual strategy**: Best for sensitive data and precise control
- **High priority**: Best for production deployments
- **Category/Device class**: Best for specific use cases
- **Custom rules**: Best for complex requirements
- **Start small**: Expand gradually
- **Monitor published count**: Keep costs and complexity manageable
- **Use labels**: Organize and categorize published items

For entity selection and filtering, see [ENTITY_SELECTION.md](ENTITY_SELECTION.md).

For configuration UI, see [CONFIG_UI.md](CONFIG_UI.md).
