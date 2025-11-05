# Advanced Features

Comprehensive guide to Phase 7 advanced features: Data Aggregation, Custom Services, and Automation Integration.

## Overview

Phase 7 provides advanced capabilities for optimizing data transmission, manual control, and automation integration:

1. **Data Aggregation** - Reduce data volume for high-frequency sensors
2. **Custom Services** - Manual control and configuration management
3. **Automation Integration** - Enable Home Assistant automations to interact with Clarify.io sync

---

## Phase 7.1: Data Aggregation Options

### Purpose

Data aggregation reduces the volume of data transmitted to Clarify.io by combining multiple data points using statistical methods. This is particularly valuable for:

- High-frequency sensors (updating every second or less)
- Reducing API calls and transmission costs
- Focusing on trends rather than individual measurements
- Managing data volume for large deployments

### Aggregation Methods

The integration supports 10 aggregation methods:

| Method | Description | Use Case |
|--------|-------------|----------|
| **none** | No aggregation, send all data points | Default, preserves all data |
| **average** | Arithmetic mean of values | Temperature, humidity, general metrics |
| **median** | Middle value (robust to outliers) | Noisy sensors, outlier-prone data |
| **min** | Minimum value in window | Low temperature, battery level |
| **max** | Maximum value in window | Peak power consumption, max temperature |
| **sum** | Sum of all values | Energy accumulation, counters |
| **first** | First value in window | State at window start |
| **last** | Last value in window | Most recent state |
| **count** | Number of data points | Activity counting, event frequency |
| **change_only** | Only send when value changes significantly | Binary sensors, stable values |

### Configuration

#### Per-Entity Configuration

Use the `set_entity_config` service to configure aggregation:

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.power_meter
  aggregation_method: average
  aggregation_window: 300  # 5 minutes
  transmission_interval: 300
```

#### Using Templates

Apply pre-configured templates that include aggregation settings:

```yaml
service: clarify_data_bridge.apply_template
data:
  template_name: energy_monitoring
  entity_ids:
    - sensor.power_meter
    - sensor.energy_total
```

### Change-Only Detection

The `change_only` aggregation method only transmits when values change significantly:

**Configuration Parameters:**
- `min_change_threshold` - Minimum relative change to trigger transmission (default: 0.01 = 1%)
- `min_change_absolute` - Minimum absolute change (optional)

**Example:**

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: binary_sensor.motion
  aggregation_method: change_only
  aggregation_window: 60  # Check every minute
```

**Behavior:**
- Initial value: Always sent
- Subsequent values: Only sent if changed by ≥ threshold
- Binary sensors (0/1): Any change triggers transmission
- Numeric sensors: Threshold-based change detection

### Aggregation Metrics

Monitor aggregation effectiveness:

```yaml
sensor.clarify_aggregation_stats:
  total_data_points: 10000
  aggregated_data_points: 2000
  reduction_ratio: 80.0  # 80% reduction
  average_window_size: 5.2
  aggregation_method_distribution:
    average: 50
    change_only: 30
    none: 20
```

### Examples

#### Example 1: High-Frequency Power Monitoring

**Problem**: Power meter updates every second (86,400 points/day)

**Solution**: Average over 5-minute windows

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.power_consumption
  aggregation_method: average
  aggregation_window: 300  # 5 minutes
  transmission_interval: 300
```

**Result**: 288 data points/day (99.7% reduction)

---

#### Example 2: Temperature with Peak Detection

**Problem**: Need average temperature but also track extremes

**Solution**: Configure multiple entities with different aggregations

```yaml
# Average temperature
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.temperature_avg
  aggregation_method: average
  aggregation_window: 600  # 10 minutes

# Maximum temperature (for alerts)
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.temperature_max
  aggregation_method: max
  aggregation_window: 600
```

---

#### Example 3: Binary Sensor Optimization

**Problem**: Motion sensor reports state every second (mostly unchanged)

**Solution**: Only transmit when state changes

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: binary_sensor.living_room_motion
  aggregation_method: change_only
  transmission_interval: 10  # Check every 10 seconds
```

**Result**: ~100x reduction in data volume

---

## Phase 7.2: Custom Service Integration

