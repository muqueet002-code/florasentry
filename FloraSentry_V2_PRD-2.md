# FloraSentry V2 — Product Requirements Document (PRD)

**Project:** FloraSentry V2  
**SIH Problem Statement:** SIH26131 — Early detection and management of crop diseases and pest infestations  
**Theme:** Agriculture, FoodTech & Rural Development  
**Target geography:** Maharashtra, India (MVP), extensible to other regions  
**Document status:** Product blueprint / MVP PRD

---

## 1. Product Overview

FloraSentry V2 is an AI-powered crop-health intelligence and decision-support platform designed to help farmers and agricultural extension workers detect crop diseases and pest infestations earlier, understand local risk, receive safer management guidance, and enable officials to monitor emerging hotspots.

The system combines:

- Image-based symptom identification
- Pest-trap and sensor-ready observations
- Weather-based risk forecasting
- Crop and field context
- Geospatial mapping and hotspot analysis
- Expert validation
- Multilingual advisories
- Integrated Pest Management (IPM)
- Follow-up monitoring
- Official dashboards

### Core principle

> **Detection is not the destination. Decision support is.**

The system must clearly distinguish AI predictions from expert-confirmed diagnoses and real observations from simulated/demo data.

---

## 2. Problem Statement

Farmers may recognize crop diseases or pest infestations only after visible damage has spread. Extension staff may cover large areas, while laboratory diagnosis and expert advice may not be immediately available.

Risk is influenced by factors such as:

- Weather
- Crop stage
- Variety
- Soil/field condition
- Location
- Local disease/pest history
- Pest-trap or sensor observations

These signals are often not combined into actionable farm-level alerts.

Incorrect or delayed diagnosis can contribute to:

- Delayed treatment
- Excessive or inappropriate pesticide use
- Increased cultivation cost
- Residue concerns
- Crop loss

FloraSentry V2 addresses this by connecting field observations, AI, contextual risk, GIS intelligence, expert validation, and management support in one workflow.

---

## 3. Goals

### Primary goals

1. Detect crop disease/pest symptoms earlier using field observations and AI.
2. Combine AI results with crop, field, weather, and historical context.
3. Provide locally relevant risk assessment and forecasting.
4. Map observations and identify potential hotspots.
5. Route uncertain cases to experts or laboratories.
6. Provide multilingual, IPM-oriented management guidance.
7. Track follow-up observations and outcomes.
8. Provide agriculture officials with surveillance and prioritization dashboards.
9. Build a feedback loop from confirmed field observations.

### MVP success criteria

A judge should be able to see one complete flow:

**Crop/Field → Image → AI Prediction → GPS → Weather → Risk → GIS Map → Advisory → Expert Validation → Follow-up → Official Dashboard**

---

## 4. Non-Goals / Scope Control

The MVP will NOT attempt to:

- Diagnose every crop and disease in India.
- Claim clinical/laboratory-level diagnosis from an image.
- Claim scientifically validated field accuracy without field validation.
- Build a complete IoT hardware ecosystem.
- Build a nationwide outbreak database from scratch.
- Provide blindly prescriptive pesticide recommendations.
- Depend on satellite imagery for the core demo.
- Build unnecessary microservices.
- Treat simulated data as real-world observations.

Advanced satellite, IoT, large-scale forecasting, and additional crops/diseases can be future extensions.

---

## 5. Target Users

### 5.1 Farmer

Needs:

- Simple crop-health check
- Easy image/report submission
- Understandable risk alerts
- Local-language guidance
- Safe management suggestions
- Expert help when uncertain
- Follow-up reminders

### 5.2 Extension Worker / Agriculture Expert

Needs:

- Review queue
- AI prediction details
- Location and field context
- Weather/risk context
- Confirm/correct diagnosis
- Lab referral
- Advisory review
- Follow-up monitoring

### 5.3 Government / Agriculture Official

Needs:

- District/region surveillance
- Disease and pest distribution
- Hotspots
- Risk zones
- Trends
- Pending validation
- Priority intervention zones
- Surveillance coverage

### 5.4 Laboratory / Diagnostic Expert

Needs:

- Referral cases
- Sample/observation context
- Diagnostic result recording
- Confirmation status

### 5.5 Administrator

Needs:

- User/role management
- Data-source management
- System configuration
- Model/version management
- Audit logs

---

## 6. Product Modules

### 6.1 Farmer Application

- Home
- My Fields
- Crop details
- Check Crop Health
- Image/report submission
- AI analysis result
- Alerts
- Weather
- Advisory
- My Reports
- Follow-up
- Expert Help
- Language selection

