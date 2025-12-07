## ADDED Requirements

### Requirement: Streaming Intelligence Emission
The recon agent SHALL emit PERCEPTION, HEALTH, PLAN, and CHECKPOINT events in realtime during planning/execution, writing both to the message bus and the world model/PostGIS incrementally (not batched end-of-mission).

**Event Types**:
- PERCEPTION: 感知事件（障碍物、被困人员、路况）
- HEALTH: 设备健康状态（电量、信号、故障）
- PLAN: 规划状态变更（航线生成、调整）
- CHECKPOINT: 任务进度检查点

**Event Required Fields** (by type):
- ALL: event_id(uuid), event_type, timestamp(ISO8601), mission_id
- PERCEPTION: geometry(with SRID), confidence, source, payload.detection_type
- HEALTH: device_id, metric_name, metric_value, severity(INFO/WARN/CRITICAL)
- PLAN: plan_id, plan_version, action(CREATED/UPDATED/ABORTED)
- CHECKPOINT: checkpoint_id, progress_percent, remaining_distance_m

**Write Order & Atomicity**:
1. Generate event_id (UUID v4)
2. Write to STOMP first (realtime, fire-and-forget if broker down)
3. Write to PostGIS second (durable, retry on failure)
4. NOT atomic: STOMP success + PostGIS failure is acceptable (eventual consistency)
5. Idempotency: PostGIS uses event_id as unique key, ON CONFLICT DO NOTHING

**Critical Event Definition** (priority >= 60):
- SURVIVOR_DETECTED (100)
- OBSTACLE_DETECTED (80)
- ROUTE_BLOCKED (70)
- HEALTH_WARNING (60)

Non-critical (priority < 60): CHECKPOINT(20), PLAN events(30)

Buffer overflow behavior: drop oldest non-critical first, then oldest critical.

**Network Retry Backoff**: Exponential backoff 1s, 2s, 4s (max 3 retries) for STOMP/PostGIS failures.

#### Scenario: Obstacle detected mid-flight
- **WHEN** the agent detects a new road blockage during execution
- **THEN** it SHALL emit a PERCEPTION event within 1 second and persist it to the world model so rescue/monitor components can react immediately.

#### Scenario: Network disconnection during emission
- **WHEN** STOMP broker is unreachable during event emission
- **THEN** the agent SHALL buffer events locally (max 1000) and retry on reconnection; if buffer overflows, oldest non-critical events SHALL be dropped first.

#### Scenario: PostGIS write failure
- **WHEN** PostGIS write fails
- **THEN** the agent SHALL log error, continue mission, and retry write in background with exponential backoff; critical PERCEPTION events (priority >= 60) SHALL trigger HEALTH warning.

### Requirement: Hierarchical Validation (L1 fast, L2 deep)
The recon agent SHALL apply L1 fast validation (2.5D geometry, coarse energy/ban zones) inside the planning loop and only run L2 deep validation (3D terrain-following + voxel collision + dynamic energy) on the final candidate plan.

**L1 Validation Contents**:
- 2.5D禁飞区检查（polygon intersection）
- 粗略能耗估算（distance-based）
- 最大飞行时间约束

**L2 Validation Contents**:
- 3D地形碰撞检测（DEM-based terrain following）
- 体素空间障碍检测
- 动态能耗精算（wind/temp/payload factors）
- 通信覆盖验证

**Timeout Scope**:
- L1 500ms: CPU-only computation, NO external I/O
- L2 5s: Includes DEM file read (cached after first load), NO network I/O
- If L2 needs comm coverage query, that's a separate async call before L2

**Retry Strategy after Timeout**:
- L1 timeout: NO retry, count as failure, adjust parameters and re-submit
- L2 timeout: Allow 1 retry with 1.5x timeout (7.5s), then fail
- Partial results: NOT reused; each validation is stateless

