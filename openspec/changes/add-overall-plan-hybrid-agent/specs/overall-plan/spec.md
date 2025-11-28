# Specification: Overall Disaster Plan Generation

## Overview

This specification defines the requirements for generating the 9 modules of "Overall Disaster Plan Element Setup" (总体救灾方案要素设置) that commanders submit to higher authorities for disaster situation reporting and resource requests.

## ADDED Requirements

### Requirement: Hybrid Agent Architecture

The system SHALL use a hybrid architecture combining CrewAI, MetaGPT, and LangGraph for overall disaster plan generation.

**Rationale**: Different modules require different processing approaches:
- Situational awareness (modules 0, 5) requires flexible, non-structured information synthesis → CrewAI
- Resource calculation (modules 1-4, 6-8) requires precise computation and SOP execution → MetaGPT
- Workflow orchestration and HITL requires state persistence → LangGraph

#### Scenario: Framework selection by task type

- **GIVEN** a disaster event requiring plan generation
- **WHEN** task requires situational awareness (module 0, 5)
- **THEN** system uses CrewAI for flexible information synthesis
- **AND** agents collaborate to extract key information from multiple sources

- **WHEN** task requires resource calculation (module 1-4, 6-8)
- **THEN** system uses MetaGPT with Data Interpreter for precise computation
- **AND** calculations follow SPHERE international humanitarian standards

#### Scenario: No silent fallback or mock outputs

- **GIVEN** CrewAI or MetaGPT fails to complete its task due to missing configuration, model errors, or runtime failures
- **WHEN** the system detects such a failure during plan generation
- **THEN** the system SHALL NOT silently fall back to a single LLM call or return template-only outputs with placeholders
- **AND** the system SHALL surface a `failed` status via the status API including a machine-readable error code and human-readable message
- **AND** the failure SHALL be logged with input snapshot and stack trace for later analysis

---

### Requirement: Human-in-the-Loop Review

The system SHALL pause for commander review before generating final document.

**Rationale**: AI cannot replace commander's responsibility for final decisions. Commanders may have additional information not available to the system.

#### Scenario: Commander reviews generated modules

- **GIVEN** system has generated all 9 modules
- **WHEN** generation completes
- **THEN** system pauses execution at checkpoint
- **AND** system persists state to PostgreSQL
- **AND** frontend can retrieve current module contents via API

#### Scenario: Commander modifies resource allocation

- **GIVEN** MetaGPT calculates tents = 5000 based on SPHERE standards
- **AND** commander knows neighboring province already sent 2000 tents
- **WHEN** commander modifies tents = 3000 in review interface
- **THEN** system accepts the modification
- **AND** system resumes with updated state when approved

#### Scenario: Commander approves without changes

- **GIVEN** commander reviews all 9 modules
- **WHEN** commander clicks "Approve" button
- **THEN** system resumes execution
- **AND** document generation proceeds with current state

#### Scenario: Commander rejects and requests re-generation

- **GIVEN** commander reviews all 9 modules
- **AND** determines that at least one module is fundamentally incorrect (e.g., uses wrong affected population)
- **WHEN** commander explicitly rejects the current plan via the review interface
- **THEN** system marks the workflow as `failed` and records commander feedback
- **AND** system SHALL NOT auto re-run the entire graph without explicit new trigger input (e.g., corrected disaster data)

---

### Requirement: State Persistence

The system SHALL persist workflow state to PostgreSQL using LangGraph Checkpointer.

**Rationale**: Commander review may take minutes to hours. System must survive server restarts.

#### Scenario: Server restart during commander review

- **GIVEN** system is waiting for commander approval
- **AND** all 9 modules have been generated
- **WHEN** server restarts
- **THEN** system recovers state from checkpoint
- **AND** commander can continue review without data loss
- **AND** no re-computation is required

#### Scenario: Multiple events under review

