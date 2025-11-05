# Data Collection and Buffering

Comprehensive guide to data collection, validation, and intelligent buffering in the Clarify Data Bridge.

## Overview

The Clarify Data Bridge uses a sophisticated three-stage data pipeline:

1. **State Change Monitoring** - Efficient event-driven capture of Home Assistant state changes
2. **Data Validation** - Robust validation and conversion of diverse state formats
3. **Intelligent Buffering** - Smart accumulation and batching before sending to Clarify.io

This architecture balances real-time responsiveness with API efficiency while ensuring data quality.

---

## State Change Monitoring

### Event-Driven Architecture

The integration uses Home Assistant's native event system for efficient state monitoring:

```python
# Automatic subscription to selected entities
async_track_state_change_event(hass, entity_ids, callback)
```

**Benefits**:
- Zero polling overhead
- Immediate capture of state changes
- Scales efficiently with entity count
- No missed updates

### Edge Case Handling

The system handles common edge cases automatically:

**Unavailable States**
```
State: "unavailable" -> Ignored (not sent)
State: "unknown" -> Ignored (not sent)
State: None -> Ignored (not sent)
```

**Rapid Changes**
- Multiple state changes are buffered
- Debouncing not applied (all changes captured)
- Buffering strategy determines send timing

**Attribute Tracking**
- Tracks both state and numeric attributes
- Creates separate signals for each tracked value
- Example: Climate entity → temperature, humidity, target_temperature

---

## Data Validation and Conversion

### Validation Pipeline

Every state change goes through comprehensive validation:

```
State Change
    ↓
Invalid State Check (unavailable/unknown)
    ↓
Staleness Check (optional, default 5 minutes)
    ↓
Type Conversion (string → numeric, boolean → 0/1)
    ↓
Numeric Validation (NaN/Inf check)
    ↓
Range Validation (device class specific)
    ↓
Valid Data → Buffer
```

### Boolean to Numeric Conversion

Automatic conversion of boolean states:

| State | Numeric Value |
|-------|--------------|
| `on` | `1.0` |
| `off` | `0.0` |
| `home` | `1.0` |
| `not_home` | `0.0` |
| `open` | `1.0` |
| `closed` | `0.0` |
| `locked` | `1.0` |
| `unlocked` | `0.0` |
| `true` | `1.0` |
| `false` | `0.0` |
| `yes` | `1.0` |
| `no` | `0.0` |
| `detected` | `1.0` |
| `clear` | `0.0` |

**Use Cases**:
- Binary sensors (motion, door, window) → 0/1 time series
- Switch states → 0/1 for on/off tracking
- Presence detection → 0/1 for occupancy analytics

### Numeric Range Validation

Device class-specific range validation prevents invalid data:

| Device Class | Valid Range | Unit |
|--------------|-------------|------|
| `temperature` | -100 to 200 | °C |
| `humidity` | 0 to 100 | % |
| `battery` | 0 to 100 | % |
| `pressure` | 0 to 2000 | hPa |
| `pm25` | 0 to 1000 | µg/m³ |
| `pm10` | 0 to 1000 | µg/m³ |
| `carbon_dioxide` | 0 to 10000 | ppm |
| `aqi` | 0 to 500 | index |
| `illuminance` | 0 to 200000 | lux |
| `power` | -50000 to 50000 | W |
| `energy` | 0 to 1000000 | kWh |
| `voltage` | 0 to 500 | V |
| `current` | 0 to 100 | A |
| `power_factor` | -1 to 1 | ratio |
| `brightness` | 0 to 255 | - |
| `volume_level` | 0 to 1 | ratio |

**Invalid values are logged and dropped, not sent to Clarify.io.**

### Stale Data Detection

Optional staleness threshold (default: 5 minutes):

```yaml
stale_threshold_minutes: 5
```

**Behavior**:
- Data older than threshold is rejected
- Useful for recovering from Home Assistant restarts
- Prevents backfilling with old data
- Configurable or disable by setting to 0

### Unit Conversion

Automatic conversion to standard units:

**Temperature**
- °F → °C: `(F - 32) × 5/9`
- K → °C: `K - 273.15`
- °C → °C: No conversion

**Power**
- kW → W: `kW × 1000`
- MW → W: `MW × 1000000`

**Energy**
- Wh → kWh: `Wh / 1000`
- MWh → kWh: `MWh × 1000`

**Pressure**
- Pa → hPa: `Pa / 100`
- psi → hPa: `psi × 68.9476`
- inHg → hPa: `inHg × 33.8639`

---

## Intelligent Buffering System

### Buffer Strategies

The integration supports 5 buffering strategies:

#### 1. Time-Based (`time`)

Flushes buffer at regular intervals regardless of size.

**Configuration**:
```yaml
buffer_strategy: time
batch_interval: 300  # Flush every 5 minutes
```

**Best For**:
- Predictable data transmission
- Fixed API quota management
- Low to medium data rates

**Behavior**:
- Timer-driven flush every X seconds
- Size-independent (flushes even 1 data point)
- Guaranteed maximum latency

---

#### 2. Size-Based (`size`)

Flushes when buffer reaches maximum size.

**Configuration**:
```yaml
buffer_strategy: size
max_batch_size: 100  # Flush at 100 data points
```

**Best For**:
- High data rate environments
- Minimizing API calls
- Maximizing batch efficiency

**Behavior**:
- Triggers flush when buffer size ≥ limit
- Time-independent (may delay if low traffic)
- Optimizes API usage

---

#### 3. Priority-Based (`priority`)

Immediate flush for high-priority data, batches others.

**Configuration**:
```yaml
buffer_strategy: priority
priority_immediate: true  # Flush HIGH priority immediately
max_batch_size: 100  # Batch LOW/MEDIUM priorities
```

**Best For**:
- Mixed priority workloads
- Critical sensor monitoring
- Real-time alerts + batch analytics

**Behavior**:
- HIGH priority: Immediate flush (< 10 seconds)
- MEDIUM/LOW priority: Size-based batching

**Priority Levels**:
- **HIGH**: Energy, temperature, CO2, power, air quality
- **MEDIUM**: Illuminance, motion, speed, humidity (non-critical)
- **LOW**: Binary sensors, availability states

---

#### 4. Hybrid (`hybrid`) - **Recommended**

Combines time and size strategies for balanced performance.

**Configuration**:
```yaml
buffer_strategy: hybrid  # Default
batch_interval: 300  # Maximum 5 minute delay
max_batch_size: 100  # Or flush at 100 points
priority_immediate: true  # Still honors priority
```

**Best For**:
- Most deployments
- Unknown data rates
- Balanced latency and efficiency

**Behavior**:
- Flushes on **whichever comes first**:
  - Time interval reached (e.g., 5 minutes)
  - Buffer size limit reached (e.g., 100 points)
  - High-priority data added (immediate)
- Adapts to varying data rates automatically

---

#### 5. Adaptive (`adaptive`)

Automatically adjusts flush frequency based on data rate.

**Configuration**:
```yaml
buffer_strategy: adaptive
adaptive_min_interval: 60  # 1 minute minimum
adaptive_max_interval: 600  # 10 minutes maximum
max_batch_size: 100  # Safety limit
```

**Best For**:
- Highly variable data rates
- Environments with periodic bursts
- Optimizing API usage automatically

**Behavior**:
- **High data rate** (>1/sec): Flush every 60 seconds
- **Medium data rate** (0.1-1/sec): Linear interpolation
- **Low data rate** (<0.1/sec): Flush every 600 seconds
- Continuously adapts to current rate

**Example**:
```
Data rate: 2 entries/sec → Interval: 60s (frequent)
Data rate: 0.5 entries/sec → Interval: ~200s (moderate)
Data rate: 0.05 entries/sec → Interval: 600s (infrequent)
```

---

### Priority Queue System

Data is organized by priority for intelligent buffering:

```
High Priority Buffer    → Immediate flush
  [Energy, Temp, CO2]

Medium Priority Buffer  → Batched (size/time)
  [Motion, Illuminance]

Low Priority Buffer     → Batched (size/time)
  [Binary sensors]
```

