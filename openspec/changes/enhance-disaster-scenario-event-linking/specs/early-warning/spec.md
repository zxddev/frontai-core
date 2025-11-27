# Early Warning Spec Delta

## MODIFIED Requirements

### Requirement: Disaster Data Ingestion
The system SHALL receive disaster situation data from third-party systems and process it with scenario and event linking.

When disaster data is received:
1. Create disaster_situations record with boundary geometry
2. Link to scenario (specified or auto-discovered)
3. Create event if needs_response=true and severity>=3
4. Create danger_zone map entity for visualization
5. Query affected teams/vehicles within buffer distance
6. Generate warning records for affected entities
7. Push WebSocket notifications

#### Scenario: Disaster with specified scenario_id
- **GIVEN** third-party system sends disaster update with scenario_id
- **WHEN** the system receives POST /disasters/update
- **THEN** disaster record is linked to specified scenario
- **AND** event is created if needs_response=true and severity>=3
- **AND** danger_zone entity is created for map rendering
- **AND** WebSocket notification is pushed to /topic/scenario.disaster.triggered

#### Scenario: Disaster without scenario_id - auto-discover
- **GIVEN** third-party system sends disaster update without scenario_id
- **WHEN** the system receives POST /disasters/update
- **AND** an active scenario exists covering the disaster location
- **THEN** disaster record is auto-linked to the discovered scenario
- **AND** event is created if needs_response=true and severity>=3

#### Scenario: Warning-only disaster (no response needed)
- **GIVEN** third-party system sends disaster update with needs_response=false
- **WHEN** the system receives POST /disasters/update
- **THEN** disaster record is created
- **AND** warning records are generated for affected teams
- **AND** NO event is created (warning-only, e.g., weather alert)

#### Scenario: High-severity disaster without matching scenario
- **GIVEN** third-party system sends disaster update with severity>=4
- **WHEN** no active scenario covers the disaster location
- **THEN** response includes suggestion to create new scenario
- **AND** disaster record is created without scenario link

## ADDED Requirements

### Requirement: Map Entity Integration
The system SHALL create map entities for disaster visualization.

#### Scenario: Danger zone creation
- **GIVEN** disaster with polygon boundary is created
- **WHEN** update_disaster processing completes
- **THEN** danger_zone entity is created in map_entities
- **AND** entity geometry matches disaster boundary
- **AND** WebSocket pushes to /topic/map.entity.create

### Requirement: Event Auto-Creation
The system SHALL automatically create events for disasters requiring response.

#### Scenario: Event created for high-severity disaster
- **GIVEN** disaster with needs_response=true and severity>=3
- **WHEN** update_disaster processing completes
- **THEN** event is created in events_v2 table
- **AND** event.scenario_id matches disaster.scenario_id
- **AND** event type is derived from disaster_type
- **AND** linked_event_id is stored in disaster record

#### Scenario: No event for warning-only disaster
- **GIVEN** disaster with needs_response=false
- **WHEN** update_disaster processing completes
- **THEN** NO event is created
- **AND** linked_event_id remains null

### Requirement: Scenario Association
The system SHALL associate disasters with scenarios for unified command structure.

#### Scenario: Manual scenario specification
- **GIVEN** request includes scenario_id parameter
- **WHEN** update_disaster is called
- **THEN** disaster.scenario_id is set to specified value

#### Scenario: Auto-discovery by location
- **GIVEN** request does not include scenario_id
- **WHEN** active scenario exists with area covering disaster location
- **THEN** disaster is linked to discovered scenario

#### Scenario: No scenario found
- **GIVEN** request does not include scenario_id
- **WHEN** no active scenario covers the disaster location
- **THEN** disaster.scenario_id remains null
- **AND** response includes warning message
