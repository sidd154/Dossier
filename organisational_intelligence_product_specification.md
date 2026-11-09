# Product Specification — Organisational Intelligence Platform

**Document status:** Draft v1.0  
**Product type:** Internal organisational intelligence platform  
**Deployment model:** Single organisation  
**Primary backend:** Python / FastAPI  
**Primary data connectors:** Google Sheets, Zoho CRM

---

## 1. Product Overview

The product is an internal organisational intelligence platform for a single organisation.

It provides two primary user-facing capabilities:

1. **An organisation-aware chatbot** powered by Retrieval-Augmented Generation (RAG).
2. **A scheduled email engine** that sends configurable, department-specific communications to users.

An administrator configures the entire system through an Admin Console, including:

- Organisation details
- Users
- Departments
- Data connectors
- Data-source access
- Chatbot/RAG configuration
- LLM/model configuration
- Mail templates
- Mail schedules

The system synchronises configured organisational data sources on a daily basis. The resulting snapshots become part of the platform's internal data/knowledge layer.

The chatbot and mail engine use this common organisational knowledge layer while enforcing department-level access control.

---

# 2. Product Goals

## 2.1 Primary goals

- Give employees a single place to ask questions about organisational data.
- Make chatbot responses grounded in the organisation's actual data.
- Ensure users only retrieve data their department is permitted to access.
- Allow administrators to configure data sources without modifying application code.
- Synchronise external data sources automatically every day.
- Provide configurable scheduled organisational emails.
- Allow administrators to define who receives which emails.
- Allow administrators to configure mail templates.
- Allow the system's organisational knowledge to become increasingly current as new daily snapshots are ingested.
- Keep the product simple enough to operate as a single-organisation system.

## 2.2 Non-goals for the initial version

The following are explicitly outside the current scope unless requirements change:

- Multi-tenant SaaS architecture.
- Row-level permissions within a data source.
- Column-level permissions within a data source.
- Per-record access control.
- User-created accounts.
- A complex hierarchy of application roles.
- Continuous fine-tuning of the underlying LLM.

---

# 3. Core Product Principles

## 3.1 Single organisation

The product serves one organisation.

The organisation's configuration is stored within the application and is available to the knowledge layer.

## 3.2 Two application roles

There are only two system roles:

- `ADMIN`
- `USER`

The Admin configures the platform.

Users consume the platform.

## 3.3 Department-based data access

Departments are the primary data-access boundary.

An administrator defines which configured data sources a department can access.

Access is granted at the source/sheet/module level rather than individual rows or columns.

Example:

```text
Sales Department
  ├── Sales Google Sheet       ✓
  ├── Zoho CRM                 ✓
  ├── HR Google Sheet          ✗
  └── Finance Google Sheet     ✗
```

If a department has access to a sheet/source, the department receives access to that source as a whole.

## 3.4 Security before retrieval

Restricted data must not be retrieved and then filtered by the LLM.

The system must determine the user's department and permitted sources before retrieval.

Conceptually:

```text
User
  ↓
Authentication
  ↓
Department
  ↓
Permission Context
  ↓
Allowed Sources
  ↓
Retrieval
  ↓
LLM
  ↓
Answer
```

## 3.5 Restricted information should not be disclosed

If a user asks about information outside their permitted data scope, the system must not reveal that restricted information exists.

The product should avoid responses that disclose:

- the existence of restricted datasets,
- the names of inaccessible sources,
- restricted departments,
- restricted records,
- or details that could be inferred from restricted information.

The exact user-facing fallback response should be defined during chatbot UX design.

---

# 4. High-Level Architecture