### Available Services

The integration provides 7 custom services for manual control and configuration:

#### 1. sync_historical

Export historical data from Home Assistant recorder to Clarify.io.

**Parameters:**
- `entity_ids` (required): List of entity IDs to sync
- `start_time` (required): Start time (ISO 8601 or relative like "-7 days")
- `end_time` (optional): End time (ISO 8601), defaults to now
- `batch_size` (optional): Data points per batch (default: 1000)
- `batch_delay` (optional): Delay between batches in seconds (default: 2.0)

**Examples:**

```yaml
# Sync last 7 days
service: clarify_data_bridge.sync_historical
data:
  entity_ids:
    - sensor.temperature
    - sensor.humidity
  start_time: "-7 days"
```

```yaml
# Sync specific date range
service: clarify_data_bridge.sync_historical
data:
  entity_ids:
    - sensor.energy_meter
  start_time: "2024-01-01T00:00:00Z"
  end_time: "2024-01-31T23:59:59Z"
  batch_size: 2000
  batch_delay: 1.0
```

```yaml
# Sync last 24 hours
service: clarify_data_bridge.sync_historical
data:
  entity_ids:
    - sensor.power_meter
  start_time: "-24 hours"
```

---

#### 2. flush_buffer

Immediately flush all buffered data to Clarify.io.

**Parameters:** None

**Example:**

```yaml
service: clarify_data_bridge.flush_buffer
```

**Use Cases:**
- Before system shutdown or restart
- After configuration changes
- Manual transmission trigger for testing
- Ensuring recent data is visible in Clarify.io

---

#### 3. apply_template

Apply a pre-defined configuration template to selected entities.

**Parameters:**
- `template_name` (required): Name of template
- `entity_ids` (required): List of entity IDs

**Available Templates:**
- `energy_monitoring` - Optimized for energy sensors (1 min interval, average)
- `environmental_monitoring` - Temperature, humidity, air quality (5 min, average)
- `hvac_monitoring` - HVAC systems (2 min, average)
- `binary_sensor` - Binary sensors (change-only)
- `motion_analytics` - Motion sensors (change-only, immediate)
- `lighting_control` - Lights (change-only)
- `comprehensive` - All sensor types (balanced)
- `real_time_critical` - Critical sensors (30s interval, no aggregation)

**Example:**

```yaml
service: clarify_data_bridge.apply_template
data:
  template_name: energy_monitoring
  entity_ids:
    - sensor.power_meter
    - sensor.energy_total
    - sensor.voltage
```

---

#### 4. set_entity_config

Configure individual entity settings for data collection and transmission.

**Parameters:**
- `entity_id` (required): Entity ID to configure
- `transmission_interval` (optional): Transmission interval in seconds
- `aggregation_method` (optional): Aggregation method (see Phase 7.1)
- `aggregation_window` (optional): Aggregation window in seconds
- `priority` (optional): Priority level (low/medium/high)
- `buffer_strategy` (optional): Buffer strategy (time/size/priority/hybrid/adaptive)

**Example:**

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.temperature
  transmission_interval: 300  # 5 minutes
  aggregation_method: average
  aggregation_window: 300
  priority: medium
  buffer_strategy: hybrid
```

---

#### 5. set_performance_profile

Change the performance profile for the entire integration.

**Parameters:**
- `profile_name` (required): Profile name

**Available Profiles:**
- `minimal` - Low resource usage (10 min interval, 50 MB limit)
- `balanced` - Balanced performance (5 min interval, 100 MB limit) [Default]
- `high_performance` - Fast transmission (1 min interval, 200 MB limit)
- `real_time` - Real-time critical (30s interval, 500 MB limit)

**Example:**

```yaml
service: clarify_data_bridge.set_performance_profile
data:
  profile_name: high_performance
```

**Effect:**
- Adjusts batch intervals
- Changes buffer sizes
- Modifies memory limits
- Affects concurrent requests

---

#### 6. get_health_report

Generate a comprehensive health diagnostic report.

**Parameters:**
- `include_history` (optional): Include recent transmission history (default: true)
- `include_errors` (optional): Include recent error details (default: true)

**Example:**

```yaml
service: clarify_data_bridge.get_health_report
data:
  include_history: true
  include_errors: true