#### Scenario: Plan fails L1
- **WHEN** a candidate route violates L1 (e.g., coarse battery/ban-zone check)
- **THEN** the agent SHALL reject it and retry with adjustments without invoking L2.

#### Scenario: Plan passes L1 but fails L2
- **WHEN** a candidate passes L1 but L2 finds 3D collision or energy shortfall
- **THEN** the agent SHALL record the failure reason and re-enter retry logic.

#### Scenario: Validation timeout
- **WHEN** L1 exceeds 500ms or L2 exceeds 5s
- **THEN** the agent SHALL abort current validation, log timeout with error code VALIDATION_TIMEOUT(4004), and count as validation failure.

### Requirement: Retry Budget, Circuit Breaker, and Human-Authorized Degradation
The recon agent SHALL track retry_count and max_retries; upon exceeding budget:
1. MUST emit FAIL_SAFE event and enter safe mode (RTH or hover)
2. MUST NOT auto-degrade; degradation requires explicit human approval
3. If human approves degradation, execute approved strategy only
4. If human rejects or approval timeout (default: 300s), maintain safe mode

**max_retries Source & Reset**:
- Default: 3 (hardcoded)
- Override: mission_config.max_retries (if provided)
- Device override: device_profile.validation_retries (highest priority)
- Reset: retry_count resets to 0 after successful validation pass

**Safe Mode Options**:
- HOVER: 原地悬停等待指令
- RTH: 返回起飞点
- EMERGENCY_LAND: 紧急就近降落（仅当RTH不可行）

**Degradation Options** (require human approval):
- REDUCE_ALTITUDE: 降低飞行高度
- REDUCE_COVERAGE: 减少覆盖范围
- SWITCH_DEVICE: 切换备用设备
- PERIMETER_ONLY: 仅执行周边扫描

**Communication Interruption Handling**:
- If signal lost AND approval_timeout (300s) expires:
  - Agent SHALL execute autonomous RTH (no ACK required)
  - Rationale: Safety over approval in comm-out scenario
- This is the ONLY case of autonomous action without approval
- Emit AUTONOMOUS_RTH event with reason="approval_timeout_comm_lost"

#### Scenario: High wind causes repeated failures
- **WHEN** repeated validations fail due to wind limits
- **THEN** agent SHALL:
  1. Enter safe mode (hover at current position if safe, else RTH)
  2. Emit APPROVAL_REQUIRED event with degradation options
  3. Wait for human decision (approve/reject/manual_rtl)
  4. Execute human-approved action only

#### Scenario: Human approves degradation
- **WHEN** human approves "REDUCE_ALTITUDE" degradation via API/UI
- **THEN** agent SHALL re-plan with approved altitude constraint and continue mission

#### Scenario: Approval timeout
- **WHEN** no human response within 300 seconds
- **THEN** agent SHALL execute RTH and emit MISSION_ABORTED event

#### Scenario: Approval timeout with signal lost
- **WHEN** approval_timeout expires AND signal is lost
- **THEN** agent SHALL execute autonomous RTH without waiting for ACK, emit AUTONOMOUS_RTH event

### Requirement: Emergency RTH (Return To Home)
The recon agent SHALL trigger Emergency RTH when ANY of the following conditions occur:
- Battery < RTH_threshold (calculated dynamically based on distance and wind)
- Signal lost > 30 seconds and no relay point reachable
- Validation failures exceed max_retries and human approval timeout
- Critical hardware fault detected (motor/GPS/IMU failure)
- Human triggers emergency return via command

**Trigger Priority** (highest first, execute highest when multiple):
1. CRITICAL_HARDWARE_FAULT (motor/GPS/IMU) - immediate
2. BATTERY_CRITICAL (< RTH_required) - immediate
3. HUMAN_COMMAND - immediate
4. SIGNAL_LOST_TIMEOUT (30s) - after timeout
5. VALIDATION_EXHAUSTED + APPROVAL_TIMEOUT - after 300s

**When Multiple Triggers**: Execute highest priority trigger's RTH path; log all active triggers in EMERGENCY_RTH event.