- **GIVEN** event A is awaiting approval
- **AND** event B is awaiting approval
- **WHEN** commander approves event A
- **THEN** only event A proceeds to document generation
- **AND** event B remains in awaiting state

#### Scenario: Stable thread and task identifiers

- **GIVEN** each event may have multiple plan-generation runs over time
- **WHEN** the system triggers a new overall-plan generation for an event
- **THEN** it SHALL create a stable `thread_id` for LangGraph and a corresponding `task_id` exposed via the API
- **AND** subsequent status / approve / document APIs SHALL address a specific run via this identifier, not only by `event_id`

---

### Requirement: SPHERE Standard Resource Estimation

The system SHALL calculate resource needs using international humanitarian standards.

**Rationale**: SPHERE standards are internationally recognized for disaster relief resource planning.

#### Scenario: Calculate shelter needs for 10000 affected population

- **GIVEN** affected population is 10000
- **AND** emergency duration is 3 days
- **WHEN** system calculates shelter needs
- **THEN** tents = 2000 (10000 / 5 persons per tent)
- **AND** blankets = 20000 (10000 * 2 per person)
- **AND** water = 600000 liters (10000 * 20L/day * 3 days)
- **AND** food = 15000 kg (10000 * 0.5kg/day * 3 days)

#### Scenario: Calculate rescue force for 500 trapped persons

- **GIVEN** trapped count is 500
- **WHEN** system calculates rescue force needs
- **THEN** rescue teams = 10 (500 / 50 persons per team)
- **AND** search dogs = 20 (10 teams * 2 dogs)
- **AND** rescue personnel = 300 (10 teams * 30 persons)

#### Scenario: Calculate medical resources for 200 injured

- **GIVEN** injured count is 200
- **AND** serious injury count is 50
- **WHEN** system calculates medical resource needs
- **THEN** medical staff = 10 (200 / 20 per staff)
- **AND** stretchers = 50 (1 per serious injury)
- **AND** ambulances = 4 (200 / 50 per ambulance)

#### Scenario: Missing or inconsistent input data

- **GIVEN** SPHERE-based estimators require numeric inputs such as affected population, trapped count, and injured count
- **WHEN** any required input is missing, negative, or clearly inconsistent (e.g., serious injuries > total injured)
- **THEN** the estimator SHALL raise a validation error instead of returning default zeros or partial estimates
- **AND** the overall plan generation SHALL fail fast with a clear error surfaced via the status API

---

### Requirement: Module 0 - Basic Disaster Situation

The system SHALL generate a structured basic disaster situation report.

#### Scenario: Generate module 0 for earthquake event

- **GIVEN** an earthquake event with EmergencyAI analysis
- **WHEN** CrewAI processes the event data
- **THEN** output includes:
  - Disaster name, type, and occurrence time
  - Magnitude and epicenter depth
  - Affected area and scope
  - Casualty statistics (deaths, injuries, missing, trapped)
  - Building damage assessment
  - Infrastructure damage assessment

---

### Requirement: Module 5 - Secondary Disaster Prevention

The system SHALL identify secondary disaster risks and provide prevention measures.

#### Scenario: Identify aftershock risk

- **GIVEN** a major earthquake event (magnitude >= 6.0)
- **WHEN** CrewAI analyzes secondary disaster risks
- **THEN** aftershock risk is identified
- **AND** prevention measures are provided
- **AND** monitoring recommendations are included

#### Scenario: Identify multiple secondary disaster types

- **GIVEN** earthquake in mountainous area with nearby chemical plants
- **WHEN** CrewAI analyzes secondary disaster risks
- **THEN** following risks are identified:
  - Aftershock
  - Landslide / debris flow
  - Dam/reservoir failure
  - Chemical leak
- **AND** each risk has specific prevention measures

#### Scenario: Structured output for downstream processing

