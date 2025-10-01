# e-Rugah - Electronic Cooking Platform

## Overview

e-Rugah is a web-based marketplace platform that connects customers hosting events with professional chefs. The platform enables customers to create events, select menus, get matched with local chefs based on proximity, and complete bookings through M-PESA payment integration. Chefs can register their services, while administrators manage the system through chef approvals, menu management, and reporting capabilities.

**Core Value Proposition:** Simplify event catering by automating chef discovery, cost estimation, and secure payment processing.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Technology Stack:** Python Flask web framework with Jinja2 templating
- **Rationale:** Flask provides lightweight, flexible routing and easy integration with SQLAlchemy ORM
- **Frontend:** Server-side rendered HTML templates with Bootstrap 5 for responsive UI
- **Session Management:** Flask-Login for authentication state persistence

### Data Persistence Layer
- **Database:** SQLite with SQLAlchemy ORM
- **Design Pattern:** Relational model with clear entity relationships
- **Key Entities:**
  - **User:** Base authentication entity with role-based access (customer/chef/admin)
  - **Chef:** Extended profile for service providers with location and verification status
  - **Event:** Customer-created events with menu selections and cost calculations
  - **Booking:** Links events to chefs with deposit tracking
  - **MenuItem:** Admin-managed catalog with pricing and ingredients
  - **Payment:** M-PESA transaction records with status tracking
  - **OTP:** Temporary verification codes with expiration logic
  - **SystemConfig:** Dynamic configuration (e.g., deposit percentage)

**Architecture Decision:** One-to-many relationships between User→Chef, User→Event, Chef→Booking, Event→Booking. Menu items stored as comma-separated IDs in Event.menu_items for simplicity.

### Authentication & Authorization
- **Strategy:** Role-based access control (RBAC) with three distinct user types
- **Implementation:** 
  - Password hashing via Werkzeug security utilities
  - Custom `@role_required` decorator for route protection
  - Flask-Login for session management
- **Email Verification:** OTP-based verification for chef registrations
  - 6-digit codes with 5-minute expiration
  - Currently prints to console (simulated SMS/email)

### Business Logic: Chef Matching Algorithm
- **Proximity-based Matching:** Three-tier location hierarchy (County → Sub-County → Town)
- **Filtering Logic:**
  1. Match chefs in same county as event
  2. Prioritize sub-county matches
  3. Further filter by town if available
  4. Only show approved and verified chefs
- **Rationale:** Ensures customers get nearby chefs without complex geolocation dependencies

### Cost Calculation System
- **Event Costing:** Sum of (selected menu items × total guests)
- **Deposit Calculation:** Configurable percentage of total event cost (admin-managed)
- **Menu Pricing:** Per-person pricing model stored in MenuItem.price

### Payment Processing
- **Gateway:** M-PESA Daraja API (Safaricom's mobile money platform)
- **Flow:**
  1. Customer selects chef → system calculates deposit
  2. STK Push initiated with phone number and amount
  3. Callback handler updates payment status
  4. Booking status changes to "confirmed" on successful payment
- **Fallback:** Simulation mode when API credentials unavailable
- **Transaction Tracking:** All payments logged with M-PESA receipt numbers and timestamps

### Reporting & Analytics
- **Filtering Capabilities:** Date range, chef, location-based queries
- **Export Formats:** 
  - CSV for spreadsheet analysis
  - PDF via ReportLab library for formal reports
- **Metrics:** Total deposits collected, booking counts, chef performance

### Admin Management Interface
- **Chef Approval Workflow:** Two-stage verification (email OTP + admin approval)
- **Menu Management:** Full CRUD operations for menu items with categorization
- **System Configuration:** Dynamic settings (currently deposit percentage only)
- **Dashboard:** Summary statistics with pending approval queue

### Security Considerations
- **Password Storage:** Hashed using Werkzeug's generate_password_hash
- **Session Security:** Secret key-based session encryption (environment variable configurable)
- **OTP Expiration:** Time-limited codes prevent replay attacks
- **Role Enforcement:** Decorator-based route protection ensures privilege separation

**Design Trade-offs:**
- SQLite chosen for simplicity; may require migration to PostgreSQL for production scale
- Menu items stored as text field rather than junction table for development speed
- M-PESA simulation mode enables testing without live credentials
- Server-side rendering chosen over SPA for reduced frontend complexity

## External Dependencies

### Third-Party Services
1. **M-PESA Daraja API (Safaricom)**
   - Purpose: Mobile money payment processing
   - Integration: STK Push for customer payments
   - Configuration: Environment variables for consumer key, secret, shortcode, passkey
   - Endpoints: OAuth token generation, STK push requests, callback handling
   - Fallback: Simulation mode for development/testing

### Python Libraries
- **Flask** - Web framework and routing
- **Flask-SQLAlchemy** - ORM for database operations
- **Flask-Login** - User session management
- **Werkzeug** - Password hashing and security utilities
- **ReportLab** - PDF generation for reports
- **Requests** - HTTP client for M-PESA API calls

### Frontend Dependencies
- **Bootstrap 5.1.3** - CSS framework (CDN)
- **Bootstrap Icons** - Icon library (CDN)

### Environment Configuration
Required environment variables:
- `SESSION_SECRET` - Flask session encryption key
- `MPESA_CONSUMER_KEY` - Daraja API credentials
- `MPESA_CONSUMER_SECRET` - Daraja API credentials
- `MPESA_SHORTCODE` - Business shortcode
- `MPESA_PASSKEY` - API passkey
- `MPESA_API_URL` - OAuth endpoint
- `MPESA_STK_URL` - STK Push endpoint

**Note:** No email/SMS service currently integrated; OTP codes print to console for development.