**RTH Path Calculation**: SHALL use route history stack inverse path to avoid known obstacles; if inverse path blocked, climb to safe altitude (min 50m above highest obstacle) then direct return.

**No Route History Fallback**:
1. If route_history_stack empty: climb to 100m AGL, direct return
2. If PostGIS unavailable: use in-memory route history only
3. If in-memory also empty: climb to max(100m, obstacle_clearance+50m), direct return
4. Emit HEALTH warning: "RTH_NO_HISTORY"

**RTH Energy Reservation**: RTH_required = (distance_to_home / cruise_speed) * power_rate * 1.3 (safety factor)

#### Scenario: Low battery triggers RTH
- **WHEN** battery_percent < RTH_required + 10% margin
- **THEN** agent SHALL immediately abort current mission segment and execute RTH; emit EMERGENCY_RTH event.

#### Scenario: Signal lost during mission
- **WHEN** signal lost for 30 seconds and no relay point within range
- **THEN** agent SHALL execute RTH using last known safe path; if path unknown, climb to 100m AGL then direct return.

#### Scenario: RTH path blocked
- **WHEN** calculated RTH path intersects with obstacle
- **THEN** agent SHALL climb to obstacle_height + 50m, then proceed with direct RTH.

#### Scenario: Multiple RTH triggers
- **WHEN** both BATTERY_CRITICAL and SIGNAL_LOST_TIMEOUT trigger simultaneously
- **THEN** agent SHALL execute RTH with BATTERY_CRITICAL priority (higher), log both triggers.

### Requirement: Forced Relay (No Blind Flight)
The recon agent SHALL avoid blind flight; when the comms map predicts a blind zone it MUST insert relay points, backtrack to the last safe signal point, upload data and receive ACK before continuing.

**Blind Zone Detection**: Query comm coverage provider (mock or real) for signal strength prediction along planned path. Threshold: signal < -90dBm.

**Total Dwell Time Limit**:
- ACK wait: 60s
- Retries: 3 × 10s = 30s
- Climb attempt: max 3 × 50m = 150m, ~60s climb time
- TOTAL MAX: 150s (2.5 minutes)
- If exceeded: trigger Emergency RTH

**Last Safe Signal Point Validity**:
- Time validity: < 10 minutes since last successful ACK at that point
- Distance validity: < 2km from current position
- Signal validity: predicted signal >= -80dBm (10dB margin above threshold)
- If ANY invalid: skip backtrack, attempt climb directly

**ACK Timeout Handling**:
1. If ACK not received within 60 seconds, retry upload 3 times with 10s intervals
2. If still no ACK after retries, attempt controlled climb (+50m, max 500m AGL)
3. If climb improves signal and ACK received, continue mission
4. If still no ACK after climb, trigger Emergency RTH

**Data Source**:
- Mock mode: Load from `mock_data/comm_coverage.json`
- Real mode: Query communication coverage service API (interface reserved)

**Algorithm**: Relay insertion SHALL backtrack using the route history stack (inverse path) to ensure obstacle avoidance; if the last safe signal point is invalid, attempt safe climb first.

**Fallback Priority**:
1. Backtrack via route history stack to last safe signal point
2. Controlled climb (+50m increments, max 500m AGL)
3. Emergency RTH to home point

#### Scenario: Route enters predicted blind zone
- **WHEN** a planned leg would enter predicted blind zone (signal < -90dBm)
- **THEN** the agent SHALL insert relay waypoint at last safe signal point, perform HOVER_AND_UPLOAD_UNTIL_ACK, and only then resume mission.

#### Scenario: ACK timeout after upload
- **WHEN** no ACK received within 60s after data upload
- **THEN** agent SHALL retry 3 times (10s intervals), then attempt climb (+50m), then trigger Emergency RTH if still no ACK.