```text
                         ┌─────────────────────────┐
                         │       ADMIN CONSOLE      │
                         │                         │
                         │ Organisation             │
                         │ Users                    │
                         │ Departments              │
                         │ Connectors               │
                         │ Permissions              │
                         │ Chatbot / RAG            │
                         │ Mail Templates           │
                         │ Mail Schedules           │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │      FASTAPI BACKEND     │
                         └────────────┬────────────┘
                                      │
              ┌───────────────────────┼──────────────────────┐
              │                       │                      │
              ▼                       ▼                      ▼
       ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
       │ PostgreSQL  │        │    Redis    │        │   Celery    │
       │ + pgvector  │        │             │        │   Workers   │
       └─────────────┘        └─────────────┘        └──────┬──────┘
                                                            │
                          ┌─────────────────────────────────┼──────────┐
                          │                                 │          │
                          ▼                                 ▼          ▼
                   Google Sheets                       Zoho CRM    Mail
                    Connector                          Connector   Engine
                          │                                 │
                          └───────────────┬─────────────────┘
                                          ▼
                                  Daily Data Snapshot
                                          │
                                          ▼
                                  Data / Knowledge Layer
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                         RAG / Retrieval          Mail Data
                              │
                              ▼
                             LLM
                              │
                              ▼
                           Chatbot
```

---

# 5. Technology Stack

## 5.1 Frontend

- **Next.js**
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**

The frontend provides:

- Admin Console
- User chatbot
- Configuration screens
- User/departments management
- Connector configuration
- Mail template configuration
- Schedule configuration
- Chat history/interface

## 5.2 Backend

- **Python**
- **FastAPI**

FastAPI is the main application/API layer.

Responsibilities include:

- Authentication
- Authorisation
- Admin APIs
- User APIs
- Connector configuration
- Data-source management
- Snapshot management
- RAG orchestration
- Chatbot APIs
- Mail configuration
- Schedule management

## 5.3 Database

- **PostgreSQL**
- **pgvector**

PostgreSQL is the primary application database.

It stores structured application data such as:

- Organisation configuration
- Users
- Departments
- Permissions
- Connector configuration
- Data-source metadata
- Snapshot metadata
- Mail templates
- Mail schedules
- Chatbot configuration
- Model configuration
- Audit information

pgvector is used for vector embeddings and semantic retrieval.

## 5.4 ORM and migrations

- **SQLAlchemy**
- **Alembic**

## 5.5 Background processing

- **Celery**
- **Redis**
- **Celery Beat**

Background processing is required for:

- Daily data synchronisation
- Snapshot processing
- Embedding generation
- Knowledge-index updates
- Scheduled mail execution
- Potential future maintenance jobs

## 5.6 RAG

The RAG implementation may use:

- **LlamaIndex**, or
- **LangChain**

The final choice should be made during implementation after defining the retrieval and data-normalisation requirements.

## 5.7 Connectors

Initial connectors:

- Google Sheets API
- Zoho CRM API

The connector system should be modular so additional sources can be added later without redesigning the application.

## 5.8 Email

Email sending should use a configurable email delivery mechanism, initially supporting SMTP or another selected organisational email provider.

## 5.9 Deployment

Initial deployment target:

- Linux
- Docker
- Nginx/reverse proxy

Monitoring can later include:

- Prometheus
- Grafana

---

# 6. Admin Console

The Admin Console is the control centre of the application.

## 6.1 Organisation Settings

The administrator can configure organisational information.

Potential fields include:

- Organisation name
- Organisation description
- Industry
- Locations
- Other organisation-specific information required by the product

This information contributes to the organisation's knowledge context.

The exact organisation metadata fields should be finalised before implementation.

## 6.2 User Management

Administrators create and manage users.

A user should have at minimum:

- Name
- Email
- Department
- System role
- Account status

Users are not responsible for creating their own accounts.

## 6.3 Department Management

Administrators create and configure organisational departments.

Examples:

```text
Management
Sales
Marketing
Finance
HR
Operations
```

Departments are configurable and are not hardcoded.

A department also acts as the primary access-control boundary for organisational data.

## 6.4 Data Connector Management

The Admin Console provides configuration for:

### Google Sheets

Potential configuration:

- Authentication/credentials
- Spreadsheet
- Sheet/tab
- Sync configuration
- Source metadata