### 6.2 AI Detection

Pipeline:

`Image → Validation → Preprocessing → Model Inference → Prediction → Confidence → Result`

Capabilities:

- Disease classification/detection
- Pest identification where supported
- Confidence score
- Optional severity estimation
- Unsupported/poor-quality image handling
- Model version tracking

### 6.3 Context Engine

Inputs:

- Crop
- Variety
- Growth stage
- Field
- Location
- Soil/field context
- Historical observations
- AI prediction
- Weather
- Pest-trap/sensor observations

### 6.4 Weather Engine

Provides:

- Current conditions
- Forecast
- Historical weather where available
- Temperature
- Humidity
- Rainfall
- Wind
- Relevant additional variables

The provider must be replaceable.

### 6.5 Risk Engine

Combines contextual signals into an explainable risk assessment.

Example:

`AI signal + Weather + Crop Stage + Historical Local Observations + Field Context → Risk`

Outputs:

- Risk score
- Risk level
- Forecast period
- Contributing factors
- Explanation
- Uncertainty where available

The MVP may use a transparent configurable rule-based model. It must be architected so a trained model can replace it later.

### 6.6 GIS Intelligence

Layers:

- Field locations
- Observation points
- Confirmed cases
- AI-predicted cases
- Disease distribution
- Pest distribution
- Risk zones
- Hotspots
- Historical spread
- Priority intervention zones

Spatial foundation:

- PostgreSQL
- PostGIS
- Spatial indexes
- GeoPandas where useful
- Leaflet frontend mapping

### 6.7 Expert Validation

Workflow:

`AI Prediction → Confidence Check → Preliminary Result OR Expert Review → Confirm/Correct → Verified Observation`

Statuses:

- PREDICTED
- PENDING_REVIEW
- CONFIRMED
- CORRECTED
- REJECTED
- LAB_REFERRED

### 6.8 Advisory Engine

Advisories should prioritize:

- IPM
- Cultural practices
- Mechanical/physical controls
- Biological controls
- Prevention
- Safe input-use guidance
- Expert/lab referral

The system must not present an uncertain AI prediction as a confirmed diagnosis.

Languages:

- English
- Hindi
- Marathi

### 6.9 Follow-up Monitoring

Workflow:

`Initial Observation → Action → Follow-up → New Observation/Image → Better/Same/Worse → Outcome`

### 6.10 Official Dashboard

Metrics and views:

- Active observations
- Confirmed cases
- Pending reviews
- Disease distribution
- Pest distribution
- High-risk zones
- Hotspots
- Trends
- Affected area
- Surveillance coverage
- Priority intervention zones

---

## 7. Real Data Strategy

The mapping system must not rely on unexplained fabricated points.

### 7.1 Real field observations

The primary operational data source should be observations collected through the platform by farmers/extension workers.

Minimum observation flow:

1. Select field
2. Select crop
3. Select variety
4. Select growth stage
5. Capture/upload image
6. Capture GPS
7. Add optional severity/notes
8. AI analysis
9. Confidence assessment
10. Expert validation if required
11. Store observation
12. Update GIS
13. Recalculate risk
14. Generate advisory
15. Schedule follow-up

### 7.2 Public/government data

Candidate categories:

- Administrative boundaries
- Agricultural statistics
- Crop distribution
- Disease/pest reports
- Weather
- Soil
- Land use
- Geospatial datasets

Every source must be verified during implementation. No dataset/API should be represented as official or live without verification.

### 7.3 Training data

Training data is separate from GIS outbreak/observation data.

Plant disease datasets such as PlantVillage may support model development, but controlled image datasets should not automatically be treated as Maharashtra field outbreak data.

### 7.4 Demo/simulated data

For the SIH prototype, simulated observations may be used to demonstrate map/hotspot functionality when real field observations are insufficient.

They must be explicitly marked:

`DEMO_SIMULATION`

The UI/database must preserve provenance.

---

## 8. Data Provenance

Every observation should record its source.

Suggested source types:

- FIELD_OBSERVATION
- PUBLIC_DATA
- GOVERNMENT_DATA
- EXPERT_VALIDATION
- DEMO_SIMULATION

Important metadata:

- Source
- Created by
- Created at
- Verification status
- Model version
- Expert reviewer
- Original observation/reference if applicable

UI should distinguish:

- Live/real
- Historical
- Simulated
- Predicted
- Expert-confirmed

---

## 9. Core Data Model

Candidate entities:

- User
- Role
- Farmer
- Field
- Crop
- Crop Variety
- Growth Stage
- Observation
- Image
- AI Prediction
- Disease
- Pest
- Symptom
- Weather Observation
- Weather Forecast
- Risk Assessment
- Expert Review
- Advisory
- Intervention
- Follow-up
- Pest Trap Observation
- Sensor Observation
- Hotspot
- Priority Zone
- Data Source
- Audit Log

### Observation

Important fields:

- ID
- Farmer/user
- Field
- Crop
- Variety
- Growth stage
- Image
- AI prediction
- Severity
- Latitude/longitude
- PostGIS geometry
- Timestamp
- Source
- Verification status
- Notes

### AI Prediction

- Model version
- Predicted class
- Confidence
- Optional severity
- Prediction timestamp
- Image reference

### Risk Assessment

- Observation/field reference
- Risk score
- Risk level
- Forecast period
- Contributing factors
- Method/model version
- Generated timestamp

---

## 10. GIS Requirements

### Spatial data

Use PostGIS geometry.

Observation points should support:

- Latitude/longitude
- Point geometry
- Field association
- Administrative region association where available

Fields may use polygons when available.

### Required spatial queries

- Nearby observations
- Observations inside a field
- Observations inside an administrative area
- Disease-specific observations
- Pest-specific observations
- Recent observations
- Observations within a radius
- Confirmed cases near a location

### Hotspots

Hotspots should combine:

- Spatial clustering
- Time window
- Observation density
- Severity where available
- Confirmed vs predicted status

The system must distinguish:

**Confirmed hotspot**

from

**Predicted/signal hotspot**

Hotspot logic is decision support and should not be represented as scientifically validated outbreak detection without expert validation.

---

## 11. AI Requirements

### MVP principle

Support a limited, defensible set of crops and diseases/pests based on available data.

The supported class list must be explicit.

### Required behavior

For each image:

- Validate image
- Run inference
- Return prediction
- Return confidence
- Store model version
- Flag low confidence
- Handle unsupported/poor-quality images

### Confidence-aware workflow

High-confidence result:

`AI Preliminary Assessment → Advisory / Expert option`

Low-confidence result:

`AI Result → Expert/Lab Referral`

The system must never claim that a prediction is confirmed simply because the model returned a class.

---

## 12. Risk Forecasting Requirements

### Inputs

- AI observation
- Crop
- Variety
- Growth stage
- Location
- Weather
- Historical local observations
- Soil/context
- Pest-trap/sensor data where available

### Outputs

- Risk score
- Low / Medium / High level
- Forecast period
- Contributing factors
- Explanation

Example explanation:

> Risk increased due to recent rainfall, elevated humidity, and nearby confirmed observations.

Risk thresholds must be configurable and clearly labeled as prototype/decision-support logic until validated.

---

## 13. Advisory Requirements

Every advisory should contain:

1. What was observed
2. AI confidence / confirmation status
3. Risk/severity context
4. Recommended IPM actions
5. Prevention
6. Safe input-use guidance where appropriate
7. When to seek expert/lab help
8. Follow-up recommendation

Avoid unsupported claims.

---

## 14. Multilingual Requirements

Initial languages:

- English
- Hindi
- Marathi

Requirements:

- No hard-coded user-facing strings where possible
- Translation keys
- Language preference
- Expandable localization architecture

---

## 15. Notification / Alert Requirements

Potential alerts:

- High-risk crop condition
- Nearby confirmed case
- Follow-up due
- Expert response
- Risk forecast change
- New local hotspot

Notifications should be useful and non-spammy.

---

## 16. Frontend Requirements

### Farmer UI

Prioritize:

- Simplicity
- Clear language
- Mobile responsiveness
- Large primary actions
- Minimal technical terminology

Primary navigation:

- Home
- My Fields
- Check Health
- Reports
- Alerts
- Advisory
- Expert Help

### Expert UI

Prioritize:

- Review queue
- Case context
- Map
- AI result
- Confirm/correct
- Referral
- Follow-up

### Official UI

Prioritize:

- GIS map
- Trends
- Risk
- Hotspots
- Confirmed vs predicted
- Priority zones
- Surveillance metrics

---

## 17. API Requirements

API groups:

### Authentication

- Login
- Registration
- Role management

### Fields/Crops

- Create field
- List fields
- Field details
- Crop assignment

### Observations

- Create observation
- Upload image
- Get observation
- List observations
- Update status

### AI

- Analyze image
- Get prediction
- Model information

### Weather

- Current weather
- Forecast
- Historical data where supported