#### Scenario: Total relay dwell exceeded
- **WHEN** relay dwell time exceeds 150s total
- **THEN** agent SHALL abort relay procedure and trigger Emergency RTH.

### Requirement: Coordinate Standard (CTS-2025)
Recon planning/validation SHALL use UTM for core computation with a recorded UTM zone; all external inputs/outputs SHALL be WGS84 with SRID noted; DEM/DSM height baseline SHALL be fixed and documented; conversions SHALL be centralized utilities.

**UTM Zone Handling**: For regions spanning multiple UTM zones (e.g., Sichuan spans 48N/49N), use the zone containing mission center point; record zone in state.utm_zone.

**Height Baseline**: All altitude values SHALL use EGM96 geoid height; DEM data baseline SHALL be documented; conversion between ellipsoid and geoid height SHALL use centralized utility.

**Conversion Utilities** (in `core/coord_transform.py`):
- `wgs84_to_utm(lng, lat) -> (easting, northing, zone, hemisphere)`
- `utm_to_wgs84(easting, northing, zone, hemisphere) -> (lng, lat)`
- `ellipsoid_to_geoid(ellipsoid_height, lat, lon) -> geoid_height`
- `geoid_to_ellipsoid(geoid_height, lat, lon) -> ellipsoid_height`

**DEM/DSM Data Source**:
- File: `data/四川省.tif` (SRTM 30m resolution)
- CRS: EPSG:4326 (WGS84)
- Height baseline: EGM96 geoid (verified)
- Resolution: 30m horizontal, 1m vertical precision
- Coverage: Sichuan province bounding box

**Precision Requirements**:
- Horizontal: < 1m accuracy for UTM coordinates
- Vertical: < 3m accuracy for altitude

**Constraint**: Developers MUST NOT perform lat/lon arithmetic inside RouteGen/Validation/Sim loops; all internal geometry computations SHALL be in UTM meters.

**Constraint**: Altitude values MUST be compatible with the declared DEM baseline (EGM96 geoid) consistently across planning/validation/output.

#### Scenario: ROI ingestion and output
- **WHEN** a ROI is ingested in WGS84
- **THEN** the agent SHALL convert it to UTM for planning/validation and output waypoints back in WGS84 with SRID=4326, preserving altitude baseline consistency.

#### Scenario: Cross-zone mission
- **WHEN** mission area spans two UTM zones
- **THEN** agent SHALL use zone of area centroid, log warning about potential edge distortion (< 0.1% at zone boundary).

### Requirement: Data Contracts (Control vs Intelligence)
Control outputs SHALL be DJI-like waypoints/KML/JSON for flight execution; intelligence events SHALL follow DDLP-style JSON with defined schema.

**Intelligence Event Schema**:
```json
{
  "event_id": "uuid",
  "event_type": "PERCEPTION|HEALTH|PLAN|CHECKPOINT",
  "timestamp": "ISO8601",
  "mission_id": "uuid",
  "geometry": {"type": "Point", "coordinates": [lon, lat, alt], "crs": "EPSG:4326"},
  "confidence": 0.0-1.0,
  "source": "sensor_type",
  "priority": "calculated as base_priority * confidence",
  "payload": {}
}
```

**Base Priority Values**:
- SURVIVOR_DETECTED: 100
- OBSTACLE_DETECTED: 80
- ROUTE_BLOCKED: 70
- HEALTH_WARNING: 60
- PLAN_UPDATED: 30
- CHECKPOINT: 20

**Control Output Minimum Fields** (DJI-like JSON):
```json
{
  "mission_id": "uuid",
  "device_id": "string",
  "home_point": {"lat": 0.0, "lng": 0.0, "alt_msl": 0.0},
  "altitude_mode": "AGL|MSL",
  "waypoints": [
    {
      "seq": 1,
      "lat": 0.0,
      "lng": 0.0,
      "alt": 0.0,
      "speed_ms": 10.0,
      "heading": 0.0,
      "gimbal_pitch": -90,
      "action": "FLY_TO|HOVER|TAKE_PHOTO|START_VIDEO|STOP_VIDEO|RTH",
      "action_params": {},
      "dwell_time_s": 0
    }
  ],
  "safety": {
    "max_altitude_agl": 500,
    "min_altitude_agl": 30,
    "geofence": {"type": "Polygon", "coordinates": []},
    "rth_altitude_agl": 100,
    "lost_signal_action": "RTH|HOVER|LAND"
  }
}
```