### Zoho CRM

Potential configuration:

- Authentication
- Zoho account/connection
- CRM modules
- Sync configuration
- Source metadata

Exact connector fields will be defined during connector design.

## 6.5 Department Access Configuration

For each department, the administrator can select permitted data sources.

Example:

```text
Department: Marketing

Available Sources:

[✓] Marketing Performance Sheet
[✓] Campaign Sheet
[✗] Finance Sheet
[✗] HR Sheet
[✓] Zoho CRM Marketing Module
```

Access is source-level.

The product does not initially support:

- row-level access
- column-level access
- individual-record permissions

---

# 7. Data Source Model

A distinction should be maintained between:

## Connector

The external integration mechanism.

Examples:

```text
Google Sheets Connector
Zoho CRM Connector
```

## Data Source / Asset

A specific usable source exposed by a connector.

Examples:

```text
Google Sheets
  ├── Sales Report
  ├── Marketing KPIs
  ├── Finance Report
  └── HR Report

Zoho CRM
  ├── Leads
  ├── Deals
  ├── Contacts
  └── Accounts
```

This distinction is important because permissions are expected to operate on the usable source rather than simply on the existence of a connector.

---

# 8. Data Synchronisation

## 8.1 Synchronisation frequency

The initial system synchronises configured external data sources **once every day**.

The exact time should be configurable or defined as an operational deployment setting.

## 8.2 Snapshot model

The system should create a daily snapshot of synchronised data.

Conceptually:

```text
External Source
      ↓
Daily Sync
      ↓
Raw/normalised snapshot
      ↓
Processing
      ↓
Knowledge update
      ↓
Retrieval index
```

Snapshots should be identifiable by:

- Source
- Date/time
- Sync execution
- Status
- Record/item counts
- Processing status

## 8.3 Why snapshots exist

Snapshots provide:

- Consistent chatbot data
- Reduced dependency on live APIs
- Controlled API usage
- Reproducibility
- Potential historical analysis
- A clear basis for detecting changes

Whether the full historical snapshot data is retained indefinitely or subject to a retention policy must be decided later.

---

# 9. Organisation Knowledge Layer

The application should maintain a common knowledge/data layer used by both the chatbot and mail engine.

It consists conceptually of:

```text
Organisation Knowledge
│
├── Organisation Information
├── Department Information
├── User/Organisational Context
├── Data Source Metadata
├── Current Data
├── Snapshot Data
└── Indexed Knowledge
```

The goal is for the chatbot to become increasingly useful as the organisation's data is synchronised each day.

This does **not** mean continuously fine-tuning the LLM.

Instead:

```text
Stable LLM
      +
Updated organisational knowledge
      +
Current data snapshots
      +
Permission context
      =
Organisation-aware chatbot
```

---

# 10. RAG / Chatbot

## 10.1 Purpose

The chatbot allows users to ask natural-language questions about information available to their department.

Example questions could include:

- "How are sales performing?"
- "What were this month's numbers?"
- "Which deals are currently open?"
- "What is the current performance of our department?"

The exact supported query types depend on the configured data.

## 10.2 Chatbot pipeline

```text
User
 ↓
Authentication
 ↓
Identify Department
 ↓
Build Permission Context
 ↓
Understand Query
 ↓
Determine Relevant Sources
 ↓
Retrieve Only Permitted Data
 ↓
Construct Context
 ↓
LLM
 ↓
Response
```

## 10.3 Retrieval security

The system must enforce permissions at the retrieval/data layer.

It must not depend on an LLM prompt such as:

> "Do not reveal Finance information."

Instead:

```text
User Department
      ↓
Allowed Source IDs
      ↓
Retrieval filter
      ↓
Only permitted chunks/data
      ↓
LLM context
```

Restricted information should therefore never be placed into the LLM's context.

## 10.4 Organisation context

The chatbot should also have access to relevant organisation-level context configured by the administrator.

This can include:

- Organisation name
- Organisation description
- Industry
- Departments
- Other approved organisation information

The exact fields will be finalised during the knowledge-model design.

## 10.5 Model configuration

The LLM/model should be configurable rather than hardcoded into the product architecture.

The administrator should eventually be able to configure model-related settings from the Admin Console.

Exact configuration options remain to be defined.

---

# 11. Mail Engine

The mail engine is separate from the interactive chatbot.

Its responsibility is to generate and send scheduled organisational communications.

## 11.1 Mail flow

```text
Scheduled Job
      ↓
Identify Department / Recipient Rules
      ↓
Identify permitted data
      ↓
Retrieve relevant snapshot/data
      ↓
Apply mail template
      ↓
Generate final email
      ↓
Send
      ↓
Record execution/result
```

## 11.2 Scheduling

Mail schedules are configured by the administrator.

A schedule should conceptually contain:

- Schedule name
- Enabled/disabled state
- Frequency
- Execution time
- Department or recipient definition
- Data sources
- Mail template
- Other required configuration

Examples:

```text
Daily Sales Brief
Every day at 09:00
Recipients: Sales department
Sources: Sales Sheet + Zoho CRM
Template: Daily Sales Brief
```

## 11.3 Recipient management

The administrator determines who receives each scheduled email.

The application should not infer recipients solely from arbitrary external data unless explicitly configured to do so.

The exact recipient-selection model is still to be finalised.

---

# 12. Mail Templates

Mail templates are configurable through the Admin Console.

Templates may eventually support:

- Static content
- Variables
- Organisation information
- Data-derived values
- Department-specific content
- Potential AI-generated summaries

Example conceptual template:

```text
Hello {{user_name}},

Here is today's sales summary.

Revenue: {{sales.revenue}}
Deals: {{sales.deals}}
Conversion: {{sales.conversion}}

Regards,
{{organisation_name}}
```

The exact template engine and whether AI-generated prose is supported should be decided after defining the required email use cases.

---

# 13. Shared Data Security Model

Both chatbot and email processing must respect the same department-level data-access model.

Conceptually:

```text
                         Permission Model
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
             Chatbot                       Mail Engine
                │                             │
                ▼                             ▼
       Allowed Sources                 Allowed Sources
                │                             │
                ▼                             ▼
           Retrieval                      Retrieval
```

This prevents the chatbot and mail engine from implementing two different interpretations of access control.

---

# 14. Suggested Database Domains

The exact schema is still to be designed, but the database will likely contain entities/domains similar to:

```text
Organisation
User
Department

Connector
ConnectorCredential / Connection
DataSource
DataSourcePermission

SyncJob
Snapshot
SnapshotItem / NormalisedData

KnowledgeDocument
KnowledgeChunk
Embedding

ChatbotConfiguration
ModelConfiguration

MailTemplate
MailSchedule
MailExecution
MailRecipient

AuditLog
```

This is a conceptual domain model, not yet the final database schema.

---

# 15. Background Job Architecture

Celery workers should handle long-running or scheduled operations.

Potential jobs:

```text
sync_google_sheets
sync_zoho_crm

process_snapshot
generate_embeddings
update_knowledge_index

execute_mail_schedule
generate_mail_content
send_email
```

Celery Beat can trigger recurring jobs.

Redis can serve as the Celery broker and may also be used for application caching where appropriate.

---

# 16. Proposed Backend Module Structure

```text
backend/
│
├── app/
│   ├── api/
│   │
│   ├── auth/
│   ├── users/
│   ├── departments/
│   ├── permissions/
│   │
│   ├── organisation/
│   │
│   ├── connectors/
│   │   ├── base/
│   │   ├── google_sheets/
│   │   └── zoho_crm/
│   │
│   ├── ingestion/
│   ├── snapshots/
│   ├── knowledge/
│   ├── embeddings/
│   ├── retrieval/
│   ├── rag/
│   ├── chatbot/
│   │
│   ├── mail/
│   │   ├── templates/
│   │   ├── schedules/
│   │   ├── recipients/
│   │   └── sender/
│   │
│   ├── admin/
│   ├── database/
│   └── config/
│
├── workers/
│
├── migrations/
│
└── tests/
```