### Risk

- Calculate risk
- Get risk history
- Get field risk

### GIS

- Observation points
- Hotspots
- Risk zones
- Priority zones
- Spatial filtering

### Expert

- Review queue
- Review case
- Confirm
- Correct
- Reject
- Refer to lab

### Advisory

- Generate/get advisory
- Localized advisory

### Follow-up

- Create follow-up
- Submit follow-up
- Compare observations

### Dashboard

- Farmer metrics
- Expert metrics
- Official metrics

---

## 18. Technical Architecture

### Frontend

- React
- Tailwind CSS
- Leaflet
- Existing reusable FloraSentry components where practical

### Backend

- FastAPI
- Python
- Modular application architecture

### Database

- PostgreSQL
- PostGIS

### AI

- PyTorch
- Ultralytics/YOLO where appropriate
- OpenCV

### Data/GIS

- GeoPandas
- PostGIS
- QGIS for data preparation/analysis when useful

### ML

- scikit-learn
- XGBoost where appropriate

Avoid introducing additional technologies unless there is a concrete requirement.

Prefer a modular monolith for the MVP.

---

## 19. Security & Reliability

Requirements:

- Authentication
- Role-based authorization
- Secure image upload
- File type/size validation
- Input validation
- API error handling
- Secret management
- Environment variables
- Audit logs
- Database backups
- Appropriate rate limiting
- Model/API failure handling

---

## 20. Performance Requirements

Initial target requirements:

- Image submission should provide clear progress/status.
- AI response should be suitable for interactive use.
- GIS map should update after a new observation is stored.
- Dashboard queries should be indexed.
- Spatial queries must use PostGIS indexes.
- Large image files should not be stored directly in database rows.

Exact performance targets should be measured rather than fabricated.

---

## 21. Observability

Log:

- API errors
- AI inference failures
- Weather provider failures
- GIS processing failures
- Authentication failures
- Expert actions
- Important data changes

Track:

- prediction count
- low-confidence rate
- expert confirmation rate
- failed inference rate
- API latency
- weather API availability

---

## 22. MVP Priority

### MUST HAVE

- Farmer/field creation
- Crop context
- Image upload
- AI disease/pest prediction for limited supported classes
- Confidence score
- GPS observation
- PostGIS storage
- Weather integration
- Explainable risk engine
- GIS observation map
- Basic hotspot/risk visualization
- Expert validation workflow
- IPM-oriented advisory
- English/Hindi/Marathi support
- Follow-up observation
- Official dashboard
- Real vs demo data provenance

### SHOULD HAVE

- Pest-trap input
- Sensor-ready data model
- Advanced hotspot analysis
- Better severity estimation
- Notifications
- Advanced trend analytics

### FUTURE

- IoT hardware integration
- Satellite-derived crop stress
- Large-scale trained risk model
- More crops/diseases/pests
- Advanced forecasting
- Wider state/national deployment
- Automated extension workflows

---

## 23. End-to-End Demo

### Scenario

1. Farmer opens FloraSentry.
2. Selects a field.
3. Selects crop, variety and growth stage.
4. Uploads a field image.
5. AI analyzes the image.
6. System displays disease/pest prediction and confidence.
7. GPS is attached.
8. Weather is retrieved.
9. Risk engine evaluates contextual risk.
10. Observation is stored in PostGIS.
11. Map updates with the observation.
12. Nearby hotspot/risk information is displayed.
13. Farmer receives IPM-oriented advisory.
14. If confidence is low, case is sent for expert/lab review.
15. Expert confirms/corrects the observation.
16. Follow-up is scheduled.
17. Farmer submits a follow-up observation.
18. Official dashboard updates with the new confirmed case/risk signal.

---

## 24. Development Phases

### Phase 0 — Architecture & Data Strategy

Output:

- Codebase audit
- Architecture
- Data strategy
- Database design
- API contracts
- AI strategy
- GIS strategy
- MVP scope

No implementation.

### Phase 1 — Backend + Database

Build:

- FastAPI foundation
- PostgreSQL/PostGIS
- Authentication
- Users/roles
- Fields
- Crops
- Observations
- Images

### Phase 2 — AI Detection

Build:

- Image pipeline
- Model interface
- Inference
- Confidence
- Prediction storage
- Supported classes
- Low-confidence handling

### Phase 3 — Weather + Risk

Build:

- Weather provider integration
- Weather storage/cache
- Risk engine
- Risk explanations

### Phase 4 — GIS + Hotspots

Build:

- PostGIS queries
- Observation map
- Layers
- Hotspots
- Risk zones
- Priority zones

### Phase 5 — Expert Validation

Build:

- Review queue
- Confirm/correct/reject
- Lab referral
- Verification history

### Phase 6 — Advisory + Multilingual

Build:

- IPM advisory engine
- Safe input guidance
- Referral
- English/Hindi/Marathi localization

### Phase 7 — Follow-up

Build:

- Follow-up records
- New images
- Condition comparison
- Outcome tracking

### Phase 8 — Dashboards

Build:

- Farmer dashboard
- Expert dashboard
- Official dashboard
- Trends
- Priority areas

### Phase 9 — Frontend Integration

Integrate:

- APIs
- AI
- weather
- risk
- GIS
- expert workflow
- advisory
- follow-up

### Phase 10 — Testing + Deployment

Test:

- APIs
- Database
- AI
- GIS
- Security
- UI
- Error handling
- End-to-end flow

Deploy a stable demo environment.

### Phase 11 — SIH Demo Preparation

Prepare:

- Demo dataset with provenance
- Complete demo flow
- Architecture explanation
- SIH requirement mapping
- Technical documentation
- Judge questions
- Limitations
- Future roadmap

---

## 25. Acceptance Criteria

The MVP is considered functional when:

### Farmer

- Can create/select a field.
- Can specify crop context.
- Can submit an image.
- Can receive an AI prediction with confidence.
- Can view weather/risk.
- Can view advisory.
- Can see their report and follow-up.

### GIS

- Observation has a valid geographic location.
- Observation appears on the map.
- Confirmed and predicted observations can be distinguished.
- Spatial filtering works.
- Hotspot/risk visualization works on available data.

### Expert

- Can see pending cases.
- Can confirm/correct/reject a prediction.
- Can refer a case to a laboratory.
- Validation status is stored.

### Official

- Can view observations.
- Can view hotspots/risk zones.
- Can filter by crop/disease/pest/time/area.
- Can see confirmed vs predicted cases.
- Can see priority intervention areas.

### Data integrity

- Every observation has provenance.
- Demo data is not represented as real.
- AI predictions are distinct from confirmed diagnoses.
- Model version is stored.

---

## 26. Key Risks & Mitigation

### Risk: Insufficient field images

Mitigation:
- Start with limited supported classes.
- Use public datasets for initial model development.
- Collect/validate field observations.
- Clearly report field-validation limitations.

### Risk: AI performs poorly on real images

Mitigation:
- Confidence-aware workflow.
- Expert/lab referral.
- Field validation dataset.
- Model versioning.
- Avoid unsupported classes.

### Risk: Lack of real geographic disease data

Mitigation:
- Build the real field-observation pipeline.
- Use verified public/government data when available.
- Clearly label demo simulations.
- Never fabricate real outbreak claims.

### Risk: Weather API dependency

Mitigation:
- Provider abstraction.
- Caching.
- Graceful fallback.
- Clearly label stale/demo data.

### Risk: Incorrect advisory

Mitigation:
- IPM-first recommendations.
- Avoid unsupported pesticide prescriptions.
- Expert/lab referral.
- Clearly distinguish preliminary AI output from confirmation.

### Risk: Over-scoping

Mitigation:
- Limited crops/classes.
- One complete vertical slice.
- Defer IoT/satellite/advanced ML.

### Risk: Over-reliance on controlled datasets

Mitigation:
- Field-image validation.
- Transparent model limitations.
- Expert confirmation.
- Do not transfer controlled-dataset accuracy directly to field claims.

---

## 27. Product Principles

1. **Real data over impressive fake data.**
2. **Explainability over black-box claims.**
3. **Decision support over simple classification.**
4. **Expert confirmation over false certainty.**
5. **Small working MVP over huge incomplete scope.**
6. **Farmer simplicity over technical complexity.**
7. **Modular architecture over unnecessary complexity.**
8. **Every map point should have provenance.**
9. **Predicted risk is not confirmed outbreak.**
10. **The system should improve as field confirmations accumulate.**

---

## 28. Final Product Statement

FloraSentry V2 is a field-oriented crop-health decision-support platform that connects:

**AI Detection + Real Field Observations + Weather + Crop Context + GIS + Risk Forecasting + Expert Validation + IPM Advisory + Follow-up Monitoring**

into one continuous surveillance and management workflow.

Its key differentiator is not merely image classification.

The platform turns an individual crop-health observation into a geographically and contextually informed decision-support signal for farmers, extension workers, and agriculture officials.