**KML Output**: Same waypoints in KML 2.2 format with `<ExtendedData>` for actions.

#### Scenario: Thermal survivor detection
- **WHEN** a thermal sensor flags a survivor
- **THEN** the agent SHALL emit a PERCEPTION event with confidence 0.9, source "THERMAL_SENSOR", SRID-tagged geometry, priority=90, and persist to PostGIS and STOMP bus.

### Requirement: Checkpoint and Resume with Re-Plan
The recon agent SHALL persist checkpoints containing progress, breakpoint coordinate, covered-area mask (UTM), environment snapshot, and cached intelligence; resume SHALL trigger re-planning using the latest environment and coverage, not a direct goto.

**Checkpoint Payload**:
- mission_id, checkpoint_id, timestamp, schema_version
- current_position (UTM), heading, altitude
- covered_area_mask (UTM polygon/raster)
- remaining_waypoints
- environment_snapshot (wind, comm_coverage, constraints)
- cached_intelligence (buffered events not yet persisted)
- battery_state, device_health

**Redis/PostgreSQL Switch Rule**:
- Mission duration < 1h: Redis only (TTL 24h)
- Mission duration >= 1h: Redis + PostgreSQL (sync write)
- Mission explicitly marked "critical": always PostgreSQL
- On resume: try Redis first, fallback to PostgreSQL if Redis miss

**Checkpoint Schema Version**:
- Field: schema_version (string, e.g., "1.0.0")
- Incompatible version: reject resume with CHECKPOINT_VERSION_MISMATCH error
- Minor version diff (1.0.x): allow resume with warning

**Distributed Lock**:
- Lock key: `recon:mission:{mission_id}:lock`
- Lock TTL: 60s
- Renewal: every 30s while mission active
- Lock value: {node_id, timestamp, pid}
- Acquire timeout: 5s (fail fast)

**Concurrency Control**: Resume SHALL acquire distributed lock on mission_id; concurrent resume attempts SHALL fail with MISSION_LOCKED error.

#### Scenario: Interrupt and later resume
- **WHEN** a mission is suspended for a higher-priority task
- **THEN** the agent SHALL save checkpoint and upon resume SHALL re-plan with updated wind/coverage before continuing.

#### Scenario: Concurrent resume attempt
- **WHEN** two processes attempt to resume same mission
- **THEN** second process SHALL receive MISSION_LOCKED error; first process proceeds.

#### Scenario: Schema version mismatch
- **WHEN** checkpoint schema_version is incompatible (major version diff)
- **THEN** resume SHALL fail with CHECKPOINT_VERSION_MISMATCH error; mission must restart.

### Requirement: Dynamic Energy Model
Energy estimation SHALL account for wind, payload, temperature, battery aging, and path shape; the same model MUST be used consistently in DeviceSelector, Validation, and Simulator; RTH margin MUST be enforced.

**Units**:
- Energy: percentage of battery (0-100%)
- Power rate: %/second
- Distance: meters
- Speed: m/s
- Temperature: Celsius
- Payload: kg

**Energy Calculation Formula**:
```
E_total = E_base * k_wind * k_temp * k_payload * k_age + E_climb + E_hover

Where:
- E_base = distance_m / 1000 * base_consumption_per_km (from device profile)
- k_wind = 1 + 0.5 * max(0, v_headwind_ms) / v_cruise_ms
- k_temp = 1.3 if temp_c < 0 else (1.1 if temp_c > 35 else 1.0)
- k_payload = 1 + payload_kg / max_payload_kg * 0.3
- k_age = 1 + cycle_count / 500 * 0.2 (battery degradation)
- E_climb = altitude_gain_m / 100 * climb_consumption_per_100m
- E_hover = hover_time_s / 60 * hover_consumption_per_min
```

