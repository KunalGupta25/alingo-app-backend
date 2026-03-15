# Alingo Backend

Django REST backend for the Alingo mobile app.

This service handles:

- OTP-based phone authentication
- user onboarding data
- identity verification submissions
- ride creation and matching
- ride join / approval / completion flows
- reviews and ratings
- Expo push token registration and notification delivery

Application data is stored in MongoDB. SQLite is only used for Django framework concerns.

## Stack

- Django
- Django REST Framework
- PyMongo
- django-cors-headers
- WhiteNoise
- Firebase Admin SDK

## Project Structure

```text
backend/
|-- apps/
|   |-- authentication/
|   |-- core/
|   |-- reviews/
|   |-- rides/
|   |-- users/
|   `-- verification/
|-- config/
|-- database/
|-- templates/
|-- media/
|-- manage.py
|-- requirements.txt
`-- README.md
```

## Requirements

- Python 3.11+
- MongoDB
- pip

## Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

## Environment Variables

Create `backend/.env` and configure the values needed for your environment.

Common variables:

```env
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=alingo_db

FIREBASE_CREDENTIALS_PATH=path/to/firebase_service_account_key.json
```

Optional production-style Firebase configuration:

```env
FIREBASE_CREDENTIALS_JSON={"type":"service_account", ...}
```

Optional frontend access control:

```env
CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

## Running The Server

```powershell
python manage.py runserver 0.0.0.0:8000
```

Default local URL:

- `http://localhost:8000`

## Data Storage

MongoDB collections used by the app include:

- `users`
- `rides`
- `reviews`
- `otps`
- `verifications`

The backend creates indexes for:

- unique user `uid`
- unique user `phone`
- OTP TTL expiry
- user geolocation lookup
- ride geolocation lookup
- review uniqueness per ride/reviewer/reviewee

## API Routes

### Authentication

Base path: `/auth/`

- `GET /auth/ping`
- `POST /auth/otp/send`
- `POST /auth/otp/verify`

### Verification

Base path: `/api/verification/`

- `POST /api/verification/submit`
- `GET /api/verification/status`

### Users

Base path: `/users/`

- `GET /users/me`
- `GET /users/me/rides`
- `PATCH /users/profile`
- `PATCH /users/availability`
- `PATCH /users/location`
- `POST /users/push-token`
- `GET /users/<user_id>`
- `GET /users/<user_id>/reviews`

### Rides

Base path: `/rides/`

- `POST /rides/create`
- `POST /rides/search`
- `POST /rides/request`
- `POST /rides/respond`
- `POST /rides/complete`
- `POST /rides/cancel`
- `GET /rides/my-active`
- `GET /rides/my-requests`
- `GET /rides/detail`

### Reviews

Base path: `/reviews/`

- `POST /reviews/create`

## Authentication Model

- OTP verification returns a JWT token.
- Protected endpoints expect `Authorization: Bearer <token>`.
- Many ride, user, and review routes require both authentication and `VERIFIED` status.

## Verification Workflow

1. User signs in with phone OTP.
2. User is created with `UNVERIFIED` status.
3. User submits:
   - document type
   - document image
   - face image
4. Backend stores the files and marks the user `PENDING`.
5. Admin review updates verification outcome.

## Local File Uploads

Verification images are currently stored under `backend/media/verifications/`.

If you do not want local media persistence in development, clear that folder manually.

## Development Notes

- OTPs are development-friendly and not wired to a real SMS provider.
- The backend currently includes a custom JWT middleware instead of a packaged auth solution.
- The verification panel is mounted separately from Django admin routes.

## Manual Verification Checklist

After making backend changes, manually verify the narrowest relevant flow:

- send OTP
- verify OTP
- submit verification
- check verification status
- create ride
- search rides
- request / approve / reject ride join
- complete ride
- create review
- fetch profile / ride history

## Important Security Notes

Before production use:

- replace development auth defaults
- lock down admin and verification review access
- remove any committed secrets
- set `DEBUG=False`
- configure strict `ALLOWED_HOSTS`
- configure proper CORS and HTTPS