The structure is intended to keep connectors, permissions, ingestion, retrieval, chatbot, and mail processing independent.

---

# 17. Frontend Areas

The frontend should broadly contain:

```text
Application
│
├── Authentication
│
├── Admin
│   ├── Dashboard
│   ├── Organisation
│   ├── Users
│   ├── Departments
│   ├── Data Sources
│   ├── Permissions
│   ├── Chatbot / AI
│   ├── Mail Templates
│   ├── Mail Schedules
│   └── System / Sync Status
│
└── User
    └── Chatbot
```

Only Admin users should access administrative configuration.

Normal Users should primarily interact with the chatbot and other explicitly enabled user functionality.

---

# 18. Observability and Auditability

The product should eventually provide visibility into:

- Connector status
- Last successful sync
- Failed syncs
- Snapshot status
- Number of records/items processed
- Embedding/indexing status
- Scheduled mail execution
- Mail delivery result
- Configuration changes
- Administrative actions

An audit log should be considered part of the production architecture because this is an organisational data system.

---

# 19. Error Handling

The system should gracefully handle:

### Connector failures

```text
Google Sheets unavailable
Zoho API unavailable
Authentication expired
API rate limit
```

The previous successful snapshot should remain available rather than being silently replaced by an incomplete sync.

### Sync failures

A failed sync should be marked as failed and should not automatically make the existing knowledge unusable.

### Mail failures

Mail execution should record:

- Schedule
- Time
- Recipient
- Status
- Failure reason where applicable

### RAG failures

If retrieval or the LLM fails, the chatbot should provide a controlled error response rather than fabricate an answer.

---

# 20. Data Freshness

The system's data is intentionally snapshot-based.

The product should therefore make a distinction internally between:

- Last successful source synchronisation
- Current snapshot
- Historical snapshot
- Knowledge-index update status

The chatbot should not imply real-time data if the underlying source was last synchronised earlier.

The exact freshness indicator shown to users remains a UX decision.

---

# 21. Security Requirements

At minimum:

- Authentication required for all users.
- Admin-only access to configuration.
- Department-based data access enforced server-side.
- Connector credentials stored securely.
- Secrets must not be exposed to frontend clients.
- Retrieval must apply permission filters.
- Restricted data must not enter unauthorised LLM context.
- Logs must avoid exposing secrets or sensitive connector credentials.
- Administrative changes should be auditable.
- Email access must respect the same organisational permission model.
- External APIs must use secure authentication mechanisms.
- HTTPS should be used in production.

---

# 22. Important Architectural Decisions Already Made

These decisions should be treated as requirements unless explicitly changed:

| Decision | Requirement |
|---|---|
| Organisation model | Single organisation |
| Application roles | Admin + User |
| User creation | Admin creates users |
| Department model | Configurable by Admin |
| Access control | Department-based |
| Row permissions | Not supported initially |
| Column permissions | Not supported initially |
| Initial connectors | Google Sheets + Zoho CRM |
| Sync model | Daily |
| Data model | Snapshot-based |
| Chatbot | RAG |
| Chatbot permissions | Department/source based |
| Mail | Scheduled |
| Mail configuration | Admin |
| Mail recipients | Admin configured |
| Organisation context | Configured in Admin |
| Knowledge evolution | Daily data/knowledge updates, not continuous model fine-tuning |
| Deployment | Single-organisation application |

---

# 23. Requirements Still To Be Finalised

These areas have intentionally **not** been assumed.

## Authentication

Need to decide:

- Email/password vs SSO
- Password reset
- Session/JWT approach
- MFA requirement

## Google Sheets connector

Need to define:

