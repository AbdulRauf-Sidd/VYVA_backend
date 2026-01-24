# Vyva Backend - FastAPI Production Template

A production-ready FastAPI backend template designed for senior care applications with modular architecture, JWT authentication, WebSocket streaming, and comprehensive deployment configurations.

## 🏗️ Project Structure

```
vyva_backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .gitignore            # Git ignore rules
├── docker-compose.yml     # Local development with Docker
├── Dockerfile            # Production Docker image
├── nginx.conf            # Nginx configuration for production
├── gunicorn.conf.py      # Gunicorn configuration
├── alembic.ini           # Alembic migration configuration
├──
├── core/                 # Core application configuration
│   ├── __init__.py
│   ├── config.py         # Environment configuration
│   ├── database.py       # Database connection and session
│   ├── security.py       # JWT authentication and password hashing
│   └── logging.py        # Logging configuration
├──
├── models/               # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── user.py           # User model
│   ├── profile.py        # Profile model
│   ├── health_care.py    # Health & Care model
│   ├── social.py         # Social model
│   ├── brain_coach.py    # Brain Coach model
│   ├── medication.py     # Medication model
│   ├── fall_detection.py # Fall Detection model
│   └── emergency.py      # Emergency Contacts model
├──
├── schemas/              # Pydantic schemas for API
│   ├── __init__.py
│   ├── user.py           # User schemas
│   ├── profile.py        # Profile schemas
│   ├── health_care.py    # Health & Care schemas
│   ├── social.py         # Social schemas
│   ├── brain_coach.py    # Brain Coach schemas
│   ├── medication.py     # Medication schemas
│   ├── fall_detection.py # Fall Detection schemas
│   └── emergency.py      # Emergency Contacts schemas
├──
├── api/                  # API routes
│   ├── __init__.py
│   ├── deps.py           # Dependency injection
│   └── v1/               # API version 1
│       ├── __init__.py
│       ├── auth.py       # Authentication endpoints
│       ├── users.py      # User management
│       ├── profiles.py   # Profile management
│       ├── health_care.py # Health & Care endpoints
│       ├── social.py     # Social features
│       ├── brain_coach.py # Brain Coach features
│       ├── medications.py # Medication management
│       ├── fall_detection.py # Fall detection
│       ├── emergency.py  # Emergency contacts
│       └── tts.py        # Text-to-Speech endpoints
├──
├── services/             # Business logic layer
│   ├── __init__.py
│   ├── email_service.py  # Email service
│   ├── sms_service.py    # SMS service
│   └── tts_service.py    # ElevenLabs TTS service
├──
├── repositories/         # Database operations layer
│   ├── __init__.py
│   ├── base.py           # Base repository
│   ├── user_repository.py # User CRUD operations
│   ├── profile_repository.py # Profile CRUD operations
│   └── ...               # Other module repositories
├──
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   ├── env.py            # Alembic environment
│   └── script.py.mako    # Migration template
├──

```

## 🚀 Quick Start

### Prerequisites

- Python 3.12
- PostgreSQL 16

### Local Development Setup

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd vyva_backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   replace the database url
   ```

3. **Setup database:**
   ```bash
   alembic revision --autogenerate -m "add age column to users"
   
   # Run migrations
   alembic upgrade head
   ```

4. **Run the application:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Enum Values In PSQL:**
   ```psql
   ALTER TYPE medicationstatus ADD VALUE 'UNCONFIRMED';
   ```

```

## 🌐 Exposing for Mobile Testing

### Using ngrok

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com/download
   # Or using snap (Ubuntu)
   sudo snap install ngrok
   ```

2. **Expose your local server:**
   ```bash
   ngrok http 8000
   ```

3. **Use the provided HTTPS URL in your mobile app**

### Using Cloudflare Tunnel

1. **Install cloudflared:**
   ```bash
   # Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
   ```

2. **Create tunnel:**
   ```bash
   cloudflared tunnel create vyva-backend
   cloudflared tunnel route dns vyva-backend your-domain.com
   ```

3. **Run tunnel:**
   ```bash
   cloudflared tunnel run vyva-backend
   ```

## 🔐 Authentication

The application uses JWT authentication with refresh tokens:

- **Access Token**: 15 minutes lifetime
- **Refresh Token**: 6-12 months lifetime (for senior users)
- **Endpoints**:
  - `POST /api/v1/auth/login` - User login
  - `POST /api/v1/auth/refresh` - Refresh access token
  - `POST /api/v1/auth/logout` - User logout

### Example Authentication Flow

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Use access token for authenticated requests
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer <access_token>"
```

## 🗄️ Database

### PostgreSQL Setup

The application uses PostgreSQL with the following features:
- SQLAlchemy ORM with async support
- Alembic migrations
- Connection pooling
- Multiple environment configurations

### Running Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```


## 🔧 Configuration

### Environment Variables

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/vyva_db

# Security
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=180

# External Services
ELEVENLABS_API_KEY=your-elevenlabs-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Environment
ENV=development
DEBUG=true
LOG_LEVEL=INFO
```

## 📝 API Documentation

The API documentation is automatically generated and available at:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

---