**Benefits**:
- Critical data has low latency
- Non-critical data batched efficiently
- Optimal API usage
- Configurable per-entity

---

### Flush Triggers

Buffer flushes are triggered by:

| Trigger | Description | Latency |
|---------|-------------|---------|
| **TIME_INTERVAL** | Time limit reached | Configurable (default: 5 min) |
| **SIZE_LIMIT** | Buffer full | Immediate |
| **PRIORITY** | High-priority data | ~10 seconds |
| **MANUAL** | Service call | Immediate |
| **SHUTDOWN** | Integration stopping | Immediate |
| **ADAPTIVE** | Dynamic adjustment | Variable |

---

## Configuration Examples

### Example 1: Real-Time Energy Monitoring

**Goal**: Minimize latency for energy sensors

```yaml
buffer_strategy: priority
priority_immediate: true
batch_interval: 60  # 1 minute for non-priority
max_batch_size: 50
```

**Result**:
- Energy/power data: < 10 second latency
- Other sensors: Batched every minute or 50 points

---

### Example 2: Large Deployment (100+ Entities)

**Goal**: Optimize API usage, acceptable latency

```yaml
buffer_strategy: hybrid
batch_interval: 300  # 5 minutes maximum
max_batch_size: 200  # Larger batches
priority_immediate: true
```

**Result**:
- High-priority: Immediate
- Others: Batched up to 5 minutes or 200 points
- Typically flushes every 2-3 minutes with 100+ entities

---

### Example 3: Low-Power/Intermittent Connection

**Goal**: Minimize API calls, maximize batch size

```yaml
buffer_strategy: size
max_batch_size: 500  # Large batches
priority_immediate: false  # Batch everything
```

**Result**:
- All data batched
- Flush only when 500 data points collected
- Minimum API calls

---

### Example 4: Mixed Workload

**Goal**: Real-time critical sensors, batch everything else

```yaml
buffer_strategy: adaptive
adaptive_min_interval: 30  # Fast during high activity
adaptive_max_interval: 600  # Slow during low activity
max_batch_size: 150
priority_immediate: true
```

**Result**:
- Adapts to data rate automatically
- High-priority: Always immediate
- Others: 30s to 600s depending on activity

---

## Data Validation Configuration

### Configurable Options

```yaml
# Staleness threshold (minutes, 0 = disabled)
stale_threshold_minutes: 5

# Validate numeric ranges
validate_ranges: true

# Only track changes (skip unchanged values)
track_changes_only: false
```

### Validation Statistics

The integration tracks validation metrics:

```yaml
sensor.clarify_validation_stats:
  total: 10000
  valid: 9500
  converted: 500  # Boolean → numeric conversions
  invalid_state: 300  # Unavailable/unknown
  invalid_type: 100  # Cannot convert to numeric
  invalid_range: 50  # Out of range
  stale: 50  # Too old
  success_rate: 95.0  # %
```

---

## Performance Considerations

### Memory Usage

**Buffer Size Impact**:
```
Typical entry: ~200 bytes
100 entries: ~20 KB
1000 entries: ~200 KB
```

**Recommendation**: Keep `max_batch_size` ≤ 500 for typical deployments

### API Rate Limits

Clarify.io API limits (typical):
- **Inserts**: ~60 requests/minute
- **Data points**: Thousands per request

**Optimization**:
- Use `hybrid` or `adaptive` strategy
- Adjust `batch_interval` based on entity count
- Monitor flush frequency in logs

### Network Efficiency

**Small batches (<10 points)**:
- API overhead dominates
- Low efficiency

**Medium batches (50-200 points)**:
- Good balance
- Recommended for most deployments

**Large batches (>500 points)**:
- High efficiency
- Increased latency
- Higher memory usage

---

## Troubleshooting

### Problem: High Validation Failure Rate

**Symptoms**:
```
validation_failed: 1000+ per day
success_rate: < 80%
```

**Solutions**:
1. Check entity selection (excluding non-numeric entities?)
2. Review device class mappings
3. Adjust range validation if needed
4. Disable `validate_ranges` if too strict