```

**Report Contents:**
```json
{
  "health_status": "healthy",
  "uptime_hours": 48.5,
  "api_metrics": {
    "total_calls": 500,
    "successful_calls": 495,
    "failed_calls": 5,
    "success_rate": 99.0,
    "avg_response_time_ms": 250.5
  },
  "transmission_metrics": {
    "total_transmissions": 100,
    "successful": 98,
    "failed": 2,
    "total_data_points": 10000,
    "avg_data_points_per_transmission": 102.0
  },
  "buffer_metrics": {
    "current_size": 50,
    "high_priority": 5,
    "medium_priority": 20,
    "low_priority": 25
  },
  "recent_history": [...],
  "recent_errors": [...],
  "recommendations": [
    "System is healthy and operating normally"
  ]
}
```

---

#### 7. reset_statistics

Reset all integration statistics and counters.

**Parameters:**
- `confirm` (required): Confirmation (must be true)

**Example:**

```yaml
service: clarify_data_bridge.reset_statistics
data:
  confirm: true
```

**What Gets Reset:**
- Total data points sent
- Successful/failed send counts
- API call statistics
- Transmission history
- Error counters

---

## Phase 7.3: Integration with Home Assistant Automations

### Automation Events

The integration fires events that can trigger Home Assistant automations:

| Event | Description | Data |
|-------|-------------|------|
| `clarify_data_bridge_data_synced` | Historical sync completed | `entity_count`, `data_points`, `duration` |
| `clarify_data_bridge_buffer_flushed` | Buffer flushed manually or automatically | `data_points`, `trigger` |
| `clarify_data_bridge_transmission_success` | Successful transmission to Clarify.io | `data_points`, `series_count`, `duration_ms` |
| `clarify_data_bridge_transmission_failed` | Failed transmission | `error_message`, `retry_count` |
| `clarify_data_bridge_health_status_changed` | Health status changed | `old_status`, `new_status`, `reason` |

### Automation Examples

#### Example 1: Alert on Sync Failure

```yaml
automation:
  - alias: "Clarify Sync Failure Alert"
    trigger:
      - platform: event
        event_type: clarify_data_bridge_transmission_failed
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.retry_count >= 3 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Clarify Sync Failed"
          message: "Transmission failed after {{ trigger.event.data.retry_count }} attempts: {{ trigger.event.data.error_message }}"
```

---

#### Example 2: Flush Buffer Before Shutdown

```yaml
automation:
  - alias: "Flush Clarify Buffer on Shutdown"
    trigger:
      - platform: homeassistant
        event: shutdown
    action:
      - service: clarify_data_bridge.flush_buffer
```

---

#### Example 3: Daily Historical Sync

```yaml
automation:
  - alias: "Daily Clarify Historical Sync"
    trigger:
      - platform: time
        at: "02:00:00"
    action:
      - service: clarify_data_bridge.sync_historical
        data:
          entity_ids:
            - sensor.daily_energy
            - sensor.daily_production
          start_time: "-1 days"
```

---

#### Example 4: Performance Profile Based on Time

```yaml
automation:
  - alias: "Clarify High Performance During Day"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: clarify_data_bridge.set_performance_profile
        data:
          profile_name: high_performance

  - alias: "Clarify Minimal Performance at Night"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: clarify_data_bridge.set_performance_profile
        data:
          profile_name: minimal
```

---

#### Example 5: Health Monitoring

```yaml
automation:
  - alias: "Clarify Health Check"
    trigger:
      - platform: time_pattern
        hours: "/6"  # Every 6 hours
    action:
      - service: clarify_data_bridge.get_health_report
        data:
          include_history: true
          include_errors: true

  - alias: "Clarify Health Degraded Alert"
    trigger:
      - platform: event
        event_type: clarify_data_bridge_health_status_changed
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.new_status in ['degraded', 'unhealthy'] }}"
    action:
      - service: persistent_notification.create
        data:
          title: "Clarify Health Degraded"
          message: "Health status changed from {{ trigger.event.data.old_status }} to {{ trigger.event.data.new_status }}"