- Authentication mechanism
- How spreadsheets are selected
- How tabs/sheets are selected
- Whether multiple spreadsheets are supported
- How schema changes are handled

## Zoho CRM connector

Need to define:

- Authentication mechanism
- Supported modules
- Which CRM fields are synchronised
- Multiple modules vs selected modules
- Relationship handling

## Snapshot retention

Need to decide:

- Whether every historical snapshot is retained
- Retention duration
- Whether historical snapshots are searchable
- Whether users can ask historical questions

## RAG strategy

Need to decide:

- Which data is embedded
- Which data remains structured
- Chunking strategy
- Metadata structure
- Hybrid search vs vector-only search
- Whether SQL-style structured queries are needed alongside semantic retrieval

## LLM strategy

Need to decide:

- Supported providers/models
- Whether the model is configurable per environment or through Admin
- Context limits
- Temperature and generation settings
- Fallback models

## Mail template system

Need to decide:

- Template syntax
- HTML support
- Variables
- Conditional logic
- AI-generated sections
- Preview functionality
- Test-send functionality

## Mail scheduling

Need to decide:

- Daily/weekly/monthly schedules
- Time zones
- Multiple schedules
- Retry behaviour
- Manual execution
- Pause/resume

## Recipient rules

Need to decide whether recipients can be selected by:

- Individual users
- Department
- Groups
- Explicit email addresses
- Data-derived recipient fields

## Chatbot behaviour

Need to define:

- Conversation history
- Citations/sources
- Tables and charts
- Follow-up questions
- Export/share functionality
- Conversation retention
- Feedback mechanism

---

# 24. Initial Product Success Criteria

The first production-ready version should be able to demonstrate the following end-to-end flow:

```text
1. Admin creates organisation configuration
        ↓
2. Admin creates departments
        ↓
3. Admin creates users
        ↓
4. Admin configures Google Sheets
        ↓
5. Admin configures Zoho CRM
        ↓
6. Admin selects accessible sources for each department
        ↓
7. System performs daily sync
        ↓
8. System creates snapshots
        ↓
9. System processes/indexes permitted knowledge
        ↓
10. User logs in
        ↓
11. User asks chatbot a question
        ↓
12. System identifies department
        ↓
13. System retrieves only permitted information
        ↓
14. LLM generates grounded response
        ↓
15. Admin creates a mail template
        ↓
16. Admin creates a mail schedule
        ↓
17. Scheduled job runs
        ↓
18. System retrieves permitted organisational data
        ↓
19. System generates/populates the email
        ↓
20. System sends it to configured recipients
        ↓
21. Execution is recorded
```

---

# 25. Architectural Philosophy

The product should be built around four clearly separated concerns:

```text
             ┌───────────────────────┐
             │       IDENTITY        │
             │ Users / Departments   │
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │       DATA            │
             │ Connectors / Snapshots│
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │       KNOWLEDGE       │
             │ RAG / Retrieval       │
             └───────────┬───────────┘
                         │
                  ┌──────┴──────┐
                  ▼             ▼
             ┌─────────┐   ┌──────────┐
             │ Chatbot │   │   Mail   │
             └─────────┘   └──────────┘
```

The **permission layer sits between identity and data access**, not inside the LLM.

The **data layer is shared** by chatbot and mail.

The **knowledge layer evolves as daily snapshots arrive**.

The **LLM is a reasoning/generation component, not the source of truth**.

The external systems remain the source of organisational data, while the application maintains controlled snapshots and an indexed representation for retrieval.

---

# 26. Guiding Principle

The system should behave as an **organisation-specific intelligence layer**, not simply as a chatbot connected to two APIs.

The long-term conceptual model is:

```text
External Organisational Data
          +
Organisation Configuration
          +
Department Permissions
          +
Daily Snapshots
          +
Knowledge / Retrieval
          +
LLM
          =
Organisational Intelligence Platform
```

The chatbot is one interface to that intelligence.

The scheduled mail engine is another.

The Admin Console is what allows the organisation to control both.