- **GIVEN** downstream MetaGPT and document-generation components consume CrewAI outputs
- **WHEN** CrewAI generates module 0 and module 5 content
- **THEN** the output SHALL be parsable into a predefined JSON schema (for example, fields for risk type, risk level, and recommended measures)
- **AND** free-form narrative text MAY be included in addition but SHALL NOT replace the structured fields required by downstream consumers

---

### Requirement: Modules 1-4, 6-8 - Resource Request Sections

The system SHALL generate professional resource request text for each module.

#### Scenario: Generate module 1 - Emergency Rescue Force

- **GIVEN** rescue force calculation from estimator
- **WHEN** MetaGPT generates module 1
- **THEN** text includes:
  - Recommended rescue team allocation by region
  - Equipment requirements per team
  - Deployment timeline suggestion
  - Professional terminology following ICS standards

#### Scenario: Generate module 4 - Temporary Shelter

- **GIVEN** shelter calculation from SPHERE standards
- **WHEN** MetaGPT generates module 4
- **THEN** text includes:
  - Tent allocation by affected area
  - Living supplies distribution plan
  - Water and food logistics plan
  - Calculation basis reference

#### Scenario: Deterministic numerical outputs

- **GIVEN** numeric estimations (tents, teams, personnel, vehicles, water, food, etc.) are derived from SPHERE standards and simple formulas
- **WHEN** the same structured input data is provided for repeated runs
- **THEN** the numeric results in modules 1-4 and 6-8 SHALL be identical between runs (barring explicit configuration changes)
- **AND** only the explanatory natural language around those numbers MAY vary between runs

---

### Requirement: Final Document Generation

The system SHALL generate a formal official document after commander approval.

#### Scenario: Generate final plan document

- **GIVEN** commander has approved all 9 modules
- **WHEN** system generates final document
- **THEN** document includes all 9 modules in standard format
- **AND** document includes proper headers and footers
- **AND** document is suitable for official submission

---

## API Specifications

### GET /api/overall-plan/{event_id}/modules

**Purpose**: Trigger plan generation and return task ID

**Response**:
```json
{
  "task_id": "uuid",
  "status": "running",
  "event_id": "event-uuid"
}
```

### GET /api/overall-plan/{event_id}/status

**Purpose**: Query generation status

**Response**:
```json
{
  "status": "awaiting_approval",
  "modules": [
    {"index": 0, "title": "灾情基本情况", "value": "..."},
    {"index": 1, "title": "应急救援力量部署", "value": "..."},
    ...
  ],
  "calculation_details": {...}
}
```

**Status values**: `pending`, `running`, `awaiting_approval`, `completed`, `failed`

### PUT /api/overall-plan/{event_id}/approve

**Purpose**: Commander approves and optionally modifies modules

**Request**:
```json
{
  "approved": true,
  "feedback": "Optional commander feedback",
  "modifications": {
    "module_4_shelter": "Modified shelter text..."
  }
}
```

### GET /api/overall-plan/{event_id}/document

**Purpose**: Retrieve final generated document

**Response**:
```json
{
  "document": "Full markdown document content",
  "generated_at": "2025-11-28T12:00:00Z"
}
```

---

## Data Flow

```
events_v2 + EmergencyAI + resources
           │
           ▼
    ┌──────────────┐
    │ load_context │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   CrewAI     │ → Module 0, 5
    │ (态势感知)   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   MetaGPT    │ → Module 1-4, 6-8
    │ (资源计算)   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  CHECKPOINT  │ ← Commander review
    └──────┬───────┘
           │ (after approval)
           ▼
    ┌──────────────┐
    │   MetaGPT    │ → Final document
    │ (公文生成)   │
    └──────────────┘
```

---

## References

- SPHERE Handbook: https://handbook.spherestandards.org/
- ICS Forms: https://training.fema.gov/emiweb/is/icsresource/
- Architecture Selection Document: `docs/agent架构选型/灾害预测与汇报LLM工具选择.md`