```

---

#### Example 6: Conditional Data Aggregation

```yaml
automation:
  - alias: "Reduce Aggregation During High Activity"
    trigger:
      - platform: numeric_state
        entity_id: sensor.home_activity_level
        above: 80
    action:
      - service: clarify_data_bridge.set_entity_config
        data:
          entity_id: sensor.motion_sensor
          aggregation_method: none  # No aggregation during high activity
          transmission_interval: 30

  - alias: "Increase Aggregation During Low Activity"
    trigger:
      - platform: numeric_state
        entity_id: sensor.home_activity_level
        below: 20
    action:
      - service: clarify_data_bridge.set_entity_config
        data:
          entity_id: sensor.motion_sensor
          aggregation_method: change_only  # Aggressive aggregation
          transmission_interval: 300
```

---

## Advanced Use Cases

### Use Case 1: Energy Analytics with Multiple Aggregations

**Goal**: Track both instantaneous and averaged power consumption

**Solution**:

```yaml
# Instantaneous power (no aggregation)
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.power_instantaneous
  aggregation_method: none
  transmission_interval: 10
  priority: high

# 5-minute average power
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.power_5min_avg
  aggregation_method: average
  aggregation_window: 300
  transmission_interval: 300
  priority: medium

# Daily peak power
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.power_daily_peak
  aggregation_method: max
  aggregation_window: 86400  # 1 day
  transmission_interval: 86400
  priority: low
```

---

### Use Case 2: Automated Recovery from Network Outages

**Goal**: Automatically sync missed data after network recovery

**Solution**:

```yaml
automation:
  - alias: "Clarify Auto-Recovery After Outage"
    trigger:
      - platform: event
        event_type: clarify_data_bridge_transmission_success
    condition:
      # Check if there were previous failures
      - condition: template
        value_template: "{{ states('sensor.clarify_consecutive_failures') | int > 5 }}"
    action:
      # Sync last 24 hours of data
      - service: clarify_data_bridge.sync_historical
        data:
          entity_ids:
            - sensor.critical_sensor_1
            - sensor.critical_sensor_2
          start_time: "-24 hours"
          batch_size: 5000
          batch_delay: 1.0
```

---

### Use Case 3: Dynamic Configuration Based on Data Rate

**Goal**: Automatically adjust aggregation based on sensor update frequency

**Solution**:

```yaml
automation:
  - alias: "Clarify Adaptive Aggregation"
    trigger:
      - platform: time_pattern
        minutes: "/15"  # Check every 15 minutes
    action:
      - service: python_script.adjust_clarify_aggregation
        data_template:
          entity_id: sensor.high_frequency_sensor
          update_rate: "{{ states('sensor.high_frequency_sensor_update_rate') | float }}"
          # If > 10 updates/sec, use average aggregation
          # If < 0.1 updates/sec, use no aggregation
```

---

## Best Practices

### 1. Start Conservative

Begin with templates and adjust based on needs:

```yaml
# Apply template first
service: clarify_data_bridge.apply_template
data:
  template_name: comprehensive
  entity_ids:
    - sensor.temperature
    - sensor.humidity

# Fine-tune specific entities later
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.temperature
  aggregation_window: 600  # Increase to 10 minutes
```

### 2. Monitor Aggregation Impact

Check reduction ratios regularly:

```yaml
sensor.clarify_aggregation_stats:
  reduction_ratio: 75.0  # Good (75% reduction)
```

**Guidelines:**
- **< 50% reduction**: Consider more aggressive aggregation
- **50-80% reduction**: Good balance
- **> 90% reduction**: May be losing important data, review carefully

### 3. Use Appropriate Aggregation Methods

| Sensor Type | Recommended Method | Reason |
|-------------|-------------------|---------|
| Temperature | average | Smooth out fluctuations |
| Energy meter | sum | Accumulate energy |
| Binary sensor | change_only | Only transmit state changes |
| Motion sensor | count | Track activity frequency |
| Peak detector | max | Capture maximum values |
| Battery level | last | Most recent value |

### 4. Balance Aggregation and Real-Time Needs

For critical sensors requiring real-time visibility:

```yaml
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.critical_alarm
  aggregation_method: none  # No aggregation
  transmission_interval: 10  # 10 seconds
  priority: high  # Immediate transmission
  buffer_strategy: priority