**Debug**:
```yaml
logger:
  logs:
    custom_components.clarify_data_bridge.data_validator: debug
```

---

### Problem: Data Arriving Late in Clarify.io

**Symptoms**:
- Delays of 5-10 minutes
- High-priority data not prioritized

**Solutions**:
1. Switch to `priority` or `hybrid` strategy
2. Enable `priority_immediate: true`
3. Reduce `batch_interval`
4. Check buffer metrics (may be size-limited)

**Verify Priority Configuration**:
```yaml
buffer_strategy: priority  # or hybrid
priority_immediate: true
batch_interval: 60  # Reduce if needed
```

---

### Problem: Too Many API Calls

**Symptoms**:
- Frequent flushes (every 10-30 seconds)
- API rate limit warnings

**Solutions**:
1. Increase `batch_interval` (e.g., 300 → 600)
2. Increase `max_batch_size` (e.g., 100 → 200)
3. Use `size` strategy instead of `time`
4. Disable `priority_immediate` if not needed

---

### Problem: Buffer Growing Indefinitely

**Symptoms**:
- Buffer size increasing over time
- Memory warnings
- No data being sent

**Check**:
1. Network connectivity to Clarify.io
2. API credentials validity
3. Integration logs for send failures

**Force Flush**:
```yaml
service: clarify_data_bridge.flush_buffer
```

---

## Advanced Topics

### Custom Validation Ranges

To customize range validation, modify `data_validator.py`:

```python
NUMERIC_RANGES = {
    "temperature": (-50, 150),  # Custom range for your climate
    "custom_sensor": (0, 1000),  # Add custom device class
}
```

### Change-Only Tracking

Enable to reduce data volume:

```yaml
track_changes_only: true
```

**Behavior**:
- Only sends when value changes
- Skips duplicate values
- Reduces API usage
- **Warning**: May miss important events if value oscillates

### Manual Buffer Management

**Force Flush**:
```yaml
service: clarify_data_bridge.flush_buffer
```

**Check Buffer Status**:
```yaml
sensor.clarify_buffer_status:
  high_priority: 5
  medium_priority: 20
  low_priority: 30
  total: 55
```

---

## Buffer Metrics

Monitor buffer performance:

```yaml
sensor.clarify_buffer_metrics:
  total_entries: 10000
  flushes: 50
  flush_triggers:
    time_interval: 30
    size_limit: 15
    priority: 5
  avg_buffer_size: 95.5
  max_buffer_size: 200
  data_rate: 0.83  # entries/second
  last_flush_time: "2024-01-15T10:30:00Z"
  last_flush_size: 102
```

---

## Best Practices

### 1. Start with Hybrid Strategy

Default `hybrid` strategy works for most deployments:
```yaml
buffer_strategy: hybrid
batch_interval: 300
max_batch_size: 100
priority_immediate: true
```

### 2. Monitor Buffer Metrics

Check buffer statistics weekly:
- Average buffer size
- Flush trigger distribution
- Data rate

### 3. Adjust Based on Needs

**High-priority monitoring** → `priority` strategy
**API optimization** → `size` or `adaptive` strategy
**Predictable timing** → `time` strategy

### 4. Enable Validation

Always enable range validation:
```yaml
validate_ranges: true
```

### 5. Set Reasonable Staleness Threshold

Prevent backfilling old data:
```yaml
stale_threshold_minutes: 5
```

---

## Summary

**Data Collection**:
- ✅ Event-driven state monitoring
- ✅ Zero polling overhead
- ✅ Automatic edge case handling

**Data Validation**:
- ✅ Boolean to numeric conversion
- ✅ Range validation by device class
- ✅ Stale data detection
- ✅ Unit conversion support

**Intelligent Buffering**:
- ✅ 5 buffering strategies
- ✅ Priority-based flushing
- ✅ Adaptive rate adjustment
- ✅ Comprehensive metrics

For entity selection, see [ENTITY_SELECTION.md](ENTITY_SELECTION.md).

For publishing strategies, see [PUBLISHING.md](PUBLISHING.md).