**Wind Direction Convention**:
- v_headwind > 0: wind opposing flight direction (increases consumption)
- v_headwind < 0: tailwind (treated as 0, no consumption reduction for safety)
- Calculation: v_headwind = wind_speed * cos(wind_direction - heading)

**Hover/Climb Limits**:
- Max hover time per waypoint: 120s (configurable)
- Max total hover time per mission: 600s
- Max single climb: 200m
- Max climb rate: 5 m/s

**Device Profile Validity**:
- Cache TTL: 5 minutes
- Refresh: on mission start, on device switch
- Stale data (> 5min): emit HEALTH warning, use cached with 10% safety penalty

**RTH Margin Enforcement**:
```
RTH_required = (distance_to_home_m / cruise_speed_ms) * power_rate * 1.3
Trigger RTH when: battery_percent < RTH_required + 10
```

**Data Source**:
- Mock mode: Load device parameters from `mock_data/device_profiles.json`
- Real mode: Query device management API (interface reserved)

#### Scenario: Strong headwind halves range
- **WHEN** headwind (v_headwind > 10m/s) reduces effective range below mission requirement
- **THEN** validation SHALL fail the plan; agent enters retry logic with adjusted parameters.

#### Scenario: Cold weather battery degradation
- **WHEN** temperature < 0°C
- **THEN** energy model SHALL apply k_temp=1.3 factor; if resulting range insufficient, emit warning and request human decision.

#### Scenario: Stale device profile
- **WHEN** device profile cache is older than 5 minutes
- **THEN** agent SHALL emit HEALTH warning "STALE_DEVICE_PROFILE" and apply 10% additional energy safety margin.

### Requirement: Performance Guardrails
The recon agent SHALL confine L2 computations to final candidates, apply concurrency limits/timeouts, and rate-limit per-device planning to prevent overload.

**Error Codes**:
- QUEUE_TIMEOUT (4001): planning request waited > 30s in queue
- RATE_LIMITED (4002): exceeded per-device or global rate limit
- CONCURRENCY_EXCEEDED (4003): max concurrent operations reached
- VALIDATION_TIMEOUT (4004): L1/L2 validation timeout

**Scope**:
- Concurrency limits: GLOBAL (across all missions on this node)
- Rate limits: PER-DEVICE (tracked by device_id)
- Queue timeout: PER-REQUEST

**Concurrency Limits**:
- Max concurrent L2 validations: 3
- Max concurrent device plannings: 5
- Planning queue timeout: 30s

**Rate Limits**:
- Per-device planning: max 2 plans/minute
- L2 validation: max 10/minute total

**Timeout Values**:
- L1 validation: 500ms
- L2 validation: 5s (first attempt), 7.5s (retry)
- Single device planning: 30s
- Full mission planning: 120s

**L2 Interruption on Queue Timeout**:
- Running L2 jobs: NOT interrupted (let them complete)
- Queued L2 jobs: rejected with QUEUE_TIMEOUT
- Rationale: interrupting running L2 wastes computation, let it finish

#### Scenario: Multi-device planning under load
- **WHEN** multiple devices are planned concurrently
- **THEN** the agent SHALL apply planning rate limits and queue excess requests; only run L2 on final candidate per device.

#### Scenario: Planning queue timeout
- **WHEN** planning request waits in queue > 30s
- **THEN** request SHALL be rejected with QUEUE_TIMEOUT(4001) error; caller may retry.

#### Scenario: Rate limit exceeded
- **WHEN** device exceeds 2 plans/minute limit
- **THEN** request SHALL be rejected with RATE_LIMITED(4002) error; include retry_after_seconds in response.
