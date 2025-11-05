# Configuration UI Guide

Complete guide to the Clarify Data Bridge configuration interface in Home Assistant.

## Overview

The Clarify Data Bridge features an intuitive multi-step configuration flow that guides you through:
1. **Credentials** - Connect to Clarify.io
2. **Selection Method** - Choose how to select entities
3. **Entity Selection** - Select entities using your chosen method
4. **Preview** - Review and confirm your selection
5. **Options** - Adjust settings after setup

## Configuration Flow

### Step 1: Credentials

**What it does**: Connects to Clarify.io and validates your credentials.

**Required Information**:
- **Client ID**: OAuth 2.0 Client ID from Clarify credentials file
- **Client Secret**: OAuth 2.0 Client Secret
- **Integration ID**: Your Clarify integration identifier

**Where to get credentials**:
1. Log into [clarify.io](https://clarify.io)
2. Go to Integrations
3. Create or select an integration
4. Download credentials file or copy OAuth credentials

**Validation**: The integration tests your credentials immediately and shows an error if they're invalid.

---

### Step 2: Selection Method

**What it does**: Choose how you want to select which entities to track.

#### Available Methods:

##### 🚀 Quick Setup (Recommended)
**Best for**: New users, getting started quickly
**What it does**: Automatically selects entities based on priority level
**Time required**: < 1 minute

**Priority Options**:
- **High Priority**: Energy, temperature, CO2, power consumption, air quality (~20-40 entities)
- **Medium Priority**: High + light levels, motion sensors, sound levels (~40-80 entities)
- **Low Priority**: All trackable entities including binary sensors (~100+ entities)

**Recommended**: Start with High Priority and expand later if needed.

##### 📊 Select by Priority Level
**Best for**: Users who want automatic classification with domain filtering
**What it does**: Shows entity counts by priority and lets you choose priority + domains
**Time required**: 1-2 minutes

**Features**:
- Real-time entity counts for each priority level
- Multi-select domains to include
- Combines priority-based and domain-based filtering

##### 📁 Select by Domain
**Best for**: Tracking specific entity types (sensors, climate, etc.)
**What it does**: Select entire domains with optional priority refinement
**Time required**: 1-2 minutes

**Common Domains**:
- **sensor**: Temperature, humidity, power, energy sensors
- **climate**: Thermostats and HVAC systems
- **binary_sensor**: Motion, door, window sensors (converted to 0/1)
- **weather**: Weather stations
- **light**: Smart lights (brightness tracking)
- **switch**: Smart switches (state tracking)

**Option**: Refine by priority level after selecting domains.

##### 🏷️ Select by Device Class
**Best for**: Precise control over specific sensor types
**What it does**: Shows available device classes with entity counts
**Time required**: 2-3 minutes

**Common Device Classes**:
| Device Class | Description | Typical Count |
|--------------|-------------|---------------|
| temperature | Temperature sensors | 5-20 |
| humidity | Humidity sensors | 5-15 |
| power | Power consumption | 3-10 |
| energy | Energy meters | 3-10 |
| voltage | Voltage sensors | 1-5 |
| current | Current sensors | 1-5 |
| carbon_dioxide | CO2 sensors | 1-3 |
| pm25 | Air quality (PM2.5) | 1-3 |

**Smart Defaults**: Temperature, humidity, power, energy, voltage, current, carbon_dioxide are pre-selected.

##### ✅ Manual Entity Selection
**Best for**: Complete control, specific entity needs
**What it does**: Shows searchable list of all trackable entities
**Time required**: 5-10 minutes (depending on entity count)

**Features**:
- Searchable entity list
- Shows friendly names, device class, and area
- Limit: First 200 entities shown (for performance)
- Option to add advanced filters after selection

**Use case**: When you need specific entities that don't fit other selection methods.

##### ⚙️ Advanced Filtering
**Best for**: Power users, complex filtering requirements
**What it does**: Uses regular expressions and patterns for precise control
**Time required**: 5-10 minutes (requires regex knowledge)

**Capabilities**:
- Include patterns (regex)
- Exclude patterns (regex)
- Exclude specific entities
- Combine with priority filtering

**Examples**:
```
Include all temperature sensors:
  sensor\..*_temperature

Kitchen and bedroom sensors only:
  sensor\.(kitchen|bedroom)_.*

All power and energy sensors:
  sensor\..*_(power|energy)

Exclude test sensors:
  sensor\.test_.*
```

---

### Step 3: Entity Selection

**What it does**: Executes your chosen selection method.

This step varies based on your chosen method (see Selection Method section above).

**Common Features**:
- Real-time entity counts
- Device class filtering
- Domain selection
- Priority-based filtering

---

### Step 4: Preview & Confirm

**What it does**: Shows a comprehensive summary of your selection before finishing.

#### Preview Information:

**📊 Entity Counts**:
- Total entities that will be tracked
- Breakdown by priority (High/Medium/Low)
- Breakdown by domain (sensor, climate, etc.)
- Breakdown by category (environmental, power, etc.)

**🔍 Sample Entities**:
Shows first 10 entities that will be tracked with:
- Friendly names
- Device classes
- Domains

**📋 Configuration Summary**:
- Domains included
- Device classes (if filtered)
- Patterns (if used)
- Priority level

#### Actions:
- **Confirm**: Complete setup and create integration
- **Go Back**: Return to selection method to make changes

**Important**: Review this carefully! This determines what data is sent to Clarify.io.

---

## Options Flow (After Setup)

Access via: Settings → Devices & Services → Clarify Data Bridge → Configure

### Options Menu

Choose what to configure:
1. **Batch Processing Settings**
2. **Entity Filtering**
3. **Advanced Filters**

---

### Option 1: Batch Processing Settings

**What it does**: Adjusts how often data is sent to Clarify.io.

#### Settings:

**Batch Interval** (60-3600 seconds):
- How often to send accumulated data points
- Default: 300 seconds (5 minutes)
- Lower = more frequent updates, higher API usage
- Higher = less frequent updates, better batching

**Maximum Batch Size** (10-1000 data points):
- Triggers automatic send when buffer reaches this size
- Default: 100 data points
- Prevents buffer overflow
- Automatically sends regardless of interval

#### Recommendations:

| Home Size | Entities | Batch Interval | Max Batch Size |
|-----------|----------|----------------|----------------|
| Small | <50 | 300s (5 min) | 100 |
| Medium | 50-150 | 180s (3 min) | 200 |
| Large | 150-300 | 120s (2 min) | 500 |
| Very Large | >300 | 90s (1.5 min) | 1000 |

**Formula**: `batch_size ≥ entity_count × (state_changes_per_minute ÷ 60) × interval`

**Example**: 100 entities, 2 state changes/min average:
- Batch size needed: `100 × 2 × (300 ÷ 60) = 1000` (use 500 for overhead)

---

### Option 2: Entity Filtering

**What it does**: Adjust entity selection without recreating the integration.

#### Settings:

**Minimum Priority**:
- HIGH: Only critical sensors (energy, temperature, CO2)
- MEDIUM: Critical + useful sensors (light, motion)
- LOW: All trackable entities

**Include Domains**:
- Multi-select domains to track
- Unchecking a domain stops tracking all entities in it

**Include Device Classes** (optional):
- Multi-select specific device classes
- Leave empty to include all device classes in selected domains
- Use to further refine entity selection

#### Effect:
Changes take effect after **restarting the integration** (not Home Assistant):
1. Go to Integrations
2. Click Clarify Data Bridge
3. Click "⋯" menu
4. Select "Reload"

---

### Option 3: Advanced Filters

**What it does**: Fine-tune entity selection with patterns and exclusions.

#### Settings:

**Include Patterns** (comma-separated regex):
- Only entities matching these patterns are included
- Multiple patterns are OR'd together
- Uses Python regex syntax

**Examples**:
```
sensor\..*_temperature, sensor\..*_humidity
  → Includes all temperature and humidity sensors

sensor\.(living_room|kitchen|bedroom)_.*
  → Includes sensors in specific rooms

sensor\..*_(power|energy|voltage|current)
  → Includes all power-related sensors
```

**Exclude Patterns** (comma-separated regex):
- Entities matching these patterns are excluded
- Applied after include patterns
- Uses Python regex syntax

**Examples**:
```
sensor\.test_.*, sensor\..*_unavailable
  → Excludes test sensors and unavailable entities

sensor\.sun_.*, sensor\.moon_.*
  → Excludes sun and moon sensors

sensor\..*_forecast_.*
  → Excludes forecast sensors
```

**Exclude Entities** (comma-separated entity IDs):
- Specific entities to exclude
- Exact entity ID matches only

**Examples**:
```
sensor.time_date, sensor.sun_elevation, binary_sensor.updater
  → Excludes specific unwanted entities
```

#### Pattern Syntax:

| Pattern | Matches | Example |
|---------|---------|---------|
| `.*` | Any characters | `sensor\..*` matches all sensors |
| `.+` | One or more characters | `sensor\.room.+temp` |
| `\.` | Literal dot (escape) | `sensor\.` for "sensor." |
| `\|` | OR operator | `(kitchen\|bedroom)` |
| `^` | Start of string | `^sensor\.temp` |
| `$` | End of string | `_temperature$` |
| `[0-9]` | Any digit | `sensor\.room[0-9]` |
| `[a-z]` | Any lowercase letter | `sensor\.[a-z]+` |

#### Effect:
Changes take effect after **reloading the integration** (see Entity Filtering section).

---

## Usage Examples

### Example 1: Energy Monitoring Home

**Goal**: Track all energy, power, and related sensors.

**Setup**:
1. Choose **Select by Device Class**
2. Select: energy, power, voltage, current, power_factor
3. Preview shows ~10-15 entities
4. Confirm

**Result**: All power monitoring entities tracked automatically.

---

### Example 2: Climate Monitoring

**Goal**: Track temperature, humidity, and air quality across the home.

**Setup**:
1. Choose **Quick Setup**
2. Select **High Priority**
3. Preview shows temperature, humidity, CO2, air quality sensors
4. Confirm

**Result**: All climate-related high-priority sensors tracked.

---

### Example 3: Specific Rooms Only

**Goal**: Track all sensors in living room and bedroom only.

**Setup**:
1. Choose **Advanced Filtering**
2. Include pattern: `sensor\.(living_room|bedroom)_.*`
3. Exclude pattern: `sensor\..*_forecast.*`
4. Preview shows only sensors in those rooms
5. Confirm

**Result**: Only living room and bedroom sensors tracked.

---

### Example 4: Everything Except Test Sensors

**Goal**: Track all entities but exclude test/diagnostic sensors.

**Setup**:
1. Choose **Quick Setup**
2. Select **Low Priority** (all entities)
3. After setup, go to Options → Advanced Filters
4. Exclude pattern: `sensor\.test_.*, sensor\..*_diagnostic.*`
5. Reload integration

**Result**: All entities tracked except test and diagnostic sensors.

---

### Example 5: Custom Priority with Domains

**Goal**: Track high/medium priority sensors and climate entities.

**Setup**:
1. Choose **Select by Priority Level**
2. Select **Medium Priority**
3. Select domains: sensor, climate, weather
4. Preview shows medium/high priority entities in selected domains
5. Confirm

**Result**: Balanced selection with climate control included.

---

## UI Tips & Best Practices

### Getting Started

1. **Start Small**: Use Quick Setup with High Priority
2. **Review Preview**: Always check the preview carefully
3. **Monitor First Week**: Watch logs to ensure data is flowing
4. **Expand Gradually**: Add more entities as needed

### Performance

1. **Limit Entities**: More entities = more data = higher costs
2. **Use Priorities**: Let automatic classification help
3. **Batch Wisely**: Larger batches = better efficiency
4. **Pattern Efficiently**: Specific patterns are faster than broad ones

### Maintenance

1. **Review Monthly**: Check if all tracked entities are still needed
2. **Update Filters**: Adjust patterns as you add/remove devices
3. **Monitor Costs**: Check Clarify.io usage regularly
4. **Clean Up**: Remove old/unused entities from tracking

### Common Patterns

**Include all temperature sensors**:
```
sensor\..*_temperature
```

**Include specific rooms**:
```
sensor\.(kitchen|living_room|bedroom_1)_.*
```

**Include power and energy**:
```
sensor\..*_(power|energy|voltage|current)
```

**Exclude battery and signal strength**:
```
sensor\..*_(battery|signal_strength|rssi)
```

**Exclude weather forecast**:
```
sensor\..*_forecast.*
```

---

## Troubleshooting

### Problem: No entities in preview

**Causes**:
- Filters too restrictive
- No entities match criteria
- Min priority too high

**Solutions**:
1. Go back and select **Low Priority**
2. Select all supported domains
3. Remove device class filters
4. Check pattern syntax

---

### Problem: Too many entities in preview

**Causes**:
- Priority too low
- Too many domains selected
- Include patterns too broad

**Solutions**:
1. Increase min priority to **Medium** or **High**
2. Select specific domains instead of all
3. Add exclude patterns for unwanted entities
4. Use device class filtering

---

### Problem: Missing expected entities

**Causes**:
- Entity has no numeric data
- Entity in excluded domain
- Entity matches exclude pattern
- Entity below min priority

**Solutions**:
1. Check entity in Developer Tools → States
2. Verify entity has numeric state or attributes
3. Check exclude patterns
4. Lower min priority

---

### Problem: Pattern not working

**Causes**:
- Incorrect regex syntax
- Forgot to escape dots
- Wrong pattern type

**Solutions**:
1. Test pattern at [regex101.com](https://regex101.com)
2. Remember: `\.` not `.` for literal dots
3. Use `.*` not `*` for wildcards
4. Check for typos in entity IDs

---

### Problem: Changes not taking effect

**Causes**:
- Integration not reloaded
- Configuration cached

**Solutions**:
1. Go to Integrations
2. Find Clarify Data Bridge
3. Click "⋯" → "Reload"
4. Wait 30 seconds for discovery
5. Check logs for confirmation

---

## Advanced Topics

### Dynamic Entity Selection

Entities are discovered at startup:
- New entities added to Home Assistant are discovered on reload
- Removed entities are automatically stopped
- Changed entities are re-evaluated

### Performance Optimization

**Large Homes (>200 entities)**:
1. Use device class filtering instead of domains
2. Use specific include patterns
3. Increase batch size to 500-1000
4. Decrease batch interval to 90-120s
5. Monitor memory usage

**Many State Changes (>1000/min)**:
1. Increase max batch size
2. Decrease batch interval
3. Consider excluding high-frequency entities
4. Use exclude patterns for rapid-changing sensors

### Pattern Testing

Before using patterns in production:
1. Test at [regex101.com](https://regex101.com)
2. Set flavor to "Python"
3. Paste entity IDs in test string
4. Verify matches are correct
5. Test both include and exclude patterns

### Migration from Basic to Advanced

If you started with Quick Setup and want more control:
1. Note current entity count
2. Go to Options → Advanced Filters
3. Add patterns to match current selection
4. Add exclude patterns for unwanted entities
5. Reload and verify entity count
6. Adjust as needed

---

## Keyboard Shortcuts

Home Assistant config flow supports keyboard navigation:
- **Tab**: Navigate between fields
- **Space**: Toggle checkboxes
- **Enter**: Submit form/continue
- **Escape**: Cancel/go back (where available)

---

## Accessibility

The configuration UI is designed for accessibility:
- Screen reader friendly
- Keyboard navigable
- Clear field labels
- Helpful descriptions
- Error messages with context

---

## Feedback & Support

### Getting Help

1. Check the preview step carefully
2. Review logs in Home Assistant
3. Check [ENTITY_SELECTION.md](./ENTITY_SELECTION.md) for filtering details
4. Search existing GitHub issues
5. Create new issue with configuration details

### Reporting Issues

Include:
- Configuration method used
- Number of entities expected vs actual
- Relevant log entries
- Patterns used (if any)
- Home Assistant version

---

## Version History

### Version 2.0 (Phase 2)
- Multi-step configuration flow
- 6 selection methods
- Entity preview
- Advanced filtering UI
- Options flow menu
- Real-time entity counts
- Pattern validation

### Version 1.0 (Phase 1)
- Basic configuration
- Domain filtering only
- No preview
- Manual YAML configuration