```

### 5. Test Before Production

Test aggregation impact with historical sync:

```yaml
# Sync with no aggregation
service: clarify_data_bridge.sync_historical
data:
  entity_ids:
    - sensor.test_sensor
  start_time: "-7 days"
  # Note data volume

# Apply aggregation
service: clarify_data_bridge.set_entity_config
data:
  entity_id: sensor.test_sensor
  aggregation_method: average
  aggregation_window: 300

# Sync again and compare
service: clarify_data_bridge.sync_historical
data:
  entity_ids:
    - sensor.test_sensor
  start_time: "-7 days"
```

---

## Troubleshooting

### Problem: Aggregation Not Reducing Data Volume

**Symptoms:**
- `reduction_ratio` is low (< 20%)
- Still sending many data points

**Solutions:**

1. Check aggregation window:
   ```yaml
   # Increase window size
   service: clarify_data_bridge.set_entity_config
   data:
     entity_id: sensor.temperature
     aggregation_window: 600  # Increase from 300 to 600
   ```

2. Verify sensor update frequency:
   - If sensor updates infrequently, aggregation has minimal effect
   - Use `change_only` method for slow-updating sensors

3. Check for multiple configurations:
   - Ensure entity isn't configured multiple times
   - Use `get_health_report` to review configuration

---

### Problem: Missing Important Data After Aggregation

**Symptoms:**
- Important peaks or events not visible in Clarify.io
- Data seems smoothed too much

**Solutions:**

1. Use different aggregation methods for different purposes:
   ```yaml
   # Average for trends
   service: clarify_data_bridge.set_entity_config
   data:
     entity_id: sensor.power_avg
     aggregation_method: average
     aggregation_window: 300

   # Max for peaks
   service: clarify_data_bridge.set_entity_config
   data:
     entity_id: sensor.power_max
     aggregation_method: max
     aggregation_window: 300
   ```

2. Reduce aggregation window:
   ```yaml
   # Reduce from 10 min to 2 min
   aggregation_window: 120
   ```

3. Disable aggregation for critical sensors:
   ```yaml
   aggregation_method: none
   transmission_interval: 30
   priority: high
   ```

---

### Problem: Historical Sync Taking Too Long

**Symptoms:**
- Historical sync running for hours
- System becoming slow

**Solutions:**

1. Reduce batch size:
   ```yaml
   service: clarify_data_bridge.sync_historical
   data:
     entity_ids: [...]
     start_time: "-30 days"
     batch_size: 500  # Reduce from 1000
     batch_delay: 3.0  # Increase delay
   ```

2. Sync in smaller time ranges:
   ```yaml
   # Sync one week at a time
   service: clarify_data_bridge.sync_historical
   data:
     entity_ids: [...]
     start_time: "2024-01-01T00:00:00Z"
     end_time: "2024-01-07T23:59:59Z"
   ```

3. Schedule during off-hours:
   ```yaml
   automation:
     - alias: "Clarify Historical Sync at Night"
       trigger:
         - platform: time
           at: "02:00:00"
       action:
         - service: clarify_data_bridge.sync_historical
           data: [...]
   ```

---

## Summary

Phase 7 Advanced Features provide:

✅ **Data Aggregation**:
- 10 aggregation methods for flexible data reduction
- Per-entity configuration
- Change-only detection for minimal data volume
- Aggregation metrics for monitoring effectiveness

✅ **Custom Services**:
- 7 services for complete manual control
- Historical data synchronization
- Dynamic configuration management
- Health monitoring and diagnostics

✅ **Automation Integration**:
- 5 automation event types
- Enable HA automations to control Clarify.io sync
- Respond to sync events and health changes
- Dynamic behavior based on system state

For more information:
- Configuration: [CONFIG.md](CONFIG.md)
- Data Collection: [DATA_COLLECTION.md](DATA_COLLECTION.md)
- Performance: [PERFORMANCE_TUNING.md](PERFORMANCE_TUNING.md)
